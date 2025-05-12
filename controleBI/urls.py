from django.urls import path
from .views import (
    IndexView, DashboardView,
    ListFuncionarioView, CadastrarFuncionarioView, FuncionarioEditView, FuncionarioDeleteView,
    ListVeiculoView, CadastrarVeiculoView, VeiculoDetailView, VeiculoEditView, VeiculoDeleteView,
    ListPedidoView, CadastrarPedidoView, ViewPedidoView, DeletePedidoView,
    RelatorioPedidoView, sync_pedido, sync_pedido_batch, edit_pedido
)
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    
    # Funcionários
    path('funcionarios/', ListFuncionarioView.as_view(), name='list_funcionario'),
    path('funcionarios/add/', CadastrarFuncionarioView.as_view(), name='add_funcionario'),
    path('funcionarios/<int:pk>/edit/', FuncionarioEditView.as_view(), name='funcionario_edit'),
    path('funcionarios/<int:pk>/delete/', FuncionarioDeleteView.as_view(), name='funcionario_delete'),
    path('funcionario/import/', views.import_funcionarios, name='import_funcionarios'),
    
    # Veículos
    path('veiculos/', ListVeiculoView.as_view(), name='list_veiculo'),
    path('veiculos/add/', CadastrarVeiculoView.as_view(), name='add_veiculo'),
    path('veiculos/<int:pk>/', VeiculoDetailView.as_view(), name='veiculo_detail'),
    path('veiculos/<int:pk>/edit/', VeiculoEditView.as_view(), name='veiculo_edit'),
    path('veiculos/<int:pk>/delete/', VeiculoDeleteView.as_view(), name='veiculo_delete'),
    path('veiculos/import/', views.import_veiculos, name='import_veiculos'),
    
    # Pedidos
    path('pedidos/', ListPedidoView.as_view(), name='list_pedido'),
    path('pedidos/add/', CadastrarPedidoView.as_view(), name='add_pedido'),
    path('pedidos/<int:pedido_id>/', ViewPedidoView.as_view(), name='view_pedido'),
    path('pedidos/<int:pedido_id>/edit/', edit_pedido, name='edit_pedido'),
    path('pedidos/<int:pedido_id>/delete/', DeletePedidoView.as_view(), name='delete_pedido'),
    path('pedidos/relatorio/', RelatorioPedidoView.as_view(), name='relatorio_pedido'),
    path('pedidos/<int:pedido_id>/sync/', sync_pedido, name='sync_pedido'),
    path('pedidos/sync-batch/', sync_pedido_batch, name='sync_pedido_batch'),
    path('pedidos/import/', views.import_pedidos, name='import_pedidos'),
    path('teste/', TemplateView.as_view(template_name='teste/base.html'), name='login'),
]
