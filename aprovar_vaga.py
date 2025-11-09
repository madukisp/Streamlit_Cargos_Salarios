import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
import logging

# Importa configuração centralizada
try:
    from config import DB_PATH_STR as DB_PATH, DATA_MINIMA_VAGAS, CACHE_TTL, validar_estrutura
except ImportError:
    # Fallback para compatibilidade
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "data", "oris.db")
    DATA_MINIMA_VAGAS = datetime(2025, 1, 1)
    CACHE_TTL = 600
    print(f"⚠️ config.py não encontrado, usando fallback: {DB_PATH}")

# Importa módulo de gestão de vagas
from gestao_vagas import (
    aprovar_vaga,
    aprovar_e_salvar_vaga,
    rejeitar_vaga,
    cancelar_vaga_aprovada,
    desfazer_decisao,
    listar_vagas,
    salvar_vaga_para_aprovacao,
    sincronizar_vagas_pendentes,
    estatisticas_vagas,
    exportar_vagas_excel
)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== CACHE E CARREGAMENTO ====================

@st.cache_data(ttl=600)
def carregar_dados():
    """Carrega dados do banco com validação robusta"""

    # Valida existência do banco
    if not os.path.exists(DB_PATH):
        st.error(f"❌ Banco de dados não encontrado!")
        st.info(f"📂 Caminho esperado: {DB_PATH}")
        logger.error(f"Banco não encontrado: {DB_PATH}")
        st.stop()
        return None, None

    try:
        conn = sqlite3.connect(DB_PATH)

        # Testa conexão
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = [row[0] for row in cursor.fetchall()]

        # Valida tabelas necessárias
        tabelas_necessarias = ['relatorio_oris', 'tlp']
        tabelas_faltando = [t for t in tabelas_necessarias if t not in tabelas]

        if tabelas_faltando:
            st.error(f"❌ Tabelas faltando no banco: {', '.join(tabelas_faltando)}")
            st.info(f"📊 Tabelas disponíveis: {', '.join(tabelas)}")
            conn.close()
            st.stop()
            return None, None

        # Carrega dados
        relatorio = pd.read_sql_query("SELECT * FROM relatorio_oris", conn)
        tlp = pd.read_sql_query("SELECT * FROM tlp", conn)

        conn.close()

        logger.info(f"✅ Dados carregados: {len(relatorio)} funcionários, {len(tlp)} registros TLP")
        return relatorio, tlp

    except sqlite3.Error as e:
        st.error(f"❌ Erro de banco de dados: {e}")
        logger.error(f"Erro SQL: {e}")
        st.stop()
        return None, None
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {e}")
        logger.error(f"Erro ao carregar dados: {e}")
        st.stop()
        return None, None

@st.cache_data
def criar_lookup_tlp(tlp):
    """Cria dicionário para lookup rápido"""
    lookup = {}
    for _, row in tlp.iterrows():
        key = (row['contrato'], row['unidade'], row['cargo'], row['carga_hora'])
        lookup[key] = int(row['quantidade_ideal'])
    return lookup

# ==================== PROCESSAMENTO ====================

def processar_data(data_str):
    """Converte string de data para datetime - VERSÃO OTIMIZADA"""
    if pd.isna(data_str) or data_str == '' or data_str is None:
        return None
    
    try:
        if isinstance(data_str, datetime):
            return data_str
        
        # Converte para string
        data_str = str(data_str).strip()
        
        # Tenta formato brasileiro primeiro (DD/MM/YYYY)
        if '/' in data_str:
            try:
                return pd.to_datetime(data_str, format='%d/%m/%Y', errors='coerce')
            except:
                pass
        
        # Tenta formato ISO (YYYY-MM-DD)
        if '-' in data_str:
            try:
                return pd.to_datetime(data_str, format='%Y-%m-%d', errors='coerce')
            except:
                pass
        
        # Fallback: deixa pandas inferir com dayfirst=True
        data_convertida = pd.to_datetime(data_str, dayfirst=True, errors='coerce')
        
        if pd.isna(data_convertida):
            return None
            
        return data_convertida
        
    except Exception as e:
        return None

    except Exception as e:
        logger.warning(f"Erro ao processar data '{data_str}': {e}")
        return None

