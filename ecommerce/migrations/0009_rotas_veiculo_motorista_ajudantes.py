import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('controleBI', '0046_alter_perfilusuario_perfil_gerente_comercial'),
        ('ecommerce', '0008_alter_rotadia_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='rotapadrao',
            name='motorista',
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={'tipo': 'Motorista'},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rotas_padrao_motorista',
                to='controleBI.funcionario',
                verbose_name='Motorista',
            ),
        ),
        migrations.AddField(
            model_name='rotapadrao',
            name='veiculo',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rotas_padrao',
                to='controleBI.veiculo',
                verbose_name='Veículo',
            ),
        ),
        migrations.AddField(
            model_name='rotadia',
            name='motorista',
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={'tipo': 'Motorista'},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rotas_dia_motorista',
                to='controleBI.funcionario',
                verbose_name='Motorista',
            ),
        ),
        migrations.AddField(
            model_name='rotadia',
            name='veiculo',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rotas_dia',
                to='controleBI.veiculo',
                verbose_name='Veículo',
            ),
        ),
        migrations.CreateModel(
            name='RotaPadraoAjudante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveIntegerField(db_index=True, default=0, verbose_name='Ordem')),
                (
                    'funcionario',
                    models.ForeignKey(
                        limit_choices_to={'tipo': 'Ajudante'},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='rotas_padrao_ajudante',
                        to='controleBI.funcionario',
                        verbose_name='Ajudante',
                    ),
                ),
                (
                    'rota',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='ajudantes_equipe',
                        to='ecommerce.rotapadrao',
                        verbose_name='Rota padrão',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Ajudante da rota padrão',
                'verbose_name_plural': 'Ajudantes da rota padrão',
                'ordering': ['ordem', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RotaDiaAjudante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveIntegerField(db_index=True, default=0, verbose_name='Ordem')),
                (
                    'funcionario',
                    models.ForeignKey(
                        limit_choices_to={'tipo': 'Ajudante'},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='rotas_dia_ajudante',
                        to='controleBI.funcionario',
                        verbose_name='Ajudante',
                    ),
                ),
                (
                    'rota_dia',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='ajudantes_equipe',
                        to='ecommerce.rotadia',
                        verbose_name='Rota do dia',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Ajudante da rota do dia',
                'verbose_name_plural': 'Ajudantes da rota do dia',
                'ordering': ['ordem', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='rotapadraoajudante',
            constraint=models.UniqueConstraint(fields=('rota', 'funcionario'), name='uniq_rota_padrao_ajudante'),
        ),
        migrations.AddConstraint(
            model_name='rotadiaajudante',
            constraint=models.UniqueConstraint(fields=('rota_dia', 'funcionario'), name='uniq_rota_dia_ajudante'),
        ),
    ]
