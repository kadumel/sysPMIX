"""
Análise de pedido antes da finalização: itens esquecidos, novidades e curva A.
"""

from __future__ import annotations

import calendar
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import groupby
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce

from api_sankhya.models import Cliente, ItemNotaFiscal, ItemPedido, NotaFiscal, Pedido, Produto
from ecommerce import catalog
from ecommerce.models import (
    AnalisePedidoLoja,
    Campanha,
    ItemAnalisePedidoLoja,
    ItemCampanha,
    ItemPedidoLoja,
    PedidoLoja,
)

SESSION_ANALISE_KEY = 'ecommerce_checkout_analise'

MAX_NOVIDADES = 15
TOP_CURVA_A_POR_GRUPO = 10

TIPO_ESQUECIDOS = ItemAnalisePedidoLoja.Tipo.ESQUECIDOS
TIPO_NOVIDADES = ItemAnalisePedidoLoja.Tipo.NOVIDADES
TIPO_CURVA_A = ItemAnalisePedidoLoja.Tipo.CURVA_A

# Até esta data (inclusive): histórico em sankhya_pedido. Depois: sankhya_nota_fiscal.
DATA_CORTE_PEDIDO_PARA_NOTA = date(2026, 4, 30)
# Pedidos Sankhya considerados na análise do e-commerce (mesmo critério da integração).
CODIGO_CONTATO_PEDIDO_ANALISE = 999999

logger = logging.getLogger(__name__)


@dataclass
class SugestaoAnalise:
    codigo_produto: int
    nome: str
    tipo: str
    grupo_produto: str = ''
    detalhe: str = ''
    preco_unitario: Decimal | None = None
    ordem: int = 0


@dataclass
class ResultadoAnalise:
    tempo_analise_meses: int
    data_inicio_periodo: date
    data_fim_periodo: date
    esquecidos: list[SugestaoAnalise] = field(default_factory=list)
    novidades: list[SugestaoAnalise] = field(default_factory=list)
    curva_a: list[SugestaoAnalise] = field(default_factory=list)

    @property
    def tem_sugestoes(self) -> bool:
        return bool(self.esquecidos or self.novidades or self.curva_a)

    def todas_sugestoes(self) -> list[SugestaoAnalise]:
        return [*self.esquecidos, *self.novidades, *self.curva_a]

    @property
    def curva_a_por_grupo(self) -> list[tuple[str, list[SugestaoAnalise]]]:
        return agrupar_itens_curva_a_por_grupo(self.curva_a)

    def to_session_dict(self) -> dict:
        def _rows(items: list[SugestaoAnalise]) -> list[dict]:
            return [
                {
                    'codigo_produto': s.codigo_produto,
                    'nome': s.nome,
                    'tipo': s.tipo,
                    'grupo_produto': s.grupo_produto,
                    'detalhe': s.detalhe,
                    'ordem': s.ordem,
                    'preco_unitario': (
                        None if s.preco_unitario is None else str(s.preco_unitario)
                    ),
                }
                for s in items
            ]

        return {
            'tempo_analise_meses': self.tempo_analise_meses,
            'data_inicio_periodo': self.data_inicio_periodo.isoformat(),
            'data_fim_periodo': self.data_fim_periodo.isoformat(),
            'esquecidos': _rows(self.esquecidos),
            'novidades': _rows(self.novidades),
            'curva_a': _rows(self.curva_a),
        }

    @classmethod
    def from_session_dict(cls, data: dict) -> ResultadoAnalise:
        def _parse(rows: list[dict]) -> list[SugestaoAnalise]:
            out: list[SugestaoAnalise] = []
            for row in rows or []:
                preco_raw = row.get('preco_unitario')
                out.append(
                    SugestaoAnalise(
                        codigo_produto=int(row['codigo_produto']),
                        nome=row.get('nome') or '',
                        tipo=row['tipo'],
                        grupo_produto=row.get('grupo_produto') or '',
                        detalhe=row.get('detalhe') or '',
                        ordem=int(row.get('ordem') or 0),
                        preco_unitario=(
                            Decimal(preco_raw)
                            if preco_raw not in (None, '')
                            else None
                        ),
                    )
                )
            return out

        return cls(
            tempo_analise_meses=int(data.get('tempo_analise_meses') or 2),
            data_inicio_periodo=date.fromisoformat(data['data_inicio_periodo']),
            data_fim_periodo=date.fromisoformat(data['data_fim_periodo']),
            esquecidos=_parse(data.get('esquecidos')),
            novidades=_parse(data.get('novidades')),
            curva_a=_parse(data.get('curva_a')),
        )


