from urllib.parse import urlencode
from collections import Counter, defaultdict

from django.template.loader import render_to_string
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from api_sankhya.models import Cliente as ClienteSankhya, GrupoProduto
from ecommerce import catalog as catalog_ecommerce
from ecommerce.services import filtrar_pedidos_loja_notificacoes_comercial
from .models import (
    Funcionario,
    Veiculo,
    Pedido,
    ItemPedido,
    Auditoria,
    Praca,
    EnderecoCliente,
    PERFIS_GESTAO_ROTAS,
    PERFIS_PAINEL_BI_LOJA,
    PerfilUsuario,
    UsuarioClienteSankhya,
)
from .forms import VeiculoForm, CriarUsuarioClienteSankhyaForm, AlterarSenhaUsuarioClienteForm
from .services import FuncionarioService, PedidoService
from django.db.models import Count, Prefetch, Sum, Q, Value
from django.db.models import OuterRef, Subquery
from django.db.models.functions import Coalesce, TruncMonth
from datetime import datetime, timedelta, date
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from .mixins import PerfilBIAccessMixin, PerfilGestaoRotasMixin, PerfilMapaRotasEcommerceMixin
from .decorators import requer_acesso_bi
from .perfil_utils import ensure_perfil
from django.views import View
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
import json
from django.views.generic import ListView, UpdateView, DeleteView
from django.db import connection
from django.utils import timezone
import time
import traceback
from .services import VeiculoService, PedidoService, FuncionarioService, ClienteService
from api_sankhya.tasks import run_integracao_sankhya
from django.db import connections
from ecommerce.models import (
    NotificacaoLoja,
    PedidoLoja,
    RotaDia,
    RotaDiaAjudante,
    RotaDiaCliente,
    RotaPadrao,
    RotaPadraoAjudante,
    RotaPadraoCliente,
)


def log_exception(request, origem, error, context=None):
    """
    Helper function to log exceptions in the audit table
    """
    error_details = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'context': context or {}
    }
    
    Auditoria.objects.create(
        origem=origem,
        user=request.user,
        obs=f"EXCEÇÃO: {json.dumps(error_details, indent=2)}"
    )


def execute_db_routine(cursor, routine_name):
    """
    Executa procedure/função de forma compatível entre SQL Server e PostgreSQL.
    """
    vendor = connection.vendor
    if vendor == "postgresql":
        # Preferir CALL para procedures.
        try:
            cursor.execute(f"CALL {routine_name}()")
            return
        except Exception:
            # Fallback para ambientes onde a rotina foi criada como function.
            cursor.execute(f"SELECT {routine_name}()")
            return
    # SQL Server
    cursor.execute(f"EXEC {routine_name}")

class IndexView(PerfilBIAccessMixin, View):
    def get(self, request):
        if request.user.is_authenticated:
            # Contagem de funcionários por tipo
            total_motoristas = Funcionario.objects.filter(tipo='Motorista').count()
            total_ajudantes = Funcionario.objects.filter(tipo='Ajudante').count()
            
            # Contagem de veículos
            total_veiculos = Veiculo.objects.count()
            veiculos_ativos = Veiculo.objects.filter(status_inicial='Ativo').count()
            veiculos_inativos = Veiculo.objects.filter(status_inicial='Inativo').count()
            
            # Contagem de pedidos
            total_pedidos = Pedido.objects.count()
            pedidos_aprovados = Pedido.objects.filter(status='1').count()
            pedidos_faturados = Pedido.objects.filter(status='4').count()
            pedidos_cancelados = Pedido.objects.filter(status='9').count()
            
            # Últimos pedidos
            ultimos_pedidos = Pedido.objects.order_by('-data_pedido')[:10]
            
            # Pedidos mensais (últimos 6 meses)
            data_inicio = datetime.now() - timedelta(days=180)
            pedidos_mensais = Pedido.objects.filter(
                data_pedido__gte=data_inicio
            ).annotate(
                mes=TruncMonth('data_pedido')
            ).values('mes').annotate(
                total=Count('id')
            ).order_by('mes')
            
            # Preparar dados para o gráfico
            meses = []
            valores = []
            for item in pedidos_mensais:
                meses.append(item['mes'].strftime('%b/%Y'))
                valores.append(item['total'])
            
            # Dados para o gráfico de status
            status_data = Pedido.objects.values('status').annotate(
                total=Count('id')
            ).order_by('status')
            
            status_labels = []
            status_values = []
            for item in status_data:
                status_labels.append(item['status'])
                status_values.append(item['total'])
            
            context = {
                'total_motoristas': total_motoristas,
                'total_ajudantes': total_ajudantes,
                'total_veiculos': total_veiculos,
                'veiculos_ativos': veiculos_ativos,
                'veiculos_inativos': veiculos_inativos,
                'total_pedidos': total_pedidos,
                'pedidos_aprovados': pedidos_aprovados,
                'pedidos_faturados': pedidos_faturados,
                'pedidos_cancelados': pedidos_cancelados,
                'ultimos_pedidos': ultimos_pedidos,
                'meses': json.dumps(meses),
                'pedidos_mensais': json.dumps(valores),
                'status_labels': json.dumps(status_labels),
                'status_values': json.dumps(status_values),
            }
            
            return render(request, 'home_globo.html', context)
        return render(request, 'index.html')

class DashboardView(PerfilBIAccessMixin, View):
    def get(self, request):
        # Contagem de funcionários por tipo
        total_motoristas = Funcionario.objects.filter(tipo='Motorista').count()
        total_ajudantes = Funcionario.objects.filter(tipo='Ajudante').count()
        
        # Contagem de veículos
        total_veiculos = Veiculo.objects.count()
        veiculos_ativos = Veiculo.objects.filter(status_inicial='Ativo').count()
        veiculos_inativos = Veiculo.objects.filter(status_inicial='Inativo').count()
        
        # Contagem de pedidos
        total_pedidos = Pedido.objects.count()
        pedidos_aprovados = Pedido.objects.filter(status='1').count()
        pedidos_faturados = Pedido.objects.filter(status='4').count()
        pedidos_cancelados = Pedido.objects.filter(status='9').count()
        pedidos_enviados = Pedido.objects.filter(sincronizado=True).count()
        
        # Últimos pedidos
        ultimos_pedidos = Pedido.objects.order_by('-data_pedido')[:10]
        
        # Pedidos mensais (últimos 6 meses)
        data_inicio = datetime.now() - timedelta(days=180)
        pedidos_mensais = Pedido.objects.filter(
            data_pedido__gte=data_inicio
        ).annotate(
            mes=TruncMonth('data_pedido')
        ).values('mes').annotate(
            total=Count('id')
        ).order_by('mes')
        
        # Preparar dados para o gráfico
        meses = []
        valores = []
        for item in pedidos_mensais:
            meses.append(item['mes'].strftime('%b/%Y'))
            valores.append(item['total'])
        
        context = {
            'total_motoristas': total_motoristas,
            'total_ajudantes': total_ajudantes,
            'total_veiculos': total_veiculos,
            'veiculos_ativos': veiculos_ativos,
            'veiculos_inativos': veiculos_inativos,
            'total_pedidos': total_pedidos,
            'pedidos_aprovados': pedidos_aprovados,
            'pedidos_faturados': pedidos_faturados,
            'pedidos_cancelados': pedidos_cancelados,
            'pedidos_enviados': pedidos_enviados,
            'ultimos_pedidos': ultimos_pedidos,
            'meses': meses,
            'pedidos_mensais': valores,
        }
        
        return render(request, 'dashboard.html', context)

class ListFuncionarioView(PerfilBIAccessMixin, ListView):
    model = Funcionario
    template_name = 'funcionario/listFuncionario.html'
    context_object_name = 'funcionarios'
    paginate_by = 10

    def get_queryset(self):
        queryset = Funcionario.objects.all()
        
        # Filtros
        search = self.request.GET.get('search')
        tipo = self.request.GET.get('tipo')
        status = self.request.GET.get('status')
        
        if search:
            queryset = queryset.filter(
                Q(nome__icontains=search) |
                Q(cpf__icontains=search) |
                Q(codigo_erp__icontains=search)
            )
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        if status:
            queryset = queryset.filter(status=status)
            
        return queryset.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        
        # Adicionar contagens ao contexto
        context['total_registros'] = Funcionario.objects.count()
        context['registros_filtrados'] = queryset.count()
        
        # Adicionar parâmetros de filtro ao contexto
        context['current_search'] = self.request.GET.get('search', '')
        context['current_tipo'] = self.request.GET.get('tipo', '')
        context['current_status'] = self.request.GET.get('status', '')
        
        # Adicionar informações de paginação
        page_obj = context.get('page_obj')
        if page_obj:
            context['funcionarios'] = page_obj
            context['is_paginated'] = page_obj.has_other_pages()
            context['page_obj'] = page_obj
            context['paginator'] = page_obj.paginator
        
        return context

class CadastrarFuncionarioView(PerfilBIAccessMixin, View):
    def get(self, request):
        return render(request, 'funcionario/addFuncionario.html')
        
    def post(self, request):
        try:
            # Criar novo funcionário
            funcionario = Funcionario()
            funcionario.nome = request.POST.get('nome')
            funcionario.cpf = request.POST.get('cpf')
            funcionario.codigo_erp = request.POST.get('codigo_erp')
            funcionario.tipo = request.POST.get('tipo')
            funcionario.status = request.POST.get('status')
            
            # Validações básicas
            if not all([funcionario.nome, funcionario.cpf, funcionario.codigo_erp, funcionario.tipo, funcionario.status]):
                messages.error(request, 'Todos os campos são obrigatórios.')
                return render(request, 'funcionario/addFuncionario.html')
            
            funcionario.save()
            messages.success(request, 'Funcionário cadastrado com sucesso!')
            return redirect('list_funcionario')
            
        except Exception as e:
            messages.error(request, f'Erro ao cadastrar funcionário: {str(e)}')
            return render(request, 'funcionario/addFuncionario.html')

class ListVeiculoView(PerfilBIAccessMixin, ListView):
    model = Veiculo
    template_name = 'veiculo/listVeiculo.html'
    context_object_name = 'veiculos'
    paginate_by = 10

    def get_queryset(self):
        queryset = Veiculo.objects.all()
        
        # Filtros
        search = self.request.GET.get('search')
        tipo_veiculo = self.request.GET.get('tipo_veiculo')
        status = self.request.GET.get('status')
        
        if search:
            queryset = queryset.filter(
                Q(placa__icontains=search) |
                Q(modelo__icontains=search) |
                Q(descricao__icontains=search)
            )
        
        if tipo_veiculo:
            queryset = queryset.filter(tipo_veiculo=tipo_veiculo)
        
        if status:
            queryset = queryset.filter(status_inicial=status)
        
        return queryset.order_by('placa')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        
        # Adicionar contagens ao contexto
        context['total_registros'] = Veiculo.objects.count()
        context['registros_filtrados'] = queryset.count()
        
        # Adicionar parâmetros de filtro ao contexto
        context['current_search'] = self.request.GET.get('search', '')
        context['current_tipo_veiculo'] = self.request.GET.get('tipo_veiculo', '')
        context['current_status'] = self.request.GET.get('status', '')
        
        # Adicionar informações de paginação
        page_obj = context.get('page_obj')
        if page_obj:
            context['veiculos'] = page_obj
            context['is_paginated'] = page_obj.has_other_pages()
            context['page_obj'] = page_obj
            context['paginator'] = page_obj.paginator
        
        return context

class CadastrarVeiculoView(PerfilBIAccessMixin, View):
    def get(self, request):
        return render(request, 'veiculo/addVeiculo.html')
    
    def post(self, request):
        try:
            # Criar novo veículo
            veiculo = Veiculo()
            
            # Atualiza os campos do veículo
            veiculo.placa = request.POST.get('placa', '').strip()
            veiculo.codigo_erp = request.POST.get('codigo_erp', '').strip()
            veiculo.descricao = request.POST.get('descricao', '').strip()
            veiculo.filial = request.POST.get('filial', '').strip()
            veiculo.modelo = request.POST.get('modelo')
            veiculo.tipo_veiculo = request.POST.get('tipo_veiculo')
            veiculo.ano_modelo = request.POST.get('ano_modelo')
            veiculo.ano_fabricacao = request.POST.get('ano_fabricacao')
            veiculo.tipo_combustivel = request.POST.get('tipo_combustivel')
            veiculo.qtd_max_entregas = request.POST.get('qtd_max_entregas')
            veiculo.peso_max_entregas = request.POST.get('peso_max_entregas', 0)
            veiculo.volume_max_entregas = request.POST.get('volume_max_entregas', 0)
            veiculo.qtd_pallets_veiculo = request.POST.get('qtd_pallets_veiculo', 0)
            veiculo.status_inicial = request.POST.get('status_inicial')
            veiculo.km_atual = request.POST.get('km_atual', 0)
            veiculo.velocidade_maxima = request.POST.get('velocidade_maxima')

    
            # Validação básica
            if not veiculo.placa:
                raise ValueError("A placa é obrigatória")
            if not veiculo.codigo_erp:
                raise ValueError("O código ERP é obrigatório")
            if not veiculo.descricao:
                raise ValueError("A descrição é obrigatória")
            if not veiculo.filial:
                raise ValueError("A filial é obrigatória")
            if not veiculo.status_inicial:
                raise ValueError("O status é obrigatório")

            # Converter valores numéricos
            try:
                if veiculo.ano_modelo:
                    veiculo.ano_modelo = int(veiculo.ano_modelo)
                if veiculo.ano_fabricacao:
                    veiculo.ano_fabricacao = int(veiculo.ano_fabricacao)
                if veiculo.qtd_max_entregas:
                    veiculo.qtd_max_entregas = int(veiculo.qtd_max_entregas)
                if veiculo.peso_max_entregas:
                    veiculo.peso_max_entregas = float(veiculo.peso_max_entregas)
                if veiculo.volume_max_entregas:
                    veiculo.volume_max_entregas = float(veiculo.volume_max_entregas)
                if veiculo.qtd_pallets_veiculo:
                    veiculo.qtd_pallets_veiculo = int(veiculo.qtd_pallets_veiculo)
                if veiculo.km_atual:
                    veiculo.km_atual = float(veiculo.km_atual)
                if veiculo.velocidade_maxima:
                    veiculo.velocidade_maxima = int(veiculo.velocidade_maxima)
            except ValueError as e:
                raise ValueError(f"Erro na conversão de valores numéricos: {str(e)}")

            veiculo.save()
            
            messages.success(request, 'Veículo cadastrado com sucesso!')
            return redirect('veiculo_detail', pk=veiculo.pk)
            
        except ValueError as e:
            print("Erro de validação:", str(e))
            messages.error(request, str(e))
            return render(request, 'veiculo/addVeiculo.html')
        except Exception as e:
            print("Erro inesperado:", str(e))
            messages.error(request, f'Erro ao cadastrar veículo: {str(e)}')
            return render(request, 'veiculo/addVeiculo.html')

