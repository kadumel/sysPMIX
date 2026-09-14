from django.db import migrations, models


def gerar_imagens_mobile_existentes(apps, schema_editor):
    BannerPromocional = apps.get_model('ecommerce', 'BannerPromocional')
    from ecommerce.banner_images import criar_arquivo_banner_mobile

    for banner in BannerPromocional.objects.exclude(imagem='').iterator():
        if banner.imagem_mobile:
            continue
        try:
            nome, conteudo = criar_arquivo_banner_mobile(banner.imagem)
        except Exception:
            continue
        banner.imagem_mobile.save(nome, conteudo, save=True)


def noop_reverse(apps, schema_editor):
    BannerPromocional = apps.get_model('ecommerce', 'BannerPromocional')
    for banner in BannerPromocional.objects.exclude(imagem_mobile='').iterator():
        banner.imagem_mobile.delete(save=False)
        banner.imagem_mobile = ''
        banner.save(update_fields=['imagem_mobile'])


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
