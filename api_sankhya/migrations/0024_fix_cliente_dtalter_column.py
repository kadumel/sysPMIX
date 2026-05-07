from django.db import migrations


SQLSERVER_VENDORS = {"microsoft", "mssql", "sql_server"}


def _rename_dataalter_to_dtalter(apps, schema_editor):
    if schema_editor.connection.vendor not in SQLSERVER_VENDORS:
        return

    schema_editor.execute(
        """
IF COL_LENGTH('sankhya_cliente', 'dataalter') IS NOT NULL
   AND COL_LENGTH('sankhya_cliente', 'dtalter') IS NULL
BEGIN
    EXEC sp_rename 'sankhya_cliente.dataalter', 'dtalter', 'COLUMN';
END
"""
    )


def _rename_dtalter_to_dataalter(apps, schema_editor):
    if schema_editor.connection.vendor not in SQLSERVER_VENDORS:
        return

    schema_editor.execute(
        """
IF COL_LENGTH('sankhya_cliente', 'dtalter') IS NOT NULL
   AND COL_LENGTH('sankhya_cliente', 'dataalter') IS NULL
BEGIN
    EXEC sp_rename 'sankhya_cliente.dtalter', 'dataalter', 'COLUMN';
END
"""
    )


class Migration(migrations.Migration):

    dependencies = [
        ("api_sankhya", "0023_cliente_dataalter"),
    ]

    operations = [
        migrations.RunPython(
            _rename_dataalter_to_dtalter,
            _rename_dtalter_to_dataalter,
        ),
    ]