class CadastrarPedidoView(PerfilBIAccessMixin, View):
    template_name = 'pedido/addPedido.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        # Processar dados do formulário
        pedido_data = {
            'nf': request.POST.get('nf'),
            'chave_nfe': request.POST.get('chave_nfe'),
            'serie': request.POST.get('serie'),
            'tipo': request.POST.get('tipo'),
            'ent_ou_serv': request.POST.get('ent_ou_serv'),
            'pedido_erp': request.POST.get('pedido_erp'),
            'forma_pgto': request.POST.get('forma_pgto'),
            'status': request.POST.get('status'),
            'obs': request.POST.get('obs'),
            'referencia_entrega': request.POST.get('referencia_entrega'),
            'descr_cliente': request.POST.get('descr_cliente'),
            'razao_cliente': request.POST.get('razao_cliente'),
            'cnpj_cliente': request.POST.get('cnpj_cliente'),
            'end_cliente': request.POST.get('end_cliente'),
            'num_end_cliente': request.POST.get('num_end_cliente'),
            'bairro_cliente': request.POST.get('bairro_cliente'),
            'cidade_cliente': request.POST.get('cidade_cliente'),
            'uf_cliente': request.POST.get('uf_cliente'),
            'cep_cliente': request.POST.get('cep_cliente'),
            'tel1_cliente': request.POST.get('tel1_cliente'),
            'tipo_nota_fiscal': request.POST.get('tipo_nota_fiscal'),
        }
        
        # Criar pedido
        pedido = Pedido.objects.create(**pedido_data)
        
        # Processar itens do pedido
        itens = request.POST.getlist('itens[]')
        for item in itens:
            ItemPedido.objects.create(
                pedido=pedido,
                cod_produto_erp=item.get('cod_produto_erp'),
                descricao=item.get('descricao'),
                unidade=item.get('unidade'),
                qtd=item.get('qtd'),
                preco=item.get('preco'),
                ncm=item.get('ncm'),
                cst=item.get('cst'),
                obs_item=item.get('obs_item')
            )
        
        return redirect('list_pedido')

class ListPedidoView(PerfilBIAccessMixin, View):
    def get(self, request):
        # Inicializar queryset
        pedidos = Pedido.objects.all()
        
        # Aplicar filtros
        search = request.GET.get('search')
        status = request.GET.get('status')
        tipo = request.GET.get('tipo')
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        sincronizado = request.GET.get('sincronizado')
        
        if search:
            pedidos = pedidos.filter(
                Q(pedido_erp__icontains=search) |
                Q(descr_cliente__icontains=search) |
                Q(cnpj_cliente__icontains=search)
            )
        
        if status:
            pedidos = pedidos.filter(status=status)
        
        if tipo:
            pedidos = pedidos.filter(ent_ou_serv=tipo)
        
        if data_inicio:
            pedidos = pedidos.filter(data_pedido__gte=data_inicio)
        
        if data_fim:
            pedidos = pedidos.filter(data_pedido__lte=data_fim)

        if sincronizado:
            pedidos = pedidos.filter(sincronizado=sincronizado == 'True')
        
        # Ordenar por data mais recente e ID para garantir ordem consistente
        pedidos = pedidos.order_by('-data_pedido', '-id')
        
        # Paginação - obter itens por página da query string ou usar padrão
        try:
            items_per_page = int(request.GET.get('per_page', 10))
            # Limitar valores válidos para evitar sobrecarga
            if items_per_page not in [5, 10, 25, 50, 100]:
                items_per_page = 10
        except ValueError:
            items_per_page = 10
        
        paginator = Paginator(pedidos, items_per_page)
        
        try:
            page = int(request.GET.get('page', '1'))
            if page < 1:
                page = 1
        except ValueError:
            page = 1
        
        try:
            pedidos_paginados = paginator.page(page)
        except PageNotAnInteger:
            pedidos_paginados = paginator.page(1)
        except EmptyPage:
            # Se a página estiver fora do intervalo, mostrar última página
            pedidos_paginados = paginator.page(paginator.num_pages)
        
        # Calcular intervalo de páginas para exibição
        current_page = pedidos_paginados.number
        total_pages = paginator.num_pages
        
        # Mostrar 5 páginas antes e depois da página atual
        page_range = range(
            max(1, current_page - 5),
            min(total_pages + 1, current_page + 6)
        )
        
        # Adicionar primeira e última página se necessário
        show_first = 1 not in page_range
        show_last = total_pages not in page_range
        
        context = {
            'pedidos': pedidos_paginados,
            'total_registros': Pedido.objects.count(),
            'registros_filtrados': pedidos.count(),
            'current_search': search,
            'current_status': status,
            'current_tipo': tipo,
            'current_data_inicio': data_inicio,
            'current_data_fim': data_fim,
            'current_sincronizado': sincronizado,
            'page_range': page_range,
            'show_first': show_first,
            'show_last': show_last,
            'total_pages': total_pages,
            'current_page': current_page,
            'items_per_page': items_per_page
        }
        
        return render(request, 'pedido/listPedido.html', context)

class ViewPedidoView(PerfilBIAccessMixin, View):
    def get(self, request, pedido_id):
        pedido = Pedido.objects.get(id=pedido_id)
        itens = ItemPedido.objects.filter(pedido=pedido)
        
        # Preservar os parâmetros de filtro
        filter_params = {
            'search': request.GET.get('search', ''),
            'status': request.GET.get('status', ''),
            'tipo': request.GET.get('tipo', ''),
            'data_inicio': request.GET.get('data_inicio', ''),
            'data_fim': request.GET.get('data_fim', ''),
            'sincronizado': request.GET.get('sincronizado', ''),
            'page': request.GET.get('page', '1')
        }
        
        context = {
            'pedido': pedido,
            'itens': itens,
            'filter_params': filter_params
        }
        
        return render(request, 'pedido/viewPedido.html', context)

@login_required
@requer_acesso_bi
def edit_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    itens = ItemPedido.objects.filter(pedido=pedido)

    if request.method == 'POST':
        try:
            # Atualizar o pedido
            pedido.podeformarcarga = request.POST.get('podeformarcarga')
            pedido.sincronizado = False  # Marca como não sincronizado para ser enviado novamente
            pedido.save()

            messages.success(request, 'Pedido atualizado com sucesso!')
            
            # Preservar os parâmetros de filtro
            filter_params = {
                'search': request.GET.get('search', ''),
                'status': request.GET.get('status', ''),
                'tipo': request.GET.get('tipo', ''),
                'data_inicio': request.GET.get('data_inicio', ''),
                'data_fim': request.GET.get('data_fim', ''),
                'sincronizado': request.GET.get('sincronizado', ''),
                'page': request.GET.get('page', '1')
            }
            
            # Construir a URL com os parâmetros de filtro
            url = reverse('list_pedido')
            query_string = '&'.join(f'{k}={v}' for k, v in filter_params.items() if v)
            if query_string:
                url = f'{url}?{query_string}'
                
            return redirect(url)
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar pedido: {str(e)}')
            return redirect('edit_pedido', pedido_id=pedido_id)

    return render(request, 'pedido/addPedido.html', {'pedido': pedido, 'itens': itens})

class DeletePedidoView(PerfilBIAccessMixin, View):
    def post(self, request, pedido_id):
        try:
            pedido = Pedido.objects.get(id=pedido_id)
            
            # Registrar na auditoria antes de deletar
            Auditoria.objects.create(
                origem="Pedido",
                user=request.user,
                obs=f"Pedido {pedido.pedido_erp} - {pedido.descr_cliente} excluído"
            )
            
            # Deletar o pedido
            pedido.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Pedido excluído com sucesso!'
            })
            
        except Pedido.DoesNotExist:
            log_exception(
                request=request,
                origem="Exclusão de Pedido",
                error=Exception("Pedido não encontrado"),
                context={'pedido_id': pedido_id}
            )
            return JsonResponse({
                'success': False,
                'message': 'Pedido não encontrado'
            }, status=404)
        except Exception as e:
            log_exception(
                request=request,
                origem="Exclusão de Pedido",
                error=e,
                context={'pedido_id': pedido_id}
            )
            return JsonResponse({
                'success': False,
                'message': f'Erro ao excluir pedido: {str(e)}'
            }, status=500)

@login_required
@requer_acesso_bi
def add_pedido(request):
    if request.method == 'POST':
        try:
            # Criar o pedido
            pedido = Pedido.objects.create(
                pedido_erp=request.POST.get('pedido_erp'),
                tipo=request.POST.get('tipo'),
                ent_ou_serv=request.POST.get('ent_ou_serv'),
                status=request.POST.get('status'),
                descr_cliente=request.POST.get('descr_cliente'),
                cnpj_cliente=request.POST.get('cnpj_cliente'),
                end_cliente=request.POST.get('end_cliente'),
                num_end_cliente=request.POST.get('num_end_cliente'),
                bairro_cliente=request.POST.get('bairro_cliente'),
                cidade_cliente=request.POST.get('cidade_cliente'),
                uf_cliente=request.POST.get('uf_cliente'),
                cep_cliente=request.POST.get('cep_cliente'),
                tel1_cliente=request.POST.get('tel1_cliente'),
                obs=request.POST.get('obs')
            )

            # Processar os itens do pedido
            codigos = request.POST.getlist('cod_produto_erp[]')
            descricoes = request.POST.getlist('descricao[]')
            unidades = request.POST.getlist('unidade[]')
            quantidades = request.POST.getlist('qtd[]')
            precos = request.POST.getlist('preco[]')

            for i in range(len(codigos)):
                if codigos[i] and descricoes[i] and unidades[i] and quantidades[i] and precos[i]:
                    ItemPedido.objects.create(
                        pedido=pedido,
                        cod_produto_erp=codigos[i],
                        descricao=descricoes[i],
                        unidade=unidades[i],
                        qtd=quantidades[i],
                        preco=precos[i]
                    )

            messages.success(request, 'Pedido criado com sucesso!')
            return redirect('list_pedido')
        except Exception as e:
            messages.error(request, f'Erro ao criar pedido: {str(e)}')
            return redirect('add_pedido')
    
    return render(request, 'pedido/addPedido.html')

@login_required
@requer_acesso_bi
@require_POST
def sync_pedido(request, pk):
    try:
        pedido = Pedido.objects.get(pk=pk)
        
        # Aqui você pode adicionar a lógica de sincronização com o ERP
        # Por exemplo, chamar um serviço que envia os dados para o ERP
        
        # Atualizar o status de sincronização
        pedido.sincronizado = True
        pedido.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Pedido sincronizado com sucesso'
        })
    except Pedido.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Pedido não encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
@requer_acesso_bi
def sync_pedido_batch(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            pedido_ids = data.get('pedido_ids', [])
            
            if not pedido_ids:
                return JsonResponse({'success': False, 'message': 'Nenhum pedido selecionado'})
            
            # Permite reenvio: buscar todos os pedidos selecionados,
            # independentemente do status de sincronização.
            pedidos = Pedido.objects.filter(id__in=pedido_ids)
            
            if not pedidos.exists():
                return JsonResponse({'success': False, 'message': 'Nenhum pedido válido para sincronização'})
            
            # Enviar pedidos usando o serviço
            success, message = PedidoService.enviar_dados(pedidos)
            
            if success:
                # Atualizar status de sincronização
                pedidos.update(sincronizado=True)
                return JsonResponse({
                    'success': True,
                    'message': f'{pedidos.count()} pedido(s) sincronizado(s) com sucesso'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Erro ao sincronizar pedidos: {message}'
                })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Dados inválidos'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Erro interno: {str(e)}'}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Método não permitido'}, status=405)

