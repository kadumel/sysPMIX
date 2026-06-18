from django import template

from ecommerce.analise_pedido import agrupar_itens_curva_a_por_grupo

register = template.Library()


@register.filter
def agrupar_curva_a(itens):
    return agrupar_itens_curva_a_por_grupo(itens)


@register.simple_tag
def itens_analise_tipo(analise, tipo):
    if not analise:
        return []
    return analise.itens.filter(tipo=tipo).order_by('ordem', 'codigo_produto')
