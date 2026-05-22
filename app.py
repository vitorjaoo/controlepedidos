import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

# ==========================================
# CONFIGURAÇÃO DE AMBIENTE
# ==========================================
st.set_page_config(page_title="ERP | Rastreio de Pedidos", layout="wide", initial_sidebar_state="collapsed")

# Diretório para simular armazenamento (Substituir por S3/Supabase Storage no deploy final)
UPLOAD_DIR = "storage_pedidos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==========================================
# BANCO DE DADOS (TURSO / SQLITE)
# ==========================================
def get_connection():
    return sqlite3.connect("sistema_pedidos.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente TEXT NOT NULL,
                    etapa_atual TEXT DEFAULT '1. Solicitação',
                    
                    arq_solicitacao TEXT,
                    
                    valor_fabrica REAL DEFAULT 0.0,
                    arq_orc_fabrica TEXT,
                    
                    valor_mercos REAL DEFAULT 0.0,
                    
                    confirmacao_cliente BOOLEAN DEFAULT 0,
                    
                    conferencia_fabrica BOOLEAN DEFAULT 0,
                    
                    valor_faturado REAL DEFAULT 0.0,
                    arq_faturamento TEXT,
                    
                    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()

init_db()

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def salvar_arquivo(arquivo_upload, prefixo, pedido_id):
    if arquivo_upload is not None:
        nome_arquivo = f"{prefixo}_P{pedido_id}_{arquivo_upload.name}"
        caminho = os.path.join(UPLOAD_DIR, nome_arquivo)
        with open(caminho, "wb") as f:
            f.write(arquivo_upload.getbuffer())
        return nome_arquivo
    return None

def atualizar_campo_pedido(pedido_id, campo, valor):
    conn = get_connection()
    conn.execute(f"UPDATE pedidos SET {campo} = ?, data_atualizacao = CURRENT_TIMESTAMP WHERE id = ?", (valor, pedido_id))
    conn.commit()

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================
st.title("📦 Central de Rastreio e Faturamento")

conn = get_connection()
df = pd.read_sql_query("SELECT * FROM pedidos", conn)

# ==========================================
# CÁLCULOS EM TEMPO REAL (SALDO)
# ==========================================
if not df.empty:
    df['saldo_faltante'] = df['valor_mercos'] - df['valor_faturado']
    # Cria uma coluna visual rápida
    df['status_saldo'] = df.apply(lambda row: "🔴 FALTA SALDO" if row['saldo_faltante'] > 0 and row['etapa_atual'] == '6. Faturamento' else "🟢 OK", axis=1)

# Layout Split: Grid (70%) e Cards de Ação (30%)
col_grid, col_cards = st.columns([7, 4])

with col_grid:
    st.subheader("Painel de Pedidos")
    
    with st.popover("➕ Novo Pedido"):
        with st.form("form_novo_pedido"):
            novo_cliente = st.text_input("Nome/Razão Social do Cliente")
            if st.form_submit_button("Gerar Pedido"):
                if novo_cliente:
                    conn.execute("INSERT INTO pedidos (cliente) VALUES (?)", (novo_cliente,))
                    conn.commit()
                    st.rerun()

    # Exibição enxuta na tabela principal
    colunas_visiveis = ['id', 'cliente', 'etapa_atual', 'valor_mercos', 'valor_faturado', 'saldo_faltante', 'status_saldo']
    df_display = df[colunas_visiveis] if not df.empty else df
    
    evento = st.dataframe(
        df_display, 
        use_container_width=True, 
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun"
    )

with col_cards:
    st.subheader("Processo do Pedido")
    
    if len(evento.selection.rows) > 0:
        linha_selecionada = evento.selection.rows[0]
        pedido = df.iloc[linha_selecionada]
        p_id = pedido['id']
        
        st.info(f"**Editando Pedido #{p_id}** | {pedido['cliente']}")
        
        # CARD 1: SOLICITAÇÃO
        with st.expander("📝 1. Solicitação do Cliente", expanded=(pedido['etapa_atual'] == '1. Solicitação')):
            if pedido['arq_solicitacao']:
                st.success(f"Arquivo anexado: {pedido['arq_solicitacao']}")
            else:
                arq = st.file_uploader("Upload Solicitação (PDF/Img)", key=f"sol_{p_id}")
                if st.button("Salvar Solicitação", key=f"btn_sol_{p_id}"):
                    if arq:
                        nome_salvo = salvar_arquivo(arq, "SOL", p_id)
                        atualizar_campo_pedido(p_id, 'arq_solicitacao', nome_salvo)
                        atualizar_campo_pedido(p_id, 'etapa_atual', '2. Orçamento Fábrica')
                        st.rerun()

        # CARD 2: ORÇAMENTO FÁBRICA
        with st.expander("🏭 2. Orçamento Fábrica", expanded=(pedido['etapa_atual'] == '2. Orçamento Fábrica')):
            v_fabrica = st.number_input("Custo Fábrica (R$)", value=float(pedido['valor_fabrica']), key=f"fab_v_{p_id}")
            if pedido['arq_orc_fabrica']:
                st.success(f"Arquivo anexado: {pedido['arq_orc_fabrica']}")
            arq_fab = st.file_uploader("Upload Orçamento Fábrica", key=f"fab_a_{p_id}")
            
            if st.button("Avançar para Mercos", key=f"btn_fab_{p_id}"):
                if arq_fab:
                    nome_salvo = salvar_arquivo(arq_fab, "FAB", p_id)
                    atualizar_campo_pedido(p_id, 'arq_orc_fabrica', nome_salvo)
                atualizar_campo_pedido(p_id, 'valor_fabrica', v_fabrica)
                atualizar_campo_pedido(p_id, 'etapa_atual', '3. Orçamento Mercos')
                st.rerun()

        # CARD 3: ORÇAMENTO MERCOS
        with st.expander("💻 3. Orçamento Mercos", expanded=(pedido['etapa_atual'] == '3. Orçamento Mercos')):
            v_mercos = st.number_input("Valor de Venda Mercos (R$)", value=float(pedido['valor_mercos']), key=f"mer_v_{p_id}")
            if st.button("Aguardar Aprovação Cliente", key=f"btn_mer_{p_id}"):
                atualizar_campo_pedido(p_id, 'valor_mercos', v_mercos)
                atualizar_campo_pedido(p_id, 'etapa_atual', '4. Confirmação Cliente')
                st.rerun()

        # CARD 4: CONFIRMAÇÃO CLIENTE
        with st.expander("✅ 4. Confirmação do Cliente", expanded=(pedido['etapa_atual'] == '4. Confirmação Cliente')):
            conf_cliente = st.checkbox("Cliente deu o 'De Acordo'?", value=bool(pedido['confirmacao_cliente']), key=f"conf_c_{p_id}")
            if st.button("Salvar Confirmação", key=f"btn_conf_c_{p_id}"):
                atualizar_campo_pedido(p_id, 'confirmacao_cliente', conf_cliente)
                if conf_cliente:
                    atualizar_campo_pedido(p_id, 'etapa_atual', '5. Conferência Fábrica')
                st.rerun()

        # CARD 5: CONFERÊNCIA FÁBRICA
        with st.expander("🔍 5. Versão Final Enviada (Conferência)", expanded=(pedido['etapa_atual'] == '5. Conferência Fábrica')):
            conf_fab = st.checkbox("Versão final conferida e enviada para produção?", value=bool(pedido['conferencia_fabrica']), key=f"conf_f_{p_id}")
            if st.button("Liberar para Faturamento", key=f"btn_conf_f_{p_id}"):
                atualizar_campo_pedido(p_id, 'conferencia_fabrica', conf_fab)
                if conf_fab:
                    atualizar_campo_pedido(p_id, 'etapa_atual', '6. Faturamento')
                st.rerun()

        # CARD 6: FATURAMENTO
        with st.expander("🧾 6. Faturamento e NFs", expanded=(pedido['etapa_atual'] == '6. Faturamento')):
            v_faturado = st.number_input("Valor Faturado (R$)", value=float(pedido['valor_faturado']), key=f"fat_v_{p_id}")
            if pedido['arq_faturamento']:
                st.success(f"Arquivo anexado: {pedido['arq_faturamento']}")
            arq_fat = st.file_uploader("Upload da NF / Faturamento", key=f"fat_a_{p_id}")
            
            if st.button("Atualizar Faturamento", key=f"btn_fat_{p_id}"):
                if arq_fat:
                    nome_salvo = salvar_arquivo(arq_fat, "FAT", p_id)
                    atualizar_campo_pedido(p_id, 'arq_faturamento', nome_salvo)
                atualizar_campo_pedido(p_id, 'valor_faturado', v_faturado)
                st.rerun()

        # CARD EXTRA: RASTREIO DE SALDO FALTANTE
        st.markdown("---")
        saldo = pedido['saldo_faltante']
        if saldo > 0:
            st.error(f"⚠️ **RASTREIO DE SALDO FALTANTE:** R$ {saldo:,.2f}")
            st.caption("Atenção: O valor faturado está menor que o orçamento fechado no Mercos.")
        else:
            if pedido['valor_mercos'] > 0:
                st.success("✔️ Faturamento completo. Sem saldo faltante.")

    else:
        st.write("👈 Selecione um pedido na tabela para abrir as etapas de processo.")