class RelatorioPedidoView(PerfilBIAccessMixin, View):
    def get(self, request):
        # Inicializar queryset
        pedidos = Pedido.objects.all()
        
        # Aplicar filtros
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        status = request.GET.get('status')
        sincronizado = request.GET.get('sincronizado')
        
        if data_inicio:
            pedidos = pedidos.filter(data_pedido__gte=data_inicio)
        
        if data_fim:
            pedidos = pedidos.filter(data_pedido__lte=data_fim)
        
        if status:
            pedidos = pedidos.filter(status=status)
        
        if sincronizado:
            pedidos = pedidos.filter(sincronizado=sincronizado == 'True')
        
        # Calcular totais
        total_pedidos = pedidos.count()
        pedidos_sincronizados = pedidos.filter(sincronizado=True).count()
        valor_total = pedidos.aggregate(total=Sum('valor'))['total'] or 0
        peso_total = pedidos.aggregate(total=Sum('peso'))['total'] or 0
        
        # Dados para o gráfico de status
        status_data = pedidos.values('status').annotate(
            total=Count('id')
        ).order_by('status')
        
        status_labels = []
        status_values = []
        for item in status_data:
            status_labels.append(item['status'])
            status_values.append(item['total'])
        
        # Dados para o gráfico mensal
        data_inicio_grafico = datetime.now() - timedelta(days=180)
        meses_data = pedidos.filter(
            data_pedido__gte=data_inicio_grafico
        ).annotate(
            mes=TruncMonth('data_pedido')
        ).values('mes').annotate(
            total=Count('id')
        ).order_by('mes')
        
        meses_labels = []
        meses_values = []
        for item in meses_data:
            meses_labels.append(item['mes'].strftime('%b/%Y'))
            meses_values.append(item['total'])
        
        context = {
            'pedidos': pedidos,
            'total_pedidos': total_pedidos,
            'pedidos_sincronizados': pedidos_sincronizados,
            'valor_total': valor_total,
            'peso_total': peso_total,
            'status_labels': json.dumps(status_labels),
            'status_values': json.dumps(status_values),
            'meses_labels': json.dumps(meses_labels),
            'meses_values': json.dumps(meses_values),
        }
        
        return render(request, 'pedido/relatorioPedido.html', context)

class VeiculoDetailView(PerfilBIAccessMixin, View):
    def get(self, request, pk):
        veiculo = get_object_or_404(Veiculo, pk=pk)
        
        context = {
            'veiculo': veiculo
        }
        
        return render(request, 'veiculo/veiculo_detail.html', context)
    
    def post(self, request, pk):
        return self.get(request, pk)

class VeiculoEditView(PerfilBIAccessMixin, View):
    def get(self, request, pk):
        veiculo = get_object_or_404(Veiculo, pk=pk)
        return render(request, 'veiculo/veiculo_edit.html', {'veiculo': veiculo})
    
    def post(self, request, pk):
        veiculo = get_object_or_404(Veiculo, pk=pk)
        try:
            
            # Atualiza os campos do veículo
            veiculo.placa = request.POST.get('placa', '').strip()
            veiculo.codigo_erp = request.POST.get('codigo_erp', '').strip()
            veiculo.descricao = request.POST.get('descricao', '').strip()
            veiculo.filial = request.POST.get('filial', '').strip()
            veiculo.modelo = request.POST.get('modelo')
            veiculo.tipo_veiculo = request.POST.get('tipo_veiculo')
            veiculo.ano_modelo = request.POST.get('ano_modelo')
            veiculo.ano_fabricacao = request.POST.get('ano_fabricacao')
            veiculo.tipo_combustivel = request.POST.get('tipo_combustivel')
            veiculo.qtd_max_entregas = request.POST.get('qtd_max_entregas')
            veiculo.peso_max_entregas = request.POST.get('peso_max_entregas',0)
            veiculo.volume_max_entregas = request.POST.get('volume_max_entregas',0)
            veiculo.qtd_pallets_veiculo = request.POST.get('qtd_pallets_veiculo',0)
            veiculo.status_inicial = request.POST.get('status_inicial')
            veiculo.km_atual = request.POST.get('km_atual',0)
            veiculo.velocidade_maxima = request.POST.get('velocidade_maxima')

            # Validação básica
            if not veiculo.placa:
                raise ValueError("A placa é obrigatória")
            if not veiculo.codigo_erp:
                raise ValueError("O código ERP é obrigatório")
            if not veiculo.descricao:
                raise ValueError("A descrição é obrigatória")
            if not veiculo.filial:
                raise ValueError("A filial é obrigatória")
            if not veiculo.status_inicial:
                raise ValueError("O status é obrigatório")

            # Converter valores numéricos
            try:
                if veiculo.ano_modelo:
                    veiculo.ano_modelo = int(veiculo.ano_modelo)
                if veiculo.ano_fabricacao:
                    veiculo.ano_fabricacao = int(veiculo.ano_fabricacao)
                if veiculo.qtd_max_entregas:
                    veiculo.qtd_max_entregas = int(veiculo.qtd_max_entregas)
                if veiculo.peso_max_entregas:
                    veiculo.peso_max_entregas = float(veiculo.peso_max_entregas)
                if veiculo.volume_max_entregas:
                    veiculo.volume_max_entregas = float(veiculo.volume_max_entregas)
                if veiculo.qtd_pallets_veiculo:
                    veiculo.qtd_pallets_veiculo = int(veiculo.qtd_pallets_veiculo)
                if veiculo.km_atual:
                    veiculo.km_atual = float(veiculo.km_atual)
                if veiculo.velocidade_maxima:
                    veiculo.velocidade_maxima = int(veiculo.velocidade_maxima)
            except ValueError as e:
                raise ValueError(f"Erro na conversão de valores numéricos: {str(e)}")

            veiculo.save()
            
            messages.success(request, 'Veículo atualizado com sucesso!')
            return redirect('list_veiculo')
            
        except ValueError as e:
            print("Erro de validação:", str(e))
            messages.error(request, str(e))
            return render(request, 'veiculo/veiculo_edit.html', {'veiculo': veiculo})
        except Exception as e:
            print("Erro inesperado:", str(e))
            messages.error(request, f'Erro ao atualizar veículo: {str(e)}')
            return render(request, 'veiculo/veiculo_edit.html', {'veiculo': veiculo})

class VeiculoDeleteView(PerfilBIAccessMixin, View):
    def post(self, request, pk):
        try:
            veiculo = get_object_or_404(Veiculo, pk=pk)
            
            # Registrar na auditoria antes de deletar
            Auditoria.objects.create(
                origem="Veículo",
                user=request.user,
                obs=f"Veículo {veiculo.placa} - {veiculo.descricao} excluído"
            )
            
            # Deletar o veículo
            veiculo.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Veículo excluído com sucesso!'
            })
            
        except Veiculo.DoesNotExist:
            log_exception(
                request=request,
                origem="Exclusão de Veículo",
                error=Exception("Veículo não encontrado"),
                context={'veiculo_id': pk}
            )
            return JsonResponse({
                'success': False,
                'message': 'Veículo não encontrado'
            }, status=404)
        except Exception as e:
            log_exception(
                request=request,
                origem="Exclusão de Veículo",
                error=e,
                context={'veiculo_id': pk}
            )
            return JsonResponse({
                'success': False,
                'message': f'Erro ao excluir veículo: {str(e)}'
            }, status=500)

class FuncionarioEditView(PerfilBIAccessMixin, UpdateView):
    model = Funcionario
    template_name = 'funcionario/funcionario_edit.html'
    fields = ['nome', 'cpf', 'codigo_erp', 'tipo', 'status']
    success_url = reverse_lazy('list_funcionario')

    def form_valid(self, form):
        messages.success(self.request, 'Funcionário atualizado com sucesso!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Erro ao atualizar funcionário.')
        return super().form_invalid(form)

class FuncionarioDeleteView(PerfilBIAccessMixin, View):
    def post(self, request, pk):
        try:
            funcionario = get_object_or_404(Funcionario, pk=pk)
            
            # Registrar na auditoria antes de deletar
            Auditoria.objects.create(
                origem="Funcionário",
                user=request.user,
                obs=f"Funcionário {funcionario.nome} - {funcionario.cpf} excluído"
            )
            
            # Deletar o funcionário
            funcionario.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Funcionário excluído com sucesso!'
            })
            
        except Funcionario.DoesNotExist:
            log_exception(
                request=request,
                origem="Exclusão de Funcionário",
                error=Exception("Funcionário não encontrado"),
                context={'funcionario_id': pk}
            )
            return JsonResponse({
                'success': False,
                'message': 'Funcionário não encontrado'
            }, status=404)
        except Exception as e:
            log_exception(
                request=request,
                origem="Exclusão de Funcionário",
                error=e,
                context={'funcionario_id': pk}
            )
            return JsonResponse({
                'success': False,
                'message': f'Erro ao excluir funcionário: {str(e)}'
            }, status=500)

@login_required
@requer_acesso_bi
@require_POST
def import_pedidos(request):
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Registrar início da importação na auditoria
            Auditoria.objects.create(
                origem="Importação de Pedidos",
                user=request.user,
                obs=(
                    "Iniciando importação de pedidos via integração api_sankhya "
                    "(clientes -> contatos -> pedidos) + procedures "
                    "(SP_ATUALIZA_CLIENTE_SANKHYA -> SP_PEDIDOS_SANKHYA). "
                    f"Tentativa {retry_count + 1} de {max_retries}."
                )
            )

            resultado_clientes = run_integracao_sankhya("clientes")
            if resultado_clientes.get("erro"):
                raise RuntimeError(f"Erro integração clientes: {resultado_clientes.get('erro')}")

            resultado_contatos = run_integracao_sankhya("contatos")
            if resultado_contatos.get("erro"):
                raise RuntimeError(f"Erro integração contatos: {resultado_contatos.get('erro')}")

            resultado_pedidos = run_integracao_sankhya("pedidos")
            if resultado_pedidos.get("erro"):
                raise RuntimeError(f"Erro integração pedidos: {resultado_pedidos.get('erro')}")
            
            # Fechar todas as conexões existentes
            connection.close()
            
            # Criar nova conexão
            with connection.cursor() as cursor:
                # Executar procedures na ordem definida
                execute_db_routine(cursor, "SP_ATUALIZA_CLIENTE_SANKHYA")
                rowcount_clientes = cursor.rowcount
                execute_db_routine(cursor, "SP_PEDIDOS_SANKHYA")
                
                # Obter o número de registros afetados
                rowcount_pedidos = cursor.rowcount
                
                # Fechar a conexão explicitamente
                cursor.close()
                connection.close()
                
                # Registrar sucesso na auditoria
                Auditoria.objects.create(
                    origem="Importação de Pedidos",
                    user=request.user,
                    obs=(
                        "Importação de pedidos realizada com sucesso via "
                        "api_sankhya (clientes -> contatos -> pedidos) + procedures "
                        "(SP_ATUALIZA_CLIENTE_SANKHYA -> SP_PEDIDOS_SANKHYA). "
                        f"Clientes Sankhya processados: {resultado_clientes.get('total_processados', 0)}. "
                        f"Contatos Sankhya processados: {resultado_contatos.get('total_processados', 0)}. "
                        f"Pedidos Sankhya processados: {resultado_pedidos.get('total_processados', 0)}. "
                        f"Procedure clientes afetou {rowcount_clientes}. "
                        f"Procedure pedidos afetou {rowcount_pedidos}."
                    )
                )

                return JsonResponse({
                    'success': True,
                    'message': (
                        "Pedidos atualizados com sucesso no fluxo completo. "
                        f"Clientes Sankhya: {resultado_clientes.get('total_processados', 0)} | "
                        f"Contatos Sankhya: {resultado_contatos.get('total_processados', 0)} | "
                        f"SP_ATUALIZA_CLIENTE_SANKHYA: {rowcount_clientes} | "
                        f"Pedidos Sankhya: {resultado_pedidos.get('total_processados', 0)} | "
                        f"SP_PEDIDOS_SANKHYA: {rowcount_pedidos}."
                    )
                })
                
        except Exception as e:
            retry_count += 1
            
            # Fechar a conexão em caso de erro
            try:
                connection.close()
            except:
                pass
            
            # Registrar erro na auditoria com contexto
            log_exception(
                request=request,
                origem="Importação de Pedidos",
                error=e,
                context={
                    'retry_count': retry_count,
                    'max_retries': max_retries,
                    'operation': (
                        'api_sankhya.clientes -> api_sankhya.contatos -> SP_ATUALIZA_CLIENTE_SANKHYA -> '
                        'api_sankhya.pedidos -> SP_PEDIDOS_SANKHYA'
                    )
                }
            )
            
            if retry_count < max_retries:
                # Aguardar um tempo antes de tentar novamente (aumenta exponencialmente)
                time.sleep(2 ** retry_count)  # 2, 4, 8 segundos
                continue
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Erro ao importar pedidos após {max_retries} tentativas. Último erro: {str(e)}'
                }, status=500)

