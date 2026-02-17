import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials


st.set_page_config(page_title="Monitor de Ativos", layout="wide")

# Leitura da planilha
SHEET_ID = "1bNKnU-HzvB--KfREcXJAmxtvtEOuqDmeFo59QGJX0hw"
GID = "0"

CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}"

MAX_ATIVOS = 10

@st.cache_resource
def get_gspread_client():
    sa_info = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    return gspread.authorize(creds)

def get_watchlist_sheet():
    gc = get_gspread_client()
    sh = gc.open_by_key(SHEET_ID)
    return sh.worksheet("watchlist")

user_id = st.sidebar.text_input("Digite seu e-mail para salvar sua lista")


@st.cache_data(ttl=300)
def load_sheet():
    try:
        df = pd.read_csv(CSV_URL, engine="python", sep=";", on_bad_lines="skip")
    except:
        df = pd.read_csv(CSV_URL, engine="python", sep=",", on_bad_lines="skip")

    # normaliza os nomes das colunas
    df.columns = df.columns.astype(str).str.strip().str.upper()

    # valida se existe a coluna ticker
    if "TICKER" not in df.columns:
        st.error("Coluna TICKER não encontrada. Colunas detectadas:")
        st.write(df.columns.tolist())
        st.stop()

    df["TICKER"] = df["TICKER"].astype(str).str.upper().str.strip()

    return df


if "watchlist" not in st.session_state:
    st.session_state.watchlist = []


st.title("📈 Monitor de Ativos")

df = load_sheet()

if user_id:
    ws = get_watchlist_sheet()
    data = ws.get_all_records()

    user_saved = [row["TICKER"] for row in data if row["USER_ID"] == user_id]
    st.session_state.watchlist = user_saved


st.sidebar.header("Escolha seus ativos")
st.sidebar.caption(f"{len(st.session_state.watchlist)}/{MAX_ATIVOS} ativos")

tickers = sorted(df["TICKER"].dropna().unique())

selected = st.sidebar.selectbox("Selecione um ativo", tickers)

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

st.sidebar.markdown("---")
st.sidebar.subheader("Minha lista")

for t in st.session_state.watchlist:
    c1, c2 = st.sidebar.columns([4,1])
    c1.write(t)
    if c2.button("❌", key=f"del_{t}"):
    st.session_state.watchlist.remove(t)

    ws = get_watchlist_sheet()
    records = ws.get_all_records()
    for i, row in enumerate(records, start=2):
        if row["USER_ID"] == user_id and row["TICKER"] == t:
            ws.delete_rows(i)
            break

    st.rerun()

if st.sidebar.button("🧹 Limpar lista"):
    st.session_state.watchlist = []
    st.rerun()


if not st.session_state.watchlist:
    st.info("Selecione até 10 ativos na lateral.")
    st.stop()


df_user = df[df["TICKER"].isin(st.session_state.watchlist)]

st.subheader("Resumo")
st.dataframe(df_user, use_container_width=True)

st.subheader("📊 Índices de Mercado")

@st.cache_data(ttl=300)
def load_indices():
    end = datetime.today()
    start = end - timedelta(days=15)  # pega dias suficientes para 5 pregões

    ibov = yf.download("^BVSP", start=start, end=end, interval="1d")
    ifix = yf.download("IFIX.SA", start=start, end=end, interval="1d")

    return ibov, ifix


ibov_df, ifix_df = load_indices()

col1, col2 = st.columns([6, 1])

with col2:
    indice = st.radio("Índice", ["IBOV", "IFIX"], horizontal=True)

data = ibov_df if indice == "IBOV" else ifix_df

if not data.empty and len(data) >= 2:

    close = data["Close"].dropna().tail(5).astype(float)


    # remove horário do eixo X
    close.index = close.index.date

    # ajuste fino da escala
    y_min = close.min() * 0.998
    y_max = close.max() * 1.002

    cor = "#00cc96" if float(close.iloc[-1]) >= float(close.iloc[0]) else "#ef553b"


    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=close.index,
        y=close.values,
        mode="lines+markers",
        line=dict(width=3, color=cor),
        fill="tozeroy",
        fillcolor=cor.replace(")", ",0.15)").replace("rgb", "rgba")
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

cols = st.columns(3)  # 👈 ESSA LINHA É OBRIGATÓRIA

for i, row in enumerate(df_user.itertuples(index=False)):
    with cols[i % 3]:
        preco = getattr(row, "Preço Atual", None)
        margem = getattr(row, "Margem Seg.", None)

        st.metric(
            row.TICKER,
            f"R$ {preco}" if preco else "Sem dados",
            f"{margem}%" if margem else ""
        )