def contar_ativos(relatorio, filtros):
    """Conta funcionários ativos com filtros específicos"""
    df_filtrado = relatorio[
        (relatorio["Nome Fantasia"] == filtros["contrato"]) &
        (relatorio["Centro custo"] == filtros["unidade"]) &
        (relatorio["Cargo"] == filtros["cargo"]) &
        (relatorio["Situação"].isin(["01-ATIVO", "18-ATESTADO MÉDICO"]))
    ]
    
    if filtros.get("carga_horaria") is not None:
        df_filtrado = df_filtrado[
            df_filtrado["Carga Horária Semanal"] == filtros["carga_horaria"]
        ]
    
    return len(df_filtrado)

def verificar_vaga_na_tlp(pessoa, tlp, relatorio_completo):
    """Verifica se a vaga está prevista na TLP"""
    
    contrato = pessoa.get("Nome Fantasia")
    unidade = pessoa.get("Centro custo")
    cargo = pessoa.get("Cargo")
    carga_horaria = pessoa.get("Carga Horária Semanal")
    
    lookup_tlp = criar_lookup_tlp(tlp)
    chave_especifica = (contrato, unidade, cargo, carga_horaria)
    
    quantidade_ativos_total = contar_ativos(relatorio_completo, {
        "contrato": contrato,
        "unidade": unidade,
        "cargo": cargo
    })
    
    if chave_especifica not in lookup_tlp:
        quantidade_ideal_total = sum(
            v for k, v in lookup_tlp.items()
            if k[0] == contrato and k[1] == unidade and k[2] == cargo
        )
        
        return {
            "vaga_prevista": False,
            "quantidade_ideal": 0,
            "quantidade_ideal_total": quantidade_ideal_total,
            "quantidade_atual": quantidade_ativos_total,
            "quantidade_atual_mesma_carga": 0,
            "deficit": 0,
            "pode_aprovar": True,
            "motivo": "⚠️ Vaga não prevista na TLP (carga horária específica)",
            "observacao": f"Existem {quantidade_ativos_total} ativos no cargo (previsão total: {quantidade_ideal_total})"
        }
    
    quantidade_ideal = lookup_tlp[chave_especifica]
    
    quantidade_ideal_total = sum(
        v for k, v in lookup_tlp.items()
        if k[0] == contrato and k[1] == unidade and k[2] == cargo
    )
    
    quantidade_atual_mesma_carga = contar_ativos(relatorio_completo, {
        "contrato": contrato,
        "unidade": unidade,
        "cargo": cargo,
        "carga_horaria": carga_horaria
    })
    
    deficit = quantidade_ideal - quantidade_atual_mesma_carga
    
    if deficit > 0:
        motivo = f"✅ Vaga aprovável - Déficit de {deficit} funcionário(s)"
    elif deficit == 0:
        motivo = f"⚠️ Quadro completo ({quantidade_atual_mesma_carga}/{quantidade_ideal})"
    else:
        motivo = f"⚠️ Excedente de {abs(deficit)} funcionário(s) ({quantidade_atual_mesma_carga}/{quantidade_ideal})"
    
    return {
        "vaga_prevista": True,
        "quantidade_ideal": quantidade_ideal,
        "quantidade_ideal_total": quantidade_ideal_total,
        "quantidade_atual": quantidade_ativos_total,
        "quantidade_atual_mesma_carga": quantidade_atual_mesma_carga,
        "deficit": deficit,
        "pode_aprovar": True,
        "motivo": motivo,
        "observacao": f"Total no cargo: {quantidade_ativos_total} ativos (previsão: {quantidade_ideal_total})"
    }