@login_required
@requer_acesso_bi
@require_POST
def import_veiculos(request):
    max_retries = 3
    retry_count = 0
    while retry_count < max_retries:
        try:
            # Registrar início da importação na auditoria
            Auditoria.objects.create(
                origem="Importação de Veículos",
                user=request.user,
                obs=(
                    "Iniciando importação de veículos via integração api_sankhya "
                    f"(veículos) + SP_ATUALIZA_VEICULO_SANKHYA. "
                    f"Tentativa {retry_count + 1} de {max_retries}."
                )
            )
            resultado_integracao = run_integracao_sankhya("veiculos")
            if resultado_integracao.get("erro"):
                raise RuntimeError(resultado_integracao.get("erro"))
            
            # Fechar todas as conexões existentes
            connection.close()
            
            # Criar nova conexão
            with connection.cursor() as cursor:
                # Executar a stored procedure
                execute_db_routine(cursor, "SP_ATUALIZA_VEICULO_SANKHYA")
                
                # Obter o número de registros afetados
                rowcount = cursor.rowcount
                
                # Fechar a conexão explicitamente
                cursor.close()
                connection.close()
                
                # Buscar veículos não sincronizados
                veiculos_nao_sincronizados = Veiculo.objects.filter(sincronizado=False)
                total_nao_sincronizados = veiculos_nao_sincronizados.count()
                
                if total_nao_sincronizados > 0:
                    try:
                        # Aqui você deve implementar a chamada ao webservice
                        # Por exemplo:
                        for veiculo in veiculos_nao_sincronizados:
                            VeiculoService.enviar_dados(veiculo)
                        
                        # Após enviar com sucesso, marcar como sincronizado
                        veiculos_nao_sincronizados.update(sincronizado=True)
                        
                        # Registrar sucesso na auditoria
                        Auditoria.objects.create(
                            origem="Importação de Veículos",
                            user=request.user,
                            obs=(
                                "Importação de veículos realizada com sucesso via "
                                "api_sankhya (veículos) + SP_ATUALIZA_VEICULO_SANKHYA. "
                                f"Processados Sankhya: {resultado_integracao.get('total_processados', 0)}. "
                                f"Procedure afetou {rowcount} veículo(s). "
                                f"{total_nao_sincronizados} veículo(s) sincronizado(s) com o webservice."
                            )
                        )
                    except Exception as ws_error:
                        # Registrar erro do webservice na auditoria
                        Auditoria.objects.create(
                            origem="Importação de Veículos",
                            user=request.user,
                            obs=f"Erro ao sincronizar veículos com o webservice: {str(ws_error)}"
                        )
                        raise
                else:
                    # Registrar sucesso na auditoria (sem veículos para sincronizar)
                    Auditoria.objects.create(
                        origem="Importação de Veículos",
                        user=request.user,
                        obs=(
                            "Importação de veículos realizada com sucesso via "
                            "api_sankhya (veículos) + SP_ATUALIZA_VEICULO_SANKHYA. "
                            f"Processados Sankhya: {resultado_integracao.get('total_processados', 0)}. "
                            f"Procedure afetou {rowcount} veículo(s). Nenhum veículo para sincronizar."
                        )
                    )
                
                return JsonResponse({
                    'success': True,
                    'message': (
                        "Veículos atualizados com sucesso via api_sankhya e procedure. "
                        f"Processados Sankhya: {resultado_integracao.get('total_processados', 0)} | "
                        f"Procedure: {rowcount} veículo(s) afetado(s) | "
                        f"Webservice: {total_nao_sincronizados} veículo(s) sincronizado(s)."
                    )
                })
                
        except Exception as e:
            retry_count += 1
            
            # Fechar a conexão em caso de erro
            try:
                connection.close()
            except:
                pass
            
            # Registrar erro na auditoria com contexto
            log_exception(
                request=request,
                origem="Importação de Veículos",
                error=e,
                context={
                    'retry_count': retry_count,
                    'max_retries': max_retries,
                    'operation': 'api_sankhya.veiculos + SP_ATUALIZA_VEICULO_SANKHYA'
                }
            )
            
            if retry_count < max_retries:
                # Aguardar um tempo antes de tentar novamente (aumenta exponencialmente)
                time.sleep(2 ** retry_count)  # 2, 4, 8 segundos
                continue
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Erro ao importar veículos após {max_retries} tentativas. Último erro: {str(e)}'
                }, status=500)

class VeiculoUpdateView(UpdateView):
    model = Veiculo
    form_class = VeiculoForm
    template_name = 'veiculo/veiculo_form.html'
    success_url = reverse_lazy('list_veiculo')

    def form_valid(self, form):
        try:
            # Get the original vehicle data before update
            original_veiculo = self.get_object()
            original_data = {
                'placa': original_veiculo.placa,
                'descricao': original_veiculo.descricao,
                'modelo': original_veiculo.modelo,
                'tipo_veiculo': original_veiculo.tipo_veiculo,
                'status_inicial': original_veiculo.status_inicial,
                'km_atual': original_veiculo.km_atual,
                'filial': original_veiculo.filial,
                'qtd_max_entregas': original_veiculo.qtd_max_entregas,
                'peso_max_entregas': original_veiculo.peso_max_entregas,
                'volume_max_entregas': original_veiculo.volume_max_entregas,
                'qtd_pallets_veiculo': original_veiculo.qtd_pallets_veiculo,
            }

            # Save the form to get the updated vehicle
            response = super().form_valid(form)
            updated_veiculo = self.object

            # Compare original and updated data to identify changes
            changes = []
            for field, old_value in original_data.items():
                new_value = getattr(updated_veiculo, field)
                if old_value != new_value:
                    changes.append(f"{field}: {old_value} -> {new_value}")

            # Create audit log entry
            Auditoria.objects.create(
                origem='Veiculo',
                user=self.request.user.username,
                detalhes=f"Veículo atualizado: {updated_veiculo.placa} - {updated_veiculo.descricao}\nAlterações: {', '.join(changes)}"
            )

            return response
        except Exception as e:
            # Log the error in audit table
            Auditoria.objects.create(
                origem='Veiculo',
                user=self.request.user.username,
                detalhes=f"Erro ao atualizar veículo: {str(e)}"
            )
            raise

@login_required
@requer_acesso_bi
def import_funcionarios(request):
    if request.method == 'POST':
        max_retries = 3
        retry_count = 0
        retry_delay = 1  # seconds

        while retry_count < max_retries:
            try:
                # Log the start of the import process
                Auditoria.objects.create(
                    origem='Funcionario',
                    user=request.user,
                    obs=(
                        "Iniciando importação de funcionários via integração api_sankhya "
                        f"(funcionários) + SP_ATUALIZA_FUNC_SANKHYA. "
                        f"Tentativa {retry_count + 1} de {max_retries}."
                    )
                )

                resultado_integracao = run_integracao_sankhya("funcionarios")
                if resultado_integracao.get("erro"):
                    raise RuntimeError(resultado_integracao.get("erro"))

                # Close any existing connections

                connections.close_all()

                # Create a new connection to the ERP database
                with connection.cursor() as cursor:
                    # Execute the stored procedure
                    try:
                        execute_db_routine(cursor, "SP_ATUALIZA_FUNC_SANKHYA")
                        rowcount = cursor.rowcount
                    except Exception as e:
                        print(f"Erro ao executar SP_ATUALIZA_FUNC_SANKHYA: {str(e)}")
                        raise

                # Get non-synchronized employees
                nao_sincronizados = Funcionario.objects.filter(sincronizado=False)
                total_nao_sincronizados = nao_sincronizados.count()

                # Send data to webservice
                if total_nao_sincronizados > 0:
                    for funcionario in nao_sincronizados:
                        try:
                            success, message = FuncionarioService.enviar_dados(funcionario)
                            if not success:
                                print(f"Erro ao sincronizar funcionário {funcionario.nome}: {message}")
                                Auditoria.objects.create(
                                    origem='Funcionario',
                                    user=request.user,
                                    obs=f"Erro ao sincronizar funcionário {funcionario.nome}: {message}"
                                )
                        except Exception as e:
                            print(f"Erro ao sincronizar funcionário {funcionario.nome}: {str(e)}")
                            Auditoria.objects.create(
                                origem='Funcionario',
                                user=request.user,
                                obs=f"Erro ao sincronizar funcionário {funcionario.nome}: {str(e)}"
                            )

                # Log success
                if total_nao_sincronizados > 0:
                    Auditoria.objects.create(
                        origem='Funcionario',
                        user=request.user,
                        obs=(
                            "Importação de funcionários realizada com sucesso via "
                            "api_sankhya (funcionários) + SP_ATUALIZA_FUNC_SANKHYA. "
                            f"Processados Sankhya: {resultado_integracao.get('total_processados', 0)}. "
                            f"Procedure afetou {rowcount} funcionário(s). "
                            f"{total_nao_sincronizados} funcionário(s) sincronizado(s) com o webservice."
                        )
                    )
                else:
                    Auditoria.objects.create(
                        origem='Funcionario',
                        user=request.user,
                        obs=(
                            "Importação de funcionários realizada com sucesso via "
                            "api_sankhya (funcionários) + SP_ATUALIZA_FUNC_SANKHYA. "
                            f"Processados Sankhya: {resultado_integracao.get('total_processados', 0)}. "
                            f"Procedure afetou {rowcount} funcionário(s). Nenhum funcionário para sincronizar."
                        )
                    )

                return JsonResponse({
                    'success': True,
                    'message': (
                        "Funcionários atualizados com sucesso via api_sankhya e procedure. "
                        f"Processados Sankhya: {resultado_integracao.get('total_processados', 0)} | "
                        f"Procedure: {rowcount} funcionário(s) afetado(s) | "
                        f"Webservice: {total_nao_sincronizados} funcionário(s) sincronizado(s)."
                    )
                })

            except Exception as e:
                retry_count += 1
                error_message = str(e)
                print(f"Erro na importação de funcionários (tentativa {retry_count}): {error_message}")
                
                # Log the error
                Auditoria.objects.create(
                    origem='Funcionario',
                     user=request.user,
                    obs=f"Erro na importação de funcionários (tentativa {retry_count}): {error_message}"
                )

                if retry_count < max_retries:
                    time.sleep(retry_delay * retry_count)  # Exponential backoff
                    continue
                else:
                    return JsonResponse({
                        'success': False,
                        'message': f'Erro na importação após {max_retries} tentativas: {error_message}'
                    }, status=500)

        return JsonResponse({
            'success': False,
            'message': 'Erro na importação de funcionários'
        }, status=500)


def atualizar_nf_pedidos(request=None):
    """
    View para atualizar os dados de nota fiscal dos pedidos.
    Atualiza pedidos onde o campo nf é igual ao pedido_erp e a serie is 99
    """
    try:
        connection.close()
            
        # Criar nova conexão
        with connection.cursor() as cursor:
            # Evita falha de conversão nvarchar->bigint dentro da procedure.
            # Mapeia pedidos com pedido_erp não numérico antes de executar.
            if connection.vendor == "postgresql":
                cursor.execute(
                    """
                    SELECT id, pedido_erp
                    FROM controleBI_pedido
                    WHERE pedido_erp IS NOT NULL
                      AND BTRIM(pedido_erp) <> ''
                      AND BTRIM(pedido_erp) !~ '^[0-9]+$'
                    ORDER BY id DESC
                    LIMIT 10
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT TOP 10 id, pedido_erp
                    FROM controleBI_pedido
                    WHERE pedido_erp IS NOT NULL
                      AND LTRIM(RTRIM(pedido_erp)) <> ''
                      AND TRY_CONVERT(BIGINT, pedido_erp) IS NULL
                    ORDER BY id DESC
                    """
                )
            invalidos = cursor.fetchall()
            if invalidos:
                detalhes = ", ".join(
                    [f"id={row[0]} pedido_erp='{row[1]}'" for row in invalidos]
                )
                return (
                    False,
                    "ERROR: Existem pedidos com pedido_erp não numérico, "
                    f"impedindo a execução de SP_ATUALIZA_NF_PEDIDO. Exemplos: {detalhes}",
                )

            # Executar a stored procedure
            execute_db_routine(cursor, "SP_ATUALIZA_NF_PEDIDO")
            
            # Obter o número de registros afetados
            rowcount = cursor.rowcount
            
            # Fechar a conexão explicitamente
            cursor.close()
            connection.close()
            
            # Registrar sucesso na auditoria
            Auditoria.objects.create(
                origem="Atualização de Nota Fiscal do Pedido",
                user_id=1,
                obs=f"Atualização de Nota Fiscal do Pedido realizada com sucesso via SP_ATUALIZA_NF_PEDIDO. {rowcount} pedido(s) afetado(s)."
            )

            pedidos = Pedido.objects.filter(tipo=3, sincronizado=True)
            enviados, msg = PedidoService.enviar_dados(pedidos)

            if enviados:
                # Atualizar o tipo para null nos pedidos que foram enviados
                pedidos.update(tipo=None)

            return True, f'{rowcount} - {msg}'
    except Exception as e:
        # Fechar a conexão em caso de erro
        try:
            connection.close()
        except:
            pass
        
          # Registrar sucesso na auditoria
        auditoria_kwargs = {
            "origem": "Atualização de Nota Fiscal do Pedido",
            "obs": f"ERROR: {str(e)}",
        }
        if request is not None:
            auditoria_kwargs["user"] = request.user
        else:
            auditoria_kwargs["user_id"] = 1
        Auditoria.objects.create(**auditoria_kwargs)
        return False, f"ERROR: {str(e)}"


# Views para gestão de Praças
class ListPracaView(PerfilBIAccessMixin, ListView):
    model = Praca
    template_name = 'praca/listPraca.html'
    context_object_name = 'pracas'
    paginate_by = 10

    def get_queryset(self):
        queryset = Praca.objects.annotate(
            enderecos_count=Count('enderecocliente')
        )
        
        # Filtros
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(praca__icontains=search)
            )
            
        return queryset.order_by('praca')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        
        # Adicionar contagens ao contexto
        context['total_pracas'] = queryset.count()
        context['search'] = self.request.GET.get('search', '')
        
        return context


class CadastrarPracaView(PerfilBIAccessMixin, View):
    template_name = 'praca/addPraca.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        try:
            nome = request.POST.get('nome')
            
            if not nome:
                messages.error(request, 'Nome da praça é obrigatório.')
                return render(request, self.template_name)
            
            # Converter para maiúsculas
            nome = nome.upper().strip()
            
            # Verificar se já existe uma praça com o mesmo nome
            if Praca.objects.filter(praca=nome).exists():
                messages.error(request, 'Já existe uma praça com este nome.')
                return render(request, self.template_name)
            
            # Criar nova praça
            praca = Praca.objects.create(
                praca=nome,
                user=request.user
            )
            
            # Registrar na auditoria
            Auditoria.objects.create(
                origem='Praca',
                user=request.user,
                obs=f'Nova praça criada: {praca.praca}'
            )
            
            messages.success(request, f'Praça "{praca.praca}" criada com sucesso!')
            return redirect('list_praca')
            
        except Exception as e:
            messages.error(request, f'Erro ao criar praça: {str(e)}')
            return render(request, self.template_name)


