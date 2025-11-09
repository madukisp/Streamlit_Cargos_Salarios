"""
Configuração centralizada do Sistema ORIS - Cargos e Salários
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# ==================== CAMINHOS ====================

# Diretório base do projeto (sobe um nível para C:\Scripts\Oris)
BASE_DIR = Path(__file__).resolve().parent.parent

# Caminhos principais
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "oris.db"

# Converte para string para compatibilidade com código legado
DB_PATH_STR = str(DB_PATH)
DATA_DIR_STR = str(DATA_DIR)

# ==================== VALIDAÇÃO ====================

def validar_estrutura():
    """Valida se a estrutura de pastas e arquivos está correta"""
    problemas = []

    # Verifica pasta data
    if not DATA_DIR.exists():
        problemas.append(f"[X] Pasta 'data' não encontrada em: {DATA_DIR}")

    # Verifica banco de dados
    if not DB_PATH.exists():
        problemas.append(f"[X] Banco de dados não encontrado em: {DB_PATH}")
        if DATA_DIR.exists():
            arquivos = list(DATA_DIR.iterdir())
            if arquivos:
                problemas.append(f"[i] Arquivos encontrados em data/: {[f.name for f in arquivos]}")
            else:
                problemas.append("[i] Pasta data/ está vazia")

    if problemas:
        print("\n".join(problemas))
        return False

    print(f"[OK] Config validado: {DB_PATH}")
    return True

# ==================== CONFIGURAÇÕES DA APLICAÇÃO ====================

# Metadados
APP_TITLE = "Sistema ORIS - Cargos e Salários"
APP_VERSION = "2.0.0"
APP_ICON = "📊"

# Data mínima para processar vagas
DATA_MINIMA_VAGAS = datetime(2025, 1, 1)

# Configurações de cache (Streamlit)
CACHE_TTL = 600  # 10 minutos

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ==================== TABELAS DO BANCO ====================

TABELAS_NECESSARIAS = {
    'relatorio_oris': 'Relatório de funcionários do sistema ORIS',
    'tlp': 'Tabela de Lotação de Pessoal (TLP)',
    'vagas': 'Vagas para aprovação/rejeição'
}

# ==================== STATUS E ENUMS ====================

STATUS_VAGA = {
    'pendente': 'Aguardando aprovação',
    'aprovado': 'Vaga aprovada',
    'rejeitado': 'Vaga rejeitada na triagem',
    'cancelado': 'Vaga aprovada mas posteriormente cancelada'
}

TIPO_VAGA = {
    'demissao': 'Vaga por demissão',
    'afastamento': 'Vaga por afastamento'
}

# ==================== INICIALIZAÇÃO ====================

# Valida estrutura ao importar
if __name__ != "__main__":
    if not validar_estrutura():
        print("\n⚠️ AVISO: Problemas encontrados na estrutura do projeto")
        print(f"📂 Diretório atual: {Path.cwd()}")
        print(f"📂 BASE_DIR esperado: {BASE_DIR}")
        print(f"📂 DATA_DIR esperado: {DATA_DIR}")

# ==================== EXPORTAÇÕES ====================

__all__ = [
    'DB_PATH',
    'DB_PATH_STR',
    'DATA_DIR',
    'DATA_DIR_STR',
    'BASE_DIR',
    'APP_TITLE',
    'APP_VERSION',
    'DATA_MINIMA_VAGAS',
    'CACHE_TTL',
    'TABELAS_NECESSARIAS',
    'STATUS_VAGA',
    'TIPO_VAGA',
    'validar_estrutura'
]

if __name__ == "__main__":
    # Teste standalone
    import sys
    import io

    # Configura UTF-8 para Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 60)
    print("TESTE DE CONFIGURAÇÃO")
    print("=" * 60)
    print(f"\nBASE_DIR: {BASE_DIR}")
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"DB_PATH: {DB_PATH}")
    print(f"\n{'OK - TUDO CERTO!' if validar_estrutura() else 'ERRO - PROBLEMAS ENCONTRADOS'}")
    print("=" * 60)
