"""Carrinho em sessão (lista de itens até existir modelo de pedido)."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SESSION_KEY = 'ecommerce_cart'

MIN_QTY = Decimal('0.001')
MAX_QTY = Decimal('99999')
QTY_STEP = Decimal('0.0001')


def parse_quantity(value):
    """
    Converte texto do usuário (vírgula ou ponto) em float seguro para JSON na sessão.
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
    if d < MIN_QTY or d > MAX_QTY:
        return None
    q = d.quantize(QTY_STEP, rounding=ROUND_HALF_UP)
    if q < MIN_QTY:
        return None
    return float(q)


def format_qty_display(q) -> str:
    """Texto legível (pt-BR: vírgula decimal), sem zeros à direita desnecessários."""
    try:
        d = Decimal(str(q)).quantize(QTY_STEP, rounding=ROUND_HALF_UP).normalize()
        s = format(d, 'f')
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        return (s or '0').replace('.', ',')
    except (InvalidOperation, ValueError, TypeError):
        return str(q).replace('.', ',')


def _qty_decimal(item_qty) -> Decimal:
    try:
        return Decimal(str(item_qty or 0)).quantize(QTY_STEP, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


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
    """Soma das quantidades (pode ser decimal, ex.: kg)."""
    total = Decimal('0')
    for item in get_cart(request):
        total += _qty_decimal(item.get('qty'))
    total = total.quantize(QTY_STEP, rounding=ROUND_HALF_UP)
    if total > MAX_QTY:
        total = MAX_QTY
    return float(total)


def add_product(request, codigo_produto, nome, qty: float):
    """
    qty: float já validado pela view (parse_quantity).
    """
    cart = get_cart(request)
    q = Decimal(str(qty)).quantize(QTY_STEP, rounding=ROUND_HALF_UP)
    if q < MIN_QTY:
        q = MIN_QTY
    if q > MAX_QTY:
        q = MAX_QTY
    codigo_produto = int(codigo_produto)
    q_float = float(q)
    for item in cart:
        if int(item.get('codigo_produto')) == codigo_produto:
            new_total = (_qty_decimal(item.get('qty')) + q).quantize(QTY_STEP, rounding=ROUND_HALF_UP)
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


def clear_cart(request):
    request.session[SESSION_KEY] = []
    request.session.modified = True
