import streamlit as st
import pandas as pd
import os
import sqlite3
from io import BytesIO
import unicodedata

# Importa configuração centralizada
try:
    from config import DB_PATH_STR as ORIS_DB_PATH, validar_estrutura
    validar_estrutura()
except ImportError:
    # Fallback para estrutura antiga
    ORIS_DB_PATH = os.path.join(os.getcwd(), "data", "oris.db")

def run():
    st.title("📊 Análise de Déficit de Horas por Centro de Custo")
    st.markdown("---")

    def _strip_accents_upper(text):
        """Remove acentos e converte para maiúsculas"""
        s = str(text).upper()
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return s.strip()

    @st.cache_data(ttl=600)
    def carregar_dados_db():
        """Carrega dados do banco oris.db"""
        if not os.path.exists(ORIS_DB_PATH):
            st.error(f"❌ Banco de dados não encontrado: {ORIS_DB_PATH}")
            return None, None, None
        
        try:
            conn = sqlite3.connect(ORIS_DB_PATH)
            
            # Carrega TLP
            tlp = pd.read_sql_query("SELECT * FROM tlp", conn)
            
            # Carrega relatório ORIS
            relatorio = pd.read_sql_query("SELECT * FROM relatorio_oris", conn)
            
            # Carrega vagas
            try:
                vagas = pd.read_sql_query("SELECT * FROM vagas", conn)
            except:
                vagas = pd.DataFrame()
            
            conn.close()
            
            st.success(f"✅ Dados carregados: {len(relatorio)} registros do ORIS, {len(tlp)} da TLP")
            return tlp, relatorio, vagas
            
        except Exception as e:
            st.error(f"❌ Erro ao carregar dados: {e}")
            return None, None, None

    def calcular_deficit(tlp, relatorio):
        """Calcula déficit de funcionários"""
        if tlp is None or relatorio is None:
            return None
        
        # Filtra apenas SBCD - REDE ASSIST. NORTE-SP
        target = "SBCD - REDE ASSIST. NORTE-SP"
        if "Nome Fantasia" in relatorio.columns:
            relatorio = relatorio[
                relatorio["Nome Fantasia"].astype(str).apply(_strip_accents_upper) 
                == _strip_accents_upper(target)
            ].copy()
        
        # Separa ativos e afastados
        ativos = relatorio[relatorio["Situação"] == "01-ATIVO"].copy()
        afastados = relatorio[
            ~relatorio["Situação"].isin(["01-ATIVO", "99-Demitido"])
        ].copy()
        
        # Converte carga horária para float em ambos os dataframes
        ativos["Carga Horária Semanal"] = pd.to_numeric(ativos["Carga Horária Semanal"], errors='coerce')
        afastados["Carga Horária Semanal"] = pd.to_numeric(afastados["Carga Horária Semanal"], errors='coerce')

        # Agrupa ativos POR CARGA HORÁRIA
        ativos_agrupado = ativos.groupby(["Centro custo", "Cargo", "Carga Horária Semanal"]).agg(
            Qtd_Ativos=("Nome", "count")
        ).reset_index()

        # Agrupa afastados POR CARGA HORÁRIA
        afastados_agrupado = afastados.groupby(["Centro custo", "Cargo", "Carga Horária Semanal"]).agg(
            Qtd_Afastados=("Nome", "count")
        ).reset_index()

        # Renomeia colunas TLP para padronizar E converte carga_hora para float
        tlp_prep = tlp.rename(columns={
            "unidade": "Centro custo",
            "cargo": "Cargo",
            "carga_hora": "Carga Horária Semanal",
            "quantidade_ideal": "Qtd_Necessaria"
        })

        # Garante que a coluna de carga horária é numérica na TLP também
        tlp_prep["Carga Horária Semanal"] = pd.to_numeric(tlp_prep["Carga Horária Semanal"], errors='coerce')

        # Merge TLP com ativos (agora incluindo carga horária)
        resultado = pd.merge(
            tlp_prep[["Centro custo", "Cargo", "Carga Horária Semanal", "Qtd_Necessaria"]],
            ativos_agrupado,
            on=["Centro custo", "Cargo", "Carga Horária Semanal"],
            how="left"
        )

        # Merge com afastados
        resultado = pd.merge(
            resultado,
            afastados_agrupado,
            on=["Centro custo", "Cargo", "Carga Horária Semanal"],
            how="left"
        )
        
        # Preenche valores nulos
        resultado["Qtd_Ativos"] = resultado["Qtd_Ativos"].fillna(0).astype(int)
        resultado["Qtd_Afastados"] = resultado["Qtd_Afastados"].fillna(0).astype(int)
        resultado["Qtd_Necessaria"] = resultado["Qtd_Necessaria"].fillna(0).astype(int)
        
        # Calcula déficit
        resultado["Deficit"] = resultado["Qtd_Necessaria"] - resultado["Qtd_Ativos"]
        resultado["Excedente"] = resultado.apply(
            lambda x: abs(x["Deficit"]) if x["Deficit"] < 0 else 0, axis=1
        )
        resultado["Funcionarios_Contratar"] = resultado.apply(
            lambda x: x["Deficit"] if x["Deficit"] > 0 else 0, axis=1
        )
        
        # Remove colunas auxiliares criadas para manter DataFrames limpos (opcional)
        if 'carga_hora_merge' in resultado.columns:
            resultado = resultado.drop(columns=['carga_hora_merge'])

        return resultado

    # Carrega dados
    with st.spinner("🔄 Carregando dados do banco..."):
        tlp, relatorio, vagas = carregar_dados_db()

    if tlp is None or relatorio is None:
        st.stop()

    # Calcula déficit
    deficit_df = calcular_deficit(tlp, relatorio)

    if deficit_df is None:
        st.error("Não foi possível calcular o déficit")
        st.stop()

    # Filtros na sidebar
    st.sidebar.header("🔍 Filtros")
    
    centros = ["Todos"] + sorted(deficit_df["Centro custo"].unique().tolist())
    centro_sel = st.sidebar.selectbox("Centro de Custo", centros)
    
    status_opcoes = ["Todos", "Apenas com Déficit", "Apenas Excedentes", "Apenas Completos"]
    status_sel = st.sidebar.radio("Mostrar", status_opcoes)
    
    # Aplica filtros
    df_filtrado = deficit_df.copy()
    
    if centro_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Centro custo"] == centro_sel]
    
    if status_sel == "Apenas com Déficit":
        df_filtrado = df_filtrado[df_filtrado["Deficit"] > 0]
    elif status_sel == "Apenas Excedentes":
        df_filtrado = df_filtrado[df_filtrado["Excedente"] > 0]
    elif status_sel == "Apenas Completos":
        df_filtrado = df_filtrado[df_filtrado["Deficit"] == 0]
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    
    total_contratar = int(df_filtrado["Funcionarios_Contratar"].sum())
    total_deficit = len(df_filtrado[df_filtrado["Deficit"] > 0])
    total_cargos = len(df_filtrado)
    perc_completo = ((total_cargos - total_deficit) / total_cargos * 100) if total_cargos > 0 else 0
    
    with col1:
        st.metric("Funcionários a Contratar", f"{total_contratar}", delta=f"-{total_contratar}", delta_color="inverse")
    with col2:
        st.metric("Cargos com Déficit", f"{total_deficit}/{total_cargos}")
    with col3:
        st.metric("Total de Cargos", f"{total_cargos}")
    with col4:
        st.metric("% Completo", f"{perc_completo:.1f}%")
    
    st.markdown("---")
    
    # Tabela principal
    st.subheader("📋 Detalhamento por Cargo")
    
    df_exibicao = df_filtrado[[
        "Centro custo", "Cargo", "Carga Horária Semanal", "Qtd_Necessaria", "Qtd_Ativos",
        "Qtd_Afastados", "Deficit", "Funcionarios_Contratar", "Excedente"
    ]].copy()

    df_exibicao.columns = [
        "Centro de Custo", "Cargo", "Carga Horária", "Qtd Necessária", "Qtd Ativos",
        "Qtd Afastados", "Déficit", "Contratar", "Excedente"
    ]
    
    def highlight_deficit(row):
        deficit = row["Déficit"]
        if deficit > 0:
            return ["background-color: #460202FF; color: white"] * len(row)
        elif deficit < 0:
            return ["background-color: #051050C2; color: white"] * len(row)
        else:
            return ["background-color: #011F01FF; color: white"] * len(row)
    
    st.dataframe(
        df_exibicao.style.apply(highlight_deficit, axis=1),
        use_container_width=True,
        height=500
    )
    
    st.markdown("---")
    
    # Funcionários por cargo
    st.subheader("👥 Funcionários Ativos por Cargo")
    
    if relatorio is not None:
        ativos_total = relatorio[relatorio["Situação"] == "01-ATIVO"].copy()
        
        centro_opts = ["Todos"] + sorted(ativos_total["Centro custo"].unique().tolist())
        centro_func = st.selectbox("Filtrar Centro", centro_opts)
        
        if centro_func != "Todos":
            cargo_opts = ["Todos"] + sorted(
                ativos_total[ativos_total["Centro custo"] == centro_func]["Cargo"].unique().tolist()
            )
        else:
            cargo_opts = ["Todos"] + sorted(ativos_total["Cargo"].unique().tolist())
        
        cargo_func = st.selectbox("Filtrar Cargo", cargo_opts)
        
        df_func = ativos_total[["Nome", "Cargo", "Centro custo"]].copy()
        
        if centro_func != "Todos":
            df_func = df_func[df_func["Centro custo"] == centro_func]
        if cargo_func != "Todos":
            df_func = df_func[df_func["Cargo"] == cargo_func]
        
        if not df_func.empty:
            st.dataframe(df_func.sort_values(["Cargo", "Nome"]).reset_index(drop=True), use_container_width=True)
        else:
            st.info("Nenhum funcionário encontrado com os filtros selecionados")
    
    st.markdown("---")
    
    # Cargos prioritários
    cargos_deficit = df_filtrado[df_filtrado["Funcionarios_Contratar"] > 0].sort_values(
        "Funcionarios_Contratar", ascending=False
    )
    
    if len(cargos_deficit) > 0:
        st.subheader("⚠️ Cargos Prioritários")
        
        for _, row in cargos_deficit.head(10).iterrows():
            with st.expander(f"**{row['Cargo']}** - {row['Centro custo']}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("#### 📊 Situação")
                    st.write(f"**Necessário:** {int(row['Qtd_Necessaria'])}")
                    st.write(f"**Ativos:** {int(row['Qtd_Ativos'])}")
                    if int(row['Qtd_Afastados']) > 0:
                        st.write(f"**Afastados:** {int(row['Qtd_Afastados'])}")
                
                with col2:
                    st.markdown("#### 📉 Déficit")
                    st.error(f"**{int(row['Deficit'])} funcionários**")
                
                with col3:
                    st.markdown("#### 🎯 Ação")
                    st.error(f"**CONTRATAR: {int(row['Funcionarios_Contratar'])}**")
    
    st.markdown("---")
    
    # Exportar
    st.subheader("💾 Exportar")
    
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_exibicao.to_excel(writer, index=False, sheet_name="Déficit")
    buffer.seek(0)
    
    st.download_button(
        "📥 Baixar Excel",
        data=buffer,
        file_name="analise_deficit.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    # Botão atualizar
    if st.sidebar.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()

if __name__ == '__main__':
    run()