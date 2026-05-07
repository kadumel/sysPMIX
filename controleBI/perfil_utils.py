from django.contrib.auth.models import User
from django.db.utils import DatabaseError
from django.urls import reverse

from .models import PerfilUsuario


def ensure_perfil(user: User) -> PerfilUsuario | None:
    """Garante registro de perfil. Retorna None se o banco falhar (ex.: migração não aplicada)."""
    try:
        perfil, _ = PerfilUsuario.objects.get_or_create(
            user=user,
            defaults={'perfil': PerfilUsuario.Perfil.COMERCIAL},
        )
        return perfil
    except DatabaseError:
        return None


def url_pos_login(user: User) -> str:
    """URL padrão após login (respeitando ?next= é responsabilidade da LoginView)."""
    perfil = ensure_perfil(user)
    if perfil is None:
        return reverse('dashboard')
    if perfil.perfil == PerfilUsuario.Perfil.CLIENTE:
        return reverse('ecommerce_home')
    # Comercial e administrador (do sistema): painel BI. O Django Admin é só para is_superuser.
    return reverse('dashboard')
