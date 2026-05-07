from django.conf import settings
from django.db import models
import os


class PedidoLoja(models.Model):
    """Pedido originado no e-commerce; aguarda análise comercial antes da integração externa."""

    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente (análise comercial)'
        AUTORIZADO = 'autorizado', 'Autorizado (integrado)'
        REJEITADO = 'rejeitado', 'Rejeitado'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='pedidos_loja',
        verbose_name='Usuário',
    )
    cliente = models.ForeignKey(
        'api_sankhya.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_loja',
        verbose_name='Cliente Sankhya',
    )
    codtab = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Código da tabela de preço',
    )
    valor_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='Valor total',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
        verbose_name='Status',
    )
    observacao_comercial = models.TextField(
        blank=True,
        verbose_name='Observações do comercial',
        help_text='Visível ao cliente e gera notificação quando alterado.',
    )
    codigo_pedido_externo = models.CharField(
        max_length=80,
        blank=True,
        verbose_name='Código no sistema externo',
        help_text='Preenchido após integração (ERP/Sankhya etc.).',
    )
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_loja_aprovados',
        verbose_name='Aprovado por',
    )
    aprovado_em = models.DateTimeField(null=True, blank=True, verbose_name='Data da autorização')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        verbose_name = 'Pedido da loja'
        verbose_name_plural = 'Pedidos da loja'
        ordering = ['-criado_em']

    def __str__(self):
        return f'Pedido #{self.pk} — {self.get_status_display()}'


class ItemPedidoLoja(models.Model):
    pedido = models.ForeignKey(
        PedidoLoja,
        on_delete=models.CASCADE,
        related_name='itens',
        verbose_name='Pedido',
    )
    codigo_produto = models.IntegerField(verbose_name='Código produto')
    nome_produto = models.CharField(max_length=300, verbose_name='Nome (snapshot)')
    quantidade = models.DecimalField(max_digits=15, decimal_places=4, verbose_name='Quantidade')
    preco_unitario = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='Preço unitário',
    )
    valor_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='Valor total do item',
    )

    class Meta:
        verbose_name = 'Item do pedido (loja)'
        verbose_name_plural = 'Itens do pedido (loja)'
        ordering = ['id']

    def __str__(self):
        return f'{self.codigo_produto} x {self.quantidade}'


class NotificacaoLoja(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificacoes_loja',
        verbose_name='Usuário',
    )
    pedido = models.ForeignKey(
        PedidoLoja,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notificacoes',
        verbose_name='Pedido',
    )
    titulo = models.CharField(max_length=200, verbose_name='Título')
    mensagem = models.TextField(verbose_name='Mensagem')
    lida = models.BooleanField(default=False, db_index=True, verbose_name='Lida')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    class Meta:
        verbose_name = 'Notificação da loja'
        verbose_name_plural = 'Notificações da loja'
        ordering = ['-criado_em']

    def __str__(self):
        return self.titulo


