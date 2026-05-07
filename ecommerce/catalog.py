"""
Catálogo a partir das tabelas Sankhya: sankhya_produto e sankhya_grupo_produto.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Prefetch, Q, QuerySet

from api_sankhya.models import Cliente, GrupoProduto, Preco, Produto
from controleBI.models import PERFIS_PAINEL_BI_LOJA, PerfilUsuario, UsuarioClienteSankhya
from ecommerce.models import ProdutoImagem

PAGE_SIZE = 24
BUSCA_MAX_LEN = 120


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


def produtos_queryset(
    codigo_grupo: int | None,
    by_id: dict,
    by_pai: dict,
    codigos_grupo_permitidos: set[int],
) -> QuerySet[Produto]:
    """Somente produtos ativos cujo `codigo_grupo_produto` está nas categorias da loja."""
    qs = Produto.objects.filter(ativo=True).order_by('nome', 'codigo_produto')
    if not codigos_grupo_permitidos:
        return qs.none()
    qs = qs.filter(codigo_grupo_produto__in=codigos_grupo_permitidos)
    if codigo_grupo is None:
        return qs
    if codigo_grupo not in by_id:
        return qs.none()
    codigos = codigos_grupo_e_descendentes(codigo_grupo, by_pai)
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
    codtab = getattr(cliente, 'codtab', None)
    if codtab in (None, 0):
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
        Preco.objects.filter(codigo_tabela=codtab, codigo_produto__in=codigos_produto)
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
