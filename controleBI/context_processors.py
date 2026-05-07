from ecommerce.models import PedidoLoja
from ecommerce.services import filtrar_pedidos_loja_notificacoes_comercial

from .models import PERFIS_GESTAO_ROTAS, PERFIS_PAINEL_BI_LOJA, PerfilUsuario


def bi_nav_context(request):
    ctx = {
        'bi_notificacoes_pendentes': 0,
        'bi_mostrar_menu_rotas': False,
        'bi_mostrar_mapa_rotas': False,
    }
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return ctx
    perfil = getattr(getattr(user, 'perfil_usuario', None), 'perfil', None)
    if perfil not in PERFIS_PAINEL_BI_LOJA:
        return ctx
    ctx['bi_mostrar_menu_rotas'] = perfil in PERFIS_GESTAO_ROTAS
    ctx['bi_mostrar_mapa_rotas'] = perfil in PERFIS_PAINEL_BI_LOJA
    pedidos = PedidoLoja.objects.all()
    if perfil == PerfilUsuario.Perfil.COMERCIAL:
        pedidos = filtrar_pedidos_loja_notificacoes_comercial(pedidos, user)
    ctx['bi_notificacoes_pendentes'] = pedidos.filter(status=PedidoLoja.Status.PENDENTE).count()
    return ctx
