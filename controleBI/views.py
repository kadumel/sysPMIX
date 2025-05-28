from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Funcionario, Veiculo, Pedido, ItemPedido, Auditoria
from .forms import VeiculoForm
from .services import FuncionarioService, PedidoService
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth.mixins import LoginRequiredMixin
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
import time
import traceback
from .services import VeiculoService, PedidoService, FuncionarioService, ClienteService
from django.db import connections


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

class IndexView(LoginRequiredMixin, View):
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

class DashboardView(LoginRequiredMixin, View):
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

class ListFuncionarioView(LoginRequiredMixin, ListView):
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

class CadastrarFuncionarioView(LoginRequiredMixin, View):
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

class ListVeiculoView(LoginRequiredMixin, ListView):
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

class CadastrarVeiculoView(LoginRequiredMixin, View):
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

class CadastrarPedidoView(LoginRequiredMixin, View):
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

class ListPedidoView(LoginRequiredMixin, View):
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
        
        # Paginação
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
            'current_page': current_page
        }
        
        return render(request, 'pedido/listPedido.html', context)

class ViewPedidoView(LoginRequiredMixin, View):
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

class DeletePedidoView(LoginRequiredMixin, View):
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
def sync_pedido_batch(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            pedido_ids = data.get('pedido_ids', [])
            
            if not pedido_ids:
                return JsonResponse({'success': False, 'message': 'Nenhum pedido selecionado'})
            
            # Buscar pedidos não sincronizados
            pedidos = Pedido.objects.filter(id__in=pedido_ids, sincronizado=False)
            
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

class RelatorioPedidoView(LoginRequiredMixin, View):
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

class VeiculoDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        veiculo = get_object_or_404(Veiculo, pk=pk)
        
        context = {
            'veiculo': veiculo
        }
        
        return render(request, 'veiculo/veiculo_detail.html', context)
    
    def post(self, request, pk):
        return self.get(request, pk)

class VeiculoEditView(LoginRequiredMixin, View):
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

class VeiculoDeleteView(LoginRequiredMixin, View):
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

class FuncionarioEditView(LoginRequiredMixin, UpdateView):
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

class FuncionarioDeleteView(LoginRequiredMixin, View):
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
                obs=f"Iniciando importação de pedidos via SP_ATUALIZA_PEDIDO. Tentativa {retry_count + 1} de {max_retries}."
            )
            
            # Fechar todas as conexões existentes
            connection.close()
            
            # Criar nova conexão
            with connection.cursor() as cursor:
                # Executar a stored procedure

                cursor.execute("exec sp_atualiza_cliente")
                cursor.execute("EXEC SP_ATUALIZA_PEDIDO")
                
                # Obter o número de registros afetados
                rowcount = cursor.rowcount

                print(rowcount)
                
                # Fechar a conexão explicitamente
                cursor.close()
                connection.close()
                
                # Registrar sucesso na auditoria
                Auditoria.objects.create(
                    origem="Importação de Pedidos",
                    user=request.user,
                    obs=f"Importação de pedidos realizada com sucesso via SP_ATUALIZA_PEDIDO. {rowcount} pedido(s) afetado(s)."
                )

                msgCliente = ''
                try:
                    enviados, msgCliente = ClienteService.enviar_dados()
                    msgCliente = 'Clientes e endereços enviados e sincronizados com sucesso'
                except Exception as e:
                    msgCliente = f"Erro ao enviar clientes: {str(e)}"

               
                atualizado, msgAtualizacaoNF = atualizar_nf_pedidos()
                
                
                return JsonResponse({
                    'success': True,
                    'message': f'{rowcount} pedido(s) importado(s) com sucesso! \n {msgCliente} \n {msgAtualizacaoNF}'
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
                    'operation': 'SP_ATUALIZA_PEDIDO'
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
                obs=f"Iniciando importação de veículos via SP_ATUALIZA_VEICULO. Tentativa {retry_count + 1} de {max_retries}."
            )
            
            # Fechar todas as conexões existentes
            connection.close()
            
            # Criar nova conexão
            with connection.cursor() as cursor:
                # Executar a stored procedure
                cursor.execute("EXEC SP_ATUALIZA_VEICULO")
                
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
                            obs=f"Importação de veículos realizada com sucesso via SP_ATUALIZA_VEICULO. {rowcount} veículo(s) afetado(s). {total_nao_sincronizados} veículo(s) sincronizado(s) com o webservice."
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
                        obs=f"Importação de veículos realizada com sucesso via SP_ATUALIZA_VEICULO. {rowcount} veículo(s) afetado(s). Nenhum veículo para sincronizar."
                    )
                
                return JsonResponse({
                    'success': True,
                    'message': f'{rowcount} veículo(s) importado(s) com sucesso! {total_nao_sincronizados} veículo(s) sincronizado(s) com o webservice.'
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
                    'operation': 'SP_ATUALIZA_VEICULO'
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
                    obs=f"Iniciando importação de funcionários via SP_ATUALIZA_FUNCIONARIO. Tentativa {retry_count + 1} de {max_retries}."
                )

                # Close any existing connections

                connections.close_all()

                # Create a new connection to the ERP database
                with connection.cursor() as cursor:
                    # Execute the stored procedure
                    try:
                        cursor.execute("EXEC SP_ATUALIZA_FUNCIONARIO")
                        rowcount = cursor.rowcount
                    except Exception as e:
                        print(f"Erro ao executar SP_ATUALIZA_FUNCIONARIO: {str(e)}")
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
                        obs=f"Importação de funcionários realizada com sucesso via SP_ATUALIZA_FUNCIONARIO. {rowcount} funcionário(s) afetado(s). {total_nao_sincronizados} funcionário(s) sincronizado(s) com o webservice."
                    )
                else:
                    Auditoria.objects.create(
                        origem='Funcionario',
                        user=request.user,
                        obs=f"Importação de funcionários realizada com sucesso via SP_ATUALIZA_FUNCIONARIO. {rowcount} funcionário(s) afetado(s). Nenhum funcionário para sincronizar."
                    )

                return JsonResponse({
                    'success': True,
                    'message': f'Importação realizada com sucesso. {rowcount} funcionário(s) afetado(s). {total_nao_sincronizados} funcionário(s) sincronizado(s).'
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


def atualizar_nf_pedidos():
    """
    View para atualizar os dados de nota fiscal dos pedidos.
    Atualiza pedidos onde o campo nf é igual ao pedido_erp e a serie is 99
    """
    try:
        connection.close()
            
        # Criar nova conexão
        with connection.cursor() as cursor:
            # Executar a stored procedure
            cursor.execute("EXEC SP_ATUALIZA_NF_PEDIDO")
            
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

            pedidos = Pedido.objects.filter(tipo=3)
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
        Auditoria.objects.create(
            origem="Atualização de Nota Fiscal do Pedido",
            user=request.user,
            obs=f"ERROR: {str(e)}"
        )
        return False, f"ERROR: {str(e)}"