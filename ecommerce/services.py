"""Regras de negócio dos pedidos da loja e integração externa (stub)."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Exists, OuterRef

from api_sankhya.models import Preco, Produto

from . import catalog
from .cart_session import clear_cart, get_cart
from .models import ItemPedidoLoja, NotificacaoLoja, PedidoLoja, RotaDiaCliente


def integrar_pedido_no_sistema_externo(pedido: PedidoLoja) -> str | None:
    """
    Registra o pedido no sistema terceiro (ERP, Sankhya, etc.).
    Retorna código/referência ou None em falha.
    Substituir por chamada real quando a API estiver disponível.
    """
    return f'EXT-{pedido.pk}'


def criar_notificacao(user, titulo: str, mensagem: str, pedido: PedidoLoja | None = None):
    return NotificacaoLoja.objects.create(
        user=user,
        pedido=pedido,
        titulo=titulo[:200],
        mensagem=mensagem,
    )


def finalizar_pedido_loja(request, user, cliente_api) -> tuple[PedidoLoja | None, str | None]:
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
        if not preco:
            return (
                None,
                f'Produto "{nome}" sem preço na tabela {codtab}. Atualize os preços antes de finalizar.',
            )
        valor_unitario = preco.valor or Decimal('0')
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
        clear_cart(request)

    criar_notificacao(
        user,
        f'Pedido #{pedido.pk} registrado',
        'Seu pedido foi recebido e está pendente de análise do comercial.',
        pedido=pedido,
    )
    return pedido, None


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