def remover_sugestao_do_snapshot(snapshot: dict, codigo_produto: int) -> None:
    """Remove produto das listas da análise na sessão (ex.: após adicionar ao carrinho)."""
    for sec in ('esquecidos', 'novidades', 'curva_a'):
        snapshot[sec] = [
            row
            for row in snapshot.get(sec, [])
            if int(row['codigo_produto']) != codigo_produto
        ]


def _data_meses_atras(ref: date, meses: int) -> date:
    y, m, d = ref.year, ref.month, ref.day
    m -= meses
    while m <= 0:
        m += 12
        y -= 1
    d = min(d, calendar.monthrange(y, m)[1])
    return date(y, m, d)


def _periodo_analise(cliente: Cliente, ref: date | None = None) -> tuple[date, date, int]:
    ref = ref or catalog.data_referencia_ecommerce()
    meses = max(1, int(getattr(cliente, 'tempo_analise', None) or 2))
    inicio = _data_meses_atras(ref, meses)
    return inicio, ref, meses


def _produtos_comprados_cliente_desde(
    cliente: Cliente,
    desde: date,
    ate: date | None = None,
) -> set[int]:
    """Produtos comprados pelo cliente desde uma data (loja + Sankhya no período)."""
    ate = ate or catalog.data_referencia_ecommerce()
    if desde > ate:
        return set()
    freq, _ = _freq_pedidos_cliente_periodo(cliente, desde, ate)
    return set(freq.keys())


def _inicio_notas_fiscais() -> date:
    return DATA_CORTE_PEDIDO_PARA_NOTA + timedelta(days=1)


def _intervalo_pedidos_sankhya(desde: date, ate: date) -> tuple[date, date] | None:
    """Trecho do período em que o histórico vem de sankhya_pedido."""
    if ate <= DATA_CORTE_PEDIDO_PARA_NOTA:
        return desde, ate
    if desde > DATA_CORTE_PEDIDO_PARA_NOTA:
        return None
    return desde, DATA_CORTE_PEDIDO_PARA_NOTA


def _intervalo_notas_fiscais(desde: date, ate: date) -> tuple[date, date] | None:
    """Trecho do período em que o histórico vem de sankhya_nota_fiscal."""
    ini_nf = _inicio_notas_fiscais()
    if ate < ini_nf:
        return None
    return max(desde, ini_nf), ate


def _filtro_pedidos_sankhya_analise(codigo_cliente: int, desde: date, ate: date):
    return Pedido.objects.filter(
        codigo_cliente=codigo_cliente,
        codigo_contato=CODIGO_CONTATO_PEDIDO_ANALISE,
        data_negociacao__gte=desde,
        data_negociacao__lte=ate,
    )


def _acumular_freq_pedidos_sankhya(
    codigo_cliente: int,
    desde: date,
    ate: date,
    freq: dict[int, int],
    pedidos_ids: set[str],
) -> None:
    pedido_pks = _filtro_pedidos_sankhya_analise(
        codigo_cliente, desde, ate
    ).order_by().values_list('pk', flat=True)
    por_pedido: dict[int, set[int]] = defaultdict(set)
    for pedido_id, cod in ItemPedido.objects.filter(
        pedido_id__in=pedido_pks, cod_produto__isnull=False
    ).order_by().values_list('pedido_id', 'cod_produto'):
        por_pedido[pedido_id].add(int(cod))
    for pedido_id, cods in por_pedido.items():
        pedidos_ids.add(f'sk:{pedido_id}')
        for cod in cods:
            freq[cod] += 1


