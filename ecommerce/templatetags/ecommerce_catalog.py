from urllib.parse import urlencode

from django import template

from ecommerce import catalog
from api_sankhya.models import GrupoProduto

register = template.Library()


@register.simple_tag(takes_context=True)
def ecommerce_catalog_qs(context, grupo=None, page=None, q=None):
    """Monta query string do catálogo preservando busca e filtro Mercadoria/Revenda."""
    request = context.get('request')
    pairs: list[tuple[str, str]] = []
    tipo = (
        catalog.tipo_loja_ativo_efetivo(request)
        if request is not None
        else catalog.tipo_loja_padrao()
    )
    pairs.append(('tipo', tipo))
    busca = q if q is not None else (
        catalog.normalizar_busca(request.GET.get('q')) if request is not None else ''
    )
    if busca:
        pairs.append(('q', busca))
    if grupo is not None:
        pairs.append(('grupo', str(grupo)))
    if page is not None:
        pairs.append(('page', str(page)))
    if not pairs:
        return ''
    return '?' + urlencode(pairs)


@register.filter
def tipo_loja_mercadoria(grupo):
    return grupo.tipo_loja == GrupoProduto.TipoLoja.MERCADORIA


@register.filter
def tipo_loja_revenda(grupo):
    return grupo.tipo_loja == GrupoProduto.TipoLoja.REVENDA