def processar_demissoes_e_afastamentos(relatorio):
    """Identifica demissões e afastamentos"""
    vagas_pendentes = []
    
    for idx, row in relatorio.iterrows():
        motivo = None
        tipo = None
        data_evento = None
        dias_afastamento = None
        
        data_rescisao = processar_data(row.get("Dt Rescisão"))
        if data_rescisao and data_rescisao >= DATA_MINIMA_VAGAS:
            motivo = "Demissão"
            tipo = "demissao"
            data_evento = data_rescisao.strftime("%d/%m/%Y")
            dias_afastamento = None
        else:
            situacao = row.get("Situação")
            
            if situacao not in ["01-ATIVO", "99-Demitido", "18-ATESTADO MÉDICO"]:
                data_situacao = None
                colunas_data = ["Dt Início Situação", "Dt Inicio Situação", "Dt Situação"]
                
                for col in colunas_data:
                    if col in row:
                        data_situacao = processar_data(row.get(col))
                        if data_situacao:
                            break
                
                if data_situacao and data_situacao >= DATA_MINIMA_VAGAS:
                    motivo = f"Afastamento - {situacao or 'Não informado'}"
                    tipo = "afastamento"
                    data_evento = data_situacao.strftime("%d/%m/%Y")
                    
                    try:
                        dias_afastamento = (datetime.now().date() - data_situacao.date()).days
                    except:
                        dias_afastamento = None
        
        if motivo:
            vagas_pendentes.append({
                "nome": row.get("Nome", ""),
                "cargo": row.get("Cargo", ""),
                "centro_custo": row.get("Centro custo", ""),
                "nome_fantasia": row.get("Nome Fantasia", ""),
                "carga_horaria": row.get("Carga Horária Semanal", ""),
                "situacao": row.get("Situação", ""),
                "motivo": motivo,
                "tipo": tipo,
                "data_evento": data_evento,
                "dias_afastamento": dias_afastamento,
                "row_data": row
            })
    
    logger.info(f"Identificadas {len(vagas_pendentes)} vagas pendentes")
    return vagas_pendentes

# ==================== INTERFACE ====================

def renderizar_card_vaga(vaga, vaga_id, info_tlp):
    """Renderiza card individual de vaga"""
    
    col_info, col_tlp, col_acoes = st.columns([2, 2, 1])
    
    with col_info:
        dias_text = ""
        if vaga.get("tipo") == "afastamento" and vaga.get("dias_afastamento") is not None:
            dias_text = f"**Dias afastado:** {vaga['dias_afastamento']} dias  \n"
        
        st.markdown(f"""
        ### 👤 {vaga['nome']}
        
        **Cargo:** {vaga['cargo']}  
        **Motivo:** {vaga['motivo']}  
        **Data:** {vaga['data_evento']}  
        {dias_text}
        **Carga horária:** {vaga['carga_horaria']}h/semana  
        **Contrato:** {vaga['nome_fantasia']}
        """)
    
    with col_tlp:
        st.markdown("### 📊 Análise TLP")
        
        if info_tlp["vaga_prevista"]:
            st.markdown(f"""
            **Previsto na TLP:** ✅ Sim  
            **Qtd Ideal:** {info_tlp['quantidade_ideal']}  
            **Qtd Atual:** {info_tlp['quantidade_atual_mesma_carga']}  
            **Déficit:** {info_tlp['deficit']}
            """)
            
            if info_tlp["deficit"] > 0:
                st.success(info_tlp["motivo"])
            else:
                st.warning(info_tlp["motivo"])
        else:
            st.warning(info_tlp["motivo"])
            st.caption(info_tlp["observacao"])
    
    with col_acoes:
        st.markdown("### 🎯 Ação")
        
        # Verifica se vaga já existe no banco
        vaga_banco = listar_vagas().query(f"id == {vaga_id}") if vaga_id else pd.DataFrame()
        
        if not vaga_banco.empty:
            status = vaga_banco.iloc[0]['status']

            if status == 'aprovado':
                st.success("✅ Aprovada")
                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    if st.button("⛔ Cancelar", key=f"vaga_{vaga_id}_cancelar", use_container_width=True):
                        if cancelar_vaga_aprovada(vaga_id, usuario="Admin", observacao="Cancelada pelo usuário"):
                            st.success("Vaga cancelada!")
                            st.rerun()

                with col_btn2:
                    if st.button("Desfazer", key=f"vaga_{vaga_id}_desfazer", use_container_width=True):
                        if desfazer_decisao(vaga_id):
                            st.success("Decisão desfeita!")
                            st.rerun()

            elif status == 'cancelado':
                st.warning("⛔ Cancelada")
                if st.button("Desfazer", key=f"vaga_{vaga_id}_desfazer"):
                    if desfazer_decisao(vaga_id):
                        st.success("Decisão desfeita!")
                        st.rerun()

            elif status == 'rejeitado':
                st.error("❌ Rejeitada")
                if st.button("Desfazer", key=f"vaga_{vaga_id}_desfazer"):
                    if desfazer_decisao(vaga_id):
                        st.success("Decisão desfeita!")
                        st.rerun()

            else:
                # Pendente
                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    if st.button("✅ Aprovar",
                               key=f"vaga_{vaga_id}_aprovar",
                               disabled=not info_tlp["pode_aprovar"],
                               use_container_width=True):
                        if aprovar_vaga(vaga_id, usuario="Admin"):
                            st.success("Vaga aprovada!")
                            st.rerun()

                with col_btn2:
                    if st.button("❌ Rejeitar",
                               key=f"vaga_{vaga_id}_rejeitar",
                               use_container_width=True):
                        if rejeitar_vaga(vaga_id, usuario="Admin"):
                            st.success("Vaga rejeitada!")
                            st.rerun()
        else:
            # Vaga vinda do relatório (não está no banco ainda)
            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                if st.button("✅ Aprovar",
                           key=f"vaga_relatorio_{vaga['nome']}_{vaga['cargo']}_aprovar",
                           disabled=not info_tlp["pode_aprovar"],
                           use_container_width=True):
                    # Aprova e salva diretamente no banco
                    resultado = aprovar_e_salvar_vaga(vaga, info_tlp, usuario="Admin")
                    if resultado == "DUPLICADA":
                        st.warning("⚠️ Esta vaga já foi aprovada anteriormente!")
                    elif resultado:
                        st.success(f"Vaga aprovada e salva com ID {resultado}!")
                        st.rerun()
                    else:
                        st.error("Erro ao aprovar vaga")

            with col_btn2:
                if st.button("❌ Rejeitar",
                           key=f"vaga_relatorio_{vaga['nome']}_{vaga['cargo']}_rejeitar",
                           use_container_width=True):
                    # Não faz nada - apenas ignora a vaga
                    st.info("Vaga ignorada (não será salva no banco)")
                    # Não precisa rerun, apenas mostra a mensagem

