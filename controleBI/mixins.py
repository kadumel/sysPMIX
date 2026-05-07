from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

from .models import PERFIS_GESTAO_ROTAS, PERFIS_PAINEL_BI_LOJA, PerfilUsuario
from .perfil_utils import ensure_perfil


class AuthRequiredMixin(LoginRequiredMixin):
    """Mixin para requerer autenticação em views"""
    login_url = 'login'
    
    def handle_no_permission(self):
        return redirect(self.login_url)


class PerfilBIAccessMixin(LoginRequiredMixin):
    """Autenticação + bloqueia perfil Cliente no painel BI (redireciona à loja)."""
    login_url = 'login'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        perfil = ensure_perfil(request.user)
        if perfil is not None and perfil.perfil == PerfilUsuario.Perfil.CLIENTE:
            return redirect('ecommerce_home')
        return super().dispatch(request, *args, **kwargs)


class PerfilGestaoRotasMixin(PerfilBIAccessMixin):
    """Somente gerente comercial ou administrador (comercial não acessa rotas)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        perfil = ensure_perfil(request.user)
        if perfil is not None and perfil.perfil == PerfilUsuario.Perfil.CLIENTE:
            return redirect('ecommerce_home')
        if perfil is None or perfil.perfil not in PERFIS_GESTAO_ROTAS:
            messages.error(request, 'Sem permissão para acessar a gestão de rotas.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class PerfilMapaRotasEcommerceMixin(PerfilBIAccessMixin):
    """Comercial, gerente comercial e administrador (visualização do mapa semanal)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        perfil = ensure_perfil(request.user)
        if perfil is not None and perfil.perfil == PerfilUsuario.Perfil.CLIENTE:
            return redirect('ecommerce_home')
        if perfil is None or perfil.perfil not in PERFIS_PAINEL_BI_LOJA:
            messages.error(request, 'Sem permissão para acessar o mapa de rotas.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
