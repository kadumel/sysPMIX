from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from api_sankhya.models import Produto
from controleBI.models import UsuarioClienteSankhya

from . import catalog
from .cart_session import (
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
    grupo_id = catalog.parse_grupo_get(request.GET.get('grupo'))
    grupo_atual = by_id.get(grupo_id) if grupo_id is not None else None
    termo_busca = catalog.normalizar_busca(request.GET.get('q'))

    qs = catalog.produtos_queryset(grupo_id, by_id, by_pai, codigos_grupo_loja)
    qs = catalog.aplicar_busca_produtos(qs, termo_busca)
    qs = catalog.prefetch_imagens_produto_loja(qs)
    paginator = Paginator(qs, catalog.PAGE_SIZE)
    page = paginator.get_page(request.GET.get('page'))

    ancestrais = catalog.ancestrais(grupo_atual, by_id) if grupo_atual else []

    context = {
        'banners': BannerPromocional.objects.filter(ativo=True).order_by('ordem', '-criado_em'),
        'arvore_grupos': catalog.arvore_grupos_nested(raizes, by_pai),
        'grupos_flat': [
            {'grupo': g, 'depth': d} for g, d in catalog.grupos_flat_indent(raizes, by_pai)
        ],
        'grupo_atual': grupo_atual,
        'grupo_ancestrais': ancestrais,
        'produtos': page,
        'paginator': paginator,
    }
    return render(request, 'ecommerce/index.html', context)


def partial_destaque(request):
    """Mais produtos (mesmo filtro de grupo e busca), próxima página após a primeira."""
    by_id, by_pai, _raizes = catalog.grupos_ativos_map(apenas_visiveis_loja=True)
    codigos_grupo_loja = catalog.codigos_grupos_permitidos_ecommerce()
    grupo_id = catalog.parse_grupo_get(request.GET.get('grupo'))
    termo_busca = catalog.normalizar_busca(request.GET.get('q'))
    qs = catalog.produtos_queryset(grupo_id, by_id, by_pai, codigos_grupo_loja)
    qs = catalog.aplicar_busca_produtos(qs, termo_busca)
    qs = catalog.prefetch_imagens_produto_loja(qs)
    start = catalog.PAGE_SIZE
    limit = catalog.PAGE_SIZE + 1
    chunk = list(qs[start : start + limit])
    has_more = len(chunk) > catalog.PAGE_SIZE
    chunk = chunk[: catalog.PAGE_SIZE]
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
    linhas = []
    for item in raw:
        cid = item.get('codigo_produto')
        if cid is None:
            continue
        cid = int(cid)
        p = produtos.get(cid)
        q = float(item.get('qty') or 0)
        linhas.append(
            {
                'codigo_produto': cid,
                'nome': (p.nome if p else None) or item.get('nome') or f'Produto {cid}',
                'qty': q,
                'qty_label': format_qty_display(q),
            }
        )
    return render(
        request,
        'ecommerce/cart.html',
        {'linhas': linhas},
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


def _safe_ecommerce_redirect_path(url: str | None, default: str = '/ecommerce/notificacoes/') -> str:
    if url and isinstance(url, str) and url.startswith('/') and not url.startswith('//'):
        if url.startswith('/ecommerce'):
            return url
    return default


@login_required
def pedidos_list(request):
    pedidos = (
        PedidoLoja.objects.filter(user=request.user)
        .select_related('cliente')
        .prefetch_related('itens')
    )
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
            }
        )
    return render(
        request,
        'ecommerce/pedido_detail.html',
        {'pedido': pedido, 'itens': itens},
    )


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
    v = (
        UsuarioClienteSankhya.objects.select_related('cliente')
        .filter(user=request.user)
        .first()
    )
    if not v or not v.cliente:
        messages.error(
            request,
            'É necessário ter um cliente Sankhya vinculado ao seu usuário para finalizar o pedido.',
        )
        return redirect('ecommerce_cart')
    pedido, err = finalizar_pedido_loja(request, request.user, v.cliente)
    if err:
        messages.error(request, err)
        return redirect('ecommerce_cart')
    messages.success(
        request,
        f'Pedido #{pedido.pk} enviado com sucesso. Aguarde a análise do comercial.',
    )
    return redirect('ecommerce_pedido_detail', pk=pedido.pk)