class PracaEditView(PerfilBIAccessMixin, UpdateView):
    model = Praca
    template_name = 'praca/praca_edit.html'
    fields = ['praca']
    success_url = reverse_lazy('list_praca')

    def form_valid(self, form):
        try:
            # Converter para maiúsculas antes de salvar
            praca = form.instance
            praca.praca = praca.praca.upper().strip()
            
            # Registrar alteração na auditoria
            Auditoria.objects.create(
                origem='Praca',
                user=self.request.user,
                obs=f'Praça atualizada: {praca.praca}'
            )
            
            messages.success(self.request, f'Praça "{praca.praca}" atualizada com sucesso!')
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f'Erro ao atualizar praça: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Erro ao atualizar praça. Verifique os dados.')
        return super().form_invalid(form)


class PracaDeleteView(PerfilBIAccessMixin, View):
    def post(self, request, pk):
        try:
            praca = get_object_or_404(Praca, pk=pk)
            nome_praca = praca.praca
            
            # Verificar se há clientes associados
            clientes_associados = praca.clienteerp_set.count()
            if clientes_associados > 0:
                messages.error(request, f'Não é possível excluir a praça "{nome_praca}" pois existem {clientes_associados} cliente(s) associado(s).')
                return redirect('list_praca')
            
            # Excluir praça
            praca.delete()
            
            # Registrar na auditoria
            Auditoria.objects.create(
                origem='Praca',
                user=request.user,
                obs=f'Praça excluída: {nome_praca}'
            )
            
            messages.success(request, f'Praça "{nome_praca}" excluída com sucesso!')
            
        except Exception as e:
            messages.error(request, f'Erro ao excluir praça: {str(e)}')
        
        return redirect('list_praca')

class GerenciarEnderecosPracaView(PerfilBIAccessMixin, View):
    template_name = 'praca/gerenciar_enderecos.html'

    def get(self, request, pk):
        praca = get_object_or_404(Praca, pk=pk)
        
        # Buscar endereços que já estão associados a esta praça
        enderecos_associados = EnderecoCliente.objects.filter(praca=praca).select_related('clienteERP')
        
        # Buscar endereços que não estão associados a nenhuma praça
        enderecos_disponiveis = EnderecoCliente.objects.filter(praca__isnull=True).select_related('clienteERP')
        
        # Filtros
        search = request.GET.get('search')
        if search:
            enderecos_disponiveis = enderecos_disponiveis.filter(
                Q(clienteERP__descr_cliente__icontains=search) |
                Q(clienteERP__razao_cliente__icontains=search) |
                Q(end__icontains=search) |
                Q(cidade__icontains=search)
            )
        
        context = {
            'praca': praca,
            'enderecos_associados': enderecos_associados,
            'enderecos_disponiveis': enderecos_disponiveis,
            'search': search,
            'total_associados': enderecos_associados.count(),
            'total_disponiveis': enderecos_disponiveis.count(),
        }
        
        return render(request, self.template_name, context)

    def post(self, request, pk):
        praca = get_object_or_404(Praca, pk=pk)
        action = request.POST.get('action')
        
        try:
            if action == 'associar':
                endereco_id = request.POST.get('endereco_id')
                endereco = get_object_or_404(EnderecoCliente, pk=endereco_id)
                
                # Verificar se o endereço já está associado a outra praça
                if endereco.praca and endereco.praca != praca:
                    messages.warning(request, f'Endereço já está associado à praça "{endereco.praca.praca}"')
                else:
                    endereco.praca = praca
                    endereco.save()
                    
                    # Registrar na auditoria
                    Auditoria.objects.create(
                        origem='Praca',
                        user=request.user,
                        obs=f'Endereço associado à praça: {endereco.clienteERP.descr_cliente} - {endereco.end}, {endereco.num_end} -> {praca.praca}'
                    )
                    
                    messages.success(request, f'Endereço associado com sucesso à praça "{praca.praca}"')
            
            elif action == 'desassociar':
                endereco_id = request.POST.get('endereco_id')
                endereco = get_object_or_404(EnderecoCliente, pk=endereco_id, praca=praca)
                
                endereco.praca = None
                endereco.save()
                
                # Registrar na auditoria
                Auditoria.objects.create(
                    origem='Praca',
                    user=request.user,
                    obs=f'Endereço desassociado da praça: {endereco.clienteERP.descr_cliente} - {endereco.end}, {endereco.num_end} <- {praca.praca}'
                )
                
                messages.success(request, f'Endereço desassociado com sucesso da praça "{praca.praca}"')
            
            elif action == 'associar_multiplos':
                endereco_ids = request.POST.getlist('endereco_ids')
                if endereco_ids:
                    enderecos = EnderecoCliente.objects.filter(
                        pk__in=endereco_ids, 
                        praca__isnull=True
                    )
                    
                    for endereco in enderecos:
                        endereco.praca = praca
                        endereco.save()
                    
                    # Registrar na auditoria
                    Auditoria.objects.create(
                        origem='Praca',
                        user=request.user,
                        obs=f'{enderecos.count()} endereço(s) associado(s) à praça "{praca.praca}"'
                    )
                    
                    messages.success(request, f'{enderecos.count()} endereço(s) associado(s) com sucesso à praça "{praca.praca}"')
                else:
                    messages.warning(request, 'Nenhum endereço selecionado para associar.')
            
        except Exception as e:
            messages.error(request, f'Erro ao processar ação: {str(e)}')
        
        return redirect('gerenciar_enderecos_praca', pk=pk)


class ListClienteSankhyaGestaoView(PerfilBIAccessMixin, ListView):
    """Lista clientes da tabela sankhya_cliente para gestão de usuários do sistema."""

    model = ClienteSankhya
    template_name = 'cliente_sankhya/list_clientes_gestao.html'
    context_object_name = 'clientes'
    paginate_by = 20

    def get_queryset(self):
        qs = ClienteSankhya.objects.annotate(qtd_usuarios=Count('usuarios_sistema'))
        search = self.request.GET.get('search', '').strip()
        if search:
            q = (
                Q(nome__icontains=search)
                | Q(razao__icontains=search)
                | Q(cnpj_cpf__icontains=search)
            )
            if search.isdigit():
                q |= Q(codigo_cliente=int(search))
            qs = qs.filter(q)
        return qs.order_by('nome', 'razao', 'codigo_cliente')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_search'] = self.request.GET.get('search', '')
        return ctx


class GestaoUsuariosClienteSankhyaView(PerfilBIAccessMixin, View):
    """Por cliente: criar usuários (perfil cliente) e alterar senhas."""

    template_name = 'cliente_sankhya/gestao_usuarios_cliente.html'

    def get_cliente(self, pk):
        return get_object_or_404(ClienteSankhya, pk=pk)

    def get(self, request, pk):
        cliente = self.get_cliente(pk)
        vinculos = (
            UsuarioClienteSankhya.objects.filter(cliente=cliente)
            .select_related('user')
            .order_by('user__username')
        )
        form = CriarUsuarioClienteSankhyaForm()
        return render(
            request,
            self.template_name,
            {
                'cliente': cliente,
                'vinculos': vinculos,
                'form_criar': form,
                'form_senha': AlterarSenhaUsuarioClienteForm(),
            },
        )

    def post(self, request, pk):
        cliente = self.get_cliente(pk)
        action = request.POST.get('action')

        if action == 'criar_usuario':
            form = CriarUsuarioClienteSankhyaForm(request.POST)
            if form.is_valid():
                try:
                    validate_password(form.cleaned_data['password'], user=User(username=form.cleaned_data['username']))
                except DjangoValidationError as e:
                    for err in e.messages:
                        form.add_error('password', err)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        user = User.objects.create_user(
                            username=form.cleaned_data['username'],
                            email=form.cleaned_data.get('email') or '',
                            password=form.cleaned_data['password'],
                            first_name=form.cleaned_data.get('first_name') or '',
                        )
                        PerfilUsuario.objects.filter(user=user).update(perfil=PerfilUsuario.Perfil.CLIENTE)
                        UsuarioClienteSankhya.objects.create(cliente=cliente, user=user)
                    messages.success(
                        request,
                        f'Usuário "{user.username}" criado e vinculado ao cliente.',
                    )
                    return redirect('gestao_usuarios_cliente_sankhya', pk=pk)
                except Exception as exc:
                    messages.error(request, f'Erro ao criar usuário: {exc}')
            vinculos = (
                UsuarioClienteSankhya.objects.filter(cliente=cliente)
                .select_related('user')
                .order_by('user__username')
            )
            return render(
                request,
                self.template_name,
                {
                    'cliente': cliente,
                    'vinculos': vinculos,
                    'form_criar': form,
                    'form_senha': AlterarSenhaUsuarioClienteForm(),
                },
            )

        if action == 'alterar_senha':
            raw_uid = request.POST.get('user_id')
            user = get_object_or_404(User, pk=raw_uid)
            vinculo = UsuarioClienteSankhya.objects.filter(cliente=cliente, user=user).first()
            if not vinculo:
                messages.error(request, 'Usuário não pertence a este cliente.')
                return redirect('gestao_usuarios_cliente_sankhya', pk=pk)
            form_senha = AlterarSenhaUsuarioClienteForm(request.POST)
            if form_senha.is_valid():
                pwd = form_senha.cleaned_data['new_password']
                try:
                    validate_password(pwd, user=user)
                except DjangoValidationError as e:
                    for err in e.messages:
                        form_senha.add_error('new_password', err)
            if form_senha.is_valid():
                user.set_password(form_senha.cleaned_data['new_password'])
                user.save()
                messages.success(request, f'Senha do usuário "{user.username}" atualizada.')
                return redirect('gestao_usuarios_cliente_sankhya', pk=pk)
            vinculos = (
                UsuarioClienteSankhya.objects.filter(cliente=cliente)
                .select_related('user')
                .order_by('user__username')
            )
            return render(
                request,
                self.template_name,
                {
                    'cliente': cliente,
                    'vinculos': vinculos,
                    'form_criar': CriarUsuarioClienteSankhyaForm(),
                    'form_senha': form_senha,
                    'senha_user_id': raw_uid,
                    'abrir_modal_senha': True,
                },
            )

        return redirect('gestao_usuarios_cliente_sankhya', pk=pk)


def _collect_codigos_arvore_grupos(nodes: list[dict]) -> list[int]:
    out: list[int] = []
    for n in nodes:
        out.append(n['grupo'].codigo_grupo_produto)
        out.extend(_collect_codigos_arvore_grupos(n['filhos']))
    return out


class GestaoCategoriasEcommerceView(PerfilBIAccessMixin, View):
    """Hierarquia sankhya_grupo_produto: define quais categorias aparecem na loja."""

    template_name = 'ecommerce_gestao/categorias.html'

    def get(self, request):
        perfil = ensure_perfil(request.user)
        if not perfil or perfil.perfil != PerfilUsuario.Perfil.ADMINISTRADOR:
            messages.error(request, 'Apenas administradores podem acessar a gestão de categorias.')
            return redirect('dashboard')
        search = catalog_ecommerce.normalizar_busca(request.GET.get('search'))
        _by_id, by_pai, raizes = catalog_ecommerce.grupos_ativos_map(apenas_visiveis_loja=False)
        arvore_full = catalog_ecommerce.arvore_grupos_nested(raizes, by_pai)
        tem_grupos_no_sistema = bool(raizes)

        if search:
            mids = catalog_ecommerce.matching_grupo_produto_ids_por_texto(
                list(_by_id.values()), search
            )
            vis = catalog_ecommerce.ids_grupos_com_hierarquia_busca(mids, _by_id, by_pai)
            arvore = catalog_ecommerce.filtrar_arvore_grupos_por_ids(arvore_full, vis) if vis else []
        else:
            arvore = arvore_full

        filtro_sem_resultado = bool(search) and not arvore and tem_grupos_no_sistema
        visible_grupo_ids = _collect_codigos_arvore_grupos(arvore) if search and arvore else []

        return render(
            request,
            self.template_name,
            {
                'arvore': arvore,
                'current_search': search,
                'filtro_sem_resultado': filtro_sem_resultado,
                'busca_categorias_max': catalog_ecommerce.BUSCA_MAX_LEN,
                'visible_grupo_ids': visible_grupo_ids,
            },
        )

    def post(self, request):
        perfil = ensure_perfil(request.user)
        if not perfil or perfil.perfil != PerfilUsuario.Perfil.ADMINISTRADOR:
            messages.error(request, 'Apenas administradores podem alterar categorias do e-commerce.')
            return redirect('dashboard')
        search = catalog_ecommerce.normalizar_busca(request.POST.get('search'))
        codigos_marcados: list[int] = []
        for x in request.POST.getlist('mostrar_ecommerce'):
            try:
                codigos_marcados.append(int(x))
            except (TypeError, ValueError):
                continue
        visiveis_tela: set[int] = set()
        for x in request.POST.getlist('visivel'):
            try:
                visiveis_tela.add(int(x))
            except (TypeError, ValueError):
                continue

        if search and visiveis_tela:
            marcados_set = set(codigos_marcados) & visiveis_tela
            with transaction.atomic():
                GrupoProduto.objects.filter(
                    ativo=True,
                    codigo_grupo_produto__in=visiveis_tela,
                ).update(mostrar_no_ecommerce=False)
                if marcados_set:
                    GrupoProduto.objects.filter(
                        ativo=True,
                        codigo_grupo_produto__in=marcados_set,
                    ).update(mostrar_no_ecommerce=True)
            messages.success(request, 'Categorias visíveis na loja foram atualizadas (apenas itens do filtro).')
        elif search and not visiveis_tela:
            messages.warning(
                request,
                'Com o filtro atual não há categorias na tela; nenhuma alteração foi salva. Limpe o filtro para editar tudo.',
            )
        else:
            with transaction.atomic():
                GrupoProduto.objects.filter(ativo=True).update(mostrar_no_ecommerce=False)
                if codigos_marcados:
                    GrupoProduto.objects.filter(
                        ativo=True,
                        codigo_grupo_produto__in=codigos_marcados,
                    ).update(mostrar_no_ecommerce=True)
            messages.success(request, 'Categorias visíveis na loja foram atualizadas.')

        redir = reverse('gestao_categorias_ecommerce')
        if search:
            redir = f'{redir}?{urlencode({"search": search})}'
        return redirect(redir)


