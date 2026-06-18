from django.db import models


class Veiculo(models.Model):
    """
    Modelo para armazenar dados de veículos da API Sankhya
    """
    codigo_veiculo = models.IntegerField(unique=True, verbose_name="Código do Veículo")
    placa = models.CharField(max_length=10, verbose_name="Placa")
    marca_modelo = models.CharField(max_length=100, null=True, blank=True, verbose_name="Marca/Modelo")
    numero_motor = models.CharField(max_length=50, null=True, blank=True, verbose_name="Número do Motor")
    renavam = models.CharField(max_length=20, null=True, blank=True, verbose_name="RENAVAM")
    chassis = models.CharField(max_length=50, null=True, blank=True, verbose_name="Chassis")
    categoria = models.CharField(max_length=50, null=True, blank=True, verbose_name="Categoria")
    peso_maximo = models.IntegerField(null=True, blank=True, verbose_name="Peso Máximo")
    combustivel = models.IntegerField(null=True, blank=True, verbose_name="Combustível")
    cor = models.CharField(max_length=50, null=True, blank=True, verbose_name="Cor")
    ano_fabricacao = models.IntegerField(null=True, blank=True, verbose_name="Ano de Fabricação")
    ano_modelo = models.IntegerField(null=True, blank=True, verbose_name="Ano do Modelo")
    codigo_cidade = models.IntegerField(null=True, blank=True, verbose_name="Código da Cidade")
    nome_cidade = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nome da Cidade")
    codigo_funcionario = models.IntegerField(null=True, blank=True, verbose_name="Código do Funcionário")
    nome_funcionario = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nome do Funcionário")
    codigo_motorista = models.IntegerField(null=True, blank=True, verbose_name="Código do Motorista")
    nome_motorista = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nome do Motorista")
    codigo_parceiro = models.IntegerField(null=True, blank=True, verbose_name="Código do Parceiro")
    nome_parceiro = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome do Parceiro")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Veículo Sankhya'
        verbose_name_plural = 'Veículos Sankhya'
        ordering = ['codigo_veiculo']
        db_table = 'sankhya_veiculo'
        indexes = [
            models.Index(fields=['codigo_veiculo']),
            models.Index(fields=['placa']),
            models.Index(fields=['ativo']),
        ]
    
    def __str__(self):
        return f"{self.placa} - {self.marca_modelo or 'N/A'}"


class Empresa(models.Model):
    """
    Modelo para armazenar dados de empresas da API Sankhya
    """
    codigo_empresa = models.IntegerField(unique=True, verbose_name="Código da Empresa")
    nome_fantasia = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome Fantasia")
    razao_social = models.CharField(max_length=200, null=True, blank=True, verbose_name="Razão Social")
    razao_abreviada = models.CharField(max_length=100, null=True, blank=True, verbose_name="Razão Abreviada")
    cnpj_cpf = models.CharField(max_length=20, null=True, blank=True, verbose_name="CNPJ/CPF")
    inscricao_estadual = models.CharField(max_length=20, null=True, blank=True, verbose_name="Inscrição Estadual")
    inscricao_municipal = models.CharField(max_length=20, null=True, blank=True, verbose_name="Inscrição Municipal")
    telefone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefone")
    email = models.EmailField(max_length=100, null=True, blank=True, verbose_name="E-mail")
    homepage = models.URLField(max_length=200, null=True, blank=True, verbose_name="Homepage")
    codigo_logradouro = models.IntegerField(null=True, blank=True, verbose_name="Código do Logradouro")
    nome_logradouro = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome do Logradouro")
    numero = models.CharField(max_length=20, null=True, blank=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, null=True, blank=True, verbose_name="Complemento")
    codigo_bairro = models.IntegerField(null=True, blank=True, verbose_name="Código do Bairro")
    nome_bairro = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nome do Bairro")
    codigo_cidade = models.IntegerField(null=True, blank=True, verbose_name="Código da Cidade")
    nome_cidade = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nome da Cidade")
    cep = models.CharField(max_length=10, null=True, blank=True, verbose_name="CEP")
    codigo_empresa_matriz = models.IntegerField(null=True, blank=True, verbose_name="Código da Empresa Matriz")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Empresa Sankhya'
        verbose_name_plural = 'Empresas Sankhya'
        ordering = ['codigo_empresa']
        db_table = 'sankhya_empresa'
        indexes = [
            models.Index(fields=['codigo_empresa']),
            models.Index(fields=['cnpj_cpf']),
            models.Index(fields=['codigo_empresa_matriz']),
        ]
    
    def __str__(self):
        return f"{self.codigo_empresa} - {self.nome_fantasia or self.razao_social or 'N/A'}"