def _acumular_freq_notas_fiscais(
    codigo_cliente: int,
    desde: date,
    ate: date,
    freq: dict[int, int],
    pedidos_ids: set[str],
) -> None:
    nf_pks = NotaFiscal.objects.filter(
        codigo_parceiro=codigo_cliente,
        data_negociacao__gte=desde,
        data_negociacao__lte=ate,
    ).order_by().values_list('pk', flat=True)
    por_nf: dict[int, set[int]] = defaultdict(set)
    for nf_id, cod in ItemNotaFiscal.objects.filter(
        nota_fiscal_id__in=nf_pks, cod_produto__isnull=False
    ).order_by().values_list('nota_fiscal_id', 'cod_produto'):
        por_nf[nf_id].add(int(cod))
    for nf_id, cods in por_nf.items():
        pedidos_ids.add(f'nf:{nf_id}')
        for cod in cods:
            freq[cod] += 1


def _acumular_historico_sankhya_periodo(
    codigo_cliente: int,
    desde: date,
    ate: date,
    freq: dict[int, int],
    pedidos_ids: set[str],
) -> None:
    intervalo_ped = _intervalo_pedidos_sankhya(desde, ate)
    if intervalo_ped:
        _acumular_freq_pedidos_sankhya(codigo_cliente, *intervalo_ped, freq, pedidos_ids)
    intervalo_nf = _intervalo_notas_fiscais(desde, ate)
    if intervalo_nf:
        _acumular_freq_notas_fiscais(codigo_cliente, *intervalo_nf, freq, pedidos_ids)


def _nome_grupo_item(item) -> str:
    nome = (getattr(item, 'grupo_produto', None) or '').strip()
    return nome or 'Outros'


def agrupar_itens_curva_a_por_grupo(itens) -> list[tuple[str, list]]:
    """Agrupa sugestões ou itens persistidos da curva A por nome do grupo."""
    lista = list(itens or [])
    if not lista:
        return []
    lista.sort(
        key=lambda i: (
            _nome_grupo_item(i),
            getattr(i, 'ordem', 0),
            getattr(i, 'codigo_produto', 0),
        )
    )
    return [(grupo, list(grupo_itens)) for grupo, grupo_itens in groupby(lista, key=_nome_grupo_item)]


def _codigos_carrinho(cart: list[dict]) -> set[int]:
    out: set[int] = set()
    for item in cart or []:
        try:
            out.add(int(item.get('codigo_produto')))
        except (TypeError, ValueError):
            continue
    return out


def _freq_pedidos_cliente_periodo(cliente: Cliente, desde: date, ate: date) -> tuple[dict[int, int], int]:
    """Retorna frequência de produtos em pedidos do cliente e total de pedidos distintos."""
    freq: dict[int, int] = defaultdict(int)
    pedidos_ids: set[str] = set()

    loja_qs = (
        PedidoLoja.objects.filter(cliente=cliente, criado_em__date__gte=desde, criado_em__date__lte=ate)
        .exclude(status=PedidoLoja.Status.REJEITADO)
        .order_by()
        .values_list('pk', flat=True)
    )
    por_pedido_loja: dict[int, set[int]] = defaultdict(set)
    for pedido_id, cod in ItemPedidoLoja.objects.filter(pedido_id__in=loja_qs).order_by().values_list(
        'pedido_id', 'codigo_produto'
    ):
        if cod:
            por_pedido_loja[pedido_id].add(int(cod))
    for pedido_id, cods in por_pedido_loja.items():
        pedidos_ids.add(f'loja:{pedido_id}')
        for cod in cods:
            freq[cod] += 1

    if cliente.codigo_cliente:
        # Mesmo critério da query SQL de validação: pedidos (contato 999999) e NF
        # em todo o período do tempo_analise (union de produtos distintos).
        _acumular_freq_pedidos_sankhya(
            cliente.codigo_cliente, desde, ate, freq, pedidos_ids
        )
        _acumular_freq_notas_fiscais(
            cliente.codigo_cliente, desde, ate, freq, pedidos_ids
        )

    return dict(freq), len(pedidos_ids)


