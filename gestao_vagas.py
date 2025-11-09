"""
Módulo de Gestão de Aprovações de Vagas
Integra com a tabela 'vagas' do banco oris.db
"""

import sqlite3
import pandas as pd
from datetime import datetime
import os
import logging

# Importa configuração centralizada
try:
    from config import DB_PATH_STR as DB_PATH, validar_estrutura
    # Valida estrutura na primeira importação
    validar_estrutura()
except ImportError:
    # Fallback para compatibilidade
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "data", "oris.db")
    print(f"⚠️ config.py não encontrado, usando fallback: {DB_PATH}")

logger = logging.getLogger(__name__)

# ==================== GERENCIAMENTO DE VAGAS ====================

def salvar_vaga_para_aprovacao(vaga_data, info_tlp):
    """
    Salva vaga na tabela 'vagas' com status pendente
    
    Args:
        vaga_data: Dict com dados da vaga vindo de processar_demissoes_e_afastamentos()
        info_tlp: Dict com informações da TLP vindo de verificar_vaga_na_tlp()
    
    Returns:
        ID da vaga inserida ou None em caso de erro
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Determina a data do evento
        if vaga_data['tipo'] == 'demissao':
            # Para demissão, busca a Dt Rescisão
            dt_rescisao = vaga_data.get('data_evento')
            dt_inicio_situacao = None
        else:
            # Para afastamento, busca Dt Início Situação
            dt_rescisao = None
            dt_inicio_situacao = vaga_data.get('data_evento')
        
        # Extrai dados do row_data
        row_data = vaga_data['row_data']
        
        cursor.execute("""
            INSERT INTO vagas (
                nome,
                centro_custo,
                cargo,
                situacao,
                nome_fantasia,
                carga_horaria_semanal,
                dt_inicio_situacao,
                dt_rescisao,
                data_evento,
                tipo_vaga,
                motivo_vaga,
                dias_afastamento,
                status,
                quantidade_ideal,
                quantidade_atual,
                deficit,
                vaga_prevista_tlp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vaga_data['nome'],
            vaga_data['centro_custo'],
            vaga_data['cargo'],
            vaga_data['situacao'],
            vaga_data['nome_fantasia'],
            vaga_data['carga_horaria'],
            dt_inicio_situacao,
            dt_rescisao,
            vaga_data['data_evento'],
            vaga_data['tipo'],
            vaga_data['motivo'],
            vaga_data.get('dias_afastamento'),
            'pendente',
            info_tlp.get('quantidade_ideal', 0),
            info_tlp.get('quantidade_atual', 0),
            info_tlp.get('deficit', 0),
            info_tlp.get('vaga_prevista', False)
        ))
        
        vaga_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Vaga salva com ID {vaga_id}: {vaga_data['nome']} - {vaga_data['cargo']}")
        return vaga_id
        
    except Exception as e:
        logger.error(f"Erro ao salvar vaga: {e}")
        return None

