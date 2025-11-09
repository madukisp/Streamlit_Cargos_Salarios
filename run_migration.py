"""
Script para executar a migration: add_cancelado_status.sql
"""

import sqlite3
import os
import sys
from pathlib import Path

# Configura encoding para UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Importa configuração centralizada
try:
    from config import DB_PATH_STR as DB_PATH, BASE_DIR
    MIGRATION_PATH = str(BASE_DIR / "02_paineis_streamlit" / "migrations" / "add_cancelado_status.sql")
except ImportError:
    # Fallback para estrutura antiga
    DB_PATH = os.path.join(os.getcwd(), "data", "oris.db")
    MIGRATION_PATH = os.path.join(os.getcwd(), "migrations", "add_cancelado_status.sql")

def run_migration():
    """Executa a migration para adicionar status 'cancelado'"""

    if not os.path.exists(DB_PATH):
        print(f"[ERRO] Banco de dados nao encontrado: {DB_PATH}")
        return False

    if not os.path.exists(MIGRATION_PATH):
        print(f"[ERRO] Migration nao encontrada: {MIGRATION_PATH}")
        return False

    try:
        # Lê o script SQL
        with open(MIGRATION_PATH, 'r', encoding='utf-8') as f:
            sql_script = f.read()

        # Conecta ao banco
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Executa o script
        print("Executando migration...")
        cursor.executescript(sql_script)

        # Verifica se a migration foi bem-sucedida
        cursor.execute("SELECT status FROM vagas LIMIT 1")

        print("[OK] Migration executada com sucesso!")
        print("\nStatus disponiveis agora: 'pendente', 'aprovado', 'rejeitado', 'cancelado'")

        # Mostra estatísticas atuais
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
        print(f"[ERRO] Erro ao executar migration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    run_migration()
