"""Carrinho em sessão (lista de itens até existir modelo de pedido)."""

from decimal import Decimal, InvalidOperation

SESSION_KEY = 'ecommerce_cart'
SESSION_TIPO_LOJA_KEY = 'ecommerce_cart_tipo_loja'

MIN_QTY = 1
MAX_QTY = 99999


def parse_quantity(value):
    """
    Converte texto do usuário em quantidade inteira (unidades).
    Retorna None se inválido.
    """
    if value is None:
        return None
    s = str(value).strip().replace(',', '.')
    if not s:
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    if d != d.to_integral_value():
        return None
    n = int(d)
    if n < MIN_QTY or n > MAX_QTY:
        return None
    return float(n)


def format_qty_display(q) -> str:
    """Texto legível — sempre número inteiro."""
    try:
        n = int(Decimal(str(q)).to_integral_value())
        return str(n)
    except (InvalidOperation, ValueError, TypeError):
        return str(q).split('.')[0] or '0'


def _qty_int(item_qty) -> int:
    try:
        return int(Decimal(str(item_qty or 0)).to_integral_value())
    except (InvalidOperation, ValueError, TypeError):
        return 0


def clear_cart_tipo_loja(request):
    if SESSION_TIPO_LOJA_KEY in request.session:
        del request.session[SESSION_TIPO_LOJA_KEY]
        request.session.modified = True


def get_cart_tipo_loja(request) -> str | None:
    """Tipo Mercadoria/Revenda travado enquanto o carrinho tiver itens."""
    if not cart_line_count(request):
        clear_cart_tipo_loja(request)
        return None
    locked = request.session.get(SESSION_TIPO_LOJA_KEY)
    if isinstance(locked, str) and locked in ('mercadoria', 'revenda'):
        return locked
    return None


def lock_cart_tipo_loja(request, tipo: str) -> None:
    request.session[SESSION_TIPO_LOJA_KEY] = tipo
    request.session.modified = True


def sync_cart_tipo_after_change(request) -> None:
    if not cart_line_count(request):
        clear_cart_tipo_loja(request)


def cart_tipo_loja_bloqueado(request) -> bool:
    return cart_line_count(request) > 0


def get_cart(request):
    cart = request.session.get(SESSION_KEY)
    if not isinstance(cart, list):
        cart = []
        request.session[SESSION_KEY] = cart
    return cart


def cart_line_count(request):
    """Quantidade de produtos distintos (linhas no carrinho) — usada no badge da navbar."""
    return len(get_cart(request))


def cart_total_units(request):
    """Soma das quantidades (unidades inteiras)."""
    total = 0
    for item in get_cart(request):
        total += _qty_int(item.get('qty'))
    if total > MAX_QTY:
        total = MAX_QTY
    return float(total)


def add_product(request, codigo_produto, nome, qty: float):
    """qty: inteiro já validado pela view (parse_quantity)."""
    cart = get_cart(request)
    q = _qty_int(qty)
    if q < MIN_QTY:
        q = MIN_QTY
    if q > MAX_QTY:
        q = MAX_QTY
    codigo_produto = int(codigo_produto)
    q_float = float(q)
    for item in cart:
        if int(item.get('codigo_produto')) == codigo_produto:
            new_total = _qty_int(item.get('qty')) + q
            if new_total > MAX_QTY:
                new_total = MAX_QTY
            item['qty'] = float(new_total)
            item['nome'] = nome or item.get('nome') or ''
            request.session.modified = True
            return
    cart.append({'codigo_produto': codigo_produto, 'nome': nome or '', 'qty': q_float})
    request.session.modified = True


def remove_product(request, codigo_produto):
    cart = get_cart(request)
    codigo_produto = int(codigo_produto)
    request.session[SESSION_KEY] = [i for i in cart if int(i.get('codigo_produto')) != codigo_produto]
    request.session.modified = True
    sync_cart_tipo_after_change(request)


def adjust_product_quantity(request, codigo_produto, delta: float):
    """
    Ajusta quantidade de um item existente no carrinho (passo de 1 unidade).
    Se o resultado ficar abaixo do mínimo, remove o item.
    """
    cart = get_cart(request)
    codigo_produto = int(codigo_produto)
    d = _qty_int(delta)
    for item in cart:
        if int(item.get('codigo_produto')) != codigo_produto:
            continue
        atual = _qty_int(item.get('qty'))
        novo = atual + d
        if novo < MIN_QTY:
            remove_product(request, codigo_produto)
            return False
        if novo > MAX_QTY:
            novo = MAX_QTY
        item['qty'] = float(novo)
        request.session.modified = True
        return True
    return False


def clear_cart(request):
    request.session[SESSION_KEY] = []
    clear_cart_tipo_loja(request)
    request.session.modified = True
