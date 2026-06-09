from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='ecommerce_home'),
    path('carrinho/', views.cart_view, name='ecommerce_cart'),
    path('carrinho/adicionar/', views.add_to_cart, name='ecommerce_add_cart'),
    path('carrinho/ajustar-quantidade/', views.adjust_cart_quantity, name='ecommerce_adjust_cart_qty'),
    path('carrinho/remover/', views.remove_from_cart, name='ecommerce_remove_cart'),
    path('carrinho/limpar/', views.clear_cart_view, name='ecommerce_clear_cart'),
    path('carrinho/analise/', views.checkout_analise_preview, name='ecommerce_checkout_analise'),
    path(
        'carrinho/analise/adicionar/',
        views.checkout_analise_adicionar,
        name='ecommerce_checkout_analise_adicionar',
    ),
    path('carrinho/finalizar/', views.checkout_finalizar, name='ecommerce_checkout_finalizar'),
    path('pedidos/', views.pedidos_list, name='ecommerce_pedidos'),
    path('pedidos/<int:pk>/', views.pedido_detail, name='ecommerce_pedido_detail'),
    path(
        'pedidos/<int:pk>/reenviar-carrinho/',
        views.pedido_reenviar_carrinho,
        name='ecommerce_pedido_reenviar_carrinho',
    ),
    path('notificacoes/', views.notificacoes_list, name='ecommerce_notificacoes'),
    path(
        'notificacoes/<int:pk>/lida/',
        views.notificacao_marcar_lida,
        name='ecommerce_notificacao_lida',
    ),
    path(
        'notificacoes/marcar-todas-lidas/',
        views.notificacoes_marcar_todas_lidas,
        name='ecommerce_notificacoes_lidas',
    ),
    path('htmx/destaque/', views.partial_destaque, name='ecommerce_htmx_destaque'),
]
