from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _
from .models import *
from django.contrib import messages
from .services import FuncionarioService, VeiculoService, PedidoService

# Personalizando o título e o cabeçalho
admin.site.site_header = _('Pannemix')
admin.site.site_title = _('Pannemix')
admin.site.index_title = _('Pannemix')



@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'cliente', 'fantasia', 'cnpj', 'sincronizado')
    search_fields = ('codigo', 'cliente', 'fantasia', 'cnpj')
    list_filter = ('codigo', 'cliente', 'fantasia', 'cnpj')
    fields = ('codigo', 'cliente', 'fantasia', 'cnpj', 'sincronizado')
    list_per_page = 10

@admin.register(ClienteERP)
class ClienteERPAdmin(admin.ModelAdmin):
    list_display = ('codigo_cliente', 'descr_cliente', 'razao_cliente', 'cnpj_cpf_cliente', 'cidade_cliente', 'uf_cliente', 'sincronizado')
    search_fields = ('codigo_cliente', 'descr_cliente', 'razao_cliente', 'cnpj_cpf_cliente', 'cidade_cliente')
    list_filter = ('uf_cliente', 'cidade_cliente', 'sincronizado', 'prioritario', 'bloqueiosefaz')
    
    fieldsets = (
        ('Informações Principais', {
            'fields': ('campo_alt', 'seq_id', 'codigo_cliente', 'filial_padrao', 'descr_cliente', 'razao_cliente', 'cnpj_cpf_cliente')
        }),
        ('Rota e Segmento', {
            'fields': ('cliente_cod_rota_erp', 'cliente_descricao_rota', 'cod_segmento', 'descr_segmento')
        }),
        ('Endereço', {
            'fields': ('cep_cliente', 'end_cliente', 'num_end_cliente', 'bairro_cliente', 'cidade_cliente', 'uf_cliente')
        }),
        ('Contato', {
            'fields': ('email1_cliente', 'email2_cliente', 'email3_cliente', 'tel1_cliente', 'tel2_cliente', 'tel3_cliente')
        }),
        ('Informações Financeiras', {
            'fields': ('data_cadastro_cliente', 'vlr_credito_cliente', 'saldo_disp_cliente', 'vlr_tits_vencido_cliente', 
                      'vlr_tits_vencer_cliente', 'status_cred_cliente', 'data_ult_compra', 'forma_pgto_cliente')
        }),
        ('Configurações Adicionais', {
            'fields': ('turnos_entrega', 'prioritario', 'bloqueiosefaz', 'rede_loja_cliente', 'sincronizado')
        })
    )
    list_per_page = 10

@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    fields = ('codigo_erp', 'nome', 'cpf', 'tipo')
    list_display = ('codigo_erp', 'nome', 'cpf', 'tipo')
    search_fields = ('codigo_erp', 'nome', 'cpf', 'tipo')
    list_filter = ('codigo_erp', 'nome', 'cpf', 'tipo')
    list_per_page = 10

     # Adiciona a ação personalizada
    actions = ['enviar_para_webservice']
    
    def enviar_para_webservice(self, request, queryset):
        total = 0
        print(queryset)
        for funcionario in queryset:
            if not funcionario.sincronizado:
                sucesso, mensagem = FuncionarioService.enviar_dados(funcionario)

                if sucesso:
                    total += 1
                else:
                    self.message_user(request, f'Erro ao enviar {funcionario.nome}: {mensagem}', level=messages.ERROR)
        
        if total > 0:
            self.message_user(request, f'{total} funcionário(s) enviado(s) com sucesso!', level=messages.SUCCESS)
        else:
            self.message_user(request, 'Nenhum funcionário foi enviado.', level=messages.WARNING)
    
    enviar_para_webservice.short_description = "Enviar selecionados para o webservice"
    

@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'vendedor','apelido','cpf', 'flat_tecnico', 'sincronizado')
    search_fields = ('codigo', 'vendedor','apelido','cpf')
    list_filter = ('codigo', 'vendedor','apelido','cpf')
    fields = ('codigo', 'vendedor','apelido','cpf', 'flat_tecnico', 'sincronizado')
    list_per_page = 10

    

@admin.register(ClienteVendedor)
class ClienteVendedorAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'vendedor', 'secao', 'data_referencia', 'percentual_comissao', 'flat')
    search_fields = ('cliente', 'vendedor', 'secao', 'data_referencia', 'percentual_comissao', 'flat')
    list_filter = ('cliente', 'vendedor', 'secao', 'data_referencia', 'percentual_comissao', 'flat')
    list_per_page = 10

@admin.register(Operacao)
class OperacaoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'operacao')
    search_fields = ('codigo', 'operacao')
    list_filter = ('codigo', 'operacao')
    list_per_page = 10


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    fields = ('codigo_erp','placa','descricao','modelo','ano_modelo','ano_fabricacao','qtd_max_entregas','velocidade_maxima','tipo_combustivel','status_inicial','peso_max_entregas','volume_max_entregas','qtd_pallets_veiculo','filial')
    list_display = ('codigo_erp', 'placa', 'descricao',  'tipo_combustivel', 'status_inicial', 'peso_max_entregas', 'volume_max_entregas', 'qtd_pallets_veiculo', 'filial')
    search_fields = ('codigo_erp', 'placa', 'descricao','filial')
    list_filter = ('codigo_erp', 'placa', 'descricao','filial')
    list_per_page = 10
    
        # Adiciona a ação personalizada
    actions = ['enviar_para_webservice']
    
    def enviar_para_webservice(self, request, queryset):
        total = 0
        for veiculo in queryset:
            if not veiculo.sincronizado:
                sucesso, mensagem = VeiculoService.enviar_dados(veiculo)
                if sucesso:
                    total += 1
                else:
                    self.message_user(request, f'Erro ao enviar {veiculo.placa}: {mensagem}', level=messages.ERROR)
        
        if total > 0:
            self.message_user(request, f'{total} veículo(s) enviado(s) com sucesso!', level=messages.SUCCESS)
        else:
            self.message_user(request, 'Nenhum veículo foi enviado.', level=messages.WARNING)
    
    enviar_para_webservice.short_description = "Enviar selecionados para o webservice"



