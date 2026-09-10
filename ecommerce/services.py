"""Regras de negócio dos pedidos da loja e integração externa."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Exists, OuterRef, Sum
from django.utils import timezone

from api_sankhya.models import Preco, Produto

from . import catalog
from .cart_session import clear_cart, get_cart
from .analise_pedido import persistir_analise_pedido
from .models import AnalisePedidoLoja, ItemAnalisePedidoLoja, ItemPedidoLoja, NotificacaoLoja, PedidoLoja, RotaDiaCliente, TopEnvioSankhya
from .sankhya_integracao import IntegracaoSankhyaError, integrar_pedido_loja_sankhya


def integrar_pedido_no_sistema_externo(
    pedido: PedidoLoja,
    top_envio: TopEnvioSankhya | None = None,
    aprovado_em: datetime | None = None,
) -> str:
    """
    Registra o pedido no Sankhya via POST /v1/vendas/pedidos.
    Retorna o código do pedido no ERP ou levanta IntegracaoSankhyaError.
    """
    top = top_envio or pedido.top_envio
    if not top:
        raise IntegracaoSankhyaError('TOP de envio não informada.')
    return integrar_pedido_loja_sankhya(
        pedido,
        top,
        aprovado_em=aprovado_em or timezone.now(),
    )


def criar_notificacao(user, titulo: str, mensagem: str, pedido: PedidoLoja | None = None):
    return NotificacaoLoja.objects.create(
        user=user,
        pedido=pedido,
        titulo=titulo[:200],
        mensagem=mensagem,
    )


def finalizar_pedido_loja(
    request,
    user,
    cliente_api,
    analise_snapshot: dict | None = None,
) -> tuple[PedidoLoja | None, str | None]:
    """
    Monta o pedido a partir da sessão do carrinho.
    Retorna (pedido, mensagem_erro).
    """
    cart = get_cart(request)
    if not cart:
        return None, 'O carrinho está vazio.'

    codigos_permitidos = catalog.codigos_grupos_permitidos_ecommerce()
    codtab = getattr(cliente_api, 'codtab', None)
    if codtab in (None, 0):
        return None, 'Cliente sem tabela de preço (CODTAB) configurada.'
    linhas_validas: list[dict] = []
    for item in cart:
        cid = item.get('codigo_produto')
        if cid is None:
            continue
        try:
            p = Produto.objects.get(codigo_produto=int(cid))
        except (ValueError, TypeError, Produto.DoesNotExist):
            return None, f'Produto {cid} não está mais disponível.'
        if not catalog.produto_permitido_na_loja(p, codigos_permitidos):
            label = (p.nome or '').strip() or str(cid)
            return None, f'O produto "{label}" não está disponível para pedido.'

        nome = (p.nome or '').strip() or f'Cód. {p.codigo_produto}'
        try:
            qty = Decimal(str(item.get('qty') or 0))
        except (InvalidOperation, ValueError, TypeError):
            qty = Decimal('0')
        if qty <= 0:
            continue
        preco = (
            Preco.objects.filter(codigo_produto=p.codigo_produto, codigo_tabela=codtab)
            .order_by('codigo_local_estoque')
            .first()
        )
        if not preco or not preco.valor or preco.valor <= 0:
            return (
                None,
                f'Produto "{nome}" sem preço válido na tabela {codtab}. Atualize os preços antes de finalizar.',
            )
        valor_unitario = preco.valor
        valor_total = (valor_unitario * qty).quantize(Decimal('0.01'))
        linhas_validas.append(
            {
                'codigo_produto': p.codigo_produto,
                'nome': nome,
                'qty': qty,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total,
            }
        )

    if not linhas_validas:
        return None, 'Nenhuma linha válida no carrinho.'

    with transaction.atomic():
        pedido = PedidoLoja.objects.create(
            user=user,
            cliente=cliente_api,
            status=PedidoLoja.Status.PENDENTE,
            codtab=codtab,
        )
        total_pedido = Decimal('0')
        for row in linhas_validas:
            ItemPedidoLoja.objects.create(
                pedido=pedido,
                codigo_produto=row['codigo_produto'],
                nome_produto=row['nome'][:300],
                quantidade=row['qty'],
                preco_unitario=row['valor_unitario'],
                valor_total=row['valor_total'],
            )
            total_pedido += row['valor_total']
        pedido.valor_total = total_pedido
        pedido.save(update_fields=['valor_total'])
        if analise_snapshot:
            persistir_analise_pedido(pedido, analise_snapshot)
        clear_cart(request)

    criar_notificacao(
        user,
        f'Pedido #{pedido.pk} registrado',
        'Seu pedido foi recebido e está pendente de análise do comercial.',
        pedido=pedido,
    )
    return pedido, None


def adicionar_produto_analise_ao_pedido(
    pedido: PedidoLoja,
    codigo_produto: int,
    qty,
) -> tuple[ItemPedidoLoja | None, str | None]:
    """Inclui um produto da análise no pedido pendente (uso do comercial)."""
    if pedido.status != PedidoLoja.Status.PENDENTE:
        return None, 'Só é possível incluir itens em pedidos pendentes.'

    try:
        qty_dec = Decimal(str(qty))
    except (InvalidOperation, ValueError, TypeError):
        return None, 'Quantidade inválida.'
    if qty_dec != qty_dec.to_integral_value() or qty_dec < 1:
        return None, 'Informe uma quantidade inteira maior ou igual a 1.'

    try:
        analise = pedido.analise
    except AnalisePedidoLoja.DoesNotExist:
        return None, 'Este pedido não possui análise registrada.'

    item_analise = analise.itens.filter(codigo_produto=codigo_produto).first()
    if not item_analise:
        return None, 'Produto não está nas sugestões deste pedido.'

    if not pedido.codtab:
        return None, 'Pedido sem tabela de preço. Não é possível incluir o item.'

    try:
        produto = Produto.objects.get(codigo_produto=codigo_produto)
    except Produto.DoesNotExist:
        return None, 'Produto não está mais disponível.'

    if not catalog.produto_permitido_na_loja(produto, catalog.codigos_grupos_permitidos_ecommerce()):
        nome = (produto.nome or '').strip() or str(codigo_produto)
        return None, f'O produto "{nome}" não está disponível para pedido.'

    nome = (produto.nome or item_analise.nome_produto or '').strip() or f'Cód. {codigo_produto}'
    preco = (
        Preco.objects.filter(codigo_produto=codigo_produto, codigo_tabela=pedido.codtab)
        .order_by('codigo_local_estoque')
        .first()
    )
    if not preco or not preco.valor or preco.valor <= 0:
        return None, f'Produto "{nome}" sem preço válido na tabela {pedido.codtab}.'

    valor_unitario = preco.valor
    with transaction.atomic():
        existente = (
            pedido.itens.select_for_update().filter(codigo_produto=codigo_produto).first()
        )
        if existente:
            existente.quantidade = existente.quantidade + qty_dec
            existente.valor_total = (existente.preco_unitario * existente.quantidade).quantize(
                Decimal('0.01')
            )
            existente.save(update_fields=['quantidade', 'valor_total'])
            item = existente
        else:
            valor_total = (valor_unitario * qty_dec).quantize(Decimal('0.01'))
            item = ItemPedidoLoja.objects.create(
                pedido=pedido,
                codigo_produto=codigo_produto,
                nome_produto=nome[:300],
                quantidade=qty_dec,
                preco_unitario=valor_unitario,
                valor_total=valor_total,
            )
        total = pedido.itens.aggregate(s=Sum('valor_total'))['s'] or Decimal('0')
        pedido.valor_total = total
        pedido.save(update_fields=['valor_total', 'atualizado_em'])
        ItemAnalisePedidoLoja.objects.filter(pk=item_analise.pk).delete()

    criar_notificacao(
        pedido.user,
        f'Pedido #{pedido.pk} atualizado',
        (
            f'O comercial incluiu {int(qty_dec)} un. de "{nome}" no pedido #{pedido.pk}.'
        ),
        pedido=pedido,
    )
    return item, None


def filtrar_pedidos_loja_notificacoes_comercial(pedidos_qs, user):
    """Restringe pedidos ao comercial: cliente na rota do dia na data do pedido, com ele como responsável da rota padrão."""
    return pedidos_qs.filter(cliente_id__isnull=False).filter(
        Exists(
            RotaDiaCliente.objects.filter(
                cliente_id=OuterRef('cliente_id'),
                rota_dia__data=OuterRef('criado_em__date'),
                rota_dia__rota_padrao__responsavel=user,
                rota_dia__rota_padrao__ativa=True,
            )
        )
    )
