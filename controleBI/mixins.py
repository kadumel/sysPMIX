from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

from .models import PerfilUsuario
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
