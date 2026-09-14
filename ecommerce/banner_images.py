"""Gera a versão mobile de banners promocionais (recorte central + resize)."""

from __future__ import annotations

import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

# Proporção próxima da faixa do celular/PWA (~390x232).
BANNER_MOBILE_WIDTH = 1080
BANNER_MOBILE_HEIGHT = 640


def _center_crop_to_ratio(im: Image.Image, ratio: float) -> Image.Image:
    width, height = im.size
    if width <= 0 or height <= 0:
        return im
    atual = width / height
    if atual > ratio:
        nova_largura = max(1, int(round(height * ratio)))
        left = max(0, (width - nova_largura) // 2)
        return im.crop((left, 0, left + nova_largura, height))
    if atual < ratio:
        nova_altura = max(1, int(round(width / ratio)))
        top = max(0, (height - nova_altura) // 2)
        return im.crop((0, top, width, top + nova_altura))
    return im


def _para_rgb(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode in ('RGBA', 'LA'):
        fundo = Image.new('RGB', im.size, (255, 255, 255))
        fundo.paste(im, mask=im.split()[-1])
        return fundo
    if im.mode != 'RGB':
        return im.convert('RGB')
    return im


def criar_arquivo_banner_mobile(field_file, width=BANNER_MOBILE_WIDTH, height=BANNER_MOBILE_HEIGHT):
    """Recorta no centro na proporção do celular e redimensiona. Retorna (nome, ContentFile)."""
    field_file.open('rb')
    try:
        with Image.open(field_file) as original:
            im = _para_rgb(original)
            im = _center_crop_to_ratio(im, width / height)
            if im.size[0] > width:
                im = im.resize((width, height), Image.Resampling.LANCZOS)
            buf = BytesIO()
            im.save(buf, format='JPEG', quality=85, optimize=True)
    finally:
        field_file.close()

    base = os.path.splitext(os.path.basename(field_file.name))[0]
    if base.endswith('_mobile'):
        base = base[: -len('_mobile')]
    return f'{base}_mobile.jpg', ContentFile(buf.getvalue())