@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('pedido_erp', 'nf', 'descr_cliente', 'status', 'valor', 'data_pedido', 'ent_ou_serv', 'sincronizado')
    search_fields = ('pedido_erp', 'nf', 'descr_cliente', 'razao_cliente', 'cnpj_cliente')
    list_filter = ('status', 'ent_ou_serv', 'empresa_fat', 'empresa_log','sincronizado')
    list_per_page = 10
    
    fieldsets = (
        ('Informações da Nota Fiscal', {
            'fields': ('nf', 'chave_nfe', 'serie', 'tipo', 'ent_ou_serv','prioridade','sincronizado')
        }),
        ('Informações do Pedido', {
            'fields': ('data_pedido','pedido_erp',  'vendedor_erp', 'forma_pgto', 'status', 'obs', 'num_ped_conf', 'carga')
        }),
        ('Medidas e Valores', {
            'fields': ('cubagem', 'podeformarcarga', 'valor', 'peso', 'qtd_pallets_entrega', 'valor_st')
        }),
        ('Informações das Empresas', {
            'fields': ('empresa_fat', 'empresa_log', 'empresa_digit', 'pedido_orig','dt_list_nf')
        }),
        ('Informações do Cliente', {
            'fields': ('codigo_cliente','descr_cliente', 'razao_cliente', 'cnpj_cliente', 'end_cliente', 'bairro_cliente', 'num_end_cliente', 'uf_cliente', 
                       'cidade_cliente', 'cep_cliente', 'retem_icms_cliente', 'permite_retira_cliente', 'rede_loja_cliente')
        }),
        ('Informações de Contato', {
            'fields': ('email1_cliente', 'email2_cliente', 'email3_cliente', 'tel1_cliente', 'tel2_cliente', 'tel3_cliente')
        }),
        ('Informações financeiras', {
            'fields': ('vlr_credito_cliente', 'data_cadastro_cliente', 'saldo_disp_cliente', 'vlr_tits_vencido_cliente', 'vlr_tits_vencer_cliente', 
                       'status_cred_cliente')
        }),
        ('Informações de Rota', {
            'fields': ('praca_cod_erp', 'praca_descricao', 'rota_cod_erp', 'rota_descricao')
        }),
        ('Informações de Segmento', {
            'fields': ('cod_segmento', 'descr_segmento', 'filial_padrao','data_ult_compra','forma_pgto_cliente')
        }),
        ('Informações Adicionais', {
            'fields': ('codigo_endereco_alt', 'referencia_entrega', 'restricao_transp', 'latitude', 'longitude',
                       'valor_adic_number_1','valor_adic_number_2','tipo_nota_fiscal')
        })
        )

    actions = ['enviar_pedidos_webservice']

    def enviar_pedidos_webservice(self, request, queryset):
        total = 0
        for pedido in queryset:
            if not pedido.sincronizado:
                sucesso, mensagem = PedidoService.enviar_dados([pedido])
                if sucesso:
                    Pedido.objects.filter(pk=pedido.pk).update(sincronizado=True)
                    total += 1
                else:
                    self.message_user(request, f'Erro ao enviar {pedido.pedido_erp}: {mensagem}', level=messages.ERROR)
        
        if total > 0:
            self.message_user(request, f'{total} pedido(s) enviado(s) com sucesso!', level=messages.SUCCESS)
        else:
            self.message_user(request, 'Nenhum pedido foi enviado.', level=messages.WARNING)

    enviar_pedidos_webservice.short_description = "Enviar selecionados para o webservice"


@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'cod_produto_erp', 'descricao', 'unidade', 'qtd', 'preco', 'subtotal')
    search_fields = ('pedido', 'cod_produto_erp', 'descricao')
    list_filter = ('pedido', 'cod_produto_erp', 'descricao')
    list_per_page = 10


@admin.register(EnderecoCliente)
class EnderecoClienteAdmin(admin.ModelAdmin):
    list_display = ('clienteERP', 'end', 'num_end', 'bairro', 'cidade', 'uf', 'sn_padrao', 'sincronizado')
    search_fields = ('clienteERP__descr_cliente', 'end', 'bairro', 'cidade', 'cod_end_erp')
    list_filter = ('uf', 'cidade', 'sn_padrao', 'sincronizado')
    
    fieldsets = (
        ('Cliente', {
            'fields': ('cliente',)
        }),
        ('Informações do Endereço', {
            'fields': ('cod_end_erp', 'end', 'num_end', 'bairro', 'cidade', 'uf', 'cep')
        }),
        ('Praça', {
            'fields': ('cod_praca_erp', 'descr_praca_erp')
        }),
        ('Configurações', {
            'fields': ('ref_entrega', 'sn_padrao', 'latitude', 'longitude', 'sincronizado')
        })
    )
    list_per_page = 10