class Cidade(models.Model):
    """
    Cidades Sankhya. Campos alinhados ao retorno de getCidadeLegado (CRUD Cidade):
    CODCID -> codigo_cidade, NOMECID -> nome, UF -> uf, CODREG -> codigo_regiao,
    DTALTER -> dt_alteracao.
    Campos nome_regiao, nome_correio e codigo_municipio_fiscal vêm de outras integrações (API v1).
    """
    codigo_cidade = models.IntegerField(unique=True, verbose_name="Código da Cidade (CODCID)")
    nome = models.CharField(max_length=200, verbose_name="Nome (NOMECID)")
    uf = models.CharField(max_length=2, null=True, blank=True, verbose_name="UF")
    codigo_regiao = models.IntegerField(null=True, blank=True, verbose_name="Código da Região (CODREG)")
    dt_alteracao = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name="Data alteração legado (DTALTER)",
    )
    nome_regiao = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nome da Região")
    nome_correio = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nome Correio")
    codigo_municipio_fiscal = models.IntegerField(null=True, blank=True, verbose_name="Código Município Fiscal")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Cidade Sankhya'
        verbose_name_plural = 'Cidades Sankhya'
        ordering = ['nome', 'uf']
        db_table = 'sankhya_cidade'
        indexes = [
            models.Index(fields=['codigo_cidade']),
            models.Index(fields=['uf']),
            models.Index(fields=['codigo_regiao']),
            models.Index(fields=['codigo_municipio_fiscal']),
        ]
    
    def __str__(self):
        return f"{self.nome} - {self.uf or 'N/A'}"


class Logradouro(models.Model):
    """
    Modelo para armazenar dados de logradouros da API Sankhya
    """
    codigo_logradouro = models.IntegerField(unique=True, verbose_name="Código do Logradouro")
    nome = models.CharField(max_length=200, verbose_name="Nome")
    tipo = models.CharField(max_length=50, null=True, blank=True, verbose_name="Tipo")
    descricao_correio = models.CharField(max_length=200, null=True, blank=True, verbose_name="Descrição Correio")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Logradouro Sankhya'
        verbose_name_plural = 'Logradouros Sankhya'
        ordering = ['nome', 'tipo']
        db_table = 'sankhya_logradouro'
        indexes = [
            models.Index(fields=['codigo_logradouro']),
            models.Index(fields=['nome']),
            models.Index(fields=['tipo']),
        ]
    
    def __str__(self):
        return f"{self.tipo or ''} {self.nome}".strip()


class Bairro(models.Model):
    """
    Modelo para armazenar dados de bairros da API Sankhya
    """
    codigo_bairro = models.IntegerField(unique=True, verbose_name="Código do Bairro")
    nome = models.CharField(max_length=200, verbose_name="Nome")
    nome_regiao = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nome da Região")
    nome_correio = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome Correio")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Bairro Sankhya'
        verbose_name_plural = 'Bairros Sankhya'
        ordering = ['nome', 'nome_regiao']
        db_table = 'sankhya_bairro'
        indexes = [
            models.Index(fields=['codigo_bairro']),
            models.Index(fields=['nome']),
            models.Index(fields=['nome_regiao']),
        ]
    
    def __str__(self):
        return f"{self.nome} - {self.nome_regiao or 'N/A'}"


class Vendedor(models.Model):
    """
    Modelo para armazenar dados de vendedores da API Sankhya
    """
    codigo_vendedor = models.IntegerField(unique=True, verbose_name="Código do Vendedor")
    nome = models.CharField(max_length=200, verbose_name="Nome")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    tipo = models.IntegerField(null=True, blank=True, verbose_name="Tipo")
    comissao_gerencia = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Comissão Gerência")
    comissao_venda = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Comissão Venda")
    email = models.EmailField(max_length=100, null=True, blank=True, verbose_name="E-mail")
    codigo_empresa = models.IntegerField(null=True, blank=True, verbose_name="Código da Empresa")
    nome_empresa = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome da Empresa")
    codigo_parceiro = models.IntegerField(null=True, blank=True, verbose_name="Código do Parceiro")
    nome_parceiro = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome do Parceiro")
    codigo_funcionario = models.IntegerField(null=True, blank=True, verbose_name="Código do Funcionário")
    nome_funcionario = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome do Funcionário")
    codigo_gerente = models.IntegerField(null=True, blank=True, verbose_name="Código do Gerente")
    nome_gerente = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome do Gerente")
    codigo_centro_resultado = models.IntegerField(null=True, blank=True, verbose_name="Código do Centro de Resultado")
    nome_centro_resultado = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome do Centro de Resultado")
    codigo_regiao = models.IntegerField(null=True, blank=True, verbose_name="Código da Região")
    nome_regiao = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome da Região")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Vendedor Sankhya'
        verbose_name_plural = 'Vendedores Sankhya'
        ordering = ['nome', 'codigo_vendedor']
        db_table = 'sankhya_vendedor'
        indexes = [
            models.Index(fields=['codigo_vendedor']),
            models.Index(fields=['nome']),
            models.Index(fields=['ativo']),
            models.Index(fields=['codigo_empresa']),
            models.Index(fields=['codigo_gerente']),
        ]
    
    def __str__(self):
        return f"{self.nome} - {self.codigo_vendedor}"