def _perfil_bi_comercial_ou_admin(user):
    perfil = ensure_perfil(user)
    if perfil is None:
        return False
    return perfil.perfil in PERFIS_PAINEL_BI_LOJA


def _veiculos_ativos_qs():
    return Veiculo.objects.filter(status_inicial='Ativo').order_by('placa')


def _motoristas_ativos_qs():
    return Funcionario.objects.filter(tipo='Motorista', status='Ativo').order_by('nome')


def _ajudantes_ativos_qs():
    return Funcionario.objects.filter(tipo='Ajudante', status='Ativo').order_by('nome')


def _veiculos_disponiveis_rota_padrao(rota_atual=None):
    """Veículos ativos ainda não vinculados a outra rota padrão (mantém o da rota em edição)."""
    ocupados_qs = RotaPadrao.objects.exclude(veiculo__isnull=True)
    if rota_atual and getattr(rota_atual, 'pk', None):
        ocupados_qs = ocupados_qs.exclude(pk=rota_atual.pk)
    ocupados = ocupados_qs.values_list('veiculo_id', flat=True)
    livres = Veiculo.objects.filter(status_inicial='Ativo').exclude(id__in=ocupados)
    if rota_atual and rota_atual.veiculo_id:
        extra = Veiculo.objects.filter(pk=rota_atual.veiculo_id, status_inicial='Ativo')
        return (livres | extra).distinct().order_by('placa')
    return livres.order_by('placa')


def _motoristas_disponiveis_rota_padrao(rota_atual=None):
    ocupados_qs = RotaPadrao.objects.exclude(motorista__isnull=True)
    if rota_atual and getattr(rota_atual, 'pk', None):
        ocupados_qs = ocupados_qs.exclude(pk=rota_atual.pk)
    ocupados = ocupados_qs.values_list('motorista_id', flat=True)
    livres = Funcionario.objects.filter(tipo='Motorista', status='Ativo').exclude(id__in=ocupados)
    if rota_atual and rota_atual.motorista_id:
        extra = Funcionario.objects.filter(
            pk=rota_atual.motorista_id, tipo='Motorista', status='Ativo'
        )
        return (livres | extra).distinct().order_by('nome')
    return livres.order_by('nome')


def _ajudantes_disponiveis_rota_padrao(rota_atual=None):
    """Ajudantes ativos não alocados em outra rota padrão (exceto na rota em edição)."""
    ocupados_qs = RotaPadraoAjudante.objects.all()
    if rota_atual and getattr(rota_atual, 'pk', None):
        ocupados_qs = ocupados_qs.exclude(rota_id=rota_atual.pk)
    ocupados = ocupados_qs.values_list('funcionario_id', flat=True)
    return (
        Funcionario.objects.filter(tipo='Ajudante', status='Ativo')
        .exclude(id__in=ocupados)
        .order_by('nome')
    )


def _veiculo_livre_outras_rotas_padrao(veiculo_id, rota_atual) -> bool:
    if not veiculo_id:
        return True
    q = RotaPadrao.objects.exclude(veiculo__isnull=True).filter(veiculo_id=veiculo_id)
    if rota_atual and getattr(rota_atual, 'pk', None):
        q = q.exclude(pk=rota_atual.pk)
    return not q.exists()


def _motorista_livre_outras_rotas_padrao(motorista_id, rota_atual) -> bool:
    if not motorista_id:
        return True
    q = RotaPadrao.objects.exclude(motorista__isnull=True).filter(motorista_id=motorista_id)
    if rota_atual and getattr(rota_atual, 'pk', None):
        q = q.exclude(pk=rota_atual.pk)
    return not q.exists()


def _ajudante_livre_outras_rotas_padrao(funcionario_id, rota_atual) -> bool:
    q = RotaPadraoAjudante.objects.filter(funcionario_id=funcionario_id)
    if rota_atual and getattr(rota_atual, 'pk', None):
        q = q.exclude(rota_id=rota_atual.pk)
    return not q.exists()


def _nome_rota_dia_executada(rota_dia: RotaDia) -> str:
    if rota_dia.rota_padrao:
        return rota_dia.rota_padrao.nome
    return f'Rota #{rota_dia.pk}'


def _copiar_equipe_padrao_para_rota_dia(rota_dia, rota_padrao):
    rota_dia.veiculo_id = rota_padrao.veiculo_id
    rota_dia.motorista_id = rota_padrao.motorista_id
    rota_dia.save(update_fields=['veiculo', 'motorista', 'atualizado_em'])
    RotaDiaAjudante.objects.filter(rota_dia=rota_dia).delete()
    linhas = list(rota_padrao.ajudantes_equipe.order_by('ordem', 'id'))
    if linhas:
        RotaDiaAjudante.objects.bulk_create(
            [
                RotaDiaAjudante(rota_dia=rota_dia, funcionario_id=row.funcionario_id, ordem=idx)
                for idx, row in enumerate(linhas)
            ]
        )


def _ensure_equipe_from_padrao_if_empty(rota_dia, rota_padrao):
    if rota_dia.veiculo_id or rota_dia.motorista_id or rota_dia.ajudantes_equipe.exists():
        return
    if not (rota_padrao.veiculo_id or rota_padrao.motorista_id or rota_padrao.ajudantes_equipe.exists()):
        return
    _copiar_equipe_padrao_para_rota_dia(rota_dia, rota_padrao)


class GestaoRotasEcommerceView(PerfilGestaoRotasMixin, View):
    template_name = 'ecommerce_gestao/rotas.html'

    def get(self, request):
        rotas = (
            RotaPadrao.objects.select_related('responsavel', 'veiculo', 'motorista')
            .prefetch_related('clientes_rota')
            .annotate(total_ajudantes=Count('ajudantes_equipe'))
            .order_by('nome')
        )
        return render(request, self.template_name, {'rotas': rotas})


class GestaoNotificacoesEcommerceView(PerfilBIAccessMixin, View):
    template_name = 'ecommerce_gestao/notificacoes.html'

    @staticmethod
    def pedidos_visiveis_para_usuario(user):
        responsavel_nome_sq = Subquery(
            RotaDiaCliente.objects.filter(
                cliente_id=OuterRef('cliente_id'),
                rota_dia__data=OuterRef('criado_em__date'),
                rota_dia__rota_padrao__isnull=False,
            )
            .order_by('rota_dia_id', 'id')
            .values('rota_dia__rota_padrao__responsavel__first_name')[:1]
        )
        responsavel_username_sq = Subquery(
            RotaDiaCliente.objects.filter(
                cliente_id=OuterRef('cliente_id'),
                rota_dia__data=OuterRef('criado_em__date'),
                rota_dia__rota_padrao__isnull=False,
            )
            .order_by('rota_dia_id', 'id')
            .values('rota_dia__rota_padrao__responsavel__username')[:1]
        )
        pedidos = (
            PedidoLoja.objects.select_related('cliente', 'user', 'aprovado_por')
            .prefetch_related('itens')
            .annotate(
                comercial_responsavel_nome=responsavel_nome_sq,
                comercial_responsavel_username=responsavel_username_sq,
            )
            .order_by('-criado_em')
        )
        perfil = ensure_perfil(user)
        restrito_notificacoes_rota_dia = False
        if perfil and perfil.perfil == PerfilUsuario.Perfil.COMERCIAL:
            restrito_notificacoes_rota_dia = True
            pedidos = filtrar_pedidos_loja_notificacoes_comercial(pedidos, user)
        return pedidos, restrito_notificacoes_rota_dia

    def get(self, request):
        pedidos, restrito_notificacoes_rota_dia = self.pedidos_visiveis_para_usuario(
            request.user
        )
        hoje_iso = date.today().isoformat()
        status = (request.GET.get('status', PedidoLoja.Status.PENDENTE) or '').strip()
        data_ini = (request.GET.get('data_ini', hoje_iso) or '').strip()
        data_fim = (request.GET.get('data_fim', hoje_iso) or '').strip()

        if status in {
            PedidoLoja.Status.PENDENTE,
            PedidoLoja.Status.AUTORIZADO,
            PedidoLoja.Status.REJEITADO,
        }:
            pedidos = pedidos.filter(status=status)
        else:
            status = ''

        if data_ini:
            try:
                pedidos = pedidos.filter(criado_em__date__gte=date.fromisoformat(data_ini))
            except ValueError:
                data_ini = ''
        if data_fim:
            try:
                pedidos = pedidos.filter(criado_em__date__lte=date.fromisoformat(data_fim))
            except ValueError:
                data_fim = ''

        contador = Counter()
        for pedido in pedidos.filter(status=PedidoLoja.Status.PENDENTE):
            nome = (
                pedido.comercial_responsavel_nome
                or pedido.comercial_responsavel_username
                or 'Sem responsável'
            )
            contador[nome] += 1
        pendencias_por_comercial = [
            {'nome': nome, 'total': total}
            for nome, total in sorted(contador.items(), key=lambda x: (-x[1], x[0]))
        ]

        context = {
            'pedidos': pedidos,
            'total_pedidos': pedidos.count(),
            'pendentes': pedidos.filter(status=PedidoLoja.Status.PENDENTE).count(),
            'autorizados': pedidos.filter(status=PedidoLoja.Status.AUTORIZADO).count(),
            'rejeitados': pedidos.filter(status=PedidoLoja.Status.REJEITADO).count(),
            'restrito_notificacoes_rota_dia': restrito_notificacoes_rota_dia,
            'filtro_status': status,
            'filtro_data_ini': data_ini,
            'filtro_data_fim': data_fim,
            'pendencias_por_comercial': pendencias_por_comercial,
        }
        return render(request, self.template_name, context)


@login_required
@requer_acesso_bi
def notificacoes_pendentes_count_api(request):
    pedidos, _ = GestaoNotificacoesEcommerceView.pedidos_visiveis_para_usuario(request.user)
    total = pedidos.filter(status=PedidoLoja.Status.PENDENTE).count()
    return JsonResponse({'pendentes': total})


@login_required
@requer_acesso_bi
@require_POST
def gestao_notificacao_aprovar(request, pk: int):
    perfil = ensure_perfil(request.user)
    if not perfil or perfil.perfil not in PERFIS_PAINEL_BI_LOJA:
        messages.error(request, 'Sem permissão para aprovar pedido.')
        return redirect('gestao_notificacoes_ecommerce')

    pedidos_qs, _ = GestaoNotificacoesEcommerceView.pedidos_visiveis_para_usuario(request.user)
    pedido = get_object_or_404(pedidos_qs, pk=pk)
    if pedido.status != PedidoLoja.Status.PENDENTE:
        messages.warning(request, 'Este pedido já foi analisado.')
        return redirect('gestao_notificacoes_ecommerce')

    pedido.status = PedidoLoja.Status.AUTORIZADO
    pedido.aprovado_por = request.user
    pedido.aprovado_em = timezone.now()
    pedido.save(update_fields=['status', 'aprovado_por', 'aprovado_em', 'atualizado_em'])

    NotificacaoLoja.objects.create(
        user=pedido.user,
        pedido=pedido,
        titulo=f'Pedido #{pedido.pk} aprovado',
        mensagem='Seu pedido foi aprovado pelo comercial e seguirá para integração no Sankhya.',
    )
    messages.success(request, f'Pedido #{pedido.pk} aprovado com sucesso.')
    return redirect('gestao_notificacoes_ecommerce')


@login_required
@requer_acesso_bi
@require_POST
def gestao_notificacao_rejeitar(request, pk: int):
    perfil = ensure_perfil(request.user)
    if not perfil or perfil.perfil not in PERFIS_PAINEL_BI_LOJA:
        messages.error(request, 'Sem permissão para rejeitar pedido.')
        return redirect('gestao_notificacoes_ecommerce')

    pedidos_qs, _ = GestaoNotificacoesEcommerceView.pedidos_visiveis_para_usuario(request.user)
    pedido = get_object_or_404(pedidos_qs, pk=pk)
    if pedido.status != PedidoLoja.Status.PENDENTE:
        messages.warning(request, 'Este pedido já foi analisado.')
        return redirect('gestao_notificacoes_ecommerce')

    mensagem = (request.POST.get('mensagem') or '').strip()
    if not mensagem:
        messages.error(request, 'Informe a mensagem de rejeição para o cliente.')
        return redirect('gestao_notificacoes_ecommerce')

    pedido.status = PedidoLoja.Status.REJEITADO
    pedido.observacao_comercial = mensagem
    pedido.aprovado_por = request.user
    pedido.aprovado_em = timezone.now()
    pedido.save(
        update_fields=[
            'status',
            'observacao_comercial',
            'aprovado_por',
            'aprovado_em',
            'atualizado_em',
        ]
    )
    NotificacaoLoja.objects.create(
        user=pedido.user,
        pedido=pedido,
        titulo=f'Pedido #{pedido.pk} rejeitado',
        mensagem=mensagem,
    )
    messages.success(request, f'Pedido #{pedido.pk} rejeitado e cliente notificado.')
    return redirect('gestao_notificacoes_ecommerce')


