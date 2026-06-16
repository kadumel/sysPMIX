from django.db import migrations, models


def deduplicar_locais_por_uf(apps, schema_editor):
    LocalEstoqueEcommerce = apps.get_model('ecommerce', 'LocalEstoqueEcommerce')
    vistos = set()
    for local in LocalEstoqueEcommerce.objects.order_by('-ativo', 'id'):
        uf = (local.uf or '').strip().upper()
        if not uf or uf in vistos:
            local.delete()
            continue
        vistos.add(uf)
        if local.uf != uf:
            local.uf = uf
            local.save(update_fields=['uf'])


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0014_local_estoque_ecommerce_uf'),
    ]

    operations = [
        migrations.RunPython(deduplicar_locais_por_uf, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='localestoqueecommerce',
            name='uniq_local_estoque_ecommerce_empresa_uf',
        ),
        migrations.RemoveField(
            model_name='localestoqueecommerce',
            name='codigo_empresa',
        ),
        migrations.AlterField(
            model_name='localestoqueecommerce',
            name='uf',
            field=models.CharField(db_index=True, max_length=2, unique=True, verbose_name='UF'),
        ),
        migrations.AlterModelOptions(
            name='localestoqueecommerce',
            options={
                'ordering': ['uf', 'codigo_local'],
                'verbose_name': 'Local de estoque (e-commerce)',
                'verbose_name_plural': 'Locais de estoque (e-commerce)',
            },
        ),
    ]
