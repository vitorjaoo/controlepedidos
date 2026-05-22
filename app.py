import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os

# Cria uma pasta para salvar os PDFs localmente (para teste)
if not os.path.exists("uploads"):
    os.makedirs("uploads")

st.set_page_config(page_title="Sistema de Pedidos", layout="wide")

# ==========================================
# 1. BANCO DE DADOS ATUALIZADO
# ==========================================
def get_connection():
    return sqlite3.connect("pedidos.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    # Adicionadas colunas para arquivos PDF
    conn.execute('''CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente TEXT, 
                    status TEXT DEFAULT '1. Solicitação', 
                    valor_fabrica REAL DEFAULT 0.0, 
                    valor_mercos REAL DEFAULT 0.0, 
                    valor_faturado REAL DEFAULT 0.0, 
                    arquivo_pdf TEXT,
                    data_atualizacao TEXT)''')
    conn.commit()

init_db()

# ==========================================
# 2. LOGIN (MANTIDO)
# ==========================================
if "role" not in st.session_state:
    st.session_state.role = "admin" # Deixei admin por padrão para facilitar seu teste agora

# ==========================================
# 3. INTERFACE COM ABAS
# ==========================================
col_title, col_logout = st.columns([8, 1])
col_title.title("📦 Sistema Central de Pedidos")
if col_logout.button("Sair"):
    st.session_state.role = None
    st.rerun()

# Criando Abas para organizar o sistema em 1 só lugar
aba_pedidos, aba_clientes = st.tabs(["🚀 Painel de Pedidos", "👥 Base de Clientes"])

# ------------------------------------------
# ABA 1: PAINEL DE PEDIDOS (Onde a mágica acontece)
# ------------------------------------------
with aba_pedidos:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM pedidos", conn)

    if not df.empty:
        df['saldo_faltante'] = df['valor_mercos'] - df['valor_faturado']
        df['alerta_saldo'] = df['saldo_faltante'].apply(lambda x: "⚠️ FALTA SALDO" if x > 0 else "OK")

    col_grid, col_side = st.columns([7, 3])

    with col_grid:
        st.subheader("Visão Geral")
        event = st.dataframe(df, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")

    with col_side:
        st.subheader("Painel Rápido")
        
        # Se selecionou um pedido na tabela
        if len(event.selection.rows) > 0:
            linha = event.selection.rows[0]
            p_id = df.iloc[linha]['id']
            p_status = df.iloc[linha]['status']
            p_arquivo = df.iloc[linha]['arquivo_pdf']
            
            st.write(f"**Pedido #{p_id}** | Cliente: {df.iloc[linha]['cliente']}")
            
            with st.form("form_edicao"):
                lista_status = ['1. Solicitação', '2. Orçamento Fábrica', '3. Orçamento Mercos', '4. Confirmação Cliente', '5. Conferência', '6. Faturamento']
                novo_status = st.selectbox("Status Atual", lista_status, index=lista_status.index(p_status) if p_status in lista_status else 0)
                
                col1, col2 = st.columns(2)
                v_fab = col1.number_input("Fábrica (R$)", value=float(df.iloc[linha]['valor_fabrica']))
                v_mer = col2.number_input("Mercos (R$)", value=float(df.iloc[linha]['valor_mercos']))
                v_fat = st.number_input("Faturado (R$)", value=float(df.iloc[linha]['valor_faturado']))
                
                # UPLOAD DE PDF AQUI
                st.markdown("---")
                st.write("📄 **Anexos do Pedido**")
                if pd.notna(p_arquivo) and p_arquivo != "":
                    st.success(f"Arquivo anexado: {p_arquivo}")
                
                novo_pdf = st.file_uploader("Subir Orçamento (PDF)", type=["pdf"])

                if st.form_submit_button("💾 Salvar Alterações"):
                    nome_arquivo_salvo = p_arquivo
                    
                    # Se o usuário subiu um arquivo novo, salva na pasta uploads
                    if novo_pdf is not None:
                        nome_arquivo_salvo = f"pedido_{p_id}_{novo_pdf.name}"
                        with open(os.path.join("uploads", nome_arquivo_salvo), "wb") as f:
                            f.write(novo_pdf.getbuffer())

                    conn.execute('''UPDATE pedidos SET 
                                    status=?, valor_fabrica=?, valor_mercos=?, valor_faturado=?, arquivo_pdf=?, data_atualizacao=? 
                                    WHERE id=?''', 
                                 (novo_status, v_fab, v_mer, v_fat, nome_arquivo_salvo, datetime.now().strftime("%d/%m/%Y %H:%M"), p_id))
                    conn.commit()
                    st.rerun()
        else:
            st.info("👈 Clique em um pedido para ver e anexar PDFs.")

        # Novo Pedido
        st.divider()
        with st.expander("➕ Iniciar Novo Pedido"):
            with st.form("form_novo"):
                novo_cliente = st.text_input("Nome/Código do Cliente")
                if st.form_submit_button("Criar Pedido"):
                    conn.execute("INSERT INTO pedidos (cliente) VALUES (?)", (novo_cliente,))
                    conn.commit()
                    st.rerun()

# ------------------------------------------
# ABA 2: BASE DE CLIENTES (O "resto do sistema")
# ------------------------------------------
with aba_clientes:
    st.subheader("Gestão de Clientes")
    st.write("Para não poluir a tela de rastreio, cadastros fixos ficam aqui.")
    st.info("Aqui você pode criar uma nova tabela no banco de dados chamada 'clientes' (com CNPJ, Endereço, Telefone, etc) e listar eles nesta aba. Depois, no 'Novo Pedido', em vez de digitar o nome, você fará um select puxando desta lista.")
    
    # Exemplo visual de como ficaria:
    with st.expander("Cadastrar Novo Cliente"):
        st.text_input("Razão Social")
        st.text_input("CNPJ")
        st.button("Salvar Cliente")
