from django.urls import path
from .views import (
    IndexView, DashboardView,
    ListFuncionarioView, CadastrarFuncionarioView, FuncionarioEditView, FuncionarioDeleteView,
    ListVeiculoView, CadastrarVeiculoView, VeiculoDetailView, VeiculoEditView, VeiculoDeleteView,
    ListPedidoView, CadastrarPedidoView, ViewPedidoView, DeletePedidoView,
    RelatorioPedidoView, sync_pedido, sync_pedido_batch, edit_pedido,
    ListPracaView, CadastrarPracaView, PracaEditView, PracaDeleteView, GerenciarEnderecosPracaView,
    ListClienteSankhyaGestaoView, GestaoUsuariosClienteSankhyaView,
    GestaoCategoriasEcommerceView,
    GestaoCampanhasEcommerceView,
    CampanhaEcommerceFormView,
    GestaoRotasEcommerceView,
    GestaoNotificacoesEcommerceView,
    EcommerceClientesSelectorView,
    EcommerceSelecionarClienteView,
    gestao_notificacao_aprovar,
    gestao_notificacao_rejeitar,
    notificacoes_pendentes_count_api,
    RotasDiaListView,
    MapaRotasSemanaView,
    MapaRotasDiaPdfView,
    MapaRotasSemanaPdfView,
    RotaPadraoFormView,
    RotaDiaBuilderView,
)
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('',  DashboardView.as_view(), name='index'),
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
    
    # Praças
    path('pracas/', ListPracaView.as_view(), name='list_praca'),
    path('pracas/add/', CadastrarPracaView.as_view(), name='add_praca'),
    path('pracas/<int:pk>/edit/', PracaEditView.as_view(), name='praca_edit'),
    path('pracas/<int:pk>/delete/', PracaDeleteView.as_view(), name='praca_delete'),
    path('pracas/<int:pk>/enderecos/', GerenciarEnderecosPracaView.as_view(), name='gerenciar_enderecos_praca'),

    # Clientes Sankhya — gestão de usuários (tabela sankhya_cliente)
    path('clientes-sankhya/', ListClienteSankhyaGestaoView.as_view(), name='gestao_clientes_sankhya'),
    path(
        'clientes-sankhya/<int:pk>/usuarios/',
        GestaoUsuariosClienteSankhyaView.as_view(),
        name='gestao_usuarios_cliente_sankhya',
    ),
    path(
        'categorias-ecommerce/',
        GestaoCategoriasEcommerceView.as_view(),
        name='gestao_categorias_ecommerce',
    ),
    path(
        'campanhas-ecommerce/',
        GestaoCampanhasEcommerceView.as_view(),
        name='gestao_campanhas_ecommerce',
    ),
    path(
        'campanhas-ecommerce/nova/',
        CampanhaEcommerceFormView.as_view(),
        name='gestao_campanha_nova',
    ),
    path(
        'campanhas-ecommerce/<int:pk>/editar/',
        CampanhaEcommerceFormView.as_view(),
        name='gestao_campanha_editar',
    ),
    path(
        'rotas-ecommerce/',
        GestaoRotasEcommerceView.as_view(),
        name='gestao_rotas_ecommerce',
    ),
    path(
        'rotas-ecommerce/nova/',
        RotaPadraoFormView.as_view(),
        name='gestao_rota_padrao_nova',
    ),
    path(
        'rotas-ecommerce/<int:pk>/editar/',
        RotaPadraoFormView.as_view(),
        name='gestao_rota_padrao_editar',
    ),
    path(
        'rotas-ecommerce/rota-dia/',
        RotaDiaBuilderView.as_view(),
        name='gestao_rota_dia_builder',
    ),
    path(
        'rotas-ecommerce/rotas-dia/',
        RotasDiaListView.as_view(),
        name='gestao_rotas_dia_list',
    ),
    path(
        'rotas-ecommerce/mapa-rotas/',
        MapaRotasSemanaView.as_view(),
        name='ecommerce_mapa_rotas_semana',
    ),
    path(
        'rotas-ecommerce/mapa-rotas/pdf/',
        MapaRotasDiaPdfView.as_view(),
        name='ecommerce_mapa_rotas_dia_pdf',
    ),
    path(
        'rotas-ecommerce/mapa-rotas/pdf-semana/',
        MapaRotasSemanaPdfView.as_view(),
        name='ecommerce_mapa_rotas_semana_pdf',
    ),
    path(
        'notificacoes-ecommerce/',
        GestaoNotificacoesEcommerceView.as_view(),
        name='gestao_notificacoes_ecommerce',
    ),
    path(
        'notificacoes-ecommerce/<int:pk>/aprovar/',
        gestao_notificacao_aprovar,
        name='gestao_notificacao_aprovar',
    ),
    path(
        'notificacoes-ecommerce/<int:pk>/rejeitar/',
        gestao_notificacao_rejeitar,
        name='gestao_notificacao_rejeitar',
    ),
    path(
        'notificacoes-ecommerce/pendentes-count/',
        notificacoes_pendentes_count_api,
        name='gestao_notificacoes_pendentes_count_api',
    ),
    path(
        'ecommerce/clientes-selector/',
        EcommerceClientesSelectorView.as_view(),
        name='gestao_ecommerce_clientes_selector',
    ),
    path(
        'ecommerce/selecionar-cliente/',
        EcommerceSelecionarClienteView.as_view(),
        name='gestao_ecommerce_cliente_selecionar',
    ),
    
    path('teste/', TemplateView.as_view(template_name='teste/base.html'), name='login'),
]