def run():
    """Função principal"""
    
    st.title("📋 Aprovação de Vagas")
    st.markdown("Sistema integrado com banco de dados")
    
    # ==================== CARREGAMENTO ====================
    relatorio, tlp = carregar_dados()
    
    if relatorio is None or tlp is None:
        st.error("Não foi possível carregar os dados.")
        st.info(f"Caminho esperado: {DB_PATH}")
        st.stop()
    
    # ==================== SINCRONIZAÇÃO ====================
    if st.sidebar.button("🔄 Sincronizar Vagas do Relatório"):
        with st.spinner("Sincronizando..."):
            resultado = sincronizar_vagas_pendentes(relatorio, tlp)
            
            if 'erro' in resultado:
                st.error(f"Erro na sincronização: {resultado['erro']}")
            else:
                st.success(f"""
                ✅ Sincronização concluída!
                - {resultado['novas']} novas vagas
                - {resultado['atualizadas']} atualizadas
                - {resultado['total_processadas']} processadas
                """)
    
    # ==================== ESTATÍSTICAS ====================
    stats = estatisticas_vagas()

    col1, col2, col3, col4, col5 = st.columns(5)

    total_pendentes = stats.get('por_status', {}).get('pendente', 0)
    total_aprovadas = stats.get('total_aprovadas', 0)
    total_rejeitadas = stats.get('total_rejeitadas', 0)
    total_canceladas = stats.get('total_canceladas', 0)
    taxa_aprov = stats.get('taxa_aprovacao', 0)

    with col1:
        st.metric("⏳ Pendentes", total_pendentes)
    with col2:
        st.metric("✅ Aprovadas", total_aprovadas)
    with col3:
        st.metric("⛔ Canceladas", total_canceladas)
    with col4:
        st.metric("❌ Rejeitadas", total_rejeitadas)
    with col5:
        st.metric("📊 Taxa Aprovação", f"{taxa_aprov:.1f}%")
    
    st.markdown("---")
    
    # ==================== FILTROS ====================
    st.sidebar.header("🔍 Filtros")
    
    modo_visualizacao = st.sidebar.radio(
        "Modo",
        ["Vagas Cadastradas", "Buscar no Relatório"]
    )
    
    if modo_visualizacao == "Vagas Cadastradas":
        # Mostra vagas já cadastradas no banco
        status_filtro = st.sidebar.selectbox(
            "Status",
            ["Todos", "Pendentes", "Aprovadas", "Canceladas", "Rejeitadas"]
        )

        status_map = {
            "Todos": None,
            "Pendentes": "pendente",
            "Aprovadas": "aprovado",
            "Canceladas": "cancelado",
            "Rejeitadas": "rejeitado"
        }
        
        vagas_df = listar_vagas(status=status_map[status_filtro])
        
        if vagas_df.empty:
            st.info("Nenhuma vaga cadastrada com os filtros selecionados")
        else:
            st.subheader(f"📋 {len(vagas_df)} Vaga(s) Encontrada(s)")
            
            # Agrupa por centro de custo
            for centro in vagas_df['centro_custo'].unique():
                vagas_centro = vagas_df[vagas_df['centro_custo'] == centro]
                
                with st.expander(f"🏢 {centro} ({len(vagas_centro)} vagas)", expanded=True):
                    for idx, row in vagas_centro.iterrows():
                        # Reconstrói vaga para renderização
                        vaga = {
                            'nome': row['nome'],
                            'cargo': row['cargo'],
                            'centro_custo': row['centro_custo'],
                            'nome_fantasia': row['nome_fantasia'],
                            'carga_horaria': row['carga_horaria_semanal'],
                            'situacao': row['situacao'],
                            'motivo': row['motivo_vaga'],
                            'tipo': row['tipo_vaga'],
                            'data_evento': row['data_evento'],
                            'dias_afastamento': row['dias_afastamento']
                        }
                        
                        # Info TLP do banco
                        info_tlp = {
                            'vaga_prevista': row['vaga_prevista_tlp'],
                            'quantidade_ideal': row['quantidade_ideal'],
                            'quantidade_atual': row['quantidade_atual'],
                            'quantidade_atual_mesma_carga': row['quantidade_atual'],
                            'deficit': row['deficit'],
                            'pode_aprovar': True,
                            'motivo': f"Déficit: {row['deficit']}" if row['deficit'] > 0 else "Quadro completo",
                            'observacao': f"Total no cargo: {row['quantidade_atual']} ativos (previsão: {row['quantidade_ideal']})"
                        }
                        
                        renderizar_card_vaga(vaga, row['id'], info_tlp)
                        st.markdown("---")
    
    else:
        # Busca no relatório ORIS (modo antigo)
        st.info("💡 Este modo busca vagas diretamente no relatório ORIS (vagas aprovadas/rejeitadas não aparecem aqui)")

        vagas_relatorio = processar_demissoes_e_afastamentos(relatorio)

        # FILTRA VAGAS JÁ CADASTRADAS (aprovadas, pendentes ou rejeitadas)
        vagas_cadastradas_df = listar_vagas()  # Busca todas as vagas do banco

        if not vagas_cadastradas_df.empty:
            # Cria conjunto de chaves (nome, cargo, centro_custo) das vagas já cadastradas
            vagas_cadastradas_keys = set(
                vagas_cadastradas_df.apply(
                    lambda row: (row['nome'], row['cargo'], row['centro_custo']),
                    axis=1
                )
            )

            # Filtra vagas do relatório que NÃO estão cadastradas
            vagas_relatorio = [
                v for v in vagas_relatorio
                if (v['nome'], v['cargo'], v['centro_custo']) not in vagas_cadastradas_keys
            ]

        tipos = ["Todos", "Demissões", "Afastamentos"]
        tipo_filtro = st.sidebar.radio("Tipo", tipos)

        unidades = ["Todas"] + sorted(list(set([v["centro_custo"] for v in vagas_relatorio]))) if vagas_relatorio else ["Todas"]
        unidade_filtro = st.sidebar.selectbox("Unidade", unidades)

        vagas_filtradas = vagas_relatorio.copy()

        if tipo_filtro == "Demissões":
            vagas_filtradas = [v for v in vagas_filtradas if v["tipo"] == "demissao"]
        elif tipo_filtro == "Afastamentos":
            vagas_filtradas = [v for v in vagas_filtradas if v["tipo"] == "afastamento"]

        if unidade_filtro != "Todas":
            vagas_filtradas = [v for v in vagas_filtradas if v["centro_custo"] == unidade_filtro]
        
        if not vagas_filtradas:
            st.info("Nenhuma vaga encontrada")
        else:
            st.subheader(f"📋 {len(vagas_filtradas)} Vaga(s) no Relatório")
            
            for vaga in vagas_filtradas:
                info_tlp = verificar_vaga_na_tlp(vaga["row_data"], tlp, relatorio)
                renderizar_card_vaga(vaga, None, info_tlp)
                st.markdown("---")
    
    # ==================== EXPORTAÇÃO ====================
    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 Exportar")
    
    if st.sidebar.button("💾 Exportar Excel"):
        buffer = exportar_vagas_excel()
        
        if buffer:
            st.sidebar.download_button(
                "📥 Download Excel",
                data=buffer,
                file_name=f"vagas_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == '__main__':
    run()
