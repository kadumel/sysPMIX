from django.contrib import admin
from .models import (
    Veiculo, Empresa, Cidade, Logradouro, Bairro, Vendedor, Cliente, Motorista,
    Preco, Produto, GrupoProduto, Pedido, ItemPedido, Contato
)


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ('codigo_veiculo', 'placa', 'marca_modelo', 'nome_motorista', 'nome_cidade', 'ativo', 'updated_at')
    list_filter = ('ativo', 'combustivel', 'codigo_cidade')
    search_fields = ('placa', 'marca_modelo', 'nome_motorista', 'nome_parceiro', 'codigo_veiculo')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo_veiculo', 'placa', 'marca_modelo', 'categoria', 'cor')
        }),
        ('Documentação', {
            'fields': ('numero_motor', 'renavam', 'chassis')
        }),
        ('Especificações', {
            'fields': ('peso_maximo', 'combustivel', 'ano_fabricacao', 'ano_modelo')
        }),
        ('Localização', {
            'fields': ('codigo_cidade', 'nome_cidade')
        }),
        ('Responsáveis', {
            'fields': ('codigo_funcionario', 'nome_funcionario', 'codigo_motorista', 'nome_motorista')
        }),
        ('Parceiro', {
            'fields': ('codigo_parceiro', 'nome_parceiro')
        }),
        ('Status', {
            'fields': ('ativo',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('codigo_empresa', 'nome_fantasia', 'razao_social', 'cnpj_cpf', 'nome_cidade', 'updated_at')
    list_filter = ('codigo_cidade', 'codigo_empresa_matriz')
    search_fields = ('codigo_empresa', 'nome_fantasia', 'razao_social', 'cnpj_cpf', 'email', 'nome_cidade')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo_empresa', 'nome_fantasia', 'razao_social', 'razao_abreviada')
        }),
        ('Documentação', {
            'fields': ('cnpj_cpf', 'inscricao_estadual', 'inscricao_municipal')
        }),
        ('Contato', {
            'fields': ('telefone', 'email', 'homepage')
        }),
        ('Endereço', {
            'fields': ('codigo_logradouro', 'nome_logradouro', 'numero', 'complemento')
        }),
        ('Localização', {
            'fields': ('codigo_bairro', 'nome_bairro', 'codigo_cidade', 'nome_cidade', 'cep')
        }),
        ('Relações', {
            'fields': ('codigo_empresa_matriz',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ('codigo_cidade', 'nome', 'uf', 'codigo_regiao', 'dt_alteracao', 'nome_regiao', 'codigo_municipio_fiscal', 'updated_at')
    list_filter = ('uf', 'codigo_regiao')
    search_fields = ('codigo_cidade', 'nome', 'uf', 'nome_regiao', 'nome_correio', 'codigo_municipio_fiscal')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Legado CRUD (getCidadeLegado)', {
            'fields': ('codigo_cidade', 'nome', 'uf', 'codigo_regiao', 'dt_alteracao')
        }),
        ('API v1 / complemento', {
            'fields': ('nome_regiao', 'nome_correio', 'codigo_municipio_fiscal')
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Logradouro)
class LogradouroAdmin(admin.ModelAdmin):
    list_display = ('codigo_logradouro', 'tipo', 'nome', 'descricao_correio', 'updated_at')
    list_filter = ('tipo',)
    search_fields = ('codigo_logradouro', 'nome', 'tipo', 'descricao_correio')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo_logradouro', 'nome', 'tipo')
        }),
        ('Dados Correio', {
            'fields': ('descricao_correio',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Bairro)
class BairroAdmin(admin.ModelAdmin):
    list_display = ('codigo_bairro', 'nome', 'nome_regiao', 'nome_correio', 'updated_at')
    list_filter = ('nome_regiao',)
    search_fields = ('codigo_bairro', 'nome', 'nome_regiao', 'nome_correio')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo_bairro', 'nome')
        }),
        ('Região', {
            'fields': ('nome_regiao',)
        }),
        ('Dados Correio', {
            'fields': ('nome_correio',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ('codigo_vendedor', 'nome', 'ativo', 'email', 'nome_empresa', 'nome_gerente', 'updated_at')
    list_filter = ('ativo', 'tipo', 'codigo_empresa', 'codigo_regiao')
    search_fields = ('codigo_vendedor', 'nome', 'email', 'nome_empresa', 'nome_parceiro', 'nome_funcionario', 'nome_gerente')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo_vendedor', 'nome', 'ativo', 'tipo', 'email')
        }),
        ('Comissões', {
            'fields': ('comissao_gerencia', 'comissao_venda')
        }),
        ('Empresa', {
            'fields': ('codigo_empresa', 'nome_empresa')
        }),
        ('Parceiro', {
            'fields': ('codigo_parceiro', 'nome_parceiro')
        }),
        ('Funcionário', {
            'fields': ('codigo_funcionario', 'nome_funcionario')
        }),
        ('Gerência', {
            'fields': ('codigo_gerente', 'nome_gerente')
        }),
        ('Centro de Resultado', {
            'fields': ('codigo_centro_resultado', 'nome_centro_resultado')
        }),
        ('Região', {
            'fields': ('codigo_regiao', 'nome_regiao')
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('codigo_cliente', 'nome', 'tipo', 'cnpj_cpf', 'email', 'cidade', 'uf', 'updated_at')
    list_filter = ('tipo', 'uf', 'cidade', 'grupo_autorizacao')
    search_fields = ('codigo_cliente', 'nome', 'razao', 'cnpj_cpf', 'email', 'telefone_numero', 'cidade', 'bairro')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo_cliente', 'tipo', 'nome', 'razao')
        }),
        ('Documentação', {
            'fields': ('cnpj_cpf', 'ie_rg')
        }),
        ('Contato', {
            'fields': ('email', 'telefone_ddd', 'telefone_numero')
        }),
        ('Financeiro', {
            'fields': ('limite_credito', 'grupo_autorizacao')
        }),
        ('Endereço', {
            'fields': ('logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf', 'cep', 'codigo_ibge')
        }),
        ('Localização GPS', {
            'fields': ('latitude', 'longitude')
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = ('codigo_motorista', 'nome', 'cpf', 'cnh', 'categoria_cnh', 'cidade', 'uf', 'updated_at')
    list_filter = ('categoria_cnh', 'uf', 'cidade')
    search_fields = ('codigo_motorista', 'nome', 'cpf', 'rg', 'cnh', 'email', 'telefone', 'cidade', 'bairro')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo_motorista', 'nome', 'email', 'telefone')
        }),
        ('Documentação', {
            'fields': ('cpf', 'rg', 'cnh', 'categoria_cnh', 'data_vencimento_cnh')
        }),
        ('Endereço', {
            'fields': ('logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf', 'cep', 'codigo_ibge')
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Preco)
class PrecoAdmin(admin.ModelAdmin):
    list_display = ('codigo_produto', 'codigo_tabela', 'codigo_local_estoque', 'valor', 'unidade', 'controle', 'updated_at')
    list_filter = ('codigo_tabela', 'codigo_local_estoque', 'unidade', 'controle')
    search_fields = ('codigo_produto', 'codigo_tabela', 'codigo_local_estoque', 'controle', 'unidade')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo_produto', 'codigo_tabela', 'codigo_local_estoque')
        }),
        ('Preço', {
            'fields': ('valor', 'unidade', 'controle')
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('codigo_produto', 'nome', 'referencia', 'marca', 'codigo_grupo_produto', 'ativo', 'updated_at')
    list_filter = ('ativo', 'codigo_grupo_produto', 'tipo_controle_estoque', 'utiliza_balanca', 'codigo_pais')
    search_fields = ('codigo_produto', 'nome', 'complemento', 'referencia', 'marca', 'ncm', 'cest', 'referencia_fornecedor')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo_produto', 'nome', 'complemento', 'data_alteracao')
        }),
        ('Descrição', {
            'fields': ('caracteristicas',)
        }),
        ('Identificação', {
            'fields': ('referencia', 'referencia_fornecedor', 'marca', 'volume')
        }),
        ('Grupo e Classificação', {
            'fields': ('codigo_grupo_produto', 'nome_grupo_produto', 'grupo_desconto', 'usado_como')
        }),
        ('Dimensões e Medidas', {
            'fields': ('peso_bruto', 'altura', 'largura', 'espessura', 'metro_cubico', 'unidade_medida')
        }),
        ('Estoque', {
            'fields': ('tipo_controle_estoque', 'estoque_minimo', 'estoque_maximo', 'agrupamento_minimo', 'quantidade_embalagem')
        }),
        ('Configurações', {
            'fields': ('decimais_valor', 'decimais_quantidade', 'utiliza_balanca', 'ativo')
        }),
        ('Fiscal', {
            'fields': ('ncm', 'cest', 'cnae', 'codigo_pais')
        }),
        ('Outros', {
            'fields': ('homepage',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GrupoProduto)
class GrupoProdutoAdmin(admin.ModelAdmin):
    list_display = (
        'codigo_grupo_produto',
        'nome',
        'codigo_grupo_produto_pai',
        'grau',
        'grupo_icms',
        'analitico',
        'ativo',
        'mostrar_no_ecommerce',
        'updated_at',
    )
    list_filter = ('ativo', 'analitico', 'mostrar_no_ecommerce', 'grau', 'grupo_icms')
    search_fields = ('codigo_grupo_produto', 'nome', 'codigo_grupo_produto_pai')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo_grupo_produto', 'nome', 'codigo_grupo_produto_pai', 'grau')
        }),
        ('Configurações', {
            'fields': ('grupo_icms', 'analitico', 'ativo', 'mostrar_no_ecommerce')
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    fields = ('sequencia', 'cod_produto', 'descricao_produto', 'quantidade', 'unidade', 'valor_unitario', 'valor_total', 'ncm', 'valor_icms')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('codigo_nota', 'numero_nota', 'codigo_cliente', 'cliente_nome', 'data_negociacao', 'valor_nota', 'entrega', 'pendente', 'confirmada', 'updated_at')
    list_filter = ('pendente', 'confirmada', 'entrega', 'codigo_empresa', 'endereco_uf')
    search_fields = ('codigo_nota', 'numero_nota', 'codigo_cliente', 'cliente_nome', 'cliente_razao', 'cliente_cnpj_cpf')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 30
    inlines = [ItemPedidoInline]
    
    fieldsets = (
        ('Nota', {
            'fields': ('codigo_nota', 'numero_nota', 'serie_nota', 'codigo_empresa', 'nome_empresa')
        }),
        ('Cliente', {
            'fields': ('codigo_cliente', 'cliente_tipo', 'cliente_cnpj_cpf', 'cliente_ie_rg', 'cliente_nome', 'cliente_razao', 'cliente_email', 'cliente_telefone')
        }),
        ('Endereço', {
            'fields': ('endereco_logradouro', 'endereco_numero', 'endereco_complemento', 'endereco_bairro', 'endereco_cidade', 'endereco_uf', 'endereco_cep', 'endereco_codigo_ibge', 'entrega')
        }),
        ('Status', {
            'fields': ('confirmada', 'pendente', 'data_negociacao', 'data_hora_alteracao')
        }),
        ('Tipo / Operação', {
            'fields': ('codigo_tipo_negociacao', 'nome_tipo_negociacao', 'codigo_tipo_operacao', 'nome_tipo_operacao', 'codigo_natureza')
        }),
        ('Valores', {
            'fields': ('valor_nota', 'desconto_total', 'valor_frete', 'valor_seguro', 'valor_outros')
        }),
        ('Logística', {
            'fields': ('codigo_ordem_carga', 'codigo_transportadora', 'nome_transportadora', 'codigo_veiculo', 'placa_veiculo', 'codigo_motorista', 'nome_motorista', 'quantidade_volumes', 'peso_bruto')
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Contato)
class ContatoAdmin(admin.ModelAdmin):
    list_display = ('codparc', 'codcontato', 'nomecontato', 'apelido', 'email', 'telefone', 'celular', 'codcid', 'updated_at')
    list_filter = ('codcid',)
    search_fields = ('codparc', 'codcontato', 'nomecontato', 'apelido', 'email', 'telefone', 'celular')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50

    fieldsets = (
        ('Parceiro / Contato', {
            'fields': ('codparc', 'codcontato', 'nomecontato', 'apelido')
        }),
        ('Endereço', {
            'fields': ('codend', 'numend', 'complemento', 'codbai', 'codcid', 'cep')
        }),
        ('Contato', {
            'fields': ('telefone', 'email', 'celular')
        }),
        ('Localização', {
            'fields': ('latitude', 'longitude')
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
