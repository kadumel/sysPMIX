from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from decimal import Decimal

from api_sankhya.models import Produto
from controleBI.models import PERFIS_PAINEL_BI_LOJA, UsuarioClienteSankhya

from . import catalog
from .cart_session import (
    adjust_product_quantity,
    add_product,
    cart_line_count,
    cart_total_units,
    clear_cart,
    format_qty_display,
    get_cart,
    parse_quantity,
    remove_product,
)
from .models import BannerPromocional, NotificacaoLoja, PedidoLoja
from .services import finalizar_pedido_loja


def _safe_ecommerce_next(url, default='/ecommerce/'):
    if url and isinstance(url, str) and url.startswith('/') and not url.startswith('//'):
        if url.startswith('/ecommerce'):
            return url
    return default


def _cart_add_wants_json(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or (
        'application/json' in (request.headers.get('Accept') or '')
    )


def index(request):
    by_id, by_pai, raizes = catalog.grupos_ativos_map(apenas_visiveis_loja=True)
    codigos_grupo_loja = catalog.codigos_grupos_permitidos_ecommerce()
    codtab_cliente = catalog.get_cliente_codtab(request)
    codigos_grupo_com_produtos = catalog.codigos_grupo_com_produtos_precificados(
        codtab_cliente, codigos_grupo_loja
    )
    arvore_grupos = catalog.filtrar_arvore_grupos_com_produtos_precificados(
        catalog.arvore_grupos_nested(raizes, by_pai),
        codigos_grupo_com_produtos,
        by_pai,
    )
    grupos_flat = catalog.grupos_flat_com_produtos_precificados(
        raizes, by_pai, codigos_grupo_com_produtos
    )
    grupo_id = catalog.parse_grupo_get(request.GET.get('grupo'))
    grupo_atual = by_id.get(grupo_id) if grupo_id is not None else None
    if grupo_atual and not catalog.grupo_tem_produtos_precificados(
        grupo_atual.codigo_grupo_produto, codigos_grupo_com_produtos, by_pai
    ):
        grupo_atual = None
    termo_busca = catalog.normalizar_busca(request.GET.get('q'))

    qs = catalog.produtos_queryset(
        grupo_id if grupo_atual else None,
        by_id,
        by_pai,
        codigos_grupo_loja,
        codtab_cliente,
    )
    qs = catalog.aplicar_busca_produtos(qs, termo_busca)
    qs = catalog.prefetch_imagens_produto_loja(qs)
    paginator = Paginator(qs, catalog.PAGE_SIZE)
    page = paginator.get_page(request.GET.get('page'))
    precos_por_produto = catalog.map_precos_por_codtab(
        [p.codigo_produto for p in page.object_list], codtab_cliente
    )
    for produto in page.object_list:
        produto.preco_ecommerce = precos_por_produto.get(produto.codigo_produto)

    ancestrais = catalog.ancestrais(grupo_atual, by_id) if grupo_atual else []

    context = {
        'banners': BannerPromocional.objects.filter(ativo=True).order_by('ordem', '-criado_em'),
        'arvore_grupos': arvore_grupos,
        'grupos_flat': [{'grupo': g, 'depth': d} for g, d in grupos_flat],
        'grupo_atual': grupo_atual,
        'grupo_ancestrais': ancestrais,
        'produtos': page,
        'paginator': paginator,
        'codtab_cliente': codtab_cliente,
    }
    return render(request, 'ecommerce/index.html', context)


def partial_destaque(request):
    """Mais produtos (mesmo filtro de grupo e busca), próxima página após a primeira."""
    by_id, by_pai, _raizes = catalog.grupos_ativos_map(apenas_visiveis_loja=True)
    codigos_grupo_loja = catalog.codigos_grupos_permitidos_ecommerce()
    codtab_cliente = catalog.get_cliente_codtab(request)
    grupo_id = catalog.parse_grupo_get(request.GET.get('grupo'))
    termo_busca = catalog.normalizar_busca(request.GET.get('q'))
    qs = catalog.produtos_queryset(
        grupo_id, by_id, by_pai, codigos_grupo_loja, codtab_cliente
    )
    qs = catalog.aplicar_busca_produtos(qs, termo_busca)
    qs = catalog.prefetch_imagens_produto_loja(qs)
    start = catalog.PAGE_SIZE
    limit = catalog.PAGE_SIZE + 1
    chunk = list(qs[start : start + limit])
    has_more = len(chunk) > catalog.PAGE_SIZE
    chunk = chunk[: catalog.PAGE_SIZE]
    precos_por_produto = catalog.map_precos_por_codtab(
        [p.codigo_produto for p in chunk], codtab_cliente
    )
    for produto in chunk:
        produto.preco_ecommerce = precos_por_produto.get(produto.codigo_produto)
    return render(
        request,
        'ecommerce/partials/destaque.html',
        {
            'produtos': chunk,
            'has_more': has_more,
        },
    )


def cart_view(request):
    raw = get_cart(request)
    codigos = [int(i['codigo_produto']) for i in raw if i.get('codigo_produto') is not None]
    produtos = {p.codigo_produto: p for p in catalog.prefetch_imagens_produto_loja(Produto.objects.filter(codigo_produto__in=codigos))} if codigos else {}
    codtab_cliente = catalog.get_cliente_codtab(request)
    precos_por_produto = catalog.map_precos_por_codtab(codigos, codtab_cliente)
    linhas = []
    total_geral = Decimal('0')
    for item in raw:
        cid = item.get('codigo_produto')
        if cid is None:
            continue
        cid = int(cid)
        p = produtos.get(cid)
        q = float(item.get('qty') or 0)
        qty_decimal = Decimal(str(q))
        preco_unitario = precos_por_produto.get(cid)
        subtotal = None
        if preco_unitario is not None:
            subtotal = preco_unitario * qty_decimal
            total_geral += subtotal
        linhas.append(
            {
                'codigo_produto': cid,
                'nome': (p.nome if p else None) or item.get('nome') or f'Produto {cid}',
                'qty': q,
                'qty_label': format_qty_display(q),
                'preco_unitario': preco_unitario,
                'subtotal': subtotal,
            }
        )
    return render(
        request,
        'ecommerce/cart.html',
        {'linhas': linhas, 'total_geral': total_geral, 'codtab_cliente': codtab_cliente},
    )


@require_POST
def add_to_cart(request):
    wants_json = _cart_add_wants_json(request)
    codigo = request.POST.get('codigo_produto')
    next_url = _safe_ecommerce_next(request.POST.get('next'))

    def json_err(msg, status=400):
        return JsonResponse({'ok': False, 'error': msg}, status=status)

    if not codigo:
        if wants_json:
            return json_err('Produto inválido.')
        messages.warning(request, 'Produto inválido.')
        return redirect(next_url)

    try:
        produto = Produto.objects.get(codigo_produto=int(codigo), ativo=True)
    except (ValueError, TypeError, Produto.DoesNotExist):
        if wants_json:
            return json_err('Produto não encontrado ou indisponível.', status=404)
        messages.error(request, 'Produto não encontrado.')
        return redirect(next_url)

    if not catalog.produto_permitido_na_loja(produto):
        if wants_json:
            return json_err('Este produto não está disponível na loja.', status=403)
        messages.warning(request, 'Este produto não está disponível na loja.')
        return redirect(next_url)

    codtab_cliente = catalog.get_cliente_codtab(request)
    if not catalog.produto_tem_preco_na_tabela(produto.codigo_produto, codtab_cliente):
        if wants_json:
            return json_err('Este produto não possui preço na sua tabela.', status=403)
        messages.warning(request, 'Este produto não possui preço na sua tabela.')
        return redirect(next_url)

    nome = (produto.nome or '').strip() or f'Cód. {produto.codigo_produto}'
    raw_qty = request.POST.get('qty', '1')
    qty = parse_quantity(raw_qty)
    if qty is None:
        err = 'Quantidade inválida. Use um número maior que zero (ex.: 1,5 ou 0,25 para kg).'
        if wants_json:
            return json_err(err)
        messages.warning(request, err)
        return redirect(next_url)

    add_product(request, produto.codigo_produto, nome, qty=qty)
    qty_txt = format_qty_display(qty)

    if wants_json:
        return JsonResponse(
            {
                'ok': True,
                'lines': cart_line_count(request),
                'units': cart_total_units(request),
                'message': f'“{nome}” — {qty_txt} adicionado ao carrinho.',
            }
        )

    messages.success(request, f'“{nome}” — {qty_txt} adicionado ao carrinho.')
    return redirect(next_url)


@require_POST
def remove_from_cart(request):
    codigo = request.POST.get('codigo_produto')
    next_url = _safe_ecommerce_next(request.POST.get('next'), default='/ecommerce/carrinho/')
    if codigo:
        remove_product(request, int(codigo))
        messages.info(request, 'Item removido do carrinho.')
    return redirect(next_url)


@require_POST
def clear_cart_view(request):
    clear_cart(request)
    messages.info(request, 'Carrinho esvaziado.')
    return redirect('/ecommerce/carrinho/')


@require_POST
def adjust_cart_quantity(request):
    codigo = request.POST.get('codigo_produto')
    acao = (request.POST.get('acao') or '').strip().lower()
    next_url = _safe_ecommerce_next(request.POST.get('next'), default='/ecommerce/carrinho/')
    if not codigo or acao not in {'inc', 'dec'}:
        messages.warning(request, 'Ajuste de quantidade inválido.')
        return redirect(next_url)
    try:
        codigo_int = int(codigo)
    except (TypeError, ValueError):
        messages.warning(request, 'Produto inválido para ajuste.')
        return redirect(next_url)

    delta = 1 if acao == 'inc' else -1
    ok = adjust_product_quantity(request, codigo_int, delta=delta)
    if not ok and acao == 'dec':
        messages.info(request, 'Item removido do carrinho.')
    return redirect(next_url)


def _safe_ecommerce_redirect_path(url: str | None, default: str = '/ecommerce/notificacoes/') -> str:
    if url and isinstance(url, str) and url.startswith('/') and not url.startswith('//'):
        if url.startswith('/ecommerce'):
            return url
    return default


@login_required
def pedidos_list(request):
    perfil = getattr(getattr(request.user, 'perfil_usuario', None), 'perfil', None)
    cliente_ctx = catalog.get_cliente_context(request)
    pedidos = PedidoLoja.objects.select_related('cliente').prefetch_related('itens')
    if perfil in PERFIS_PAINEL_BI_LOJA:
        if cliente_ctx:
            pedidos = pedidos.filter(cliente=cliente_ctx)
        else:
            pedidos = PedidoLoja.objects.none()
    else:
        pedidos = pedidos.filter(user=request.user)
    return render(request, 'ecommerce/pedidos_list.html', {'pedidos': pedidos})


@login_required
def pedido_detail(request, pk: int):
    pedido = get_object_or_404(
        PedidoLoja.objects.select_related('cliente').prefetch_related('itens'),
        pk=pk,
        user=request.user,
    )
    itens = []
    for it in pedido.itens.all():
        itens.append(
            {
                'codigo_produto': it.codigo_produto,
                'nome': it.nome_produto,
                'qty_label': format_qty_display(it.quantidade),
                'preco_unitario': it.preco_unitario,
                'subtotal': it.valor_total,
            }
        )
    return render(
        request,
        'ecommerce/pedido_detail.html',
        {'pedido': pedido, 'itens': itens},
    )


@login_required
@require_POST
def pedido_reenviar_carrinho(request, pk: int):
    pedido = get_object_or_404(
        PedidoLoja.objects.prefetch_related('itens'),
        pk=pk,
        user=request.user,
    )
    if pedido.status != PedidoLoja.Status.REJEITADO:
        messages.warning(
            request,
            'Somente pedidos rejeitados podem ser enviados novamente ao carrinho.',
        )
        return redirect('ecommerce_pedido_detail', pk=pedido.pk)

    clear_cart(request)
    itens = list(pedido.itens.all())
    if not itens:
        messages.warning(request, 'Este pedido não possui itens para reenviar.')
        return redirect('ecommerce_pedido_detail', pk=pedido.pk)

    for item in itens:
        add_product(
            request,
            codigo_produto=item.codigo_produto,
            nome=item.nome_produto,
            qty=float(item.quantidade),
        )
    messages.success(
        request,
        'Itens do pedido rejeitado enviados ao carrinho. Ajuste conforme a mensagem do comercial e finalize novamente.',
    )
    return redirect('ecommerce_cart')


@login_required
def notificacoes_list(request):
    notificacoes = NotificacaoLoja.objects.filter(user=request.user).select_related(
        'pedido'
    )
    return render(
        request,
        'ecommerce/notificacoes_list.html',
        {'notificacoes': notificacoes},
    )


@login_required
@require_POST
def notificacao_marcar_lida(request, pk: int):
    n = get_object_or_404(NotificacaoLoja, pk=pk, user=request.user)
    n.lida = True
    n.save(update_fields=['lida'])
    return redirect(_safe_ecommerce_redirect_path(request.POST.get('next')))


@login_required
@require_POST
def notificacoes_marcar_todas_lidas(request):
    NotificacaoLoja.objects.filter(user=request.user, lida=False).update(lida=True)
    return redirect('ecommerce_notificacoes')


@login_required
@require_POST
def checkout_finalizar(request):
    cliente_ctx = catalog.get_cliente_context(request)
    if not cliente_ctx:
        v = (
            UsuarioClienteSankhya.objects.select_related('cliente')
            .filter(user=request.user)
            .first()
        )
        cliente_ctx = v.cliente if v and v.cliente else None
    if not cliente_ctx:
        messages.error(
            request,
            'É necessário ter um cliente Sankhya vinculado ao seu usuário para finalizar o pedido.',
        )
        return redirect('ecommerce_cart')
    pedido, err = finalizar_pedido_loja(request, request.user, cliente_ctx)
    if err:
        messages.error(request, err)
        return redirect('ecommerce_cart')
    messages.success(
        request,
        f'Pedido #{pedido.pk} enviado com sucesso. Aguarde a análise do comercial.',
    )
    return redirect('ecommerce_pedido_detail', pk=pedido.pk)
