from django.db import migrations, models


def forwards_marcar_todos_visiveis(apps, schema_editor):
    GrupoProduto = apps.get_model('api_sankhya', 'GrupoProduto')
    GrupoProduto.objects.update(mostrar_no_ecommerce=True)


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0018_alter_cidade_codigo_cidade_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='grupoproduto',
            name='mostrar_no_ecommerce',
            field=models.BooleanField(
                default=False,
                help_text='Se marcado, a categoria aparece na navegação da loja (respeitando a hierarquia).',
                verbose_name='Mostrar no e-commerce',
            ),
        ),
        migrations.AddIndex(
            model_name='grupoproduto',
            index=models.Index(fields=['ativo', 'mostrar_no_ecommerce'], name='sankhya_gru_ativo_m_6a8b2c_idx'),
        ),
        migrations.RunPython(forwards_marcar_todos_visiveis, migrations.RunPython.noop),
    ]
