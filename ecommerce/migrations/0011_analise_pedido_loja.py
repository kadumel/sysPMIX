import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0010_campanha_itemcampanha'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnalisePedidoLoja',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tempo_analise_meses', models.PositiveIntegerField(default=2, verbose_name='Período analisado (meses)')),
                ('gerada_em', models.DateTimeField(auto_now_add=True, verbose_name='Gerada em')),
                ('pedido', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='analise', to='ecommerce.pedidoloja', verbose_name='Pedido')),
            ],
            options={
                'verbose_name': 'Análise do pedido (loja)',
                'verbose_name_plural': 'Análises dos pedidos (loja)',
            },
        ),
        migrations.CreateModel(
            name='ItemAnalisePedidoLoja',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('esquecidos', 'Itens que costuma pedir'), ('novidades', 'Novidades'), ('curva_a', 'Curva A (alto giro)')], db_index=True, max_length=20, verbose_name='Tipo')),
                ('codigo_produto', models.IntegerField(verbose_name='Código produto')),
                ('nome_produto', models.CharField(max_length=300, verbose_name='Nome do produto')),
                ('grupo_produto', models.CharField(blank=True, max_length=200, verbose_name='Grupo de produto')),
                ('detalhe', models.CharField(blank=True, help_text='Ex.: frequência no histórico, campanha, posição na curva A.', max_length=200, verbose_name='Detalhe')),
                ('ordem', models.PositiveIntegerField(default=0, verbose_name='Ordem')),
                ('analise', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='ecommerce.analisepedidoloja', verbose_name='Análise')),
            ],
            options={
                'verbose_name': 'Item da análise do pedido',
                'verbose_name_plural': 'Itens da análise do pedido',
                'ordering': ['tipo', 'ordem', 'codigo_produto'],
            },
        ),
        migrations.AddConstraint(
            model_name='itemanalisepedidoloja',
            constraint=models.UniqueConstraint(fields=('analise', 'codigo_produto'), name='uniq_analise_pedido_produto'),
        ),
    ]
