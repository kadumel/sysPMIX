from django.db import migrations, models


def gerar_imagens_mobile_existentes(apps, schema_editor):
    # Recorte automático removido; o upload da imagem de celular é manual.
    return


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0019_alerta_loja_clientes_m2m'),
    ]

    operations = [
        migrations.AddField(
            model_name='bannerpromocional',
            name='imagem_mobile',
            field=models.ImageField(
                blank=True,
                help_text='Gerada automaticamente no upload (recorte central na proporção do celular).',
                upload_to='ecommerce/banners/mobile/',
                verbose_name='Imagem (celular)',
            ),
        ),
        migrations.AlterField(
            model_name='bannerpromocional',
            name='imagem',
            field=models.ImageField(
                help_text='Arte principal (desktop). No upload, o sistema gera automaticamente a versão para celular.',
                upload_to='ecommerce/banners/',
                verbose_name='Imagem',
            ),
        ),
        migrations.RunPython(gerar_imagens_mobile_existentes, noop_reverse),
    ]