class Cliente(models.Model):
    """
    Modelo para armazenar dados de clientes da API Sankhya
    """
    codigo_cliente = models.IntegerField(unique=True, verbose_name="Código do Cliente")
    tipo = models.CharField(max_length=10, null=True, blank=True, verbose_name="Tipo")
    cnpj_cpf = models.CharField(max_length=20, null=True, blank=True, verbose_name="CNPJ/CPF")
    ie_rg = models.CharField(max_length=20, null=True, blank=True, verbose_name="IE/RG")
    nome = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome")
    razao = models.CharField(max_length=200, null=True, blank=True, verbose_name="Razão Social")
    email = models.EmailField(max_length=100, null=True, blank=True, verbose_name="E-mail")
    telefone_ddd = models.CharField(max_length=5, null=True, blank=True, verbose_name="DDD")
    telefone_numero = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefone")
    limite_credito = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Limite de Crédito")
    grupo_autorizacao = models.CharField(max_length=10, null=True, blank=True, verbose_name="Grupo Autorização")
    # Campos do endereço
    latitude = models.CharField(max_length=50, null=True, blank=True, verbose_name="Latitude")
    longitude = models.CharField(max_length=50, null=True, blank=True, verbose_name="Longitude")
    codend = models.IntegerField(null=True, blank=True, verbose_name="Código do Endereço")
    numero = models.CharField(max_length=20, null=True, blank=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, null=True, blank=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, null=True, blank=True, verbose_name="Bairro")
    cidade = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Cidade (CODCID)",
        help_text='Código da cidade no Sankhya (CODCID), relacionado a sankhya_cidade.codigo_cidade.',
    )
    cep = models.CharField(max_length=10, null=True, blank=True, verbose_name="CEP")
    codtab = models.IntegerField(null=True, blank=True, verbose_name="Código da Tabela de Preço")
    codvend = models.IntegerField(null=True, blank=True, verbose_name="Código do Vendedor (CODVEND)")
    codigo_empresa = models.IntegerField(null=True, blank=True, verbose_name="Código da Empresa (CODEMP)")
    tempo_analise = models.PositiveIntegerField(
        default=2,
        verbose_name="Tempo de análise (meses)",
        help_text="Período padrão em meses para análise comercial do cliente.",
    )
    dtalter = models.CharField(max_length=50, null=True, blank=True, verbose_name="Data Alteração (DTALTER)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Cliente Sankhya'
        verbose_name_plural = 'Clientes Sankhya'
        ordering = ['nome', 'codigo_cliente']
        db_table = 'sankhya_cliente'
        indexes = [
            models.Index(fields=['codigo_cliente']),
            models.Index(fields=['cnpj_cpf']),
            models.Index(fields=['nome']),
            models.Index(fields=['tipo']),
            models.Index(fields=['cidade']),
            models.Index(fields=['codtab']),
            models.Index(fields=['codvend']),
            models.Index(fields=['codigo_empresa']),
            models.Index(fields=['codend']),
        ]
    
    def __str__(self):
        return f"{self.nome or self.razao or 'N/A'} - {self.codigo_cliente}"


class Motorista(models.Model):
    """
    Modelo para armazenar dados de motoristas da API Sankhya
    """
    codigo_motorista = models.IntegerField(unique=True, verbose_name="Código do Motorista")
    nome = models.CharField(max_length=200, verbose_name="Nome")
    cpf = models.CharField(max_length=14, null=True, blank=True, verbose_name="CPF")
    rg = models.CharField(max_length=20, null=True, blank=True, verbose_name="RG")
    cnh = models.CharField(max_length=20, null=True, blank=True, verbose_name="CNH")
    categoria_cnh = models.CharField(max_length=10, null=True, blank=True, verbose_name="Categoria CNH")
    data_vencimento_cnh = models.CharField(max_length=50, null=True, blank=True, verbose_name="Data Vencimento CNH")
    email = models.EmailField(max_length=100, null=True, blank=True, verbose_name="E-mail")
    telefone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefone")
    # Campos do endereço
    logradouro = models.CharField(max_length=200, null=True, blank=True, verbose_name="Logradouro")
    numero = models.CharField(max_length=20, null=True, blank=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, null=True, blank=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, null=True, blank=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, null=True, blank=True, verbose_name="Cidade")
    codigo_ibge = models.CharField(max_length=20, null=True, blank=True, verbose_name="Código IBGE")
    uf = models.CharField(max_length=2, null=True, blank=True, verbose_name="UF")
    cep = models.CharField(max_length=10, null=True, blank=True, verbose_name="CEP")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Motorista Sankhya'
        verbose_name_plural = 'Motoristas Sankhya'
        ordering = ['nome', 'codigo_motorista']
        db_table = 'sankhya_motorista'
        indexes = [
            models.Index(fields=['codigo_motorista']),
            models.Index(fields=['cpf']),
            models.Index(fields=['nome']),
            models.Index(fields=['cnh']),
            models.Index(fields=['uf']),
            models.Index(fields=['cidade']),
        ]
    
    def __str__(self):
        return f"{self.nome or 'N/A'} - {self.codigo_motorista}"


class Preco(models.Model):
    """
    Modelo para armazenar dados de preços da API Sankhya
    """
    codigo_produto = models.IntegerField(verbose_name="Código do Produto")
    codigo_local_estoque = models.IntegerField(default=0, verbose_name="Código Local Estoque")
    controle = models.CharField(max_length=50, null=True, blank=True, verbose_name="Controle")
    unidade = models.CharField(max_length=10, null=True, blank=True, verbose_name="Unidade")
    codigo_tabela = models.IntegerField(verbose_name="Código da Tabela")
    valor = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Valor")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Preço Sankhya'
        verbose_name_plural = 'Preços Sankhya'
        ordering = ['codigo_produto', 'codigo_tabela', 'codigo_local_estoque']
        db_table = 'sankhya_preco'
        unique_together = [['codigo_produto', 'codigo_local_estoque', 'codigo_tabela']]
        indexes = [
            models.Index(fields=['codigo_produto']),
            models.Index(fields=['codigo_tabela']),
            models.Index(fields=['codigo_local_estoque']),
            models.Index(fields=['codigo_produto', 'codigo_tabela']),
        ]
    
    def __str__(self):
        return f"Produto {self.codigo_produto} - Tabela {self.codigo_tabela} - R$ {self.valor}"


class Produto(models.Model):
    """
    Modelo para armazenar dados de produtos da API Sankhya
    """
    codigo_produto = models.IntegerField(unique=True, verbose_name="Código do Produto")
    data_alteracao = models.CharField(max_length=50, null=True, blank=True, verbose_name="Data Alteração")
    nome = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome")
    complemento = models.CharField(max_length=200, null=True, blank=True, verbose_name="Complemento")
    caracteristicas = models.TextField(null=True, blank=True, verbose_name="Características")
    referencia = models.CharField(max_length=100, null=True, blank=True, verbose_name="Referência")
    codigo_grupo_produto = models.IntegerField(null=True, blank=True, verbose_name="Código Grupo Produto")
    nome_grupo_produto = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome Grupo Produto")
    volume = models.CharField(max_length=10, null=True, blank=True, verbose_name="Volume")
    marca = models.CharField(max_length=100, null=True, blank=True, verbose_name="Marca")
    decimais_valor = models.IntegerField(null=True, blank=True, verbose_name="Decimais Valor")
    decimais_quantidade = models.IntegerField(null=True, blank=True, verbose_name="Decimais Quantidade")
    peso_bruto = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True, verbose_name="Peso Bruto")
    agrupamento_minimo = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True, verbose_name="Agrupamento Mínimo")
    quantidade_embalagem = models.IntegerField(null=True, blank=True, verbose_name="Quantidade Embalagem")
    tipo_controle_estoque = models.IntegerField(null=True, blank=True, verbose_name="Tipo Controle Estoque")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    estoque_maximo = models.IntegerField(null=True, blank=True, verbose_name="Estoque Máximo")
    estoque_minimo = models.IntegerField(null=True, blank=True, verbose_name="Estoque Mínimo")
    homepage = models.URLField(max_length=200, null=True, blank=True, verbose_name="Homepage")
    grupo_desconto = models.CharField(max_length=50, null=True, blank=True, verbose_name="Grupo Desconto")
    referencia_fornecedor = models.CharField(max_length=100, null=True, blank=True, verbose_name="Referência Fornecedor")
    usado_como = models.IntegerField(null=True, blank=True, verbose_name="Usado Como")
    cnae = models.BigIntegerField(null=True, blank=True, verbose_name="CNAE")
    metro_cubico = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True, verbose_name="Metro Cúbico")
    altura = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True, verbose_name="Altura")
    largura = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True, verbose_name="Largura")
    espessura = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True, verbose_name="Espessura")
    unidade_medida = models.CharField(max_length=10, null=True, blank=True, verbose_name="Unidade Medida")
    utiliza_balanca = models.BooleanField(default=False, verbose_name="Utiliza Balança")
    codigo_pais = models.IntegerField(null=True, blank=True, verbose_name="Código País")
    ncm = models.CharField(max_length=20, null=True, blank=True, verbose_name="NCM")
    cest = models.CharField(max_length=20, null=True, blank=True, verbose_name="CEST")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Produto Sankhya'
        verbose_name_plural = 'Produtos Sankhya'
        ordering = ['nome', 'codigo_produto']
        db_table = 'sankhya_produto'
        indexes = [
            models.Index(fields=['codigo_produto']),
            models.Index(fields=['nome']),
            models.Index(fields=['referencia']),
            models.Index(fields=['codigo_grupo_produto']),
            models.Index(fields=['ativo']),
            models.Index(fields=['ncm']),
        ]
    
    def __str__(self):
        return f"{self.nome or 'N/A'} - {self.codigo_produto}"


