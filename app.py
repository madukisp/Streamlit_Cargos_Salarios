import streamlit as st

# set_page_config deve ser a primeira chamada do Streamlit no arquivo
st.set_page_config(
    page_title="Painel Oris",
    layout="wide"
)

# Agora importe os módulos de página (que podem usar Streamlit) somente depois
import aprovar_vaga as aprovar_vaga
import quadro_func
import traceback

# Inicializa session_state para navegação
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Página Inicial"

def home_page():
    """Página inicial do sistema"""
    st.title("🏠 Painel ORIS - Sistema de Gestão")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Quadro de Funcionários")
        st.markdown("""
        - Visualize o quadro completo de funcionários
        - Detalhamento por cargo e unidade
        - Comparação com TLP (Tabela de Lotação de Pessoal)
        - Análise de déficits e superávits
        """)
        if st.button("Acessar Quadro de Funcionários", use_container_width=True):
            st.session_state.current_page = "Quadro de Funcionários"
            st.rerun()

    with col2:
        st.subheader("✅ Aprovação de Vagas")
        st.markdown("""
        - Aprovar vagas de demissões e afastamentos
        - Sincronizar vagas do relatório
        - Visualizar histórico de aprovações
        - Gerenciar vagas canceladas
        """)
        if st.button("Acessar Aprovação de Vagas", use_container_width=True):
            st.session_state.current_page = "Aprovação de Vagas"
            st.rerun()

PAGES = {
    "Página Inicial": {"module": None, "function": home_page},
    "Quadro de Funcionários": {"module": quadro_func, "function": None},
    "Aprovação de Vagas": {"module": aprovar_vaga, "function": None},
}

st.sidebar.title('🧭 Navegação')

# Botões de navegação
if st.sidebar.button("🏠 Página Inicial",
                     use_container_width=True,
                     type="primary" if st.session_state.current_page == "Página Inicial" else "secondary"):
    st.session_state.current_page = "Página Inicial"
    st.rerun()

if st.sidebar.button("📊 Quadro de Funcionários",
                     use_container_width=True,
                     type="primary" if st.session_state.current_page == "Quadro de Funcionários" else "secondary"):
    st.session_state.current_page = "Quadro de Funcionários"
    st.rerun()

if st.sidebar.button("✅ Aprovação de Vagas",
                     use_container_width=True,
                     type="primary" if st.session_state.current_page == "Aprovação de Vagas" else "secondary"):
    st.session_state.current_page = "Aprovação de Vagas"
    st.rerun()

page_info = PAGES[st.session_state.current_page]

# Adiciona um CSS para o tema escuro se a página for o quadro de funcionários
if st.session_state.current_page == "Quadro de Funcionários":
    st.markdown(
        """
        <style>
        :root {
            color-scheme: dark;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

try:
    # Se for página inicial, chama a função diretamente
    if page_info["function"] is not None:
        page_info["function"]()
    # Caso contrário, chama o módulo.run()
    elif page_info["module"] is not None:
        page_info["module"].run()
except NameError as e:
    st.error(f"Erro de execução: {e}")
    st.markdown(
        """
        **Possíveis causas e correções rápidas**
        - A função `carregar_dados` (ou outro nome referenciado) não foi definida em `aprovar_vaga.py`.
        - Verifique em `aprovar_vaga.py` se existe uma função `def carregar_dados(...):` ou se está sendo importada corretamente.
        - Alternativamente, ajuste `aprovar_vaga.run()` para não chamar nomes não definidos ou exporte as funções necessárias.
        """
    )
    st.subheader("Stack trace")
    st.text(traceback.format_exc())
except AttributeError as e:
    st.error(f"Erro de atributo: {e}")
    st.markdown("Verifique se o módulo de página exporta uma função `run()`.")
    st.subheader("Stack trace")
    st.text(traceback.format_exc())
except Exception as e:
    st.error("Ocorreu um erro ao executar a página.")
    st.subheader("Stack trace")
    st.text(traceback.format_exc())
