from django.db import migrations


def _ensure_pedido_origem_schema(apps, schema_editor):
    """Garante coluna origem e unique (origem, codigo_nota) mesmo se 0026 foi fake/aplicada parcialmente."""
    if schema_editor.connection.vendor != 'microsoft':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT DB_NAME(), @@SERVERNAME")
        db_name, server_name = cursor.fetchone()
        print(f'[0027] Banco: {db_name} | Servidor: {server_name}')

        cursor.execute(
            "SELECT COL_LENGTH('dbo.sankhya_pedido', 'origem')"
        )
        if cursor.fetchone()[0] is None:
            print('[0027] Adicionando coluna origem em dbo.sankhya_pedido...')
            cursor.execute(
                """
                ALTER TABLE dbo.sankhya_pedido
                ADD origem NVARCHAR(50) NOT NULL
                    CONSTRAINT DF_sankhya_pedido_origem DEFAULT 'SANKHYA' WITH VALUES
                """
            )
        else:
            print('[0027] Coluna origem já existe.')

        cursor.execute(
            """
            UPDATE dbo.sankhya_pedido
            SET origem = 'SANKHYA'
            WHERE origem IS NULL OR LTRIM(RTRIM(origem)) = ''
            """
        )

        cursor.execute(
            """
            DECLARE @constraint SYSNAME;
            SELECT @constraint = kc.name
            FROM sys.key_constraints kc
            INNER JOIN sys.tables t ON kc.parent_object_id = t.object_id
            INNER JOIN sys.index_columns ic
                ON kc.parent_object_id = ic.object_id AND kc.unique_index_id = ic.index_id
            INNER JOIN sys.columns c
                ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            WHERE t.name = 'sankhya_pedido'
              AND kc.type = 'UQ'
            GROUP BY kc.name
            HAVING COUNT(*) = 1 AND MAX(c.name) = 'codigo_nota';

            IF @constraint IS NOT NULL
            BEGIN
                DECLARE @drop_sql NVARCHAR(MAX) =
                    N'ALTER TABLE dbo.sankhya_pedido DROP CONSTRAINT ' + QUOTENAME(@constraint);
                EXEC sp_executesql @drop_sql;
            END
            """
        )

        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1
                FROM sys.key_constraints kc
                INNER JOIN sys.tables t ON kc.parent_object_id = t.object_id
                WHERE t.name = 'sankhya_pedido'
                  AND kc.name = 'sankhya_pedido_origem_codigo_nota_uniq'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM sys.key_constraints kc
                INNER JOIN sys.tables t ON kc.parent_object_id = t.object_id
                WHERE t.name = 'sankhya_pedido'
                  AND kc.name LIKE 'sankhya_pedido_origem_codigo_nota%'
            )
            BEGIN
                ALTER TABLE dbo.sankhya_pedido
                ADD CONSTRAINT sankhya_pedido_origem_codigo_nota_uniq
                    UNIQUE (origem, codigo_nota);
            END
            """
        )

        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1 FROM sys.indexes i
                INNER JOIN sys.tables t ON i.object_id = t.object_id
                WHERE t.name = 'sankhya_pedido' AND i.name = 'sankhya_ped_origem_4a1b2c_idx'
            )
            CREATE INDEX sankhya_ped_origem_4a1b2c_idx
                ON dbo.sankhya_pedido (origem, codigo_nota);
            """
        )

        cursor.execute(
            "SELECT COL_LENGTH('dbo.sankhya_pedido', 'origem')"
        )
        if cursor.fetchone()[0] is None:
            raise RuntimeError(
                'Falha ao criar coluna origem em dbo.sankhya_pedido. '
                f'Verifique o banco {db_name} no servidor {server_name}.'
            )
        print('[0027] Schema de origem confirmado.')


class Migration(migrations.Migration):

    dependencies = [
        ('api_sankhya', '0026_pedido_origem'),
    ]

    operations = [
        migrations.RunPython(_ensure_pedido_origem_schema, migrations.RunPython.noop),
    ]
