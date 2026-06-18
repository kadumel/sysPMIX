import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0002_empresa'),
        ('ecommerce', '0012_top_envio_sankhya_pedido_top_envio'),
    ]

    operations = [
        migrations.CreateModel(
            name='LocalEstoqueEcommerce',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo_local', models.CharField(max_length=12, verbose_name='Código do local')),
                ('ativo', models.BooleanField(db_index=True, default=True, verbose_name='Ativo')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                (
                    'codigo_empresa',
                    models.ForeignKey(
                        db_column='codigo_empresa',
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='locais_estoque_ecommerce',
                        to='api_sankhya.empresa',
                        to_field='codigo_empresa',
                        verbose_name='Empresa',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Local de estoque (e-commerce)',
                'verbose_name_plural': 'Locais de estoque (e-commerce)',
                'ordering': ['codigo_empresa__codigo_empresa', 'codigo_local'],
            },
        ),
        migrations.AddConstraint(
            model_name='localestoqueecommerce',
            constraint=models.UniqueConstraint(fields=('codigo_empresa',), name='uniq_local_estoque_ecommerce_empresa'),
        ),
    ]