class EcommerceClientesSelectorView(PerfilBIAccessMixin, View):
    """Lista clientes para o modal da loja com paginação (evita truncar em 200)."""

    template_name = 'ecommerce_gestao/partials/loja_clientes_selector_list.html'
    page_size = 150

    def get(self, request):
        q = (request.GET.get('q') or '').strip()
        try:
            offset = max(0, int(request.GET.get('offset', 0) or 0))
        except (TypeError, ValueError):
            offset = 0
        selected_raw = request.session.get('ecommerce_cliente_context_id')
        try:
            selected_id = int(selected_raw)
        except (TypeError, ValueError):
            selected_id = None

        qs = ClienteSankhya.objects.all()
        if q:
            lookup = (
                Q(nome__icontains=q)
                | Q(razao__icontains=q)
                | Q(cnpj_cpf__icontains=q)
            )
            if q.isdigit():
                lookup |= Q(codigo_cliente=int(q))
            qs = qs.filter(lookup)
        qs = qs.order_by('nome', 'razao', 'codigo_cliente')

        limit = self.page_size + 1
        batch = list(qs[offset : offset + limit])
        has_more = len(batch) > self.page_size
        batch = batch[: self.page_size]
        total_carregados = offset + len(batch)

        ctx = {
            'clientes': batch,
            'selected_id': selected_id,
            'filtro': q,
            'has_more': has_more,
            'next_offset': offset + len(batch),
            'total_carregados': total_carregados,
        }

        if request.GET.get('format') == 'json':
            rows_html = render_to_string(
                'ecommerce_gestao/partials/loja_clientes_selector_rows.html',
                ctx,
                request=request,
            )
            footer_html = ''
            if has_more:
                footer_html = render_to_string(
                    'ecommerce_gestao/partials/loja_clientes_selector_footer_row.html',
                    ctx,
                    request=request,
                )
            return JsonResponse(
                {
                    'rows_html': rows_html,
                    'footer_html': footer_html,
                    'has_more': has_more,
                    'next_offset': offset + len(batch),
                    'total_carregados': total_carregados,
                }
            )

        return render(request, self.template_name, ctx)


class EcommerceSelecionarClienteView(PerfilBIAccessMixin, View):
    def post(self, request):
        perfil = ensure_perfil(request.user)
        if not perfil or perfil.perfil not in PERFIS_PAINEL_BI_LOJA:
            messages.error(request, 'Perfil sem permissão para selecionar cliente da loja.')
            return redirect('dashboard')

        cliente_id = request.POST.get('cliente_id')
        next_url = request.POST.get('next') or reverse('ecommerce_home')

        if not cliente_id:
            request.session.pop('ecommerce_cliente_context_id', None)
            messages.info(request, 'Seleção de cliente limpa.')
            return redirect(next_url)

        try:
            cliente_id = int(cliente_id)
        except (TypeError, ValueError):
            messages.error(request, 'Cliente inválido.')
            return redirect(next_url)

        cliente = ClienteSankhya.objects.filter(id=cliente_id).first()
        if not cliente:
            messages.error(request, 'Cliente não encontrado.')
            return redirect(next_url)

        request.session['ecommerce_cliente_context_id'] = cliente.id
        messages.success(
            request,
            f'Loja aberta para o cliente: {cliente.nome or cliente.razao or cliente.codigo_cliente}.',
        )
        return redirect(next_url)


class RotasDiaListView(PerfilGestaoRotasMixin, View):
    template_name = 'ecommerce_gestao/rotas_dia_list.html'

    def get(self, request):
        data_ini = request.GET.get('data_ini')
        data_fim = request.GET.get('data_fim')
        rota_padrao_id = request.GET.get('rota_padrao')
        # .order_by() limpa Meta.ordering (ordem, id); senão o SQL Server falha no GROUP BY da subquery.
        _sub_total_clientes = (
            RotaDiaCliente.objects.filter(rota_dia=OuterRef('pk'))
            .values('rota_dia')
            .annotate(n=Count('pk'))
            .values('n')
            .order_by()[:1]
        )
        _sub_total_ajudantes = (
            RotaDiaAjudante.objects.filter(rota_dia=OuterRef('pk'))
            .values('rota_dia')
            .annotate(n=Count('pk'))
            .values('n')
            .order_by()[:1]
        )
        qs = (
            RotaDia.objects.select_related('rota_padrao', 'criado_por', 'veiculo', 'motorista')
            .annotate(
                total_clientes=Coalesce(Subquery(_sub_total_clientes), Value(0)),
                total_ajudantes=Coalesce(Subquery(_sub_total_ajudantes), Value(0)),
            )
            .order_by('-data', 'rota_padrao__nome', '-id')
        )
        if data_ini:
            try:
                qs = qs.filter(data__gte=date.fromisoformat(data_ini))
            except ValueError:
                data_ini = ''
        if data_fim:
            try:
                qs = qs.filter(data__lte=date.fromisoformat(data_fim))
            except ValueError:
                data_fim = ''
        if rota_padrao_id:
            try:
                qs = qs.filter(rota_padrao_id=int(rota_padrao_id))
            except (TypeError, ValueError):
                rota_padrao_id = ''

        return render(
            request,
            self.template_name,
            {
                'rotas_dia': qs,
                'data_ini': data_ini or '',
                'data_fim': data_fim or '',
                'rota_padrao_id': str(rota_padrao_id or ''),
                'rotas_padrao': RotaPadrao.objects.filter(ativa=True).order_by('nome'),
            },
        )


DIAS_SEMANA_PT = (
    'Segunda-feira',
    'Terça-feira',
    'Quarta-feira',
    'Quinta-feira',
    'Sexta-feira',
    'Sábado',
    'Domingo',
)


def _week_range_containing(d: date) -> tuple[date, date]:
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


class MapaRotasSemanaView(PerfilMapaRotasEcommerceMixin, View):
    """Rotas a executar da semana (comercial: só rotas padrão em que é responsável)."""

    template_name = 'ecommerce_gestao/mapa_rotas_semana.html'

    def get(self, request):
        ref_raw = request.GET.get('ref')
        try:
            ref = date.fromisoformat(ref_raw) if ref_raw else date.today()
        except ValueError:
            ref = date.today()
        week_start, week_end = _week_range_containing(ref)

        perfil = ensure_perfil(request.user)
        qs = (
            RotaDia.objects.filter(data__gte=week_start, data__lte=week_end)
            .select_related('rota_padrao', 'rota_padrao__responsavel', 'veiculo', 'motorista', 'criado_por')
            .prefetch_related(
                'ajudantes_equipe__funcionario',
                Prefetch(
                    'clientes_rota',
                    queryset=RotaDiaCliente.objects.select_related('cliente').order_by('ordem', 'id'),
                ),
            )
            .annotate(total_clientes=Count('clientes_rota'))
            .order_by('data', 'rota_padrao__nome', 'id')
        )
        if perfil and perfil.perfil == PerfilUsuario.Perfil.COMERCIAL:
            qs = qs.filter(rota_padrao__responsavel=request.user)

        rotas_list = list(qs)
        rotas_por_dia = defaultdict(list)
        for rd in rotas_list:
            rotas_por_dia[rd.data].append(rd)

        dias_grid = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            dias_grid.append(
                {
                    'data': d,
                    'dia_semana': DIAS_SEMANA_PT[d.weekday()],
                    'rotas': rotas_por_dia.get(d, []),
                }
            )

        prev_week_ref = (week_start - timedelta(days=7)).isoformat()
        next_week_ref = (week_start + timedelta(days=7)).isoformat()

        return render(
            request,
            self.template_name,
            {
                'week_start': week_start,
                'week_end': week_end,
                'ref': ref,
                'dias_grid': dias_grid,
                'prev_week_ref': prev_week_ref,
                'next_week_ref': next_week_ref,
                'total_rotas_semana': len(rotas_list),
                'filtro_comercial': bool(perfil and perfil.perfil == PerfilUsuario.Perfil.COMERCIAL),
                'pode_editar_rotas_dia': bool(perfil and perfil.perfil in PERFIS_GESTAO_ROTAS),
            },
        )


class RotaPadraoFormView(PerfilGestaoRotasMixin, View):
    template_name = 'ecommerce_gestao/rota_form.html'

    def get(self, request, pk=None):
        rota = None
        if pk:
            rota = get_object_or_404(
                RotaPadrao.objects.select_related('responsavel', 'veiculo', 'motorista').prefetch_related(
                    'clientes_rota__cliente',
                    'ajudantes_equipe',
                ),
                pk=pk,
            )

        responsaveis = (
            User.objects.filter(perfil_usuario__perfil__in=PERFIS_PAINEL_BI_LOJA)
            .order_by('first_name', 'username')
            .distinct()
        )
        clientes = ClienteSankhya.objects.order_by('nome', 'razao', 'codigo_cliente')
        selecionados = set()
        if rota:
            selecionados = set(
                rota.clientes_rota.values_list('cliente_id', flat=True)
            )
        clientes = (
            ClienteSankhya.objects.filter(
                Q(rotas_padrao__isnull=True) | Q(id__in=selecionados)
            )
            .distinct()
            .order_by('nome', 'razao', 'codigo_cliente')
        )
        ajudantes_selecionados = []
        if rota:
            ajudantes_selecionados = list(
                rota.ajudantes_equipe.order_by('ordem', 'id').values_list('funcionario_id', flat=True)
            )

        return render(
            request,
            self.template_name,
            {
                'rota': rota,
                'responsaveis': responsaveis,
                'clientes': clientes,
                'selecionados': selecionados,
                'veiculos': _veiculos_disponiveis_rota_padrao(rota),
                'motoristas': _motoristas_disponiveis_rota_padrao(rota),
                'ajudantes': _ajudantes_disponiveis_rota_padrao(rota),
                'ajudantes_selecionados': ajudantes_selecionados,
            },
        )

    def post(self, request, pk=None):
        rota = None
        if pk:
            rota = get_object_or_404(RotaPadrao, pk=pk)

        nome = (request.POST.get('nome') or '').strip()
        descricao = (request.POST.get('descricao') or '').strip()
        ativa = request.POST.get('ativa') == 'on'
        responsavel_id = request.POST.get('responsavel')
        cliente_ids = []
        for cid in request.POST.getlist('clientes'):
            try:
                cliente_ids.append(int(cid))
            except (TypeError, ValueError):
                continue

        veiculo_id = (request.POST.get('veiculo') or '').strip()
        motorista_id = (request.POST.get('motorista') or '').strip()
        ajudante_ids = []
        for aid in request.POST.getlist('ajudantes'):
            try:
                ajudante_ids.append(int(aid))
            except (TypeError, ValueError):
                continue

        if not nome:
            messages.error(request, 'Informe o nome da rota.')
            return self.get(request, pk=pk)

        responsavel = User.objects.filter(pk=responsavel_id).first()
        if not responsavel or not _perfil_bi_comercial_ou_admin(responsavel):
            messages.error(request, 'Selecione um responsável comercial válido.')
            return self.get(request, pk=pk)

        veiculo = None
        if veiculo_id:
            veiculo = Veiculo.objects.filter(pk=veiculo_id, status_inicial='Ativo').first()
            if not veiculo:
                messages.error(request, 'Selecione um veículo ativo válido.')
                return self.get(request, pk=pk)

        motorista = None
        if motorista_id:
            motorista = Funcionario.objects.filter(
                pk=motorista_id, tipo='Motorista', status='Ativo'
            ).first()
            if not motorista:
                messages.error(request, 'Selecione um motorista ativo válido.')
                return self.get(request, pk=pk)

        ajudantes_validos = list(
            Funcionario.objects.filter(
                id__in=ajudante_ids, tipo='Ajudante', status='Ativo'
            ).values_list('id', flat=True)
        )
        ajudantes_ordenados = list(
            dict.fromkeys([fid for fid in ajudante_ids if fid in ajudantes_validos])
        )

        if veiculo and not _veiculo_livre_outras_rotas_padrao(veiculo.pk, rota):
            messages.error(request, 'Este veículo já está vinculado a outra rota padrão.')
            return self.get(request, pk=pk)
        if motorista and not _motorista_livre_outras_rotas_padrao(motorista.pk, rota):
            messages.error(request, 'Este motorista já está vinculado a outra rota padrão.')
            return self.get(request, pk=pk)
        for fid in ajudantes_ordenados:
            if not _ajudante_livre_outras_rotas_padrao(fid, rota):
                messages.error(request, 'Um dos ajudantes selecionados já está em outra rota padrão.')
                return self.get(request, pk=pk)

        with transaction.atomic():
            if rota is None:
                rota = RotaPadrao.objects.create(
                    nome=nome,
                    descricao=descricao,
                    ativa=ativa,
                    responsavel=responsavel,
                    veiculo=veiculo,
                    motorista=motorista,
                )
            else:
                rota.nome = nome
                rota.descricao = descricao
                rota.ativa = ativa
                rota.responsavel = responsavel
                rota.veiculo = veiculo
                rota.motorista = motorista
                rota.save()

            RotaPadraoAjudante.objects.filter(rota=rota).delete()
            if ajudantes_ordenados:
                RotaPadraoAjudante.objects.bulk_create(
                    [
                        RotaPadraoAjudante(rota=rota, funcionario_id=fid, ordem=idx)
                        for idx, fid in enumerate(ajudantes_ordenados)
                    ]
                )

            RotaPadraoCliente.objects.filter(rota=rota).delete()
            if cliente_ids:
                clientes_validos = list(
                    ClienteSankhya.objects.filter(id__in=cliente_ids).values_list('id', flat=True)
                )
                RotaPadraoCliente.objects.bulk_create(
                    [
                        RotaPadraoCliente(rota=rota, cliente_id=cid, ordem=idx)
                        for idx, cid in enumerate(cliente_ids)
                        if cid in clientes_validos
                    ]
                )

        messages.success(
            request,
            'Rota padrão salva com sucesso.',
        )
        return redirect('gestao_rotas_ecommerce')


