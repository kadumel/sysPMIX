from functools import wraps

from django.shortcuts import redirect

from .models import PerfilUsuario
from .perfil_utils import ensure_perfil


def requer_acesso_bi(view_func):
    """Usar após @login_required: clientes vão para o e-commerce."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            perfil = ensure_perfil(request.user)
            if perfil is not None and perfil.perfil == PerfilUsuario.Perfil.CLIENTE:
                return redirect('ecommerce_home')
        return view_func(request, *args, **kwargs)

    return _wrapped
