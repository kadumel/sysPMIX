from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.contrib.auth.models import User



class Cliente(models.Model):
    codigo = models.CharField(max_length=6)
    cliente = models.CharField(max_length=100)
    cnpj = models.CharField(max_length=14, blank=True, null=True)
    fantasia = models.CharField(max_length=100, blank=True, null=True)
    sincronizado = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Integração - Cliente'
        verbose_name_plural = 'Integração - Clientes'
        ordering = ['id']

    def __str__(self):
        return self.cliente    
    
class Funcionario(models.Model):
    campo_alt = models.CharField(max_length=10, null=True, blank=True, default='NEW_825')
    seq_id = models.CharField(max_length=10, null=True, blank=True)
    codigo_erp = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=14)
    tipo = models.CharField(max_length=20, choices=[('Motorista', 'Motorista'), ('Ajudante', 'Ajudante')])
    status = models.CharField(max_length=20, default='Ativo', choices=[('Ativo', 'Ativo'), ('Inativo', 'Inativo')])
    sincronizado = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Integração - Funcionário'
        verbose_name_plural = 'Integração - Funcionários'
        ordering = ['id']

    def __str__(self):
        return self.nome
    

    def save(self, *args, **kwargs):
        # Gera o seq_id usando o ID do registro e a data atual
        self.seq_id = self.codigo_erp
        self.sincronizado = False
        
        super().save(*args, **kwargs)
    
    
class Veiculo(models.Model):
    campo_alt = models.CharField(max_length=10, null=True, blank=True, default='NEW_762')
    seq_id = models.CharField(max_length=10, null=True, blank=True)
    codigo_erp = models.CharField(max_length=20, unique=True)
    placa = models.CharField(max_length=10)
    descricao = models.CharField(max_length=100)
    km_atual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    modelo = models.CharField(max_length=50, null=True, blank=True, choices=[('Volkswagen', 'Volkswagen'), ('ford', 'Ford'), ('chevrolet', 'Chevrolet'), ('fiat', 'Fiat'), 
                                                                             ('hyundai', 'Hyundai'), ('nissan', 'Nissan'), ('peugeot', 'Peugeot'), ('renault', 'Renault'), 
                                                                             ('toyota', 'Toyota'), ('volvo', 'Volvo'),('mercedes', 'Mercedes')])
    tipo_veiculo = models.CharField(max_length=20, null=True, blank=True, choices=[('Caminhão', 'Caminhão'), ('Furgão', 'Furgão'), ('Van', 'Van'), ('Carro', 'Carro')])
    ano_modelo = models.IntegerField(null=True, blank=True)
    ano_fabricacao = models.IntegerField(null=True, blank=True)
    qtd_max_entregas = models.IntegerField(null=True, blank=True, default=0)
    velocidade_maxima = models.IntegerField(null=True, blank=True)
    tipo_combustivel = models.CharField(max_length=20, default='Diesel', choices=[('Gasolina', 'Gasolina'), ('Diesel', 'Diesel'), ('Flex', 'Flex'), ('Eletrico', 'Eletrico'),('Alcool', 'Alcool'),('Outros', 'Outros')])
    status_inicial = models.CharField(max_length=20, default='Ativo', choices=[('Ativo', 'Ativo'), ('Inativo', 'Inativo')])
    peso_max_entregas = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    volume_max_entregas = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    qtd_pallets_veiculo = models.IntegerField(null=True, blank=True, default=0)
    filial = models.CharField(max_length=10)
    sincronizado = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Integração - Veículo'
        verbose_name_plural = 'Integração - Veículos'
        ordering = ['id']

    def __str__(self):
        return self.placa
    
    def save(self, *args, **kwargs):
        # Gera o seq_id usando o ID do registro e a data atual
        self.seq_id = self.codigo_erp
        self.sincronizado = False
        
        super().save(*args, **kwargs)
    
    