def _produtos_ja_comprados_cliente(cliente: Cliente) -> set[int]:
    comprados: set[int] = set()

    loja_qs = PedidoLoja.objects.filter(cliente=cliente).exclude(status=PedidoLoja.Status.REJEITADO)
    comprados.update(
        int(c)
        for c in ItemPedidoLoja.objects.filter(pedido__in=loja_qs, codigo_produto__isnull=False).values_list(
            'codigo_produto', flat=True
        )
        if c
    )

    if cliente.codigo_cliente:
        comprados.update(
            int(c)
            for c in ItemPedido.objects.filter(
                pedido__codigo_cliente=cliente.codigo_cliente,
                pedido__codigo_contato=CODIGO_CONTATO_PEDIDO_ANALISE,
                pedido__data_negociacao__lte=DATA_CORTE_PEDIDO_PARA_NOTA,
                cod_produto__isnull=False,
            ).order_by().values_list('cod_produto', flat=True)
            if c
        )
        comprados.update(
            int(c)
            for c in ItemNotaFiscal.objects.filter(
                nota_fiscal__codigo_parceiro=cliente.codigo_cliente,
                nota_fiscal__data_negociacao__gte=_inicio_notas_fiscais(),
                cod_produto__isnull=False,
            ).order_by().values_list('cod_produto', flat=True)
            if c
        )
    return comprados


def _produtos_disponiveis_loja(
    codigos: set[int],
    codtab: int | None,
    codigos_permitidos: set[int],
) -> dict[int, Produto]:
    if not codigos or not codtab:
        return {}
    produtos = {
        p.codigo_produto: p
        for p in Produto.objects.filter(codigo_produto__in=codigos, ativo=True)
    }
    precos = catalog.map_precos_por_codtab(list(produtos.keys()), codtab)
    out: dict[int, Produto] = {}
    for cod, produto in produtos.items():
        if not catalog.produto_permitido_na_loja(produto, codigos_permitidos):
            continue
        preco = precos.get(cod)
        if not preco or preco <= 0:
            continue
        produto.preco_ecommerce = preco
        out[cod] = produto
    return out


def _produtos_para_esquecidos(
    codigos: set[int],
    codtab: int | None,
) -> dict[int, Produto]:
    """Produtos ativos do histórico; preço da tabela quando existir (sem exigir preço/grupo loja)."""
    if not codigos:
        return {}
    produtos = {
        p.codigo_produto: p
        for p in Produto.objects.filter(codigo_produto__in=codigos, ativo=True)
    }
    precos = catalog.map_precos_por_codtab(list(produtos.keys()), codtab) if codtab else {}
    for cod, produto in produtos.items():
        produto.preco_ecommerce = precos.get(cod)
    return produtos


def _sugestao_de_produto(
    produto: Produto,
    tipo: str,
    detalhe: str,
    ordem: int,
) -> SugestaoAnalise:
    return SugestaoAnalise(
        codigo_produto=produto.codigo_produto,
        nome=(produto.nome or '').strip() or f'Cód. {produto.codigo_produto}',
        tipo=tipo,
        grupo_produto=(produto.nome_grupo_produto or '').strip(),
        detalhe=detalhe,
        preco_unitario=getattr(produto, 'preco_ecommerce', None),
        ordem=ordem,
    )


def _itens_esquecidos(
    cliente: Cliente,
    cart_codigos: set[int],
    desde: date,
    ate: date,
    codtab: int | None,
    codigos_permitidos: set[int],
) -> list[SugestaoAnalise]:
    freq, total_pedidos = _freq_pedidos_cliente_periodo(cliente, desde, ate)
    if not freq:
        return []

    # Mesmo critério da consulta SQL: produtos distintos comprados no período, exceto o carrinho.
    candidatos = [
        (cod, qtd)
        for cod, qtd in freq.items()
        if cod not in cart_codigos
    ]
    candidatos.sort(key=lambda x: (-x[1], x[0]))
    if not candidatos:
        return []

    produtos = _produtos_para_esquecidos({c for c, _ in candidatos}, codtab)
    out: list[SugestaoAnalise] = []
    for cod, qtd in candidatos:
        if total_pedidos > 0:
            detalhe = f'Em {qtd} de {total_pedidos} pedido(s) no período'
        else:
            detalhe = 'Comprado no período'
        produto = produtos.get(cod)
        if not produto:
            continue
        out.append(
            _sugestao_de_produto(
                produto,
                TIPO_ESQUECIDOS,
                detalhe,
                len(out),
            )
        )
    return out