class GrupoProduto(models.Model):
    """
    Modelo para armazenar dados de grupos de produtos da API Sankhya
    """
    codigo_grupo_produto = models.IntegerField(unique=True, verbose_name="Código do Grupo Produto")
    nome = models.CharField(max_length=200, verbose_name="Nome")
    codigo_grupo_produto_pai = models.IntegerField(null=True, blank=True, verbose_name="Código Grupo Produto Pai")
    grau = models.IntegerField(null=True, blank=True, verbose_name="Grau")
    grupo_icms = models.IntegerField(null=True, blank=True, verbose_name="Grupo ICMS")
    analitico = models.BooleanField(default=False, verbose_name="Analítico")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    mostrar_no_ecommerce = models.BooleanField(
        default=False,
        verbose_name='Mostrar no e-commerce',
        help_text='Se marcado, a categoria aparece na navegação da loja (respeitando a hierarquia).',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Grupo Produto Sankhya'
        verbose_name_plural = 'Grupos Produto Sankhya'
        ordering = ['nome', 'codigo_grupo_produto']
        db_table = 'sankhya_grupo_produto'
        indexes = [
            models.Index(fields=['codigo_grupo_produto']),
            models.Index(fields=['nome']),
            models.Index(fields=['codigo_grupo_produto_pai']),
            models.Index(fields=['ativo']),
            models.Index(fields=['grupo_icms']),
            models.Index(fields=['ativo', 'mostrar_no_ecommerce']),
        ]
    
    def __str__(self):
        return f"{self.nome or 'N/A'} - {self.codigo_grupo_produto}"


class Pedido(models.Model):
    """
    Modelo para armazenar pedidos de venda da API Sankhya (v1/vendas/pedidos).
    """
    ORIGEM_SANKHYA = 'SANKHYA'

    origem = models.CharField(
        max_length=50,
        default=ORIGEM_SANKHYA,
        verbose_name="Origem",
    )
    codigo_nota = models.IntegerField(verbose_name="Código da Nota")
    codigo_empresa = models.IntegerField(null=True, blank=True, verbose_name="Código Empresa")
    nome_empresa = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome Empresa")
    codigo_cliente = models.IntegerField(null=True, blank=True, verbose_name="Código Cliente")
    # Cliente (dados desnormalizados)
    cliente_tipo = models.CharField(max_length=10, null=True, blank=True)
    cliente_cnpj_cpf = models.CharField(max_length=20, null=True, blank=True)
    cliente_ie_rg = models.CharField(max_length=20, null=True, blank=True)
    cliente_nome = models.CharField(max_length=200, null=True, blank=True)
    cliente_razao = models.CharField(max_length=200, null=True, blank=True)
    cliente_email = models.EmailField(max_length=100, null=True, blank=True)
    cliente_telefone = models.CharField(max_length=20, null=True, blank=True)
    # Endereço entrega
    endereco_logradouro = models.CharField(max_length=200, null=True, blank=True)
    endereco_numero = models.CharField(max_length=20, null=True, blank=True)
    endereco_complemento = models.CharField(max_length=100, null=True, blank=True)
    endereco_bairro = models.CharField(max_length=100, null=True, blank=True)
    endereco_cidade = models.CharField(max_length=100, null=True, blank=True)
    endereco_codigo_ibge = models.CharField(max_length=20, null=True, blank=True)
    endereco_uf = models.CharField(max_length=2, null=True, blank=True)
    endereco_cep = models.CharField(max_length=10, null=True, blank=True)
    entrega = models.BooleanField(default=False, verbose_name="Endereço de entrega")
    # Status e datas
    confirmada = models.BooleanField(default=False)
    pendente = models.BooleanField(default=True)
    data_negociacao = models.DateField(null=True, blank=True)
    data_hora_alteracao = models.CharField(max_length=50, null=True, blank=True)
    # Nota
    numero_nota = models.IntegerField(null=True, blank=True)
    serie_nota = models.CharField(max_length=10, null=True, blank=True)
    # Tipo e operação
    codigo_tipo_negociacao = models.IntegerField(null=True, blank=True)
    nome_tipo_negociacao = models.CharField(max_length=100, null=True, blank=True)
    codigo_tipo_operacao = models.IntegerField(null=True, blank=True)
    nome_tipo_operacao = models.CharField(max_length=100, null=True, blank=True)
    codigo_natureza = models.BigIntegerField(null=True, blank=True)
    # Centro resultado / projeto
    codigo_centro_resultado = models.BigIntegerField(null=True, blank=True)
    nome_centro_resultado = models.CharField(max_length=200, null=True, blank=True)
    codigo_projeto = models.IntegerField(null=True, blank=True)
    nome_projeto = models.CharField(max_length=200, null=True, blank=True)
    codigo_contrato = models.IntegerField(null=True, blank=True)
    # Vendedor / contato
    codigo_vendedor = models.IntegerField(null=True, blank=True)
    nome_vendedor = models.CharField(max_length=200, null=True, blank=True)
    codigo_contato = models.IntegerField(null=True, blank=True)
    nome_contato = models.CharField(max_length=200, null=True, blank=True)
    # Moeda
    codigo_moeda = models.IntegerField(null=True, blank=True)
    nome_moeda = models.CharField(max_length=50, null=True, blank=True)
    valor_moeda = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    # Valores
    valor_nota = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    desconto_total = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valor_seguro = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valor_destaque = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valor_vendor = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valor_juro = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valor_outros = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valor_embalagem = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valor_frete = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    vencimento_frete = models.CharField(max_length=50, null=True, blank=True)
    # Logística
    codigo_ordem_carga = models.IntegerField(null=True, blank=True)
    codigo_veiculo = models.IntegerField(null=True, blank=True)
    placa_veiculo = models.CharField(max_length=10, null=True, blank=True)
    codigo_motorista = models.IntegerField(null=True, blank=True)
    nome_motorista = models.CharField(max_length=200, null=True, blank=True)
    codigo_transportadora = models.IntegerField(null=True, blank=True)
    nome_transportadora = models.CharField(max_length=200, null=True, blank=True)
    codigo_remetente = models.IntegerField(null=True, blank=True)
    nome_remetente = models.CharField(max_length=200, null=True, blank=True)
    codigo_destinatario = models.IntegerField(null=True, blank=True)
    nome_destinatario = models.CharField(max_length=200, null=True, blank=True)
    quantidade_volumes = models.IntegerField(null=True, blank=True)
    numeracao_volumes = models.CharField(max_length=200, null=True, blank=True)
    lacres = models.CharField(max_length=200, null=True, blank=True)
    peso_bruto = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True)
    cif_fob = models.CharField(max_length=1, null=True, blank=True)
    tipo_frete = models.CharField(max_length=1, null=True, blank=True)
    base_icms_frete = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    icms_frete = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    # WMS
    status_wms = models.CharField(max_length=10, null=True, blank=True)
    situacao_wms = models.IntegerField(null=True, blank=True)
    status_conferencia = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pedido Sankhya'
        verbose_name_plural = 'Pedidos Sankhya'
        ordering = ['-data_negociacao', '-codigo_nota']
        db_table = 'sankhya_pedido'
        unique_together = [['codigo_nota', 'codigo_empresa', 'origem']]
        indexes = [
            models.Index(fields=['codigo_nota', 'codigo_empresa', 'origem']),
            models.Index(fields=['codigo_cliente']),
            models.Index(fields=['data_negociacao']),
            models.Index(fields=['pendente', 'confirmada']),
        ]

    def __str__(self):
        return f"Nota {self.codigo_nota} ({self.origem}) - {self.cliente_nome or self.cliente_razao or 'N/A'}"


