import django.db.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ecommerce', '0001_pedido_loja_notificacao'),
    ]

    operations = [
        migrations.CreateModel(
            name='BannerPromocional',
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
                ('titulo', models.CharField(blank=True, max_length=120, verbose_name='Título')),
                (
                    'imagem',
                    models.ImageField(upload_to='ecommerce/banners/', verbose_name='Imagem'),
                ),
                ('link', models.URLField(blank=True, verbose_name='Link')),
                (
                    'ordem',
                    models.PositiveIntegerField(
                        db_index=True, default=0, verbose_name='Ordem'
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
            ],
            options={
                'verbose_name': 'Banner promocional',
                'verbose_name_plural': 'Banners promocionais',
                'ordering': ['ordem', '-criado_em'],
            },
        ),
    ]
