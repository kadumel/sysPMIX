"""Caminhos de mídia (imagens de produto) a partir de settings."""
import os

from django.conf import settings


def diretorio_imagens_produto_absoluto() -> str:
    """Pasta absoluta onde gravar imagens baixadas (MEDIA_ROOT + MEDIA_PRODUCT_IMAGES_UPLOAD_TO)."""
    sub = getattr(settings, 'MEDIA_PRODUCT_IMAGES_UPLOAD_TO', 'ecommerce/produtos/')
    sub = sub.strip().strip('/')
    if not sub:
        sub = 'ecommerce/produtos'
    return os.path.join(settings.MEDIA_ROOT, sub)


def url_publica_imagem_produto(caminho_relativo_media: str) -> str:
    """
    URL pública para um arquivo sob MEDIA_ROOT.
    caminho_relativo_media: ex. ecommerce/produtos/123.jpg (sem barra inicial).
    """
    rel = caminho_relativo_media.lstrip('/')
    media_url = getattr(settings, 'MEDIA_URL', '/media/')
    if not media_url.endswith('/'):
        media_url = media_url + '/'
    rel_path = f'{media_url}{rel}'
    base = (getattr(settings, 'MEDIA_PUBLIC_BASE_URL', '') or '').rstrip('/')
    if base:
        return f'{base}{rel_path}'
    return rel_path