class ItemPedido(models.Model):
    """
    Item do pedido de venda (itens do documento).
    """
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='itens')
    sequencia = models.IntegerField(verbose_name="Sequência")
    cod_produto = models.IntegerField(null=True, blank=True, verbose_name="Código Produto")
    descricao_produto = models.CharField(max_length=300, null=True, blank=True)
    quantidade = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    unidade = models.CharField(max_length=10, null=True, blank=True)
    valor_unitario = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    valor_total = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cfop = models.IntegerField(null=True, blank=True)
    ncm = models.CharField(max_length=20, null=True, blank=True)
    cst = models.CharField(max_length=10, null=True, blank=True)
    valor_desconto = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valor_icms = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valor_ipi = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Item do Pedido Sankhya'
        verbose_name_plural = 'Itens do Pedido Sankhya'
        ordering = ['pedido', 'sequencia']
        db_table = 'sankhya_item_pedido'
        unique_together = [['pedido', 'sequencia']]
        indexes = [
            models.Index(fields=['pedido']),
            models.Index(fields=['cod_produto']),
        ]

    def __str__(self):
        return f"{self.pedido_id} - Seq {self.sequencia} - {self.descricao_produto or 'N/A'}"


class NotaFiscal(models.Model):
    """
    Cabeçalho de nota fiscal emitida (CRUD ItemNota + join CabecalhoNota).
    Chave natural: NUNOTA.
    """
    nunota = models.IntegerField(unique=True, verbose_name="Nº único (NUNOTA)")
    codigo_empresa = models.IntegerField(null=True, blank=True, verbose_name="Código Empresa (CODEMP)")
    numero_nota = models.IntegerField(null=True, blank=True, verbose_name="Número NF (NUMNOTA)")
    data_entrada_saida = models.DateField(null=True, blank=True, verbose_name="Data Entrada/Saída (DTENTSAI)")
    data_negociacao = models.DateField(null=True, blank=True, verbose_name="Data Negociação (DTNEG)")
    codigo_tipo_operacao = models.IntegerField(null=True, blank=True, verbose_name="Tipo Operação (CODTIPOPER)")
    codigo_parceiro = models.IntegerField(null=True, blank=True, verbose_name="Parceiro (CODPARC)")
    codigo_vendedor = models.IntegerField(null=True, blank=True, verbose_name="Vendedor (CODVEND)")
    tipo_movimento = models.CharField(max_length=10, null=True, blank=True, verbose_name="Tipo Movimento (TIPMOV)")
    pendente = models.CharField(max_length=5, null=True, blank=True, verbose_name="Pendente (PENDENTE)")
    status_nfe = models.CharField(max_length=30, null=True, blank=True, verbose_name="Status NFe (STATUSNFE)")
    status_nota = models.CharField(max_length=30, null=True, blank=True, verbose_name="Status Nota (STATUSNOTA)")
    aprovado = models.CharField(max_length=5, null=True, blank=True, verbose_name="Aprovado (APROVADO)")
    dtalter = models.CharField(max_length=50, null=True, blank=True, verbose_name="Data Alteração (DTALTER)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Nota Fiscal Sankhya"
        verbose_name_plural = "Notas Fiscais Sankhya"
        ordering = ["-data_negociacao", "-numero_nota"]
        db_table = "sankhya_nota_fiscal"
        indexes = [
            models.Index(fields=["nunota"]),
            models.Index(fields=["codigo_empresa", "numero_nota"]),
            models.Index(fields=["codigo_parceiro"]),
            models.Index(fields=["codigo_vendedor"]),
            models.Index(fields=["data_negociacao"]),
            models.Index(fields=["status_nfe"]),
        ]

    def __str__(self):
        return f"NF {self.numero_nota or '?'} (NUNOTA {self.nunota})"


class ItemNotaFiscal(models.Model):
    """Item de nota fiscal emitida (linha ItemNota)."""
    nota_fiscal = models.ForeignKey(NotaFiscal, on_delete=models.CASCADE, related_name="itens")
    sequencia = models.IntegerField(verbose_name="Sequência (SEQUENCIA)")
    cod_produto = models.IntegerField(null=True, blank=True, verbose_name="Código Produto (CODPROD)")
    quantidade = models.DecimalField(
        max_digits=15, decimal_places=4, null=True, blank=True, verbose_name="Quantidade (QTDNEG)"
    )
    valor_unitario = models.DecimalField(
        max_digits=15, decimal_places=4, null=True, blank=True, verbose_name="Valor Unitário (VLRUNIT)"
    )
    valor_total = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Valor Total (VLRTOT)"
    )
    valor_desconto = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Valor Desconto (VLRDESC)"
    )
    uso_produto = models.CharField(max_length=10, null=True, blank=True, verbose_name="Uso Produto (USOPROD)")
    status_nota = models.CharField(max_length=30, null=True, blank=True, verbose_name="Status Nota (STATUSNOTA)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Item Nota Fiscal Sankhya"
        verbose_name_plural = "Itens Nota Fiscal Sankhya"
        ordering = ["nota_fiscal", "sequencia"]
        db_table = "sankhya_item_nota_fiscal"
        unique_together = [["nota_fiscal", "sequencia"]]
        indexes = [
            models.Index(fields=["nota_fiscal"]),
            models.Index(fields=["cod_produto"]),
        ]

    def __str__(self):
        return f"{self.nota_fiscal_id} - Seq {self.sequencia} - Prod {self.cod_produto or '?'}"


class Contato(models.Model):
    """
    Modelo para armazenar contatos (parceiros) da API Sankhya.
    Chave: CODPARC + CODCONTATO.
    """
    codparc = models.IntegerField(verbose_name="Código Parceiro")
    codcontato = models.IntegerField(verbose_name="Código Contato")
    nomecontato = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome Contato")
    apelido = models.CharField(max_length=100, null=True, blank=True, verbose_name="Apelido")
    codend = models.IntegerField(null=True, blank=True, verbose_name="Código Endereço")
    numend = models.CharField(max_length=20, null=True, blank=True, verbose_name="Número Endereço")
    complemento = models.CharField(max_length=100, null=True, blank=True, verbose_name="Complemento")
    codbai = models.IntegerField(null=True, blank=True, verbose_name="Código Bairro")
    codcid = models.IntegerField(null=True, blank=True, verbose_name="Código Cidade")
    cep = models.CharField(max_length=10, null=True, blank=True, verbose_name="CEP")
    telefone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefone")
    email = models.EmailField(max_length=100, null=True, blank=True, verbose_name="E-mail")
    celular = models.CharField(max_length=20, null=True, blank=True, verbose_name="Celular")
    dtalter = models.CharField(max_length=50, null=True, blank=True, verbose_name="Data Alteração (DTALTER)")
    latitude = models.CharField(max_length=50, null=True, blank=True, verbose_name="Latitude")
    longitude = models.CharField(max_length=50, null=True, blank=True, verbose_name="Longitude")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contato Sankhya'
        verbose_name_plural = 'Contatos Sankhya'
        ordering = ['codparc', 'codcontato']
        db_table = 'sankhya_contato'
        unique_together = [['codparc', 'codcontato']]
        indexes = [
            models.Index(fields=['codparc']),
            models.Index(fields=['codcontato']),
            models.Index(fields=['email']),
            models.Index(fields=['codcid']),
        ]

    def __str__(self):
        return f"{self.nomecontato or self.apelido or 'N/A'} (Parc: {self.codparc}, Cont: {self.codcontato})"


class Funcionario(models.Model):
    """
    Funcionário Sankhya (dados consolidados a partir das APIs de resumo e detalhe).
    Chave natural: empresa_codigo + codigo_funcionario.
    """
    # Identificação básica
    empresa_codigo = models.IntegerField(verbose_name="Código Empresa")
    codigo_funcionario = models.IntegerField(verbose_name="Código Funcionário")
    cpf = models.CharField(max_length=14, null=True, blank=True, verbose_name="CPF")
    nome = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome")
    matricula = models.IntegerField(null=True, blank=True, verbose_name="Matrícula")

    # Dados pessoais
    nascimento = models.CharField(max_length=10, null=True, blank=True, verbose_name="Data Nascimento")
    sexo = models.CharField(max_length=1, null=True, blank=True, verbose_name="Sexo")
    celular = models.CharField(max_length=20, null=True, blank=True, verbose_name="Celular")
    email = models.EmailField(max_length=150, null=True, blank=True, verbose_name="E-mail")
    nome_mae = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nome da Mãe")

    # Endereço
    endereco_cep = models.CharField(max_length=10, null=True, blank=True, verbose_name="CEP")
    endereco_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Endereço")
    endereco_descricao = models.CharField(max_length=200, null=True, blank=True, verbose_name="Logradouro")
    endereco_numero = models.CharField(max_length=20, null=True, blank=True, verbose_name="Número")
    endereco_complemento = models.CharField(max_length=100, null=True, blank=True, verbose_name="Complemento")
    bairro_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Bairro")
    bairro_descricao = models.CharField(max_length=150, null=True, blank=True, verbose_name="Bairro")
    cidade_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Cidade")
    cidade_descricao = models.CharField(max_length=150, null=True, blank=True, verbose_name="Cidade")
    cidade_codigo_ibge = models.IntegerField(null=True, blank=True, verbose_name="Código IBGE Cidade")

    # Dados contratuais / empresa
    empresa_cnpj = models.CharField(max_length=20, null=True, blank=True, verbose_name="CNPJ Empresa")
    empresa_razao_social = models.CharField(max_length=200, null=True, blank=True, verbose_name="Razão Social Empresa")
    data_admissao = models.CharField(max_length=10, null=True, blank=True, verbose_name="Data Admissão")
    codigo_categoria_esocial = models.IntegerField(null=True, blank=True, verbose_name="Categoria eSocial")
    situacao = models.CharField(max_length=2, null=True, blank=True, verbose_name="Situação")
    salario_base = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Salário Base")
    bolsa_estagio_ou_pro_labore = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Bolsa Estágio / Pró-labore")

    departamento_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Departamento")
    departamento_descricao = models.CharField(max_length=150, null=True, blank=True, verbose_name="Departamento")

    cargo_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Cargo")
    cargo_descricao = models.CharField(max_length=150, null=True, blank=True, verbose_name="Cargo")
    cargo_cbo = models.IntegerField(null=True, blank=True, verbose_name="CBO Cargo")

    funcao_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Função")
    funcao_descricao = models.CharField(max_length=150, null=True, blank=True, verbose_name="Função")
    funcao_cbo = models.IntegerField(null=True, blank=True, verbose_name="CBO Função")

    local_trabalho_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Local Trabalho")
    local_trabalho_descricao = models.CharField(max_length=150, null=True, blank=True, verbose_name="Local Trabalho")

    cidade_trabalho_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Cidade Trabalho")
    cidade_trabalho_descricao = models.CharField(max_length=150, null=True, blank=True, verbose_name="Cidade Trabalho")
    cidade_trabalho_codigo_ibge = models.IntegerField(null=True, blank=True, verbose_name="Código IBGE Cidade Trabalho")

    sindicato_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Sindicato")
    sindicato_nome = models.CharField(max_length=200, null=True, blank=True, verbose_name="Sindicato")
    sindicato_cnpj = models.CharField(max_length=20, null=True, blank=True, verbose_name="CNPJ Sindicato")

    carga_horaria_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Carga Horária")
    carga_horaria_descricao = models.CharField(max_length=150, null=True, blank=True, verbose_name="Carga Horária")

    # Afastamento
    afast_motivo_desligamento_esocial = models.CharField(max_length=200, null=True, blank=True, verbose_name="Motivo Desligamento eSocial")
    afast_data_afastamento = models.CharField(max_length=10, null=True, blank=True, verbose_name="Data Afastamento")
    afast_causa_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Causa Afastamento")
    afast_causa_descricao = models.CharField(max_length=200, null=True, blank=True, verbose_name="Causa Afastamento")
    afast_tipo_rescisao_codigo = models.IntegerField(null=True, blank=True, verbose_name="Código Tipo Rescisão")
    afast_tipo_rescisao_descricao = models.CharField(max_length=200, null=True, blank=True, verbose_name="Tipo Rescisão")
    afast_data_desligamento = models.CharField(max_length=10, null=True, blank=True, verbose_name="Data Desligamento")
    afast_data_aviso_previo = models.CharField(max_length=10, null=True, blank=True, verbose_name="Data Aviso Prévio")

    # Transferência
    transf_data_transferencia_destino = models.CharField(max_length=10, null=True, blank=True, verbose_name="Data Transferência Destino")
    transf_empresa_destino = models.IntegerField(null=True, blank=True, verbose_name="Empresa Destino")
    transf_cnpj_empresa_destino = models.CharField(max_length=20, null=True, blank=True, verbose_name="CNPJ Empresa Destino")
    transf_codigo_funcionario_destino = models.IntegerField(null=True, blank=True, verbose_name="Código Funcionário Destino")
    transf_motivo_desligamento = models.CharField(max_length=200, null=True, blank=True, verbose_name="Motivo Desligamento (Transferência)")
    transf_data_transferencia = models.CharField(max_length=10, null=True, blank=True, verbose_name="Data Transferência")
    transf_empresa_origem = models.IntegerField(null=True, blank=True, verbose_name="Empresa Origem")
    transf_codigo_funcionario_origem = models.IntegerField(null=True, blank=True, verbose_name="Código Funcionário Origem")
    transf_data_inicio_vinculo = models.CharField(max_length=10, null=True, blank=True, verbose_name="Data Início Vínculo")
    transf_cnpj_empresa_anterior = models.CharField(max_length=20, null=True, blank=True, verbose_name="CNPJ Empresa Anterior")
    transf_matricula_empresa_anterior = models.IntegerField(null=True, blank=True, verbose_name="Matrícula Empresa Anterior")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Funcionário Sankhya'
        verbose_name_plural = 'Funcionários Sankhya'
        db_table = 'sankhya_funcionario'
        ordering = ['empresa_codigo', 'codigo_funcionario']
        unique_together = [['empresa_codigo', 'codigo_funcionario']]
        indexes = [
            models.Index(fields=['empresa_codigo']),
            models.Index(fields=['codigo_funcionario']),
            models.Index(fields=['cpf']),
            models.Index(fields=['matricula']),
            models.Index(fields=['situacao']),
        ]

    def __str__(self):
        return f"{self.nome or 'N/A'} (Emp: {self.empresa_codigo}, Func: {self.codigo_funcionario})"



