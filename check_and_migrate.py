"""
Script para verificar estado do banco e executar migration apropriada
"""

import sqlite3
import os
import sys

# Configura encoding para UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

DB_PATH = os.path.join(os.getcwd(), "data", "oris.db")

def check_table_exists(cursor, table_name):
    """Verifica se uma tabela existe"""
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    return cursor.fetchone() is not None

def get_table_constraint(cursor, table_name):
    """Pega a definição da tabela para verificar constraints"""
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    result = cursor.fetchone()
    return result[0] if result else None

def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERRO] Banco de dados nao encontrado: {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Verifica se tabela vagas existe
        if check_table_exists(cursor, 'vagas'):
            print("Tabela 'vagas' encontrada!")

            # Verifica se já tem o status 'cancelado'
            table_def = get_table_constraint(cursor, 'vagas')

            if 'cancelado' in table_def:
                print("\n[OK] Status 'cancelado' ja existe na tabela!")
                print("Nenhuma migration necessaria.")
            else:
                print("\nStatus 'cancelado' NAO encontrado.")
                print("Executando migration para adicionar...")

                # Executa migration
                with open('migrations/add_cancelado_status.sql', 'r', encoding='utf-8') as f:
                    # Lê e filtra apenas a parte de ALTER (pula DROP da tabela inexistente)
                    sql_script = f.read()

                # Remove views
                cursor.execute("DROP VIEW IF EXISTS vagas_pendentes")
                cursor.execute("DROP VIEW IF EXISTS vagas_aprovadas")
                cursor.execute("DROP VIEW IF EXISTS vagas_canceladas")
                cursor.execute("DROP TABLE IF EXISTS vagas_new")

                # Cria nova tabela
                cursor.execute("""
                    CREATE TABLE vagas_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT NOT NULL,
                        centro_custo TEXT NOT NULL,
                        cargo TEXT NOT NULL,
                        situacao TEXT NOT NULL,
                        nome_fantasia TEXT NOT NULL,
                        carga_horaria_semanal REAL,
                        dt_inicio_situacao DATE,
                        dt_rescisao DATE,
                        data_evento DATE,
                        tipo_vaga TEXT NOT NULL,
                        motivo_vaga TEXT,
                        dias_afastamento INTEGER,
                        status TEXT NOT NULL DEFAULT 'pendente',
                        data_decisao DATETIME,
                        usuario_aprovador TEXT,
                        observacao TEXT,
                        quantidade_ideal INTEGER,
                        quantidade_atual INTEGER,
                        deficit INTEGER,
                        vaga_prevista_tlp INTEGER,
                        data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                        data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                        CHECK (tipo_vaga IN ('demissao', 'afastamento')),
                        CHECK (status IN ('pendente', 'aprovado', 'rejeitado', 'cancelado'))
                    )
                """)

                # Copia dados
                cursor.execute("INSERT INTO vagas_new SELECT * FROM vagas")

                # Remove antiga e renomeia
                cursor.execute("DROP TABLE vagas")
                cursor.execute("ALTER TABLE vagas_new RENAME TO vagas")

                # Recria indices
                cursor.execute("CREATE INDEX idx_vagas_status ON vagas(status)")
                cursor.execute("CREATE INDEX idx_vagas_tipo ON vagas(tipo_vaga)")
                cursor.execute("CREATE INDEX idx_vagas_centro_custo ON vagas(centro_custo)")
                cursor.execute("CREATE INDEX idx_vagas_cargo ON vagas(cargo)")
                cursor.execute("CREATE INDEX idx_vagas_data_evento ON vagas(data_evento)")
                cursor.execute("CREATE INDEX idx_vagas_data_decisao ON vagas(data_decisao)")

                # Recria trigger
                cursor.execute("""
                    CREATE TRIGGER update_vagas_timestamp
                    AFTER UPDATE ON vagas
                    BEGIN
                        UPDATE vagas
                        SET data_atualizacao = CURRENT_TIMESTAMP
                        WHERE id = NEW.id;
                    END
                """)

                # Recria views
                cursor.execute("""
                    CREATE VIEW vagas_pendentes AS
                    SELECT id, nome, cargo, centro_custo, tipo_vaga, motivo_vaga,
                           data_evento, dias_afastamento, deficit, vaga_prevista_tlp
                    FROM vagas WHERE status = 'pendente' ORDER BY data_evento DESC
                """)

                cursor.execute("""
                    CREATE VIEW vagas_aprovadas AS
                    SELECT id, nome, cargo, centro_custo, tipo_vaga, data_evento,
                           data_decisao, usuario_aprovador, deficit
                    FROM vagas WHERE status = 'aprovado' ORDER BY data_decisao DESC
                """)

                cursor.execute("""
                    CREATE VIEW vagas_canceladas AS
                    SELECT id, nome, cargo, centro_custo, tipo_vaga, data_evento,
                           data_decisao, usuario_aprovador, observacao, deficit
                    FROM vagas WHERE status = 'cancelado' ORDER BY data_decisao DESC
                """)

                conn.commit()
                print("\n[OK] Migration executada com sucesso!")
        else:
            print("Tabela 'vagas' NAO encontrada!")
            print("Criando tabela inicial com status 'cancelado'...")

            # Cria tabela inicial já com o novo constraint
            with open('migrations/create_vagas.sql', 'r', encoding='utf-8') as f:
                sql_create = f.read()
                # Substitui o constraint antigo pelo novo
                sql_create = sql_create.replace(
                    "CHECK (status IN ('pendente', 'aprovado', 'rejeitado'))",
                    "CHECK (status IN ('pendente', 'aprovado', 'rejeitado', 'cancelado'))"
                )
                cursor.executescript(sql_create)
                conn.commit()
                print("[OK] Tabela criada com sucesso!")

        # Mostra estatísticas
        cursor.execute("SELECT status, COUNT(*) FROM vagas GROUP BY status")
        stats = cursor.fetchall()

        if stats:
            print("\nEstatisticas atuais:")
            for status, count in stats:
                print(f"   {status}: {count}")
        else:
            print("\nNenhuma vaga cadastrada ainda")

        conn.close()
        return True

    except Exception as e:
        print(f"[ERRO] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