class RotaDiaBuilderView(PerfilGestaoRotasMixin, View):
    template_name = 'ecommerce_gestao/rota_dia_builder.html'

    def _load_or_create_rota_dia(self, data_rota: date, rota_padrao, request):
        rota_dia = RotaDia.objects.filter(data=data_rota, rota_padrao=rota_padrao).first()
        if rota_dia:
            return rota_dia, False
        rota_dia = RotaDia.objects.create(
            data=data_rota,
            rota_padrao=rota_padrao,
            criado_por=request.user,
        )
        return rota_dia, True

    def _seed_from_rota_padrao(self, rota_dia, rota_padrao):
        if rota_dia.clientes_rota.exists():
            return
        clientes = list(
            rota_padrao.clientes_rota.order_by('ordem', 'id').values_list('cliente_id', flat=True)
        )
        if not clientes:
            return
        RotaDiaCliente.objects.bulk_create(
            [RotaDiaCliente(rota_dia=rota_dia, cliente_id=cid, ordem=idx) for idx, cid in enumerate(clientes)]
        )

    def get(self, request):
        data_raw = request.GET.get('data')
        try:
            data_rota = date.fromisoformat(data_raw) if data_raw else date.today()
        except ValueError:
            data_rota = date.today()
        aplicar_padrao = request.GET.get('aplicar_padrao') == '1'

        rotas_padrao = (
            RotaPadrao.objects.filter(ativa=True)
            .select_related('responsavel')
            .order_by('nome')
        )
        rota_padrao_id = request.GET.get('rota_padrao') or ''
        rota_padrao = None
        if rota_padrao_id:
            rota_padrao = rotas_padrao.filter(pk=rota_padrao_id).first()

        rota_dia = None
        clientes_rota = []
        clientes_disponiveis = ClienteSankhya.objects.none()
        if rota_padrao:
            rota_dia, _created = self._load_or_create_rota_dia(data_rota, rota_padrao, request)
            rota_dia.rota_padrao = rota_padrao
            rota_dia.save(update_fields=['rota_padrao', 'atualizado_em'])
            if aplicar_padrao:
                clientes_padrao = list(
                    rota_padrao.clientes_rota.order_by('ordem', 'id').values_list('cliente_id', flat=True)
                )
                with transaction.atomic():
                    RotaDiaCliente.objects.filter(rota_dia=rota_dia).delete()
                    if clientes_padrao:
                        RotaDiaCliente.objects.bulk_create(
                            [
                                RotaDiaCliente(rota_dia=rota_dia, cliente_id=cid, ordem=idx)
                                for idx, cid in enumerate(clientes_padrao)
                            ]
                        )
                    _copiar_equipe_padrao_para_rota_dia(rota_dia, rota_padrao)
            else:
                self._seed_from_rota_padrao(rota_dia, rota_padrao)
                _ensure_equipe_from_padrao_if_empty(rota_dia, rota_padrao)
            clientes_rota = list(
                rota_dia.clientes_rota.select_related('cliente').order_by('ordem', 'id')
            )
            ids_na_rota = {item.cliente_id for item in clientes_rota}
            clientes_disponiveis = ClienteSankhya.objects.exclude(id__in=ids_na_rota).order_by(
                'nome',
                'razao',
                'codigo_cliente',
            )

        ajudantes_selecionados = []
        ajudantes_na_rota = []
        veiculos_disponiveis = Veiculo.objects.none()
        motoristas_disponiveis = Funcionario.objects.none()
        ajudantes_disponiveis = Funcionario.objects.none()
        if rota_dia:
            rota_dia = (
                RotaDia.objects.select_related('veiculo', 'motorista', 'rota_padrao')
                .prefetch_related(
                    'ajudantes_equipe__funcionario',
                )
                .get(pk=rota_dia.pk)
            )
            ajudantes_selecionados = list(
                rota_dia.ajudantes_equipe.order_by('ordem', 'id').values_list('funcionario_id', flat=True)
            )
            ajudantes_na_rota = list(
                rota_dia.ajudantes_equipe.select_related('funcionario').order_by('ordem', 'id')
            )
            v_ativos = _veiculos_ativos_qs()
            m_ativos = _motoristas_ativos_qs()
            a_ativos = _ajudantes_ativos_qs()
            if rota_dia.veiculo_id:
                veiculos_disponiveis = v_ativos.exclude(pk=rota_dia.veiculo_id)
            else:
                veiculos_disponiveis = v_ativos
            if rota_dia.motorista_id:
                motoristas_disponiveis = m_ativos.exclude(pk=rota_dia.motorista_id)
            else:
                motoristas_disponiveis = m_ativos
            if ajudantes_selecionados:
                ajudantes_disponiveis = a_ativos.exclude(id__in=ajudantes_selecionados)
            else:
                ajudantes_disponiveis = a_ativos

        return render(
            request,
            self.template_name,
            {
                'rota_dia': rota_dia,
                'data_rota': data_rota,
                'rotas_padrao': rotas_padrao,
                'rota_padrao_id_selecionada': str(rota_padrao_id or ''),
                'clientes_rota': clientes_rota,
                'clientes_disponiveis': clientes_disponiveis,
                'rota_selecionada': bool(rota_padrao),
                'veiculos_disponiveis': veiculos_disponiveis,
                'motoristas_disponiveis': motoristas_disponiveis,
                'ajudantes_disponiveis': ajudantes_disponiveis,
                'ajudantes_na_rota': ajudantes_na_rota,
                'ajudantes_selecionados': ajudantes_selecionados,
            },
        )

    def post(self, request):
        data_raw = request.POST.get('data')
        try:
            data_rota = date.fromisoformat(data_raw) if data_raw else date.today()
        except ValueError:
            messages.error(request, 'Data inválida para rota do dia.')
            return redirect('gestao_rotas_ecommerce')

        rota_padrao_id = request.POST.get('rota_padrao')
        rota_padrao = RotaPadrao.objects.filter(pk=rota_padrao_id, ativa=True).first() if rota_padrao_id else None
        only_check = request.POST.get('only_check') == '1'
        if not rota_padrao:
            if only_check:
                return JsonResponse({'ok': False, 'error': 'Selecione uma rota padrão.'}, status=400)
            messages.error(request, 'Selecione uma rota padrão para montar a rota executada.')
            query = urlencode({'data': data_rota.isoformat()})
            return redirect(f"{reverse('gestao_rota_dia_builder')}?{query}")

        rota_dia, _created = self._load_or_create_rota_dia(data_rota, rota_padrao, request)
        observacao_post = (request.POST.get('observacao') or '').strip()

        cliente_ids = []
        for cid in request.POST.getlist('clientes_rota'):
            try:
                cliente_ids.append(int(cid))
            except (TypeError, ValueError):
                continue

        valid_ids = set(ClienteSankhya.objects.filter(id__in=cliente_ids).values_list('id', flat=True))
        cliente_ids_validos = [cid for cid in cliente_ids if cid in valid_ids]

        veiculo_raw = (request.POST.get('veiculo') or '').strip()
        motorista_raw = (request.POST.get('motorista') or '').strip()
        ajudante_ids_post = []
        for aid in request.POST.getlist('ajudantes'):
            try:
                ajudante_ids_post.append(int(aid))
            except (TypeError, ValueError):
                continue

        veiculo_eq = None
        if veiculo_raw:
            veiculo_eq = Veiculo.objects.filter(pk=veiculo_raw, status_inicial='Ativo').first()
            if not veiculo_eq:
                msg = 'Selecione um veículo ativo válido.'
                if only_check:
                    return JsonResponse({'ok': False, 'error': msg}, status=400)
                messages.error(request, msg)
                query = urlencode({'data': data_rota.isoformat(), 'rota_padrao': str(rota_padrao.id)})
                return redirect(f"{reverse('gestao_rota_dia_builder')}?{query}")

        motorista_eq = None
        if motorista_raw:
            motorista_eq = Funcionario.objects.filter(
                pk=motorista_raw, tipo='Motorista', status='Ativo'
            ).first()
            if not motorista_eq:
                msg = 'Selecione um motorista ativo válido.'
                if only_check:
                    return JsonResponse({'ok': False, 'error': msg}, status=400)
                messages.error(request, msg)
                query = urlencode({'data': data_rota.isoformat(), 'rota_padrao': str(rota_padrao.id)})
                return redirect(f"{reverse('gestao_rota_dia_builder')}?{query}")

        ajudantes_validos_set = set(
            Funcionario.objects.filter(
                id__in=ajudante_ids_post, tipo='Ajudante', status='Ativo'
            ).values_list('id', flat=True)
        )
        ajudantes_ordenados = list(
            dict.fromkeys([fid for fid in ajudante_ids_post if fid in ajudantes_validos_set])
        )

        conflitos_qs = (
            RotaDiaCliente.objects.select_related('rota_dia__rota_padrao', 'cliente')
            .filter(
                rota_dia__data=data_rota,
                cliente_id__in=cliente_ids_validos,
            )
            .exclude(rota_dia=rota_dia)
        )
        conflitos = []
        for item in conflitos_qs:
            nome_rota = (
                item.rota_dia.rota_padrao.nome
                if item.rota_dia.rota_padrao
                else f'Rota #{item.rota_dia_id}'
            )
            conflitos.append(
                {
                    'cliente_id': item.cliente_id,
                    'cliente': item.cliente.nome or item.cliente.razao or f'Cliente {item.cliente.codigo_cliente}',
                    'codigo_cliente': item.cliente.codigo_cliente,
                    'rota_id': item.rota_dia_id,
                    'rota': nome_rota,
                }
            )

        conflito_veiculo = None
        if veiculo_eq:
            outro_v = (
                RotaDia.objects.filter(data=data_rota, veiculo_id=veiculo_eq.pk)
                .exclude(pk=rota_dia.pk)
                .select_related('rota_padrao')
                .first()
            )
            if outro_v:
                conflito_veiculo = {
                    'veiculo': f'{veiculo_eq.placa} — {veiculo_eq.descricao}',
                    'rota': _nome_rota_dia_executada(outro_v),
                    'rota_id': outro_v.pk,
                }

        conflito_motorista = None
        if motorista_eq:
            outro_m = (
                RotaDia.objects.filter(data=data_rota, motorista_id=motorista_eq.pk)
                .exclude(pk=rota_dia.pk)
                .select_related('rota_padrao')
                .first()
            )
            if outro_m:
                conflito_motorista = {
                    'motorista': f'{motorista_eq.nome} ({motorista_eq.codigo_erp})',
                    'rota': _nome_rota_dia_executada(outro_m),
                    'rota_id': outro_m.pk,
                }

        conflitos_ajudantes_equipe = []
        if ajudantes_ordenados:
            vistos = set()
            for fid in ajudantes_ordenados:
                for row in (
                    RotaDiaAjudante.objects.filter(
                        funcionario_id=fid,
                        rota_dia__data=data_rota,
                    )
                    .exclude(rota_dia=rota_dia)
                    .select_related('rota_dia__rota_padrao', 'funcionario')
                ):
                    chave = (row.funcionario_id, row.rota_dia_id)
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    f = row.funcionario
                    conflitos_ajudantes_equipe.append(
                        {
                            'funcionario_id': fid,
                            'nome': f'{f.nome} ({f.codigo_erp})',
                            'rota': _nome_rota_dia_executada(row.rota_dia),
                            'rota_id': row.rota_dia_id,
                        }
                    )

        tem_conflito = bool(
            conflitos
            or conflito_veiculo
            or conflito_motorista
            or conflitos_ajudantes_equipe
        )

        if tem_conflito:
            payload_conflitos = {
                'ok': False,
                'conflitos': conflitos,
                'conflito_veiculo': conflito_veiculo,
                'conflito_motorista': conflito_motorista,
                'conflitos_ajudantes': conflitos_ajudantes_equipe,
            }
            if only_check:
                return JsonResponse(payload_conflitos, status=409)
            messages.error(
                request,
                'Não é possível salvar: há conflito com outra rota executada nesta data. '
                'Ajuste clientes, veículo, motorista ou ajudantes nas outras rotas e tente novamente.',
            )
            query = urlencode({'data': data_rota.isoformat(), 'rota_padrao': str(rota_padrao.id)})
            return redirect(f"{reverse('gestao_rota_dia_builder')}?{query}")

        if only_check:
            return JsonResponse({'ok': True, 'conflitos': []})

        with transaction.atomic():
            rota_dia.rota_padrao = rota_padrao
            rota_dia.observacao = observacao_post
            rota_dia.veiculo = veiculo_eq
            rota_dia.motorista = motorista_eq
            rota_dia.save(
                update_fields=[
                    'rota_padrao',
                    'observacao',
                    'veiculo',
                    'motorista',
                    'atualizado_em',
                ]
            )
            RotaDiaCliente.objects.filter(rota_dia=rota_dia).delete()
            RotaDiaCliente.objects.bulk_create(
                [
                    RotaDiaCliente(rota_dia=rota_dia, cliente_id=cid, ordem=idx)
                    for idx, cid in enumerate(cliente_ids_validos)
                ]
            )
            RotaDiaAjudante.objects.filter(rota_dia=rota_dia).delete()
            if ajudantes_ordenados:
                RotaDiaAjudante.objects.bulk_create(
                    [
                        RotaDiaAjudante(rota_dia=rota_dia, funcionario_id=fid, ordem=idx)
                        for idx, fid in enumerate(ajudantes_ordenados)
                    ]
                )

        messages.success(request, 'Rota do dia salva com sucesso.')
        query = urlencode(
            {
                'data_ini': data_rota.isoformat(),
                'data_fim': data_rota.isoformat(),
                'rota_padrao': str(rota_padrao.id),
            }
        )
        return redirect(f"{reverse('gestao_rotas_dia_list')}?{query}")