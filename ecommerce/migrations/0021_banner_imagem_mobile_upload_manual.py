from django.db import migrations, models


def limpar_imagens_mobile_automaticas(apps, schema_editor):
    """Remove recortes gerados automaticamente; o upload passa a ser manual."""
    BannerPromocional = apps.get_model('ecommerce', 'BannerPromocional')
    for banner in BannerPromocional.objects.exclude(imagem_mobile='').iterator():
        banner.imagem_mobile.delete(save=False)
        banner.imagem_mobile = ''
        banner.save(update_fields=['imagem_mobile'])


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0020_bannerpromocional_imagem_mobile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bannerpromocional',
            name='imagem',
            field=models.ImageField(
                help_text='Tamanho padrão: 1920 × 360 px (proporção panorâmica). Usada no computador.',
                upload_to='ecommerce/banners/',
                verbose_name='Imagem (desktop)',
            ),
        ),
        migrations.AlterField(
            model_name='bannerpromocional',
            name='imagem_mobile',
            field=models.ImageField(
                blank=True,
                help_text='Tamanho padrão: 1080 × 640 px. Envie uma arte própria para o celular. Se ficar vazio, a loja usa a imagem de desktop.',
                upload_to='ecommerce/banners/mobile/',
                verbose_name='Imagem (celular / PWA)',
            ),
        ),
        migrations.RunPython(limpar_imagens_mobile_automaticas, migrations.RunPython.noop),
    ]
