from datetime import date
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
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
from .analise_pedido import (
    SESSION_ANALISE_KEY,
    ResultadoAnalise,
    calcular_analise_pedido,
    diagnosticar_novidades_campanha,
    remover_sugestao_do_snapshot,
)
from .models import BannerPromocional, NotificacaoLoja, PedidoLoja
from .services import finalizar_pedido_loja


_CARRINHO_ACOES_NEXT = frozenset(
    {
        '/ecommerce/carrinho/adicionar/',
        '/ecommerce/carrinho/remover/',
        '/ecommerce/carrinho/ajustar-quantidade/',
        '/ecommerce/carrinho/limpar/',
        '/ecommerce/carrinho/finalizar/',
        '/ecommerce/carrinho/analise/',
        '/ecommerce/carrinho/analise/adicionar/',
    }
)


def _safe_ecommerce_next(url, default='/ecommerce/'):
    if url and isinstance(url, str) and url.startswith('/') and not url.startswith('//'):
        if url.startswith('/ecommerce'):
            normalizado = url if url.endswith('/') else f'{url}/'
            if normalizado not in _CARRINHO_ACOES_NEXT:
                return url
    return default


def _cart_add_wants_json(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or (
        'application/json' in (request.headers.get('Accept') or '')
    )


def _cliente_para_checkout(request):
    cliente = catalog.get_cliente_context(request)
    if not cliente:
        v = (
            UsuarioClienteSankhya.objects.select_related('cliente')
            .filter(user=request.user)
            .first()
        )
        cliente = v.cliente if v and v.cliente else None
    return cliente


def _cart_snapshot_context(request) -> dict:
    raw = get_cart(request)
    codigos = [int(i['codigo_produto']) for i in raw if i.get('codigo_produto') is not None]
    produtos = (
        {p.codigo_produto: p for p in catalog.prefetch_imagens_produto_loja(Produto.objects.filter(codigo_produto__in=codigos))}
        if codigos
        else {}
    )
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
    return {
        'linhas': linhas,
        'total_geral': total_geral,
        'codtab_cliente': codtab_cliente,
        'cart_count': cart_line_count(request),
        'cart_units_label': format_qty_display(cart_total_units(request)),
    }


def _render_cart_snapshots_html(request) -> dict[str, str]:
    ctx = _cart_snapshot_context(request)
    return {
        'cart_page_list_html': render(
            request, 'ecommerce/partials/cart_page_list.html', ctx
        ).content.decode('utf-8'),
        'cart_page_footer_html': render(
            request, 'ecommerce/partials/cart_page_footer.html', ctx
        ).content.decode('utf-8'),
    }


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
    ctx = _cart_snapshot_context(request)
    return render(request, 'ecommerce/cart.html', ctx)


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


def _pedidos_list_query(request, *, ordem=None, dir_param=None, data_ini=None, data_fim=None, status=None):
    params = {}
    for key, value in (
        ('data_ini', data_ini if data_ini is not None else request.GET.get('data_ini', '')),
        ('data_fim', data_fim if data_fim is not None else request.GET.get('data_fim', '')),
        ('status', status if status is not None else request.GET.get('status', '')),
        ('ordem', ordem if ordem is not None else request.GET.get('ordem', '')),
        ('dir', dir_param if dir_param is not None else request.GET.get('dir', '')),
    ):
        value = (value or '').strip()
        if value:
            params[key] = value
    return '?' + urlencode(params) if params else '?'


def _pedidos_list_sort_link(request, column, ordem_atual, dir_atual):
    if ordem_atual == column:
        next_dir = 'desc' if dir_atual == 'asc' else 'asc'
    else:
        next_dir = 'asc'
    return _pedidos_list_query(request, ordem=column, dir_param=next_dir)


@login_required
def pedidos_list(request):
    perfil = getattr(getattr(request.user, 'perfil_usuario', None), 'perfil', None)
    cliente_ctx = catalog.get_cliente_context(request)
    pedidos = PedidoLoja.objects.select_related('cliente')
    if perfil in PERFIS_PAINEL_BI_LOJA:
        if cliente_ctx:
            pedidos = pedidos.filter(cliente=cliente_ctx)
        else:
            pedidos = PedidoLoja.objects.none()
    else:
        pedidos = pedidos.filter(user=request.user)

    data_ini = (request.GET.get('data_ini') or '').strip()
    data_fim = (request.GET.get('data_fim') or '').strip()
    status = (request.GET.get('status') or '').strip()
    ordem = (request.GET.get('ordem') or '').strip()
    dir_atual = (request.GET.get('dir') or '').strip().lower()

    if status in {
        PedidoLoja.Status.PENDENTE,
        PedidoLoja.Status.AUTORIZADO,
        PedidoLoja.Status.REJEITADO,
    }:
        pedidos = pedidos.filter(status=status)
    else:
        status = ''

    if data_ini:
        try:
            pedidos = pedidos.filter(criado_em__date__gte=date.fromisoformat(data_ini))
        except ValueError:
            data_ini = ''
    if data_fim:
        try:
            pedidos = pedidos.filter(criado_em__date__lte=date.fromisoformat(data_fim))
        except ValueError:
            data_fim = ''

    sort_fields = {
        'pedido': 'id',
        'data': 'criado_em',
        'valor_total': 'valor_total',
    }
    if ordem in sort_fields:
        if dir_atual not in {'asc', 'desc'}:
            dir_atual = 'asc'
        order_field = sort_fields[ordem]
        if dir_atual == 'desc':
            order_field = f'-{order_field}'
        pedidos = pedidos.order_by(order_field, '-id')
    else:
        ordem = ''
        dir_atual = ''
        pedidos = pedidos.order_by('-criado_em', '-id')

    tem_filtros = bool(data_ini or data_fim or status)
    return render(
        request,
        'ecommerce/pedidos_list.html',
        {
            'pedidos': pedidos,
            'filtro_data_ini': data_ini,
            'filtro_data_fim': data_fim,
            'filtro_status': status,
            'ordem_atual': ordem,
            'dir_atual': dir_atual,
            'tem_filtros': tem_filtros,
            'sort_link_pedido': _pedidos_list_sort_link(request, 'pedido', ordem, dir_atual),
            'sort_link_data': _pedidos_list_sort_link(request, 'data', ordem, dir_atual),
            'sort_link_valor_total': _pedidos_list_sort_link(request, 'valor_total', ordem, dir_atual),
            'limpar_filtros_url': _pedidos_list_query(
                request,
                data_ini='',
                data_fim='',
                status='',
                ordem='',
                dir_param='',
            ),
        },
    )


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
@require_GET
def checkout_analise_preview(request):
    cliente_ctx = _cliente_para_checkout(request)
    if not cliente_ctx:
        return JsonResponse(
            {'ok': False, 'erro': 'Cliente não vinculado ao usuário.'},
            status=400,
        )
    if not get_cart(request):
        return JsonResponse({'ok': False, 'erro': 'O carrinho está vazio.'}, status=400)

    resultado = calcular_analise_pedido(cliente_ctx, get_cart(request))
    snapshot = resultado.to_session_dict()
    request.session[SESSION_ANALISE_KEY] = snapshot
    request.session.modified = True

    html = render(
        request,
        'ecommerce/partials/checkout_analise_modal_body.html',
        {'analise': resultado},
    ).content.decode('utf-8')

    ctx_carrinho = _cart_snapshot_context(request)
    snapshots = _render_cart_snapshots_html(request)
    payload = {
        'ok': True,
        'tem_sugestoes': resultado.tem_sugestoes,
        'html': html,
        'total_sugestoes': len(resultado.todas_sugestoes()),
        'total_novidades': len(resultado.novidades),
        **snapshots,
        'cart_count': ctx_carrinho['cart_count'],
        'cart_units_label': ctx_carrinho['cart_units_label'],
    }
    if settings.DEBUG:
        payload['debug_novidades'] = diagnosticar_novidades_campanha(
            cliente_ctx,
            get_cart(request),
        )
    return JsonResponse(payload)


@login_required
@require_POST
def checkout_analise_adicionar(request):
    cliente_ctx = _cliente_para_checkout(request)
    if not cliente_ctx:
        return JsonResponse({'ok': False, 'erro': 'Cliente não vinculado.'}, status=400)

    snapshot = request.session.get(SESSION_ANALISE_KEY)
    if not isinstance(snapshot, dict):
        return JsonResponse({'ok': False, 'erro': 'Análise expirada. Abra a finalização novamente.'}, status=400)

    try:
        codigo = int(request.POST.get('codigo_produto'))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'Produto inválido.'}, status=400)

    permitidos = {
        int(row['codigo_produto'])
        for sec in ('esquecidos', 'novidades', 'curva_a')
        for row in snapshot.get(sec, [])
    }
    if codigo not in permitidos:
        return JsonResponse({'ok': False, 'erro': 'Produto não está nas sugestões atuais.'}, status=400)

    produto = Produto.objects.filter(codigo_produto=codigo, ativo=True).first()
    if not produto:
        return JsonResponse({'ok': False, 'erro': 'Produto indisponível.'}, status=400)

    qty = parse_quantity(request.POST.get('qty'))
    if qty is None:
        return JsonResponse({'ok': False, 'erro': 'Quantidade inválida.'}, status=400)
    add_product(request, codigo, (produto.nome or '').strip(), qty)
    remover_sugestao_do_snapshot(snapshot, codigo)
    request.session[SESSION_ANALISE_KEY] = snapshot
    request.session.modified = True

    resultado = ResultadoAnalise.from_session_dict(snapshot)
    analise_html = render(
        request,
        'ecommerce/partials/checkout_analise_modal_body.html',
        {'analise': resultado},
    ).content.decode('utf-8')

    ctx = _cart_snapshot_context(request)
    snapshots = _render_cart_snapshots_html(request)
    return JsonResponse(
        {
            'ok': True,
            'html': analise_html,
            'tem_sugestoes': resultado.tem_sugestoes,
            'total_sugestoes': len(resultado.todas_sugestoes()),
            'cart_count': ctx['cart_count'],
            'cart_units_label': ctx['cart_units_label'],
            'total_geral': f'{ctx["total_geral"]:.2f}',
            **snapshots,
        }
    )


@login_required
@require_POST
def checkout_finalizar(request):
    cliente_ctx = _cliente_para_checkout(request)
    if not cliente_ctx:
        messages.error(
            request,
            'É necessário ter um cliente Sankhya vinculado ao seu usuário para finalizar o pedido.',
        )
        return redirect('ecommerce_cart')

    snapshot = request.session.pop(SESSION_ANALISE_KEY, None)
    if snapshot is None:
        resultado = calcular_analise_pedido(cliente_ctx, get_cart(request))
        snapshot = resultado.to_session_dict()

    pedido, err = finalizar_pedido_loja(
        request,
        request.user,
        cliente_ctx,
        analise_snapshot=snapshot,
    )
    if err:
        request.session[SESSION_ANALISE_KEY] = snapshot
        request.session.modified = True
        messages.error(request, err)
        return redirect('ecommerce_cart')
    messages.success(
        request,
        f'Pedido #{pedido.pk} enviado com sucesso. Aguarde a análise do comercial.',
    )
    return redirect('ecommerce_pedido_detail', pk=pedido.pk)
