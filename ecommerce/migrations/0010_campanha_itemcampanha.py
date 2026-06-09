import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0032_cliente_tempo_analise'),
        ('ecommerce', '0009_rotas_veiculo_motorista_ajudantes'),
    ]

    operations = [
        migrations.CreateModel(
            name='Campanha',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120, verbose_name='Nome')),
                ('descricao', models.TextField(blank=True, verbose_name='Descrição')),
                ('data_inicio', models.DateField(db_index=True, verbose_name='Data de início')),
                ('data_fim', models.DateField(db_index=True, verbose_name='Data de fim')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'Campanha',
                'verbose_name_plural': 'Campanhas',
                'ordering': ['-data_inicio', 'nome'],
            },
        ),
        migrations.CreateModel(
            name='ItemCampanha',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('campanha', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='ecommerce.campanha', verbose_name='Campanha')),
                ('produto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens_campanha', to='api_sankhya.produto', verbose_name='Produto Sankhya')),
            ],
            options={
                'verbose_name': 'Item da campanha',
                'verbose_name_plural': 'Itens da campanha',
                'ordering': ['campanha', 'produto__codigo_produto'],
            },
        ),
        migrations.AddConstraint(
            model_name='itemcampanha',
            constraint=models.UniqueConstraint(fields=('campanha', 'produto'), name='uniq_campanha_produto'),
        ),
    ]
