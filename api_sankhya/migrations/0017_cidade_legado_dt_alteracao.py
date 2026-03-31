# Generated manually for Cidade alignment with getCidadeLegado

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0016_funcionario'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cidade',
            name='nome',
            field=models.CharField(max_length=200, verbose_name='Nome (NOMECID)'),
        ),
        migrations.AddField(
            model_name='cidade',
            name='dt_alteracao',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Data alteração legado (DTALTER)'),
        ),
    ]
