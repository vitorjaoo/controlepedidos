import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ==========================================
# 1. CONFIGURAÇÃO E CONEXÃO COM BANCO (TURSO)
# ==========================================
st.set_page_config(page_title="Rastreio de Pedidos", layout="wide")

# Para conectar ao Turso real, instale: pip install libsql-client
# E substitua a conexão abaixo pela URL do seu banco Turso.
# Ex: conn = libsql_client.create_client_sync(url="libsql://controlepedido-vitorrastrep.aws-us-east-2.turso.io", auth_token="eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3Nzk0NTYzMjksImlkIjoiMDE5ZTRmZDItMDAwMS03NDAzLWIzNzctYzE3NzExNTNkMDg4IiwicmlkIjoiYTIyZDdhOTUtYTE3My00MGE5LWE4NzItNzI1NmExM2U2OTdjIn0.p-XVNA5MQkdU_b5-lMWbwr23BAaeFKO9geGozBgV7xhBBnhIDUXz3grL7JI6NbUqsnE4xxLwCZvHeEKJjsroCg")
def get_connection():
    return sqlite3.connect("pedidos.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente TEXT, status TEXT, valor_fabrica REAL, 
                    valor_mercos REAL, valor_faturado REAL, data_atualizacao TEXT)''')
    conn.commit()

init_db()

# ==========================================
# 2. SISTEMA DE LOGIN SIMPLES
# ==========================================
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    st.title("🔐 Acesso ao Sistema")
    senha = st.text_input("Digite a senha de acesso", type="password")
    
    if st.button("Entrar"):
        if senha == "admin123": # Senha do Administrador
            st.session_state.role = "admin"
            st.rerun()
        elif senha == "viewer123": # Senha de Visualização
            st.session_state.role = "viewer"
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()

# ==========================================
# 3. INTERFACE PRINCIPAL (GRID + SIDEBAR)
# ==========================================
# Topo da tela
col_title, col_logout = st.columns([8, 1])
col_title.title("📦 Rastreio Central de Pedidos")
if col_logout.button("Sair"):
    st.session_state.role = None
    st.rerun()

# Carregar dados
conn = get_connection()
df = pd.read_sql_query("SELECT * FROM pedidos", conn)

# Calcular Saldo Faltante em tempo real
if not df.empty:
    df['saldo_faltante'] = df['valor_mercos'] - df['valor_faturado']
    df['alerta_saldo'] = df['saldo_faltante'].apply(lambda x: "⚠️ FALTA SALDO" if x > 0 else "OK")

# Layout Dividido (Grid e Sidebar)
col_grid, col_side = st.columns([7, 3])

with col_grid:
    st.subheader("Visão Geral")
    
    # Se for viewer, permite baixar os dados
    if st.session_state.role == "viewer" and not df.empty:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Baixar Relatório (CSV)", data=csv, file_name='pedidos.csv', mime='text/csv')

    # A Tabela Interativa
    # Usamos on_select="rerun" para atualizar a barra lateral ao clicar numa linha
    event = st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun"
    )

with col_side:
    st.subheader("Painel de Ação Rápida")
    
    # Se o usuário clicou em uma linha
    if len(event.selection.rows) > 0:
        linha_selecionada = event.selection.rows[0]
        pedido_id = df.iloc[linha_selecionada]['id']
        cliente_atual = df.iloc[linha_selecionada]['cliente']
        status_atual = df.iloc[linha_selecionada]['status']
        
        st.write(f"**Editando Pedido #{pedido_id}** - {cliente_atual}")
        
        # Apenas Admin pode editar
        if st.session_state.role == "admin":
            lista_status = [
                '1. Solicitação', '2. Orçamento Fábrica', '3. Orçamento Mercos', 
                '4. Confirmação Cliente', '5. Conferência Fábrica', '6. Faturamento'
            ]
            
            with st.form("form_edicao"):
                novo_status = st.selectbox("Status", lista_status, index=lista_status.index(status_atual))
                v_fabrica = st.number_input("Orçamento Fábrica (R$)", value=float(df.iloc[linha_selecionada]['valor_fabrica']))
                v_mercos = st.number_input("Orçamento Mercos (R$)", value=float(df.iloc[linha_selecionada]['valor_mercos']))
                v_faturado = st.number_input("Valor Faturado (R$)", value=float(df.iloc[linha_selecionada]['valor_faturado']))
                
                # Exibe alerta visual no painel se houver saldo faltante
                if v_mercos - v_faturado > 0 and novo_status == '6. Faturamento':
                    st.error(f"⚠️ Saldo Faltante: R$ {v_mercos - v_faturado:.2f}")
                
                if st.form_submit_button("💾 Salvar Alterações"):
                    conn.execute('''UPDATE pedidos SET 
                                    status=?, valor_fabrica=?, valor_mercos=?, valor_faturado=?, data_atualizacao=? 
                                    WHERE id=?''', 
                                 (novo_status, v_fabrica, v_mercos, v_faturado, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pedido_id))
                    conn.commit()
                    st.rerun()
        else:
            st.info("Visualizadores não podem alterar dados.")
            st.write(f"**Status Atual:** {status_atual}")
            
    else:
        st.write("👈 Clique em um pedido na tabela para ver os detalhes ou atualizar.")

    # Formulário para criar novo pedido (Apenas Admin)
    if st.session_state.role == "admin":
        st.divider()
        with st.expander("➕ Novo Pedido"):
            with st.form("form_novo"):
                novo_cliente = st.text_input("Nome do Cliente")
                if st.form_submit_button("Criar Pedido"):
                    conn.execute("INSERT INTO pedidos (cliente) VALUES (?)", (novo_cliente,))
                    conn.commit()
                    st.rerun()