def _campanhas_vigentes(ref: date) -> list[Campanha]:
    return list(
        Campanha.objects.filter(data_inicio__lte=ref, data_fim__gte=ref).order_by('-data_inicio', 'nome')
    )


def _itens_novidades(
    cliente: Cliente,
    cart_codigos: set[int],
    excluir: set[int],
    ref: date,
    codtab: int | None,
    codigos_permitidos: set[int],
) -> list[SugestaoAnalise]:
    campanhas = _campanhas_vigentes(ref)
    if not campanhas:
        return []

    codigos_campanha: dict[int, str] = {}
    for campanha in campanhas:
        comprados_desde_inicio = _produtos_comprados_cliente_desde(cliente, campanha.data_inicio, ref)
        for cod in ItemCampanha.objects.filter(campanha=campanha).values_list(
            'produto__codigo_produto', flat=True
        ):
            if (
                cod
                and cod not in cart_codigos
                and cod not in excluir
                and cod not in comprados_desde_inicio
            ):
                codigos_campanha.setdefault(int(cod), campanha.nome)

    if not codigos_campanha:
        if campanhas:
            logger.info(
                'Análise novidades: campanhas vigentes=%s, nenhum produto elegível (cliente=%s).',
                len(campanhas),
                cliente.pk,
            )
        return []

    produtos = _produtos_disponiveis_loja(set(codigos_campanha.keys()), codtab, codigos_permitidos)
    out: list[SugestaoAnalise] = []
    for idx, cod in enumerate(sorted(codigos_campanha.keys())):
        if len(out) >= MAX_NOVIDADES:
            break
        produto = produtos.get(cod)
        if not produto:
            continue
        out.append(
            _sugestao_de_produto(
                produto,
                TIPO_NOVIDADES,
                f'Campanha: {codigos_campanha[cod]}',
                idx,
            )
        )

    if codigos_campanha and not out:
        logger.warning(
            'Análise novidades: %s produto(s) de campanha filtrados pela loja '
            '(cliente=%s, codtab=%s, grupos_permitidos=%s).',
            len(codigos_campanha),
            cliente.pk,
            codtab,
            len(codigos_permitidos),
        )
    return out


def _somar_vendas_agregadas(
    por_grupo: dict[int, dict[int, Decimal]],
    rows,
) -> None:
    codigos = [int(r['cod_produto']) for r in rows if r.get('cod_produto')]
    if not codigos:
        return
    grupo_por_cod = {
        p.codigo_produto: p.codigo_grupo_produto
        for p in Produto.objects.filter(codigo_produto__in=codigos).only(
            'codigo_produto', 'codigo_grupo_produto'
        )
        if p.codigo_grupo_produto
    }
    for row in rows:
        cod = int(row['cod_produto'])
        grupo = grupo_por_cod.get(cod)
        if grupo is None:
            continue
        por_grupo[grupo][cod] += row['qtd'] or Decimal('0')


def _vendas_globais_por_grupo(desde: date, ate: date) -> dict[int, list[tuple[int, Decimal]]]:
    """Grupo → [(cod_produto, qtd_total)] ordenado por volume."""
    por_grupo: dict[int, dict[int, Decimal]] = defaultdict(lambda: defaultdict(Decimal))

    intervalo_ped = _intervalo_pedidos_sankhya(desde, ate)
    if intervalo_ped:
        ped_ini, ped_fim = intervalo_ped
        pedido_ids = Pedido.objects.filter(
            data_negociacao__gte=ped_ini,
            data_negociacao__lte=ped_fim,
        ).order_by().values_list('pk', flat=True)
        rows_ped = (
            ItemPedido.objects.filter(pedido_id__in=pedido_ids, cod_produto__isnull=False)
            .values('cod_produto')
            .annotate(qtd=Coalesce(Sum('quantidade'), Decimal('0')))
            .order_by()
        )
        _somar_vendas_agregadas(por_grupo, rows_ped)

    intervalo_nf = _intervalo_notas_fiscais(desde, ate)
    if intervalo_nf:
        nf_ini, nf_fim = intervalo_nf
        nf_ids = NotaFiscal.objects.filter(
            data_negociacao__gte=nf_ini,
            data_negociacao__lte=nf_fim,
        ).order_by().values_list('pk', flat=True)
        rows_nf = (
            ItemNotaFiscal.objects.filter(nota_fiscal_id__in=nf_ids, cod_produto__isnull=False)
            .values('cod_produto')
            .annotate(qtd=Coalesce(Sum('quantidade'), Decimal('0')))
            .order_by()
        )
        _somar_vendas_agregadas(por_grupo, rows_nf)

    resultado: dict[int, list[tuple[int, Decimal]]] = {}
    for grupo, prod_map in por_grupo.items():
        ranking = sorted(prod_map.items(), key=lambda x: (-x[1], x[0]))[:TOP_CURVA_A_POR_GRUPO]
        if ranking:
            resultado[grupo] = ranking
    return resultado