def aprovar_e_salvar_vaga(vaga_data, info_tlp, usuario="Sistema"):
    """
    Salva e aprova uma vaga diretamente do relatório (sem passar por status pendente)

    Args:
        vaga_data: Dict com dados da vaga vindo de processar_demissoes_e_afastamentos()
        info_tlp: Dict com informações da TLP vindo de verificar_vaga_na_tlp()
        usuario: Nome do usuário que aprovou

    Returns:
        ID da vaga inserida, "DUPLICADA" se já existe, ou None em caso de erro
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # VERIFICA SE VAGA JÁ EXISTE (evita duplicação)
        cursor.execute("""
            SELECT id, status FROM vagas
            WHERE nome = ? AND cargo = ? AND centro_custo = ?
            AND status IN ('pendente', 'aprovado')
        """, (vaga_data['nome'], vaga_data['cargo'], vaga_data['centro_custo']))

        vaga_existente = cursor.fetchone()

        if vaga_existente:
            vaga_id_existente, status_existente = vaga_existente
            logger.warning(f"⚠️ Vaga já existe (ID {vaga_id_existente}, status: {status_existente}): {vaga_data['nome']} - {vaga_data['cargo']}")
            conn.close()
            return "DUPLICADA"

        # Determina a data do evento
        if vaga_data['tipo'] == 'demissao':
            dt_rescisao = vaga_data.get('data_evento')
            dt_inicio_situacao = None
        else:
            dt_rescisao = None
            dt_inicio_situacao = vaga_data.get('data_evento')

        cursor.execute("""
            INSERT INTO vagas (
                nome,
                centro_custo,
                cargo,
                situacao,
                nome_fantasia,
                carga_horaria_semanal,
                dt_inicio_situacao,
                dt_rescisao,
                data_evento,
                tipo_vaga,
                motivo_vaga,
                dias_afastamento,
                status,
                data_decisao,
                usuario_aprovador,
                quantidade_ideal,
                quantidade_atual,
                deficit,
                vaga_prevista_tlp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vaga_data['nome'],
            vaga_data['centro_custo'],
            vaga_data['cargo'],
            vaga_data['situacao'],
            vaga_data['nome_fantasia'],
            vaga_data['carga_horaria'],
            dt_inicio_situacao,
            dt_rescisao,
            vaga_data['data_evento'],
            vaga_data['tipo'],
            vaga_data['motivo'],
            vaga_data.get('dias_afastamento'),
            'aprovado',  # Já salva como aprovado!
            datetime.now(),  # data_decisao
            usuario,  # usuario_aprovador
            info_tlp.get('quantidade_ideal', 0),
            info_tlp.get('quantidade_atual', 0),
            info_tlp.get('deficit', 0),
            info_tlp.get('vaga_prevista', False)
        ))

        vaga_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"✅ Vaga aprovada e salva com ID {vaga_id}: {vaga_data['nome']} - {vaga_data['cargo']} por {usuario}")
        return vaga_id

    except Exception as e:
        logger.error(f"Erro ao aprovar e salvar vaga: {e}")
        return None

def aprovar_vaga(vaga_id, usuario="Sistema"):
    """
    Aprova uma vaga pendente
    
    Args:
        vaga_id: ID da vaga na tabela
        usuario: Nome do usuário que aprovou
    
    Returns:
        True se aprovado com sucesso, False caso contrário
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE vagas
            SET status = 'aprovado',
                data_decisao = ?,
                usuario_aprovador = ?
            WHERE id = ? AND status = 'pendente'
        """, (datetime.now(), usuario, vaga_id))
        
        if cursor.rowcount > 0:
            conn.commit()
            logger.info(f"✅ Vaga ID {vaga_id} aprovada por {usuario}")
            resultado = True
        else:
            logger.warning(f"⚠️ Vaga ID {vaga_id} não encontrada ou já processada")
            resultado = False
        
        conn.close()
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao aprovar vaga {vaga_id}: {e}")
        return False

def rejeitar_vaga(vaga_id, usuario="Sistema", observacao=None):
    """
    Rejeita uma vaga pendente

    Args:
        vaga_id: ID da vaga na tabela
        usuario: Nome do usuário que rejeitou
        observacao: Motivo da rejeição (opcional)

    Returns:
        True se rejeitado com sucesso, False caso contrário
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE vagas
            SET status = 'rejeitado',
                data_decisao = ?,
                usuario_aprovador = ?,
                observacao = ?
            WHERE id = ? AND status = 'pendente'
        """, (datetime.now(), usuario, observacao, vaga_id))

        if cursor.rowcount > 0:
            conn.commit()
            logger.info(f"❌ Vaga ID {vaga_id} rejeitada por {usuario}")
            resultado = True
        else:
            logger.warning(f"⚠️ Vaga ID {vaga_id} não encontrada ou já processada")
            resultado = False

        conn.close()
        return resultado

    except Exception as e:
        logger.error(f"Erro ao rejeitar vaga {vaga_id}: {e}")
        return False

