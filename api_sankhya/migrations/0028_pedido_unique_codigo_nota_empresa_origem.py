from django.db import migrations, models


def _drop_old_pedido_unique_constraints(apps, schema_editor):
    if schema_editor.connection.vendor != 'microsoft':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DECLARE @name SYSNAME;
            DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
                SELECT kc.name
                FROM sys.key_constraints kc
                INNER JOIN sys.tables t ON kc.parent_object_id = t.object_id
                WHERE t.name = 'sankhya_pedido'
                  AND kc.type = 'UQ'
                  AND kc.name NOT LIKE 'pedido_codigo_nota_codigo_empresa_origem%'
            OPEN cur;
            FETCH NEXT FROM cur INTO @name;
            WHILE @@FETCH_STATUS = 0
            BEGIN
                DECLARE @sql NVARCHAR(MAX) =
                    N'ALTER TABLE dbo.sankhya_pedido DROP CONSTRAINT ' + QUOTENAME(@name);
                EXEC sp_executesql @sql;
                FETCH NEXT FROM cur INTO @name;
            END
            CLOSE cur;
            DEALLOCATE cur;
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0027_pedido_origem_ensure'),
    ]

    operations = [
        migrations.RunPython(_drop_old_pedido_unique_constraints, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='pedido',
            unique_together={('codigo_nota', 'codigo_empresa', 'origem')},
        ),
        migrations.RemoveIndex(
            model_name='pedido',
            name='sankhya_ped_origem_4a1b2c_idx',
        ),
        migrations.AddIndex(
            model_name='pedido',
            index=models.Index(
                fields=['codigo_nota', 'codigo_empresa', 'origem'],
                name='sankhya_ped_nota_empr_orig_idx',
            ),
        ),
    ]
