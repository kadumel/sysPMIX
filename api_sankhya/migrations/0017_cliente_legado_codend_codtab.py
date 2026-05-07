from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api_sankhya", "0016_funcionario"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="cliente",
            name="sankhya_cli_uf_dc098c_idx",
        ),
        migrations.RemoveField(
            model_name="cliente",
            name="codigo_ibge",
        ),
        migrations.RemoveField(
            model_name="cliente",
            name="logradouro",
        ),
        migrations.RemoveField(
            model_name="cliente",
            name="uf",
        ),
        migrations.AddField(
            model_name="cliente",
            name="codend",
            field=models.IntegerField(blank=True, null=True, verbose_name="Código do Endereço"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="codtab",
            field=models.IntegerField(blank=True, null=True, verbose_name="Código da Tabela de Preço"),
        ),
        migrations.AddIndex(
            model_name="cliente",
            index=models.Index(fields=["codtab"], name="sankhya_cli_codtab_a28c70_idx"),
        ),
        migrations.AddIndex(
            model_name="cliente",
            index=models.Index(fields=["codend"], name="sankhya_cli_codend_94f051_idx"),
        ),
    ]
