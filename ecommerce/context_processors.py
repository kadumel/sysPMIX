from controleBI.models import PERFIS_PAINEL_BI_LOJA, UsuarioClienteSankhya
from django.urls import reverse

from . import catalog
from .cart_session import cart_line_count, cart_total_units, format_qty_display
from .models import NotificacaoLoja


def ecommerce_nav(request):
    units = cart_total_units(request)
    ctx = {
        'ecommerce_cart_count': cart_line_count(request),
        'ecommerce_cart_units': units,
        'ecommerce_cart_units_label': format_qty_display(units),
        'ecommerce_busca': catalog.normalizar_busca(request.GET.get('q')),
        'ecommerce_cliente_nome': None,
        'ecommerce_usuario_exibicao': None,
        'ecommerce_notificacoes_nao_lidas': 0,
        'ecommerce_selector_habilitado': False,
        'ecommerce_cliente_context_id': None,
        'ecommerce_clientes_selector_url': reverse('gestao_ecommerce_clientes_selector'),
        'ecommerce_cliente_selecionar_url': reverse('gestao_ecommerce_cliente_selecionar'),
    }
    user = request.user
    if user.is_authenticated:
        name = (user.get_full_name() or '').strip()
        ctx['ecommerce_usuario_exibicao'] = name or user.username
        c = catalog.get_cliente_context(request)
        if c:
            ctx['ecommerce_cliente_nome'] = (c.razao or c.nome or f'Cliente {c.codigo_cliente}').strip()
            ctx['ecommerce_cliente_context_id'] = c.id
        else:
            v = (
                UsuarioClienteSankhya.objects.select_related('cliente')
                .filter(user=user)
                .first()
            )
            if v and v.cliente:
                c = v.cliente
                ctx['ecommerce_cliente_nome'] = (c.razao or c.nome or f'Cliente {c.codigo_cliente}').strip()
        ctx['ecommerce_notificacoes_nao_lidas'] = NotificacaoLoja.objects.filter(
            user=user, lida=False
        ).count()
        perfil = getattr(getattr(user, 'perfil_usuario', None), 'perfil', None)
        ctx['ecommerce_selector_habilitado'] = perfil in PERFIS_PAINEL_BI_LOJA
    return ctx