def cancelar_vaga_aprovada(vaga_id, usuario="Sistema", observacao=None):
    """
    Cancela uma vaga que foi previamente aprovada

    Args:
        vaga_id: ID da vaga na tabela
        usuario: Nome do usuário que cancelou
        observacao: Motivo do cancelamento (opcional)

    Returns:
        True se cancelado com sucesso, False caso contrário
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE vagas
            SET status = 'cancelado',
                data_decisao = ?,
                usuario_aprovador = ?,
                observacao = ?
            WHERE id = ? AND status = 'aprovado'
        """, (datetime.now(), usuario, observacao, vaga_id))

        if cursor.rowcount > 0:
            conn.commit()
            logger.info(f"⛔ Vaga ID {vaga_id} cancelada por {usuario}")
            resultado = True
        else:
            logger.warning(f"⚠️ Vaga ID {vaga_id} não encontrada ou não está aprovada")
            resultado = False

        conn.close()
        return resultado

    except Exception as e:
        logger.error(f"Erro ao cancelar vaga {vaga_id}: {e}")
        return False

def desfazer_decisao(vaga_id):
    """
    Reverte uma decisão (aprovação ou rejeição) para pendente
    
    Args:
        vaga_id: ID da vaga na tabela
    
    Returns:
        True se desfeito com sucesso, False caso contrário
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE vagas
            SET status = 'pendente',
                data_decisao = NULL,
                usuario_aprovador = NULL,
                observacao = NULL
            WHERE id = ?
        """, (vaga_id,))
        
        if cursor.rowcount > 0:
            conn.commit()
            logger.info(f"🔄 Decisão da vaga ID {vaga_id} desfeita")
            resultado = True
        else:
            logger.warning(f"⚠️ Vaga ID {vaga_id} não encontrada")
            resultado = False
        
        conn.close()
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao desfazer decisão da vaga {vaga_id}: {e}")
        return False

# ==================== CONSULTAS ====================

def buscar_vaga_por_funcionario(nome, cargo, centro_custo):
    """
    Busca se já existe uma vaga para determinado funcionário
    
    Returns:
        Dict com dados da vaga ou None se não encontrada
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        
        query = """
            SELECT * FROM vagas
            WHERE nome = ? AND cargo = ? AND centro_custo = ?
            ORDER BY data_criacao DESC
            LIMIT 1
        """
        
        df = pd.read_sql_query(query, conn, params=(nome, cargo, centro_custo))
        conn.close()
        
        if len(df) > 0:
            return df.iloc[0].to_dict()
        return None
        
    except Exception as e:
        logger.error(f"Erro ao buscar vaga: {e}")
        return None

def listar_vagas(status=None, tipo_vaga=None, centro_custo=None):
    """
    Lista vagas com filtros opcionais

    Args:
        status: 'pendente', 'aprovado', 'rejeitado', 'cancelado' ou None (todos)
        tipo_vaga: 'demissao', 'afastamento' ou None (todos)
        centro_custo: Nome do centro de custo ou None (todos)

    Returns:
        DataFrame com vagas filtradas
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        
        query = "SELECT * FROM vagas WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if tipo_vaga:
            query += " AND tipo_vaga = ?"
            params.append(tipo_vaga)
        
        if centro_custo:
            query += " AND centro_custo = ?"
            params.append(centro_custo)
        
        query += " ORDER BY data_evento DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
        
    except Exception as e:
        logger.error(f"Erro ao listar vagas: {e}")
        return pd.DataFrame()

def estatisticas_vagas():
    """
    Retorna estatísticas gerais sobre as vagas
    
    Returns:
        Dict com estatísticas
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Total por status
        cursor.execute("""
            SELECT status, COUNT(*) as total
            FROM vagas
            GROUP BY status
        """)
        por_status = dict(cursor.fetchall())
        
        # Total por tipo
        cursor.execute("""
            SELECT tipo_vaga, COUNT(*) as total
            FROM vagas
            GROUP BY tipo_vaga
        """)
        por_tipo = dict(cursor.fetchall())
        
        # Cargos com mais vagas
        cursor.execute("""
            SELECT cargo, COUNT(*) as total
            FROM vagas
            GROUP BY cargo
            ORDER BY total DESC
            LIMIT 5
        """)
        top_cargos = cursor.fetchall()
        
        # Taxa de aprovação
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN status = 'aprovado' THEN 1 END) as aprovadas,
                COUNT(CASE WHEN status = 'rejeitado' THEN 1 END) as rejeitadas,
                COUNT(CASE WHEN status = 'cancelado' THEN 1 END) as canceladas,
                COUNT(*) as total
            FROM vagas
            WHERE status != 'pendente'
        """)
        row = cursor.fetchone()
        aprovadas, rejeitadas, canceladas, total_decididas = row

        taxa_aprovacao = (aprovadas / total_decididas * 100) if total_decididas > 0 else 0

        conn.close()

        return {
            'por_status': por_status,
            'por_tipo': por_tipo,
            'top_cargos': top_cargos,
            'taxa_aprovacao': taxa_aprovacao,
            'total_aprovadas': aprovadas,
            'total_rejeitadas': rejeitadas,
            'total_canceladas': canceladas
        }
        
    except Exception as e:
        logger.error(f"Erro ao gerar estatísticas: {e}")
        return {}

