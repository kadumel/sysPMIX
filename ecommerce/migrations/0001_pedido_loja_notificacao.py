# Generated manually for environments without local DB driver.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api_sankhya', '0019_grupoproduto_mostrar_no_ecommerce'),
    ]

    operations = [
        migrations.CreateModel(
            name='PedidoLoja',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pendente', 'Pendente (análise comercial)'),
                            ('autorizado', 'Autorizado (integrado)'),
                            ('rejeitado', 'Rejeitado'),
                        ],
                        db_index=True,
                        default='pendente',
                        max_length=20,
                        verbose_name='Status',
                    ),
                ),
                (
                    'observacao_comercial',
                    models.TextField(
                        blank=True,
                        help_text='Visível ao cliente e gera notificação quando alterado.',
                        verbose_name='Observações do comercial',
                    ),
                ),
                (
                    'codigo_pedido_externo',
                    models.CharField(
                        blank=True,
                        help_text='Preenchido após integração (ERP/Sankhya etc.).',
                        max_length=80,
                        verbose_name='Código no sistema externo',
                    ),
                ),
                (
                    'aprovado_em',
                    models.DateTimeField(
                        blank=True, null=True, verbose_name='Data da autorização'
                    ),
                ),
                (
                    'criado_em',
                    models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
                ),
                (
                    'atualizado_em',
                    models.DateTimeField(auto_now=True, verbose_name='Atualizado em'),
                ),
                (
                    'aprovado_por',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='pedidos_loja_aprovados',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Aprovado por',
                    ),
                ),
                (
                    'cliente',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='pedidos_loja',
                        to='api_sankhya.cliente',
                        verbose_name='Cliente Sankhya',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='pedidos_loja',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Usuário',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Pedido da loja',
                'verbose_name_plural': 'Pedidos da loja',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='ItemPedidoLoja',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('codigo_produto', models.IntegerField(verbose_name='Código produto')),
                (
                    'nome_produto',
                    models.CharField(max_length=300, verbose_name='Nome (snapshot)'),
                ),
                (
                    'quantidade',
                    models.DecimalField(
                        decimal_places=4, max_digits=15, verbose_name='Quantidade'
                    ),
                ),
                (
                    'pedido',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='itens',
                        to='ecommerce.pedidoloja',
                        verbose_name='Pedido',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Item do pedido (loja)',
                'verbose_name_plural': 'Itens do pedido (loja)',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='NotificacaoLoja',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('titulo', models.CharField(max_length=200, verbose_name='Título')),
                ('mensagem', models.TextField(verbose_name='Mensagem')),
                (
                    'lida',
                    models.BooleanField(
                        db_index=True, default=False, verbose_name='Lida'
                    ),
                ),
                (
                    'criado_em',
                    models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
                ),
                (
                    'pedido',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='notificacoes',
                        to='ecommerce.pedidoloja',
                        verbose_name='Pedido',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='notificacoes_loja',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Usuário',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Notificação da loja',
                'verbose_name_plural': 'Notificações da loja',
                'ordering': ['-criado_em'],
            },
        ),
    ]
