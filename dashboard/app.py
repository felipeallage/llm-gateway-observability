"""Streamlit dashboard for the LLM gateway observability log.

Run with: streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

import db

st.set_page_config(page_title="LLM Gateway Observatory", layout="wide")
st.title("🔭 LLM Gateway Observatory")
st.caption("Custo, latência e uso de tokens por modelo, logados a partir de um gateway multi-LLM (AIsa).")

rows = db.fetch_all()
if not rows:
    st.info(
        "Nenhuma chamada registrada ainda. Rode:\n\n"
        "`python demo/compare_models.py --prompt \"...\" --models gpt-5-nano deepseek-v4-flash --yes`"
    )
    st.stop()

df = pd.DataFrame([dict(r) for r in rows])
df["ts"] = pd.to_datetime(df["ts"])

with st.sidebar:
    st.header("Filtros")
    models = st.multiselect("Modelo", sorted(df["model"].unique()), default=list(df["model"].unique()))
    run_tags = st.multiselect("Run tag", sorted(df["run_tag"].dropna().unique()), default=list(df["run_tag"].dropna().unique()))

fdf = df[df["model"].isin(models)]
if run_tags:
    fdf = fdf[fdf["run_tag"].isin(run_tags)]

col1, col2, col3, col4 = st.columns(4)
known_cost = fdf.loc[fdf["cost_status"] == "known", "cost_usd"].sum()
unknown_count = (fdf["cost_status"] == "unknown_price").sum()
error_count = (fdf["status"] == "error").sum()

col1.metric("Chamadas registradas", len(fdf))
col2.metric("Custo total conhecido (USD)", f"${known_cost:.4f}")
col3.metric("Chamadas com preço desconhecido", int(unknown_count))
col4.metric("Erros", int(error_count))

if unknown_count > 0:
    st.warning(
        f"{unknown_count} chamada(s) usaram modelo(s) sem preço verificado em pricing.json — "
        "custo real dessas chamadas NÃO está incluído no total acima. Veja known_data_quality_issue "
        "em pricing.json."
    )

st.subheader("Custo por modelo")
cost_by_model = fdf[fdf["cost_status"] == "known"].groupby("model", as_index=False)["cost_usd"].sum()
if not cost_by_model.empty:
    st.plotly_chart(px.bar(cost_by_model, x="model", y="cost_usd", labels={"cost_usd": "USD"}), use_container_width=True)
else:
    st.caption("Sem chamadas com preço conhecido ainda.")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Latência por modelo")
    st.plotly_chart(
        px.box(fdf, x="model", y="latency_ms", points="all", labels={"latency_ms": "ms"}),
        use_container_width=True,
    )
with col_b:
    st.subheader("Tokens por chamada")
    st.plotly_chart(
        px.scatter(fdf, x="prompt_tokens", y="completion_tokens", color="model", hover_data=["ts", "run_tag"]),
        use_container_width=True,
    )

st.subheader("Custo ao longo do tempo (acumulado)")
timeline = fdf[fdf["cost_status"] == "known"].sort_values("ts").copy()
if not timeline.empty:
    timeline["cumulative_cost"] = timeline["cost_usd"].cumsum()
    st.plotly_chart(px.line(timeline, x="ts", y="cumulative_cost", labels={"cumulative_cost": "USD acumulado"}), use_container_width=True)

st.subheader("Log bruto")
st.dataframe(fdf.sort_values("ts", ascending=False), use_container_width=True)
