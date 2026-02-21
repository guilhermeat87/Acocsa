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
def get_price_and_change(ticker: str):
    """
    Retorna (preco_atual, delta_reais, delta_percentual)
    delta baseado no fechamento anterior (mais estável).
    """
    t = yf.Ticker(ticker + ".SA")
    try:
        info = t.fast_info  # mais rápido quando disponível
        last = float(info["last_price"])
        prev = float(info["previous_close"])
        delta = last - prev
        delta_pct = (delta / prev) * 100 if prev else 0.0
        return last, delta, delta_pct
    except Exception:
        # fallback
        try:
            hist = t.history(period="5d", interval="1d")
            if hist.empty or "Close" not in hist:
                return None, None, None

            last_close = float(hist["Close"].dropna().iloc[-1])
            prev_close = float(hist["Close"].dropna().iloc[-2]) if len(hist["Close"].dropna()) >= 2 else last_close
            delta = last_close - prev_close
            delta_pct = (delta / prev_close) * 100 if prev_close else 0.0
            return last_close, delta, delta_pct
        except Exception:
            return None, None, None
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

#st.subheader("Resumo")
#st.dataframe(df_user, use_container_width=True)

# ==============================
# ÍNDICES
# ==============================

st.subheader("📊 Índices de Mercado")

@st.cache_data(ttl=300)
def load_indices():
    end = datetime.today()
    start = end - timedelta(days=30)  # mais folga

    ibov = yf.download("^BVSP", start=start, end=end, interval="1d", progress=False)
    ifix = yf.download("IFIX.SA", start=start, end=end, interval="1d", progress=False)

    return ibov, ifix

ibov_df, ifix_df = load_indices()

col1, col2 = st.columns([6, 1])
with col2:
    indice = st.radio("Índice", ["IBOV", "IFIX"], horizontal=True)

data = ibov_df if indice == "IBOV" else ifix_df

# achata colunas multiindex (às vezes o yfinance devolve assim)
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

if data.empty or "Close" not in data.columns:
    st.warning("Sem dados para o índice selecionado.")
    st.stop()

close = data["Close"]

# Se por algum motivo vier como DataFrame, pega só a 1ª coluna
if isinstance(close, pd.DataFrame):
    close = close.iloc[:, 0]

close = close.dropna().tail(5).astype(float)

if len(close) < 2:
    st.warning("Dados insuficientes para gerar gráfico.")
    st.stop()

# eixo X sem horário
close.index = close.index.date

y_min = close.min() * 0.998
y_max = close.max() * 1.002

first = float(close.iloc[0])
last = float(close.iloc[-1])

cor = "#00cc96" if last >= first else "#ef553b"
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

# ==============================
# MÉTRICAS
# ==============================

cols = st.columns(3)

for i, row in enumerate(df_user.itertuples(index=False)):
    with cols[i % 3]:
        preco, delta, delta_pct = get_price_and_change(row.TICKER)

        if preco is None:
            st.metric(row.TICKER, "Sem dados", "")
            continue

        delta_txt = f"R$ {delta:+.2f} ({delta_pct:+.2f}%)" if delta is not None else ""

        st.metric(
            row.TICKER,
            f"R$ {preco:.2f}",
            delta_txt
        )























