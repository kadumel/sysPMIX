from django.db import migrations, models


def converter_sincronizado_boolean_para_char(apps, schema_editor):
    Pedido = apps.get_model('controleBI', 'Pedido')
    for pedido in Pedido.objects.all():
        if pedido.sincronizado_old:
            pedido.sincronizado = 'sim'
        else:
            pedido.sincronizado = 'nao'
        pedido.save(update_fields=['sincronizado'])


class Migration(migrations.Migration):

    dependencies = [
        ('controleBI', '0049_alter_clienteerp_codigo_cliente_unique'),
    ]

    operations = [
        migrations.RenameField(
            model_name='pedido',
            old_name='sincronizado',
            new_name='sincronizado_old',
        ),
        migrations.AddField(
            model_name='pedido',
            name='sincronizado',
            field=models.CharField(
                choices=[('nao', 'Não'), ('sim', 'Sim'), ('erro', 'Erro')],
                default='nao',
                max_length=10,
                verbose_name='Status Envio',
            ),
        ),
        migrations.AddField(
            model_name='pedido',
            name='data_envio',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Data de Envio'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='retorno',
            field=models.TextField(blank=True, null=True, verbose_name='Retorno do Envio'),
        ),
        migrations.RunPython(
            converter_sincronizado_boolean_para_char,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='pedido',
            name='sincronizado_old',
        ),
    ]
