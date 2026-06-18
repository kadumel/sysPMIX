from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0015_local_estoque_por_uf'),
    ]

    operations = [
        migrations.RenameField(
            model_name='pedidoloja',
            old_name='codigo_pedido_externo',
            new_name='codigo_pedido_sankhya',
        ),
        migrations.AlterField(
            model_name='pedidoloja',
            name='codigo_pedido_sankhya',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Preenchido com retorno.codigoPedido após inclusão bem-sucedida na API Sankhya.',
                max_length=20,
                verbose_name='Código do pedido no Sankhya',
            ),
        ),
    ]