def _itens_curva_a(
    cliente: Cliente,
    cart_codigos: set[int],
    excluir: set[int],
    desde: date,
    ate: date,
    codtab: int | None,
    codigos_permitidos: set[int],
) -> list[SugestaoAnalise]:
    ja_comprou = _produtos_ja_comprados_cliente(cliente)
    ranking_por_grupo = _vendas_globais_por_grupo(desde, ate)
    candidatos: list[tuple[int, int, Decimal]] = []
    for grupo, ranking in ranking_por_grupo.items():
        for pos, (cod, qtd) in enumerate(ranking, start=1):
            if cod in cart_codigos or cod in excluir or cod in ja_comprou:
                continue
            candidatos.append((grupo, cod, qtd))

    if not candidatos:
        return []

    produtos = _produtos_disponiveis_loja({c[1] for c in candidatos}, codtab, codigos_permitidos)
    out: list[SugestaoAnalise] = []
    ordem = 0
    for grupo, cod, qtd in candidatos:
        produto = produtos.get(cod)
        if not produto:
            continue
        grupo_nome = (produto.nome_grupo_produto or '').strip() or f'Grupo {grupo}'
        out.append(
            _sugestao_de_produto(
                produto,
                TIPO_CURVA_A,
                f'Top {TOP_CURVA_A_POR_GRUPO} do grupo · vol. {qtd:.0f}',
                ordem,
            )
        )
        ordem += 1
    return out


def diagnosticar_novidades_campanha(
    cliente: Cliente,
    cart: list[dict],
    ref: date | None = None,
) -> dict:
    """Detalha por que produtos de campanha não entram em novidades (uso em DEBUG/suporte)."""
    ref = ref or catalog.data_referencia_ecommerce()
    cart_codigos = _codigos_carrinho(cart)
    codtab = catalog.normalizar_codtab(getattr(cliente, 'codtab', None))
    codigos_permitidos = catalog.codigos_grupos_permitidos_ecommerce()
    desde, ate, meses = _periodo_analise(cliente, ref)
    esquecidos = _itens_esquecidos(cliente, cart_codigos, desde, ate, codtab, codigos_permitidos)
    excluir = {s.codigo_produto for s in esquecidos}
    campanhas = _campanhas_vigentes(ref)

    diag: dict = {
        'data_referencia': ref.isoformat(),
        'cliente_id': cliente.pk,
        'codigo_cliente': cliente.codigo_cliente,
        'codtab': codtab,
        'grupos_permitidos': len(codigos_permitidos),
        'campanhas_vigentes': [
            {
                'id': c.pk,
                'nome': c.nome,
                'data_inicio': c.data_inicio.isoformat(),
                'data_fim': c.data_fim.isoformat(),
            }
            for c in campanhas
        ],
        'produtos': [],
    }

    if not campanhas:
        diag['motivo'] = 'nenhuma_campanha_vigente'
        return diag

    for campanha in campanhas:
        comprados_desde_inicio = _produtos_comprados_cliente_desde(cliente, campanha.data_inicio, ref)
        for cod in ItemCampanha.objects.filter(campanha=campanha).values_list(
            'produto__codigo_produto', flat=True
        ):
            if not cod:
                continue
            cod = int(cod)
            produto = Produto.objects.filter(codigo_produto=cod).first()
            preco = catalog.map_precos_por_codtab([cod], codtab).get(cod) if codtab else None
            motivos: list[str] = []
            if cod in cart_codigos:
                motivos.append('no_carrinho')
            if cod in excluir:
                motivos.append('em_esquecidos')
            if cod in comprados_desde_inicio:
                motivos.append('comprado_desde_inicio_campanha')
            if not produto or not produto.ativo:
                motivos.append('produto_inativo_ou_inexistente')
            elif not catalog.produto_permitido_na_loja(produto, codigos_permitidos):
                motivos.append('grupo_nao_habilitado_loja')
            if not preco or preco <= 0:
                motivos.append('sem_preco_na_tabela_cliente')
            diag['produtos'].append(
                {
                    'codigo_produto': cod,
                    'campanha': campanha.nome,
                    'elegivel': not motivos,
                    'motivos': motivos,
                    'preco_tabela': str(preco) if preco else None,
                }
            )

    if not diag['produtos']:
        diag['motivo'] = 'campanhas_sem_produtos'
    elif all(not p['elegivel'] for p in diag['produtos']):
        diag['motivo'] = 'todos_produtos_filtrados'
    return diag


