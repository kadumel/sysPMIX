import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards_criar_perfis(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    PerfilUsuario = apps.get_model('controleBI', 'PerfilUsuario')
    for u in User.objects.all():
        PerfilUsuario.objects.get_or_create(
            user_id=u.pk,
            defaults={'perfil': 'comercial'},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('controleBI', '0042_remove_clienteerp_praca_enderecocliente_praca'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilUsuario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'perfil',
                    models.CharField(
                        choices=[
                            ('cliente', 'Cliente (e-commerce)'),
                            ('comercial', 'Comercial (painel BI)'),
                            ('administrador', 'Administrador (Django Admin)'),
                        ],
                        default='comercial',
                        max_length=20,
                        verbose_name='Perfil',
                    ),
                ),
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='perfil_usuario',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Usuário',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Perfil do usuário',
                'verbose_name_plural': 'Perfis de usuário',
            },
        ),
        migrations.RunPython(forwards_criar_perfis, migrations.RunPython.noop),
    ]
