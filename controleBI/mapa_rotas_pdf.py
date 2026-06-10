"""Geração do PDF do mapa de rotas (layout diário em 4 colunas)."""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DIAS_SEMANA_PT = (
    'Segunda-feira',
    'Terça-feira',
    'Quarta-feira',
    'Quinta-feira',
    'Sexta-feira',
    'Sábado',
    'Domingo',
)

NUM_COLUNAS = 4
MARGEM_PAGINA = 10 * mm
ESPACO_ENTRE_BLOCOS = 4 * mm
ESPACO_APOS_TITULO = 7 * mm
ESPACO_ENTRE_DIAS = 4 * mm
BORDA_ESPESSURA = 0.75
COR_CABECALHO = colors.HexColor('#C8C8C8')
COR_BORDA = colors.black

ESTILO_TITULO = ParagraphStyle(
    name='MapaRotasTitulo',
    fontName='Helvetica-Bold',
    fontSize=13,
    leading=15,
    alignment=TA_CENTER,
    spaceAfter=ESPACO_APOS_TITULO,
)
ESTILO_EQUIPE = ParagraphStyle(
    name='MapaRotasEquipe',
    fontName='Helvetica-Bold',
    fontSize=8.5,
    leading=10.5,
    alignment=TA_CENTER,
)
ESTILO_VEICULO = ParagraphStyle(
    name='MapaRotasVeiculo',
    fontName='Helvetica-Bold',
    fontSize=8,
    leading=10,
    alignment=TA_CENTER,
)
ESTILO_CLIENTE = ParagraphStyle(
    name='MapaRotasCliente',
    fontName='Helvetica',
    fontSize=7.5,
    leading=9.5,
    alignment=TA_CENTER,
)
ESTILO_SUBTITULO_SEMANA = ParagraphStyle(
    name='MapaRotasSubtituloSemana',
    fontName='Helvetica',
    fontSize=9,
    leading=11,
    alignment=TA_CENTER,
    spaceAfter=4 * mm,
    textColor=colors.HexColor('#444444'),
)


def _nome_cliente(cliente) -> str:
    return (cliente.nome or cliente.razao or '').strip()


def _equipe_nomes(rota) -> str:
    nomes = []
    if rota.motorista:
        nomes.append(rota.motorista.nome.strip())
    for aj in rota.ajudantes_equipe.all():
        nomes.append(aj.funcionario.nome.strip())
    return ' // '.join(n.upper() for n in nomes if n)


def _veiculo_rotulo(rota) -> str:
    if rota.veiculo:
        rotulo = (rota.veiculo.descricao or rota.veiculo.placa or '').strip()
        if rotulo:
            return f'CAMINHÃO: {rotulo.upper()}'
    return 'CAMINHÃO: —'


def _altura_rota(rota) -> int:
    return 2 + len(list(rota.clientes_rota.all())) + 1


def _distribuir_rotas_colunas(rotas: list, num_cols: int = NUM_COLUNAS) -> list[list]:
    colunas: list[list] = [[] for _ in range(num_cols)]
    alturas = [0] * num_cols
    for rota in rotas:
        idx = min(range(num_cols), key=lambda i: alturas[i])
        colunas[idx].append(rota)
        alturas[idx] += _altura_rota(rota)
    return colunas


def _estilo_bloco_rota() -> TableStyle:
    pad_v = 4
    pad_h = 3
    return TableStyle(
        [
            ('BOX', (0, 0), (-1, -1), BORDA_ESPESSURA, COR_BORDA),
            ('INNERGRID', (0, 0), (-1, -1), BORDA_ESPESSURA, COR_BORDA),
            ('BACKGROUND', (0, 0), (-1, 1), COR_CABECALHO),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), pad_v),
            ('BOTTOMPADDING', (0, 0), (-1, -1), pad_v),
            ('LEFTPADDING', (0, 0), (-1, -1), pad_h),
            ('RIGHTPADDING', (0, 0), (-1, -1), pad_h),
        ]
    )


def _bloco_rota_table(rota, largura: float):
    linhas = [
        [Paragraph(_equipe_nomes(rota) or '—', ESTILO_EQUIPE)],
        [Paragraph(_veiculo_rotulo(rota), ESTILO_VEICULO)],
    ]
    for rc in rota.clientes_rota.all():
        nome = _nome_cliente(rc.cliente).upper() or '—'
        linhas.append([Paragraph(nome, ESTILO_CLIENTE)])

    tabela = Table(linhas, colWidths=[largura])
    tabela.setStyle(_estilo_bloco_rota())
    return tabela


def _coluna_table(rotas: list, largura: float):
    if not rotas:
        return Spacer(1, 1)
    blocos = []
    for rota in rotas:
        blocos.append([_bloco_rota_table(rota, largura)])
        blocos.append([Spacer(1, ESPACO_ENTRE_BLOCOS)])
    tabela = Table(blocos, colWidths=[largura])
    tabela.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )
    return tabela


def _grade_dia_table(rotas: list, largura_col: float):
    colunas = _distribuir_rotas_colunas(rotas)
    grade = Table(
        [[_coluna_table(col, largura_col) for col in colunas]],
        colWidths=[largura_col] * NUM_COLUNAS,
    )
    grade.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 1.5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 1.5),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )
    return grade


def formatar_titulo_data(d: date) -> str:
    return f'{DIAS_SEMANA_PT[d.weekday()].lower()} {d.strftime("%d.%m.%Y")}'


def formatar_titulo_semana(inicio: date, fim: date) -> str:
    return f'Semana de {inicio.strftime("%d.%m.%Y")} a {fim.strftime("%d.%m.%Y")}'


def _largura_coluna() -> float:
    page_w, _ = landscape(A4)
    return (page_w - 2 * MARGEM_PAGINA) / NUM_COLUNAS


def _story_dia(dia: date, rotas: list, largura_col: float) -> list:
    return [
        Paragraph(formatar_titulo_data(dia), ESTILO_TITULO),
        _grade_dia_table(rotas, largura_col),
    ]


def _montar_story(dias_rotas: list[tuple[date, list]], subtitulo_semana: str | None = None) -> list:
    largura_col = _largura_coluna()
    story: list = []
    if subtitulo_semana:
        story.append(Paragraph(subtitulo_semana, ESTILO_SUBTITULO_SEMANA))

    blocos = [(dia, rotas) for dia, rotas in dias_rotas if rotas]
    for idx, (dia, rotas) in enumerate(blocos):
        if idx > 0:
            story.append(PageBreak())
        story.extend(_story_dia(dia, rotas, largura_col))
    return story


def _gerar_pdf(story: list) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=MARGEM_PAGINA,
        rightMargin=MARGEM_PAGINA,
        topMargin=9 * mm,
        bottomMargin=9 * mm,
    )
    doc.build(story)
    return buffer.getvalue()


def gerar_mapa_rotas_pdf(dia: date, rotas: list) -> bytes:
    return _gerar_pdf(_montar_story([(dia, rotas)]))


def gerar_mapa_rotas_semana_pdf(
    week_start: date,
    rotas_por_dia: dict[date, list],
) -> bytes:
    dias_rotas = []
    for i in range(7):
        dia = week_start + timedelta(days=i)
        dias_rotas.append((dia, rotas_por_dia.get(dia, [])))
    subtitulo = formatar_titulo_semana(week_start, week_start + timedelta(days=6))
    return _gerar_pdf(_montar_story(dias_rotas, subtitulo_semana=subtitulo))