class Vendedor(models.Model):
    codigo = models.CharField(max_length=6)
    vendedor = models.CharField(max_length=100)
    apelido = models.CharField(max_length=100, blank=True, null=True)
    cpf = models.CharField(max_length=14, blank=True, null=True)
    sincronizado = models.BooleanField(default=False)
    flat_tecnico = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'BI - Vendedor'
        verbose_name_plural = 'BI - Vendedores'
        ordering = ['id']

    def __str__(self):
        return self.vendedor
    

class Operacao(models.Model):
    codigo = models.CharField(max_length=6)
    operacao = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'BI - Operação'
        verbose_name_plural = 'BI - Operações'
        ordering = ['id']

    def __str__(self):
        return self.operacao
    
class Secao(models.Model):
    codigo = models.CharField(max_length=6)
    secao = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'BI - Seção'
        verbose_name_plural = 'BI - Seções'
        ordering = ['id']

    def __str__(self):
        return self.secao
    



class ClienteVendedor(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    vendedor = models.ForeignKey(Vendedor, on_delete=models.CASCADE)
    secao = models.ForeignKey(Secao, on_delete=models.CASCADE)
    data_referencia = models.DateField()
    percentual_comissao = models.DecimalField(max_digits=5, decimal_places=2)
    flat = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'BI - Cliente Vendedor'
        verbose_name_plural = 'BI - Clientes Vendedores'
        ordering = ['id']

    def __str__(self):
        return f"{self.cliente} - {self.vendedor}"

class Pedido(models.Model):
    # Campos da Nota Fiscal
    nf = models.BigIntegerField('Número da Nota Fiscal', null=True, blank=True)
    chave_nfe = models.CharField('Chave NFE', max_length=45, null=True, blank=True)
    serie = models.CharField('Série', max_length=45, null=True, blank=True)
    tipo = models.CharField('Tipo', max_length=45, null=True, blank=True)
    ent_ou_serv = models.CharField('Entrega ou Serviço', max_length=45, choices=[('Entrega', 'Entrega'),('Servico', 'Serviço')])
    
    # Campos do Pedido
    pedido_erp = models.CharField('Código do Pedido ERP', max_length=45)
    forma_pgto = models.CharField('Forma de Pagamento', max_length=45, null=True, blank=True)
    status = models.CharField('Status', max_length=45, choices=[('1', 'Aprovado'),('4', 'Faturado'),('9', 'Cancelado')])
    obs = models.TextField('Observação', max_length=255, null=True, blank=True)
    num_ped_conf = models.CharField('Número do Pedido Confirmado', max_length=45, null=True, blank=True)
    carga = models.BigIntegerField('Código do Carregamento', null=True, blank=True)
    
    # Campos de Medidas e Valores
    cubagem = models.DecimalField('Cubagem', max_digits=18, decimal_places=7, null=True, blank=True)
    podeformarcarga = models.CharField('Pode Formar Carga', max_length=1, choices=[('S', 'Sim'),('N', 'Não')], default='S')
    valor = models.DecimalField('Valor', max_digits=18, decimal_places=7, default=0)
    peso = models.DecimalField('Peso (kg)', max_digits=18, decimal_places=7, default=0)
    qtd_pallets_entrega = models.DecimalField('Quantidade de Pallets', max_digits=18, decimal_places=7, null=True, blank=True)
    valor_st = models.DecimalField('Valor ST', max_digits=18, decimal_places=7, default=0)
    
    # Campos de Empresas
    empresa_fat = models.CharField('Empresa Faturamento', max_length=45)
    empresa_log = models.CharField('Empresa Logística', max_length=45)
    empresa_digit = models.CharField('Empresa Digitação', max_length=45)
    pedido_orig = models.CharField('Pedido Original', max_length=100)
    dt_list_nf = models.DateField('Data da Coleta', null=True, blank=True)
    
    # Campos do Cliente
    descr_cliente = models.CharField('Nome Fantasia', max_length=100)
    razao_cliente = models.CharField('Razão Social', max_length=100)
    cnpj_cliente = models.CharField('CNPJ/CPF', max_length=14)
    end_cliente = models.CharField('Endereço', max_length=255)
    bairro_cliente = models.CharField('Bairro', max_length=45)
    num_end_cliente = models.CharField('Número', max_length=45)
    uf_cliente = models.CharField('UF', max_length=45)
    cidade_cliente = models.CharField('Cidade', max_length=45)
    cep_cliente = models.CharField('CEP', max_length=8)
    
    # Contatos do Cliente
    email1_cliente = models.EmailField('E-mail 1', max_length=45, null=True, blank=True)
    email2_cliente = models.EmailField('E-mail 2', max_length=45, null=True, blank=True)
    email3_cliente = models.EmailField('E-mail 3', max_length=45, null=True, blank=True)
    tel1_cliente = models.CharField('Telefone 1', max_length=45, null=True, blank=True)
    tel2_cliente = models.CharField('Telefone 2', max_length=45, null=True, blank=True)
    tel3_cliente = models.CharField('Telefone 3', max_length=45, null=True, blank=True)
    
    # Informações Financeiras do Cliente
    vlr_credito_cliente = models.DecimalField('Valor Crédito', max_digits=18, decimal_places=7, null=True, blank=True)
    data_cadastro_cliente = models.DateField('Data Cadastro Cliente', null=True, blank=True)
    saldo_disp_cliente = models.DecimalField('Saldo Disponível', max_digits=18, decimal_places=7, null=True, blank=True)
    vlr_tits_vencido_cliente = models.DecimalField('Títulos Vencidos', max_digits=18, decimal_places=7, default=0, null=True, blank=True)
    vlr_tits_vencer_cliente = models.DecimalField('Títulos a Vencer', max_digits=18, decimal_places=7, default=0, null=True, blank=True)
    status_cred_cliente = models.CharField('Status Crédito', max_length=45, null=True, blank=True)
    codigo_cliente = models.CharField('Código Cliente', max_length=45)
    
    # Segmento do Cliente
    cod_segmento = models.CharField('Código Segmento', max_length=45, null=True, blank=True)
    descr_segmento = models.CharField('Descrição Segmento', max_length=45, null=True, blank=True)
    filial_padrao = models.CharField('Filial Padrão', max_length=45)
    data_ult_compra = models.DateField('Última Compra', null=True, blank=True)
    forma_pgto_cliente = models.CharField('Forma Pagamento Cliente', max_length=45, null=True, blank=True)
    
    # Configurações do Cliente
    retem_icms_cliente = models.CharField('Retém ICMS', max_length=1, choices=[('S', 'Sim'),('N', 'Não')], default='N', null=True, blank=True)
    permite_retira_cliente = models.CharField('Permite Retirada', max_length=1, choices=[('S', 'Sim'),('N', 'Não')], default='N', null=True, blank=True)
    rede_loja_cliente = models.CharField('Rede/Loja', max_length=45, null=True, blank=True)
    
    # Informações de Rota
    praca_cod_erp = models.CharField('Código Praça', max_length=45, null=True, blank=True)
    praca_descricao = models.CharField('Descrição Praça', max_length=45, null=True, blank=True)
    rota_cod_erp = models.CharField('Código Rota', max_length=45, null=True, blank=True)
    rota_descricao = models.CharField('Descrição Rota', max_length=45, null=True, blank=True)
    vendedor_erp = models.CharField('Vendedor ERP', max_length=45, null=True, blank=True)
    data_pedido = models.DateField('Data do Pedido', null=True, blank=True)
    
    # Endereço Alternativo
    codigo_endereco_alt = models.CharField('Código Endereço Alternativo', max_length=45, null=True, blank=True)
    referencia_entrega = models.CharField('Referência Entrega', max_length=200, null=True, blank=True)
    restricao_transp = models.CharField('Restrição Transporte', max_length=45, null=True, blank=True)
    
    # Prioridade e Localização
    prioridade = models.CharField('Prioridade', max_length=1, choices=[ ('S', 'Prioridade Geral'),
                                                                        ('A', 'Prioridade por Agrupamento'),
                                                                        ('N', 'Sem Prioridade')                                                               ], default='N')
    latitude = models.DecimalField('Latitude', max_digits=18, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField('Longitude', max_digits=18, decimal_places=7, null=True, blank=True)
    
    # Campos Adicionais
    valor_adic_number_1 = models.DecimalField('Valor Adicional 1', max_digits=14, decimal_places=4, null=True, blank=True)
    valor_adic_number_2 = models.DecimalField('Valor Adicional 2', max_digits=14, decimal_places=4, null=True, blank=True)
    tipo_nota_fiscal = models.CharField('Tipo Nota Fiscal', max_length=50, choices=[('Venda', 'Venda'),('Transferencia', 'Transferência')], null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sincronizado = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-data_pedido']

    def __str__(self):
        return f'Pedido {self.pedido_erp} - {self.descr_cliente}'

class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='itens')
    cod_produto_erp = models.CharField('Código do Produto ERP', max_length=50)
    descricao = models.CharField('Descrição', max_length=100)
    unidade = models.CharField('Unidade', max_length=45, null=True, blank=True, 
                             choices=[('UN', 'Unidade'),('CX', 'Caixa'),('KG', 'Quilograma'),('LT', 'Litro'),('MT', 'Metro'),('M2', 'Metro Quadrado'),
                                 ('M3', 'Metro Cúbico'),('PC', 'Peça'),('PR', 'Par'),('DZ', 'Dúzia'),('FD', 'Fardo'),('RL', 'Rolo'),('SC', 'Saco'),
                                 ('TB', 'Tambor'),('GL', 'Galão'),('PT', 'Pacote'),('BD', 'Balde'),('CT', 'Cartela'),('FR', 'Frasco'),('GR', 'Grama'),
                                 ('ML', 'Mililitro'),('PÇ', 'Peça'),('RL', 'Rolo'),('SC', 'Saco'),('TB', 'Tambor'),('UN', 'Unidade'),('VD', 'Vidro'),
                                 ('VL', 'Valor'),('ZZ', 'Outros')
                             ])
    qtd = models.DecimalField('Quantidade', max_digits=18, decimal_places=7)
    preco = models.DecimalField('Preço Unitário', max_digits=18, decimal_places=7)
    subtotal = models.DecimalField('Subtotal', max_digits=18, decimal_places=7)
    valor_icms_st = models.DecimalField('Valor ICMS ST', max_digits=18, decimal_places=7, default=0)
    ncm = models.CharField('NCM', max_length=45, null=True, blank=True)
    cst = models.CharField('CST', max_length=45, null=True, blank=True)
    peso = models.DecimalField('Peso (kg)', max_digits=18, decimal_places=7, null=True, blank=True)
    cubagem = models.DecimalField('Cubagem', max_digits=18, decimal_places=7, null=True, blank=True)
    obs_item = models.TextField('Observação', max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Item do Pedido'
        verbose_name_plural = 'Itens do Pedido'
        ordering = ['id']

    def __str__(self):
        return f'{self.cod_produto_erp} - {self.descricao}'

    def save(self, *args, **kwargs):
        # Calcula o subtotal automaticamente
        self.subtotal = self.qtd * self.preco
        super().save(*args, **kwargs)

class Auditoria(models.Model):
    origem = models.CharField(max_length=100, verbose_name="Origem")
    user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Usuário")
    obs = models.TextField(verbose_name="Observação")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")

    class Meta:
        verbose_name = "Auditoria"
        verbose_name_plural = "Auditorias"
        ordering = ['-created']

    def __str__(self):
        return f"{self.origem} - {self.user.username} - {self.created.strftime('%d/%m/%Y %H:%M')}"