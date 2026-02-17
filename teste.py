import streamlit as st
import pandas as pd

st.set_page_config(page_title="Monitor B3", layout="wide")

# 🔹 Cole aqui o ID da sua planilha
SHEET_ID = "COLE_AQUI_O_ID"
GID = "0"  # mude se necessário

CSV_URL = f"https://docs.google.com/spreadsheets/d/1bNKnU-HzvB--KfREcXJAmxtvtEOuqDmeFo59QGJX0hw/edit?usp=sharing{GID}"

MAX_ATIVOS = 10



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


st.title("📈 Monitor B3 (Google Sheets)")

df = load_sheet()

st.sidebar.header("Escolha seus ativos")
st.sidebar.caption(f"{len(st.session_state.watchlist)}/{MAX_ATIVOS} ativos")

tickers = sorted(df["TICKER"].dropna().unique())

selected = st.sidebar.selectbox("Selecione um ativo", tickers)

if st.sidebar.button("➕ Adicionar"):
    if selected in st.session_state.watchlist:
        st.sidebar.info("Já está na lista.")
    elif len(st.session_state.watchlist) >= MAX_ATIVOS:
        st.sidebar.error("Limite de 10 ativos atingido.")
    else:
        st.session_state.watchlist.append(selected)
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Minha lista")

for t in st.session_state.watchlist:
    c1, c2 = st.sidebar.columns([4,1])
    c1.write(t)
    if c2.button("❌", key=f"del_{t}"):
        st.session_state.watchlist.remove(t)
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


st.subheader("Cards rápidos")
cols = st.columns(3)

for i, row in enumerate(df_user.itertuples(index=False)):
    with cols[i % 3]:
        preco = getattr(row, "Preço Atual", None)
        margem = getattr(row, "Margem Seg.", None)

        st.metric(
            row.TICKER,
            f"R$ {preco}" if preco else "Sem dados",
            f"{margem}%" if margem else ""
        )



