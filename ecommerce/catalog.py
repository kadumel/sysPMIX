"""
Catálogo a partir das tabelas Sankhya: sankhya_produto e sankhya_grupo_produto.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Exists, OuterRef, Prefetch, Q, QuerySet

from api_sankhya.models import Cliente, GrupoProduto, Preco, Produto
from controleBI.models import PERFIS_PAINEL_BI_LOJA, PerfilUsuario, UsuarioClienteSankhya
from ecommerce.models import ProdutoImagem

PAGE_SIZE = 24
BUSCA_MAX_LEN = 120
ECOMMERCE_TZ = ZoneInfo('America/Sao_Paulo')
TIPOS_LOJA_VALIDOS = frozenset({GrupoProduto.TipoLoja.MERCADORIA, GrupoProduto.TipoLoja.REVENDA})
SESSION_CATALOG_TIPO_KEY = 'ecommerce_catalog_tipo_loja'


def normalizar_codtab(codtab) -> int | None:
    if codtab in (None, 0, ''):
        return None
    try:
        return int(codtab)
    except (TypeError, ValueError):
        return None


def data_referencia_ecommerce() -> date:
    """Data civil usada em campanhas e análise de pedido (fuso Brasil)."""
    from django.utils import timezone

    return timezone.now().astimezone(ECOMMERCE_TZ).date()


def grupos_ativos_map(apenas_visiveis_loja: bool = False):
    """Retorna grupos ativos indexados por código e estrutura pai → filhos.

    Se apenas_visiveis_loja=True, restringe a categorias com mostrar_no_ecommerce=True
    (gestão em controleBI / painel).
    """
    qs = GrupoProduto.objects.filter(ativo=True)
    if apenas_visiveis_loja:
        qs = qs.filter(mostrar_no_ecommerce=True)
    grupos = list(qs.order_by('grau', 'nome'))
    by_id = {g.codigo_grupo_produto: g for g in grupos}
    by_pai: dict[int | None, list[GrupoProduto]] = {}
    raizes: list[GrupoProduto] = []
    for g in grupos:
        pai = g.codigo_grupo_produto_pai
        if pai is None or pai not in by_id:
            raizes.append(g)
        else:
            by_pai.setdefault(pai, []).append(g)
    for k in list(by_pai.keys()):
        by_pai[k].sort(key=lambda x: ((x.grau or 0), (x.nome or '').lower()))
    raizes.sort(key=lambda x: (x.nome or '').lower())
    return by_id, by_pai, raizes


def arvore_grupos_nested(raizes: list[GrupoProduto], by_pai: dict) -> list[dict]:
    def build(g: GrupoProduto) -> dict:
        filhos = by_pai.get(g.codigo_grupo_produto, [])
        return {'grupo': g, 'filhos': [build(c) for c in filhos]}

    return [build(r) for r in raizes]


def grupos_flat_indent(raizes: list[GrupoProduto], by_pai: dict) -> list[tuple[GrupoProduto, int]]:
    """Lista (grupo, profundidade) para `<select>` ou lista linear."""

    rows: list[tuple[GrupoProduto, int]] = []

    def walk(g: GrupoProduto, depth: int) -> None:
        rows.append((g, depth))
        for c in by_pai.get(g.codigo_grupo_produto, []):
            walk(c, depth + 1)

    for r in raizes:
        walk(r, 0)
    return rows


def codigos_grupo_e_descendentes(codigo_raiz: int, by_pai: dict) -> set[int]:
    out: set[int] = {codigo_raiz}
    fila = [codigo_raiz]
    while fila:
        pid = fila.pop(0)
        for child in by_pai.get(pid, []):
            cid = child.codigo_grupo_produto
            if cid not in out:
                out.add(cid)
                fila.append(cid)
    return out


def _ids_self_e_ancestrais_grupo(codigo: int, by_id: dict) -> set[int]:
    out: set[int] = set()
    g = by_id.get(codigo)
    while g is not None:
        out.add(g.codigo_grupo_produto)
        pid = g.codigo_grupo_produto_pai
        g = by_id.get(pid) if pid is not None else None
    return out


def matching_grupo_produto_ids_por_texto(grupos: list[GrupoProduto], termo: str) -> set[int]:
    """Códigos de grupo cujo nome contém o termo ou cujo código numérico coincide / começa com o termo."""
    termo = normalizar_busca(termo)
    if not termo:
        return set()
    out: set[int] = set()
    termo_lower = termo.lower()
    for g in grupos:
        nome = (g.nome or '').lower()
        if termo_lower in nome:
            out.add(g.codigo_grupo_produto)
            continue
        cod_str = str(g.codigo_grupo_produto)
        if termo_lower.isdigit() and (cod_str == termo_lower or cod_str.startswith(termo_lower)):
            out.add(g.codigo_grupo_produto)
    return out


def ids_grupos_com_hierarquia_busca(match_ids: set[int], by_id: dict, by_pai: dict) -> set[int]:
    """Para localizar na árvore: ancestrais + o próprio nó + descendentes de cada match."""
    if not match_ids:
        return set()
    vis: set[int] = set()
    for mid in match_ids:
        if mid not in by_id:
            continue
        vis |= _ids_self_e_ancestrais_grupo(mid, by_id)
        vis |= codigos_grupo_e_descendentes(mid, by_pai)
    return vis


def filtrar_arvore_grupos_por_ids(arvore: list[dict], visiveis: set[int]) -> list[dict]:
    out: list[dict] = []
    for node in arvore:
        g = node['grupo']
        if g.codigo_grupo_produto not in visiveis:
            continue
        filhos_f = filtrar_arvore_grupos_por_ids(node['filhos'], visiveis)
        out.append({'grupo': g, 'filhos': filhos_f})
    return out


def codigos_grupos_permitidos_ecommerce() -> set[int]:
    """Grupos marcados para a loja + todos os filhos ativos na hierarquia Sankhya."""
    _by_id, by_pai, _raizes = grupos_ativos_map(apenas_visiveis_loja=False)
    seeds = list(
        GrupoProduto.objects.filter(ativo=True, mostrar_no_ecommerce=True).values_list(
            'codigo_grupo_produto', flat=True
        )
    )
    if not seeds:
        return set()
    out: set[int] = set()
    for s in seeds:
        if s in _by_id:
            out |= codigos_grupo_e_descendentes(s, by_pai)
    return out


def produto_permitido_na_loja(produto: Produto, codigos_permitidos: set[int] | None = None) -> bool:
    """Produto ativo e com grupo dentro das categorias habilitadas para o e-commerce."""
    if not produto.ativo:
        return False
    cid = produto.codigo_grupo_produto
    if cid is None:
        return False
    if codigos_permitidos is None:
        codigos_permitidos = codigos_grupos_permitidos_ecommerce()
    return cid in codigos_permitidos


def ancestrais(grupo: GrupoProduto, by_id: dict) -> list[GrupoProduto]:
    chain: list[GrupoProduto] = []
    g: GrupoProduto | None = grupo
    while g is not None:
        chain.append(g)
        pid = g.codigo_grupo_produto_pai
        g = by_id.get(pid) if pid is not None else None
    return list(reversed(chain))


def _preco_positivo_na_tabela_exists(codtab: int):
    return Preco.objects.filter(
        codigo_produto=OuterRef('codigo_produto'),
        codigo_tabela=codtab,
        valor__gt=0,
    )


def aplicar_filtro_preco_tabela_cliente(
    qs: QuerySet[Produto], codtab: int | None
) -> QuerySet[Produto]:
    """Restringe a produtos com preço > 0 na tabela (CODTAB) do cliente."""
    if not codtab:
        return qs.none()
    return qs.filter(Exists(_preco_positivo_na_tabela_exists(codtab)))


def codigos_grupo_com_produtos_precificados(
    codtab: int | None, codigos_grupo_permitidos: set[int]
) -> set[int]:
    """Grupos que possuem ao menos um produto ativo com preço > 0 na tabela do cliente."""
    if not codtab or not codigos_grupo_permitidos:
        return set()
    qs = Produto.objects.filter(
        ativo=True, codigo_grupo_produto__in=codigos_grupo_permitidos
    )
    qs = aplicar_filtro_preco_tabela_cliente(qs, codtab)
    return set(qs.values_list('codigo_grupo_produto', flat=True).distinct())


def grupo_tem_produtos_precificados(
    codigo_grupo: int,
    codigos_grupo_com_produtos: set[int],
    by_pai: dict,
    *,
    by_pai_hierarquia: dict | None = None,
) -> bool:
    """True se o grupo ou algum descendente tem produto com preço na tabela do cliente.

    by_pai_hierarquia: mapa pai→filhos com todos os grupos ativos (Sankhya). Use quando a
    navegação da loja lista só categorias visíveis, mas o filtro deve incluir produtos de
    filhos não exibidos no menu.
    """
    if not codigos_grupo_com_produtos:
        return False
    hier = by_pai_hierarquia if by_pai_hierarquia is not None else by_pai
    return bool(
        codigos_grupo_e_descendentes(codigo_grupo, hier) & codigos_grupo_com_produtos
    )


def filtrar_arvore_grupos_com_produtos_precificados(
    arvore: list[dict],
    codigos_grupo_com_produtos: set[int],
    by_pai: dict,
    *,
    by_pai_hierarquia: dict | None = None,
) -> list[dict]:
    out: list[dict] = []
    for node in arvore:
        g = node['grupo']
        if not grupo_tem_produtos_precificados(
            g.codigo_grupo_produto,
            codigos_grupo_com_produtos,
            by_pai,
            by_pai_hierarquia=by_pai_hierarquia,
        ):
            continue
        filhos_f = filtrar_arvore_grupos_com_produtos_precificados(
            node['filhos'],
            codigos_grupo_com_produtos,
            by_pai,
            by_pai_hierarquia=by_pai_hierarquia,
        )
        out.append({'grupo': g, 'filhos': filhos_f})
    return out


def grupos_flat_com_produtos_precificados(
    raizes: list[GrupoProduto],
    by_pai: dict,
    codigos_grupo_com_produtos: set[int],
    *,
    by_pai_hierarquia: dict | None = None,
) -> list[tuple[GrupoProduto, int]]:
    return [
        (g, depth)
        for g, depth in grupos_flat_indent(raizes, by_pai)
        if grupo_tem_produtos_precificados(
            g.codigo_grupo_produto,
            codigos_grupo_com_produtos,
            by_pai,
            by_pai_hierarquia=by_pai_hierarquia,
        )
    ]


def produtos_queryset(
    codigo_grupo: int | None,
    by_id: dict,
    by_pai: dict,
    codigos_grupo_permitidos: set[int],
    codtab: int | None = None,
    *,
    by_pai_hierarquia: dict | None = None,
) -> QuerySet[Produto]:
    """Produtos ativos nas categorias da loja, com preço > 0 na tabela do cliente."""
    qs = Produto.objects.filter(ativo=True).order_by('nome', 'codigo_produto')
    if not codigos_grupo_permitidos:
        return qs.none()
    qs = qs.filter(codigo_grupo_produto__in=codigos_grupo_permitidos)
    qs = aplicar_filtro_preco_tabela_cliente(qs, codtab)
    if codigo_grupo is None:
        return qs
    if codigo_grupo not in by_id:
        return qs.none()
    hier = by_pai_hierarquia if by_pai_hierarquia is not None else by_pai
    codigos = codigos_grupo_e_descendentes(codigo_grupo, hier)
    codigos &= codigos_grupo_permitidos
    if not codigos:
        return qs.none()
    return qs.filter(codigo_grupo_produto__in=codigos)


def parse_grupo_get(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_tipos_loja_get(values: list[str] | None) -> set[str]:
    """Tipos Mercadoria/Revenda explícitos na query string (sem aplicar padrão)."""
    if not values:
        return set()
    out: set[str] = set()
    for raw in values:
        v = (raw or '').strip().lower()
        if v in TIPOS_LOJA_VALIDOS:
            out.add(v)
    return out


def tipo_loja_padrao() -> str:
    return GrupoProduto.TipoLoja.MERCADORIA


def _tipo_loja_de_querydict(qd) -> str | None:
    if qd is None:
        return None
    for raw in qd.getlist('tipo'):
        v = (raw or '').strip().lower()
        if v in TIPOS_LOJA_VALIDOS:
            return v
    return None


def salvar_catalog_tipo_sessao(request, tipo: str) -> None:
    if tipo in TIPOS_LOJA_VALIDOS:
        request.session[SESSION_CATALOG_TIPO_KEY] = tipo
        request.session.modified = True


def tipo_loja_ativo_from_request(request) -> str:
    """Tipo do catálogo: GET, POST (ex.: adicionar ao carrinho), sessão ou mercadoria."""
    for qd in (request.GET, request.POST):
        t = _tipo_loja_de_querydict(qd)
        if t:
            return t
    stored = request.session.get(SESSION_CATALOG_TIPO_KEY)
    if stored in TIPOS_LOJA_VALIDOS:
        return stored
    return tipo_loja_padrao()


def sincronizar_catalog_tipo_sessao(request) -> str:
    """Persiste o tipo ativo na sessão (exceto quando o carrinho trava o tipo)."""
    from .cart_session import cart_tipo_loja_bloqueado

    tipo = tipo_loja_ativo_efetivo(request)
    if not cart_tipo_loja_bloqueado(request):
        salvar_catalog_tipo_sessao(request, tipo)
    return tipo


def tipo_loja_do_codigo_grupo(codigo_grupo: int | None) -> str | None:
    if codigo_grupo is None:
        return None
    tipo = (
        GrupoProduto.objects.filter(
            ativo=True,
            codigo_grupo_produto=codigo_grupo,
        )
        .values_list('tipo_loja', flat=True)
        .first()
    )
    if tipo in TIPOS_LOJA_VALIDOS:
        return tipo
    return None


def tipo_loja_do_produto(produto: Produto) -> str | None:
    return tipo_loja_do_codigo_grupo(produto.codigo_grupo_produto)


def infer_tipo_loja_carrinho(request) -> str | None:
    """Infere o tipo a partir dos grupos dos produtos no carrinho (carrinhos antigos sem sessão)."""
    from .cart_session import get_cart

    cart = get_cart(request)
    codigos = []
    for item in cart:
        try:
            codigos.append(int(item.get('codigo_produto')))
        except (TypeError, ValueError):
            continue
    if not codigos:
        return None
    grupos = set(
        filter(
            None,
            Produto.objects.filter(codigo_produto__in=codigos).values_list(
                'codigo_grupo_produto', flat=True
            ),
        )
    )
    if not grupos:
        return tipo_loja_padrao()
    tipos = set(
        GrupoProduto.objects.filter(
            codigo_grupo_produto__in=grupos,
            tipo_loja__in=TIPOS_LOJA_VALIDOS,
        ).values_list('tipo_loja', flat=True)
    )
    if len(tipos) == 1:
        return next(iter(tipos))
    return tipo_loja_padrao()


def tipo_loja_ativo_efetivo(request) -> str:
    """Tipo usado no catálogo: trava no do carrinho enquanto houver itens."""
    from .cart_session import cart_line_count, get_cart_tipo_loja, lock_cart_tipo_loja

    if cart_line_count(request) > 0:
        locked = get_cart_tipo_loja(request)
        if not locked:
            locked = infer_tipo_loja_carrinho(request)
            if locked:
                lock_cart_tipo_loja(request, locked)
        if locked:
            return locked
    return tipo_loja_ativo_from_request(request)


def validar_e_adicionar_ao_carrinho(
    request,
    produto: Produto,
    qty: float,
    nome: str | None = None,
    *,
    tipo_catalogo: str | None = None,
) -> tuple[bool, str]:
    """Valida tipo Mercadoria/Revenda e adiciona ao carrinho. Retorna (ok, mensagem_erro)."""
    from .cart_session import (
        add_product,
        cart_line_count,
        get_cart_tipo_loja,
        lock_cart_tipo_loja,
    )

    tipo_ativo = tipo_loja_ativo_efetivo(request)
    if tipo_catalogo in TIPOS_LOJA_VALIDOS and not cart_line_count(request):
        tipo_ativo = tipo_catalogo
    tipo_produto = tipo_loja_do_produto(produto)
    if not tipo_produto:
        return False, 'Este produto não possui tipo configurado (Mercadoria ou Revenda).'

    if tipo_produto != tipo_ativo:
        label = 'Revenda' if tipo_produto == GrupoProduto.TipoLoja.REVENDA else 'Mercadoria'
        ativo = 'Revenda' if tipo_ativo == GrupoProduto.TipoLoja.REVENDA else 'Mercadoria'
        return False, f'Este produto é de {label}, mas o catálogo está em modo {ativo}.'

    cart_tipo = get_cart_tipo_loja(request)
    if cart_tipo and cart_tipo != tipo_produto:
        return False, 'Não é possível misturar Mercadoria e Revenda no mesmo carrinho.'

    if not cart_line_count(request):
        lock_cart_tipo_loja(request, tipo_ativo)

    rotulo = nome or (produto.nome or '').strip() or f'Cód. {produto.codigo_produto}'
    add_product(request, produto.codigo_produto, rotulo, qty=qty)
    salvar_catalog_tipo_sessao(request, tipo_ativo)
    return True, ''


def codigos_grupo_filtrados_tipo_loja(
    codigos: set[int],
    tipos_loja: set[str],
    by_id: dict[int, GrupoProduto],
) -> set[int]:
    """Restringe códigos de grupo aos tipos Mercadoria/Revenda configurados."""
    if not tipos_loja:
        return codigos
    return {
        c
        for c in codigos
        if (g := by_id.get(c)) is not None and g.tipo_loja in tipos_loja
    }


def normalizar_busca(value: str | None) -> str:
    if not value:
        return ''
    s = str(value).strip()
    if len(s) > BUSCA_MAX_LEN:
        s = s[:BUSCA_MAX_LEN]
    return s


def prefetch_imagens_produto_loja(qs: QuerySet[Produto]) -> QuerySet[Produto]:
    """Evita N+1 ao exibir imagens do e-commerce (modelo ProdutoImagem)."""
    return qs.prefetch_related(
        Prefetch(
            'imagens_ecommerce',
            queryset=ProdutoImagem.objects.filter(ativo=True).order_by('id'),
        )
    )


def aplicar_busca_produtos(qs: QuerySet[Produto], termo: str) -> QuerySet[Produto]:
    """Filtra por texto em campos comuns do produto Sankhya."""
    termo = normalizar_busca(termo)
    if not termo:
        return qs
    filtro = (
        Q(nome__icontains=termo)
        | Q(complemento__icontains=termo)
        | Q(referencia__icontains=termo)
        | Q(referencia_fornecedor__icontains=termo)
        | Q(nome_grupo_produto__icontains=termo)
        | Q(caracteristicas__icontains=termo)
        | Q(ncm__icontains=termo)
        | Q(marca__icontains=termo)
    )
    if termo.isdigit():
        try:
            filtro |= Q(codigo_produto=int(termo))
        except (TypeError, ValueError):
            pass
    return qs.filter(filtro)


def get_cliente_codtab(user) -> int | None:
    request = user if hasattr(user, 'user') else None
    cliente = get_cliente_context(request) if request is not None else None
    if cliente is None:
        if not getattr(user, 'is_authenticated', False):
            return None
        vinculo = getattr(user, 'vinculo_cliente_sankhya', None)
        cliente = getattr(vinculo, 'cliente', None)
    if cliente is None:
        return None
    codtab = normalizar_codtab(getattr(cliente, 'codtab', None))
    if codtab is None:
        return None
    return codtab


def get_cliente_context(request):
    """Cliente ativo do e-commerce para a requisição atual.

    - Perfil cliente: cliente vinculado ao usuário.
    - Perfil comercial/gerente/admin: cliente escolhido em sessão (qualquer cliente cadastrado).
    """
    if request is None or not getattr(request, 'user', None):
        return None
    user = request.user
    if not user.is_authenticated:
        return None

    perfil = getattr(getattr(user, 'perfil_usuario', None), 'perfil', None)
    if perfil == PerfilUsuario.Perfil.CLIENTE:
        vinculo = (
            UsuarioClienteSankhya.objects.select_related('cliente')
            .filter(user=user)
            .first()
        )
        return vinculo.cliente if vinculo and vinculo.cliente else None

    if perfil not in PERFIS_PAINEL_BI_LOJA:
        return None

    raw_cliente_id = request.session.get('ecommerce_cliente_context_id')
    try:
        cliente_id = int(raw_cliente_id)
    except (TypeError, ValueError):
        return None

    return Cliente.objects.filter(id=cliente_id).first()


def map_precos_por_codtab(codigos_produto: list[int], codtab: int | None) -> dict[int, Decimal]:
    if not codtab or not codigos_produto:
        return {}
    precos = (
        Preco.objects.filter(
            codigo_tabela=codtab,
            codigo_produto__in=codigos_produto,
            valor__gt=0,
        )
        .order_by('codigo_produto', 'codigo_local_estoque')
        .values('codigo_produto', 'valor')
    )
    out: dict[int, Decimal] = {}
    for row in precos:
        codigo = int(row['codigo_produto'])
        # Mantém o primeiro preço por produto (menor local_estoque).
        if codigo not in out:
            out[codigo] = row['valor']
    return out


def produto_tem_preco_na_tabela(codigo_produto: int, codtab: int | None) -> bool:
    if not codtab:
        return False
    return map_precos_por_codtab([codigo_produto], codtab).get(codigo_produto) is not None