class BannerPromocional(models.Model):
    titulo = models.CharField('Título', max_length=120, blank=True)
    descricao_curta = models.CharField('Descrição curta', max_length=220, blank=True)
    descricao_longa = models.TextField('Descrição longa', blank=True)
    call_to_action = models.CharField('Call-to-action', max_length=120, blank=True)
    imagem = models.ImageField('Imagem', upload_to='ecommerce/banners/')
    link = models.URLField('Link', blank=True)
    ordem = models.PositiveIntegerField('Ordem', default=0, db_index=True)
    ativo = models.BooleanField('Ativo', default=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Banner promocional'
        verbose_name_plural = 'Banners promocionais'
        ordering = ['ordem', '-criado_em']

    def __str__(self):
        return self.titulo or f'Banner #{self.pk}'


def _produto_imagem_upload_to(instance, filename):
    """Subpasta configurável via MEDIA_PRODUCT_IMAGES_UPLOAD_TO em settings."""
    sub = getattr(settings, 'MEDIA_PRODUCT_IMAGES_UPLOAD_TO', 'ecommerce/produtos/')
    sub = sub.strip().strip('/')
    if not sub:
        sub = 'ecommerce/produtos'
    return f'{sub}/{filename}'


class ProdutoImagem(models.Model):
    produto = models.ForeignKey(
        'api_sankhya.Produto',
        on_delete=models.CASCADE,
        related_name='imagens_ecommerce',
        verbose_name='Produto Sankhya',
    )
    nome_imagem = models.CharField('Nome da imagem', max_length=255, blank=True)
    imagem = models.ImageField('Imagem', upload_to=_produto_imagem_upload_to)
    ativo = models.BooleanField('Ativo', default=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Imagem de produto (e-commerce)'
        verbose_name_plural = 'Imagens de produto (e-commerce)'
        ordering = ['produto__codigo_produto', 'id']

    def __str__(self):
        return f'{self.produto.codigo_produto} - {self.nome_imagem or "imagem"}'

    def save(self, *args, **kwargs):
        if self.imagem and not self.nome_imagem:
            self.nome_imagem = os.path.basename(self.imagem.name)
        super().save(*args, **kwargs)


class RotaPadrao(models.Model):
    nome = models.CharField(max_length=120, verbose_name='Nome')
    descricao = models.TextField(blank=True, verbose_name='Descrição')
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='rotas_padrao_responsavel',
        verbose_name='Responsável comercial',
    )
    veiculo = models.ForeignKey(
        'controleBI.Veiculo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rotas_padrao',
        verbose_name='Veículo',
    )
    motorista = models.ForeignKey(
        'controleBI.Funcionario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rotas_padrao_motorista',
        limit_choices_to={'tipo': 'Motorista'},
        verbose_name='Motorista',
    )
    ativa = models.BooleanField(default=True, db_index=True, verbose_name='Ativa')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        verbose_name = 'Rota padrão'
        verbose_name_plural = 'Rotas padrão'
        ordering = ['nome', 'id']

    def __str__(self):
        return self.nome


class RotaPadraoAjudante(models.Model):
    rota = models.ForeignKey(
        RotaPadrao,
        on_delete=models.CASCADE,
        related_name='ajudantes_equipe',
        verbose_name='Rota padrão',
    )
    funcionario = models.ForeignKey(
        'controleBI.Funcionario',
        on_delete=models.CASCADE,
        related_name='rotas_padrao_ajudante',
        limit_choices_to={'tipo': 'Ajudante'},
        verbose_name='Ajudante',
    )
    ordem = models.PositiveIntegerField(default=0, db_index=True, verbose_name='Ordem')

    class Meta:
        verbose_name = 'Ajudante da rota padrão'
        verbose_name_plural = 'Ajudantes da rota padrão'
        ordering = ['ordem', 'id']
        constraints = [
            models.UniqueConstraint(fields=['rota', 'funcionario'], name='uniq_rota_padrao_ajudante'),
        ]

    def __str__(self):
        return f'{self.rota} — {self.funcionario}'


class RotaPadraoCliente(models.Model):
    rota = models.ForeignKey(
        RotaPadrao,
        on_delete=models.CASCADE,
        related_name='clientes_rota',
        verbose_name='Rota padrão',
    )
    cliente = models.ForeignKey(
        'api_sankhya.Cliente',
        on_delete=models.CASCADE,
        related_name='rotas_padrao',
        verbose_name='Cliente',
    )
    ordem = models.PositiveIntegerField(default=0, db_index=True, verbose_name='Ordem')

    class Meta:
        verbose_name = 'Cliente da rota padrão'
        verbose_name_plural = 'Clientes da rota padrão'
        ordering = ['ordem', 'id']
        constraints = [
            models.UniqueConstraint(fields=['rota', 'cliente'], name='uniq_rota_padrao_cliente'),
        ]

    def __str__(self):
        return f'{self.rota} - {self.cliente}'


class RotaDia(models.Model):
    data = models.DateField(db_index=True, verbose_name='Data')
    rota_padrao = models.ForeignKey(
        RotaPadrao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='execucoes',
        verbose_name='Rota padrão base',
    )
    veiculo = models.ForeignKey(
        'controleBI.Veiculo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rotas_dia',
        verbose_name='Veículo',
    )
    motorista = models.ForeignKey(
        'controleBI.Funcionario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rotas_dia_motorista',
        limit_choices_to={'tipo': 'Motorista'},
        verbose_name='Motorista',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='rotas_dia_criadas',
        verbose_name='Criado por',
    )
    observacao = models.TextField(blank=True, verbose_name='Observações')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        verbose_name = 'Rota do dia'
        verbose_name_plural = 'Rotas do dia'
        ordering = ['-data']

    def __str__(self):
        return f'Rota do dia {self.data:%d/%m/%Y}'


class RotaDiaAjudante(models.Model):
    rota_dia = models.ForeignKey(
        RotaDia,
        on_delete=models.CASCADE,
        related_name='ajudantes_equipe',
        verbose_name='Rota do dia',
    )
    funcionario = models.ForeignKey(
        'controleBI.Funcionario',
        on_delete=models.CASCADE,
        related_name='rotas_dia_ajudante',
        limit_choices_to={'tipo': 'Ajudante'},
        verbose_name='Ajudante',
    )
    ordem = models.PositiveIntegerField(default=0, db_index=True, verbose_name='Ordem')

    class Meta:
        verbose_name = 'Ajudante da rota do dia'
        verbose_name_plural = 'Ajudantes da rota do dia'
        ordering = ['ordem', 'id']
        constraints = [
            models.UniqueConstraint(fields=['rota_dia', 'funcionario'], name='uniq_rota_dia_ajudante'),
        ]

    def __str__(self):
        return f'{self.rota_dia} — {self.funcionario}'


class RotaDiaCliente(models.Model):
    rota_dia = models.ForeignKey(
        RotaDia,
        on_delete=models.CASCADE,
        related_name='clientes_rota',
        verbose_name='Rota do dia',
    )
    cliente = models.ForeignKey(
        'api_sankhya.Cliente',
        on_delete=models.CASCADE,
        related_name='rotas_dia',
        verbose_name='Cliente',
    )
    ordem = models.PositiveIntegerField(default=0, db_index=True, verbose_name='Ordem')

    class Meta:
        verbose_name = 'Cliente da rota do dia'
        verbose_name_plural = 'Clientes da rota do dia'
        ordering = ['ordem', 'id']
        constraints = [
            models.UniqueConstraint(fields=['rota_dia', 'cliente'], name='uniq_rota_dia_cliente'),
        ]

    def __str__(self):
        return f'{self.rota_dia} - {self.cliente}'
