from django.db import migrations


def normalizar_status_envio_legado(apps, schema_editor):
    Pedido = apps.get_model('controleBI', 'Pedido')
    Pedido.objects.filter(sincronizado__in=['0', 'False', 'false']).update(sincronizado='nao')
    Pedido.objects.filter(sincronizado__in=['1', 'True', 'true']).update(sincronizado='sim')


class Migration(migrations.Migration):

    dependencies = [
        ('controleBI', '0050_pedido_envio_fields'),
    ]

    operations = [
        migrations.RunPython(
            normalizar_status_envio_legado,
            migrations.RunPython.noop,
        ),
    ]
