import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api_sankhya', '0019_grupoproduto_mostrar_no_ecommerce'),
        ('ecommerce', '0003_bannerpromocional_conteudo'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProdutoImagem',
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
                    'nome_imagem',
                    models.CharField(
                        blank=True, max_length=255, verbose_name='Nome da imagem'
                    ),
                ),
                (
                    'imagem',
                    models.ImageField(
                        upload_to='ecommerce/produtos/', verbose_name='Imagem'
                    ),
                ),
                (
                    'ativo',
                    models.BooleanField(db_index=True, default=True, verbose_name='Ativo'),
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
                    'produto',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='imagens_ecommerce',
                        to='api_sankhya.produto',
                        verbose_name='Produto Sankhya',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Imagem de produto (e-commerce)',
                'verbose_name_plural': 'Imagens de produto (e-commerce)',
                'ordering': ['produto__codigo_produto', 'id'],
            },
        ),
    ]
