from django.db import migrations, models


def popular_ordem(apps, schema_editor):
    GrupoProduto = apps.get_model('api_sankhya', 'GrupoProduto')
    usados = set()
    for g in GrupoProduto.objects.all().order_by('nome', 'codigo_grupo_produto'):
        candidato = g.codigo_grupo_produto
        if candidato is None or candidato in usados:
            candidato = 1
            while candidato in usados:
                candidato += 1
        g.ordem = candidato
        g.save(update_fields=['ordem'])
        usados.add(candidato)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0035_grupoproduto_tipo_loja'),
    ]

    operations = [
        migrations.AddField(
            model_name='grupoproduto',
            name='ordem',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Define a ordem de exibição das categorias (e dos produtos) no e-commerce. Deve ser único.',
                null=True,
                verbose_name='Ordem na loja',
            ),
        ),
        migrations.RunPython(popular_ordem, noop_reverse),
        migrations.AlterField(
            model_name='grupoproduto',
            name='ordem',
            field=models.PositiveIntegerField(
                help_text='Define a ordem de exibição das categorias (e dos produtos) no e-commerce. Deve ser único.',
                unique=True,
                verbose_name='Ordem na loja',
            ),
        ),
        migrations.AlterModelOptions(
            name='grupoproduto',
            options={
                'ordering': ['ordem', 'nome', 'codigo_grupo_produto'],
                'verbose_name': 'Grupo Produto Sankhya',
                'verbose_name_plural': 'Grupos Produto Sankhya',
            },
        ),
        migrations.AddIndex(
            model_name='grupoproduto',
            index=models.Index(fields=['ordem'], name='sankhya_gru_ordem_7c2a1b_idx'),
        ),
    ]
