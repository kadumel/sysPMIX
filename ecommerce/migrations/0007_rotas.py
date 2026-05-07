from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0021_merge_0017_cliente_0020_grupo'),
        ('ecommerce', '0006_pedido_valores_por_tabela_preco'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RotaPadrao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120, verbose_name='Nome')),
                ('descricao', models.TextField(blank=True, verbose_name='Descrição')),
                ('ativa', models.BooleanField(db_index=True, default=True, verbose_name='Ativa')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('responsavel', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rotas_padrao_responsavel', to=settings.AUTH_USER_MODEL, verbose_name='Responsável comercial')),
            ],
            options={
                'verbose_name': 'Rota padrão',
                'verbose_name_plural': 'Rotas padrão',
                'ordering': ['nome', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RotaDia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField(db_index=True, unique=True, verbose_name='Data')),
                ('observacao', models.TextField(blank=True, verbose_name='Observações')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('criado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rotas_dia_criadas', to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
                ('rota_padrao', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='execucoes', to='ecommerce.rotapadrao', verbose_name='Rota padrão base')),
            ],
            options={
                'verbose_name': 'Rota do dia',
                'verbose_name_plural': 'Rotas do dia',
                'ordering': ['-data'],
            },
        ),
        migrations.CreateModel(
            name='RotaPadraoCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveIntegerField(db_index=True, default=0, verbose_name='Ordem')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rotas_padrao', to='api_sankhya.cliente', verbose_name='Cliente')),
                ('rota', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clientes_rota', to='ecommerce.rotapadrao', verbose_name='Rota padrão')),
            ],
            options={
                'verbose_name': 'Cliente da rota padrão',
                'verbose_name_plural': 'Clientes da rota padrão',
                'ordering': ['ordem', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RotaDiaCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveIntegerField(db_index=True, default=0, verbose_name='Ordem')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rotas_dia', to='api_sankhya.cliente', verbose_name='Cliente')),
                ('rota_dia', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clientes_rota', to='ecommerce.rotadia', verbose_name='Rota do dia')),
            ],
            options={
                'verbose_name': 'Cliente da rota do dia',
                'verbose_name_plural': 'Clientes da rota do dia',
                'ordering': ['ordem', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='rotapadraocliente',
            constraint=models.UniqueConstraint(fields=('rota', 'cliente'), name='uniq_rota_padrao_cliente'),
        ),
        migrations.AddConstraint(
            model_name='rotadiacliente',
            constraint=models.UniqueConstraint(fields=('rota_dia', 'cliente'), name='uniq_rota_dia_cliente'),
        ),
    ]
