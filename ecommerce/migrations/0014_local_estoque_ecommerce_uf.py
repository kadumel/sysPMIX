from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0013_local_estoque_ecommerce'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='localestoqueecommerce',
            name='uniq_local_estoque_ecommerce_empresa',
        ),
        migrations.AddField(
            model_name='localestoqueecommerce',
            name='uf',
            field=models.CharField(db_index=True, default='--', max_length=2, verbose_name='UF'),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='localestoqueecommerce',
            options={
                'ordering': ['codigo_empresa__codigo_empresa', 'uf', 'codigo_local'],
                'verbose_name': 'Local de estoque (e-commerce)',
                'verbose_name_plural': 'Locais de estoque (e-commerce)',
            },
        ),
        migrations.AddConstraint(
            model_name='localestoqueecommerce',
            constraint=models.UniqueConstraint(
                fields=('codigo_empresa', 'uf'),
                name='uniq_local_estoque_ecommerce_empresa_uf',
            ),
        ),
    ]