def calcular_analise_pedido(
    cliente: Cliente,
    cart: list[dict],
    ref: date | None = None,
) -> ResultadoAnalise:
    ref = ref or catalog.data_referencia_ecommerce()
    desde, ate, meses = _periodo_analise(cliente, ref)
    cart_codigos = _codigos_carrinho(cart)
    codtab = catalog.normalizar_codtab(getattr(cliente, 'codtab', None))
    codigos_permitidos = catalog.codigos_grupos_permitidos_ecommerce()

    esquecidos = _itens_esquecidos(cliente, cart_codigos, desde, ate, codtab, codigos_permitidos)
    usados = {s.codigo_produto for s in esquecidos}

    novidades = _itens_novidades(cliente, cart_codigos, usados, ref, codtab, codigos_permitidos)
    usados.update(s.codigo_produto for s in novidades)

    curva_a = _itens_curva_a(cliente, cart_codigos, usados, desde, ate, codtab, codigos_permitidos)

    return ResultadoAnalise(
        tempo_analise_meses=meses,
        data_inicio_periodo=desde,
        data_fim_periodo=ate,
        esquecidos=esquecidos,
        novidades=novidades,
        curva_a=curva_a,
    )


def persistir_analise_pedido(pedido: PedidoLoja, resultado: ResultadoAnalise | dict) -> AnalisePedidoLoja:
    if isinstance(resultado, dict):
        resultado = ResultadoAnalise.from_session_dict(resultado)

    analise, _ = AnalisePedidoLoja.objects.update_or_create(
        pedido=pedido,
        defaults={'tempo_analise_meses': resultado.tempo_analise_meses},
    )
    analise.itens.all().delete()
    bulk: list[ItemAnalisePedidoLoja] = []
    for sugestao in resultado.todas_sugestoes():
        bulk.append(
            ItemAnalisePedidoLoja(
                analise=analise,
                tipo=sugestao.tipo,
                codigo_produto=sugestao.codigo_produto,
                nome_produto=sugestao.nome[:300],
                grupo_produto=(sugestao.grupo_produto or '')[:200],
                detalhe=(sugestao.detalhe or '')[:200],
                ordem=sugestao.ordem,
            )
        )
    if bulk:
        ItemAnalisePedidoLoja.objects.bulk_create(bulk)
    return analise


def agrupar_itens_analise_por_tipo(analise: AnalisePedidoLoja) -> dict[str, list[ItemAnalisePedidoLoja]]:
    grupos: dict[str, list[ItemAnalisePedidoLoja]] = {
        TIPO_ESQUECIDOS: [],
        TIPO_NOVIDADES: [],
        TIPO_CURVA_A: [],
    }
    for item in analise.itens.all().order_by('ordem', 'codigo_produto'):
        grupos.setdefault(item.tipo, []).append(item)
    return grupos
