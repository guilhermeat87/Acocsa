import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Monitor de Ativos", layout="wide")

# ==============================
# CONFIGURAÇÕES
# ==============================

SHEET_ID = "1bNKnU-HzvB--KfREcXJAmxtvtEOuqDmeFo59QGJX0hw"
GID = "0"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}"
MAX_ATIVOS = 10

# ==============================
# GOOGLE SHEETS
# ==============================

@st.cache_resource
def get_gspread_client():
    sa_info = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource
def get_watchlist_sheet():
    gc = get_gspread_client()
    sh = gc.open_by_key(SHEET_ID)
    return sh.worksheet("watchlist")

# ==============================
# CARREGAMENTO PLANILHA
# ==============================

@st.cache_data(ttl=300)
def load_sheet():
    try:
        df = pd.read_csv(CSV_URL, engine="python", sep=";", on_bad_lines="skip")
    except:
        df = pd.read_csv(CSV_URL, engine="python", sep=",", on_bad_lines="skip")

    df.columns = df.columns.astype(str).str.strip().str.upper()

    if "TICKER" not in df.columns:
        st.error("Coluna TICKER não encontrada.")
        st.write(df.columns.tolist())
        st.stop()

    df["TICKER"] = df["TICKER"].astype(str).str.upper().str.strip()

    return df

# ==============================
# PREÇO AUTOMÁTICO (UPGRADE 6)
# ==============================

@st.cache_data(ttl=300)
def get_price(ticker):
    try:
        data = yf.download(ticker + ".SA", period="1d", interval="1m", progress=False)
        return float(data["Close"].iloc[-1])
    except:
        return None

# ==============================
# INÍCIO APP
# ==============================

st.title("📈 Monitor de Ativos")

st.markdown("""
<style>
div[data-testid="metric-container"] {
    background-color: #111;
    padding: 15px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

df = load_sheet()

if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

user_id = st.sidebar.text_input("Digite seu e-mail para salvar sua lista")

# ==============================
# CARREGA LISTA DO USUÁRIO
# ==============================

if user_id:
    ws = get_watchlist_sheet()
    data = ws.get_all_records()
    user_saved = [row["TICKER"] for row in data if row["USER_ID"] == user_id]
    st.session_state.watchlist = user_saved

# ==============================
# SIDEBAR
# ==============================

st.sidebar.header("Escolha seus ativos")
st.sidebar.caption(f"{len(st.session_state.watchlist)}/{MAX_ATIVOS} ativos")

tickers = sorted(df["TICKER"].dropna().unique())
selected = st.sidebar.selectbox("Selecione um ativo", tickers)

# ADICIONAR
if st.sidebar.button("➕ Adicionar"):
    if not user_id:
        st.sidebar.error("Digite seu e-mail para salvar.")
    elif selected in st.session_state.watchlist:
        st.sidebar.info("Já está na lista.")
    elif len(st.session_state.watchlist) >= MAX_ATIVOS:
        st.sidebar.error("Limite de 10 ativos atingido.")
    else:
        st.session_state.watchlist.append(selected)
        ws = get_watchlist_sheet()
        ws.append_row([user_id, selected])
        st.rerun()

# REMOVER
st.sidebar.markdown("---")
st.sidebar.subheader("Minha lista")

for t in st.session_state.watchlist:
    c1, c2 = st.sidebar.columns([4, 1])
    c1.write(t)

    if c2.button("❌", key=f"del_{t}"):

        st.session_state.watchlist.remove(t)

        ws = get_watchlist_sheet()
        cells = ws.get_all_values()

        for i, row in enumerate(cells[1:], start=2):
            if row[0] == user_id and row[1] == t:
                ws.delete_rows(i)
                break

        st.rerun()

if st.sidebar.button("🧹 Limpar lista"):
    st.session_state.watchlist = []
    st.rerun()

# ==============================
# SE NÃO HOUVER ATIVOS
# ==============================

if not st.session_state.watchlist:
    st.info("Selecione até 10 ativos na lateral.")
    st.stop()

df_user = df[df["TICKER"].isin(st.session_state.watchlist)]

# ==============================
# RESUMO
# ==============================

st.subheader("Resumo")
st.dataframe(df_user, use_container_width=True)

# ==============================
# ÍNDICES
# ==============================

@st.cache_data(ttl=300)
def load_indices():
    end = datetime.today()
    start = end - timedelta(days=15)

    ibov = yf.download("^BVSP", start=start, end=end, interval="1d", progress=False)
    ifix = yf.download("IFIX.SA", start=start, end=end, interval="1d", progress=False)

    return ibov, ifix

ibov_df, ifix_df = load_indices()

col1, col2 = st.columns([6, 1])

with col2:
    indice = st.radio("Índice", ["IBOV", "IFIX"], horizontal=True)

data = ibov_df if indice == "IBOV" else ifix_df

if not data.empty and len(data) >= 2:

   close = data["Close"]

# garante que é Series (1 coluna)
if isinstance(close, pd.DataFrame):
    close = close.iloc[:, 0]

close = close.dropna().tail(5).astype(float)

if len(close) >= 2:
    first = float(close.iloc[0])
    last = float(close.iloc[-1])
    cor = "#00cc96" if last >= first else "#ef553b"
else:
    st.warning("Dados insuficientes para gerar gráfico.")
    st.stop()

    fillcolor = "rgba(0, 204, 150, 0.15)" if cor == "#00cc96" else "rgba(239, 85, 59, 0.15)"

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=close.index,
        y=close.values,
        mode="lines+markers",
        line=dict(width=3, color=cor),
        fill="tozeroy",
        fillcolor=fillcolor
    ))

    fig.update_layout(
        height=350,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(range=[y_min, y_max]),
        xaxis=dict(showgrid=False),
        template="plotly_dark",
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Dados insuficientes para gerar gráfico.")

# ==============================
# MÉTRICAS
# ==============================

cols = st.columns(3)

for i, row in enumerate(df_user.itertuples(index=False)):
    with cols[i % 3]:

        preco = get_price(row.TICKER)
        margem = getattr(row, "MARGEM SEG.", None)

        st.metric(
            row.TICKER,
            f"R$ {preco:.2f}" if preco is not None else "Sem dados",
            f"{margem:.2f}%" if pd.notna(margem) else ""
        )













