import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0011_analise_pedido_loja'),
    ]

    operations = [
        migrations.CreateModel(
            name='TopEnvioSankhya',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo_top', models.IntegerField(unique=True, verbose_name='Código TOP')),
                ('codigo_modelo', models.IntegerField(verbose_name='Código modelo')),
                ('descricao', models.CharField(max_length=200, verbose_name='Descrição')),
                ('ativo', models.BooleanField(db_index=True, default=True, verbose_name='Ativo')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'TOP para envio Sankhya',
                'verbose_name_plural': 'TOPs para envio Sankhya',
                'ordering': ['descricao', 'codigo_top'],
            },
        ),
        migrations.AddField(
            model_name='pedidoloja',
            name='top_envio',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pedidos_loja',
                to='ecommerce.topenviosankhya',
                verbose_name='TOP de envio',
            ),
        ),
    ]
