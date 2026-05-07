import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0018_alter_cidade_codigo_cidade_and_more'),
        ('controleBI', '0043_perfilusuario'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UsuarioClienteSankhya',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'cliente',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='usuarios_sistema',
                        to='api_sankhya.cliente',
                        verbose_name='Cliente Sankhya',
                    ),
                ),
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='vinculo_cliente_sankhya',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Usuário',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Usuário de cliente Sankhya',
                'verbose_name_plural': 'Usuários de clientes Sankhya',
                'ordering': ['cliente', 'user__username'],
            },
        ),
    ]
