from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api_sankhya", "0022_rename_sankhya_cli_codtab_a28c70_idx_sankhya_cli_codtab_0d4c78_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="dtalter",
            field=models.CharField(
                blank=True,
                max_length=50,
                null=True,
                verbose_name="Data Alteração (DTALTER)",
            ),
        ),
    ]