# ==================== SINCRONIZAÇÃO ====================

def sincronizar_vagas_pendentes(relatorio, tlp):
    """
    Sincroniza vagas do relatório ORIS com a tabela vagas
    Adiciona novas vagas e marca como resolvidas as que não existem mais
    
    Args:
        relatorio: DataFrame com relatório ORIS
        tlp: DataFrame com TLP
    
    Returns:
        Dict com estatísticas da sincronização
    """
    from aprovar_vaga import processar_demissoes_e_afastamentos, verificar_vaga_na_tlp
    
    try:
        # Processa vagas do relatório
        vagas_relatorio = processar_demissoes_e_afastamentos(relatorio)
        
        # Busca vagas já cadastradas
        vagas_existentes = listar_vagas(status='pendente')
        
        novas = 0
        atualizadas = 0
        
        for vaga in vagas_relatorio:
            # Verifica se já existe
            vaga_existente = buscar_vaga_por_funcionario(
                vaga['nome'],
                vaga['cargo'],
                vaga['centro_custo']
            )
            
            if vaga_existente is None:
                # Nova vaga - cadastra
                info_tlp = verificar_vaga_na_tlp(vaga['row_data'], tlp, relatorio)
                vaga_id = salvar_vaga_para_aprovacao(vaga, info_tlp)
                
                if vaga_id:
                    novas += 1
            else:
                # Vaga já existe - atualiza se necessário
                atualizadas += 1
        
        logger.info(f"📊 Sincronização: {novas} novas, {atualizadas} atualizadas")
        
        return {
            'novas': novas,
            'atualizadas': atualizadas,
            'total_processadas': len(vagas_relatorio)
        }
        
    except Exception as e:
        logger.error(f"Erro na sincronização: {e}")
        return {'erro': str(e)}

# ==================== EXPORTAÇÃO ====================

def exportar_vagas_excel(status=None, arquivo="vagas_export.xlsx"):
    """
    Exporta vagas para Excel
    
    Args:
        status: Filtro de status ou None para todos
        arquivo: Nome do arquivo de saída
    
    Returns:
        Path do arquivo gerado
    """
    try:
        from io import BytesIO
        
        df = listar_vagas(status=status)
        
        if df.empty:
            logger.warning("Nenhuma vaga para exportar")
            return None
        
        # Formata colunas
        colunas_exibir = [
            'id', 'nome', 'cargo', 'centro_custo', 'situacao',
            'tipo_vaga', 'data_evento', 'status', 'data_decisao',
            'usuario_aprovador', 'deficit', 'dias_afastamento'
        ]
        
        df_export = df[colunas_exibir].copy()
        
        # Renomeia colunas
        df_export.columns = [
            'ID', 'Nome', 'Cargo', 'Centro de Custo', 'Situação',
            'Tipo', 'Data Evento', 'Status', 'Data Decisão',
            'Aprovador', 'Déficit', 'Dias Afastamento'
        ]
        
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Vagas')
            
            # Formata planilha
            workbook = writer.book
            worksheet = writer.sheets['Vagas']
            
            # Formato para cabeçalho
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1
            })
            
            # Aplica formato
            for col_num, value in enumerate(df_export.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)
        
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logger.error(f"Erro ao exportar para Excel: {e}")
        return None
