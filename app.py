"""
Dashboard e-SUS AB — Atividades Coletivas
Município de Espinosa · MG
Lê PDFs diretamente — adicione novos PDFs na pasta 'data/' e recarregue.
"""

import re
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import pdfplumber
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Dashboard e-SUS AB · Espinosa/MG",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Pasta para os relatórios gerais
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Pasta para os relatórios filtrados (ex: apenas Práticas Corporais)
DATA1_DIR = Path(__file__).parent / "data1"
DATA1_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════
# PARSER DE PDF
# ══════════════════════════════════════════════════════════════
SECOES = [
    "Resumo de produção",
    "Número de participantes",
    "Turno",
    "Programa saúde na escola",
    "Atividade",
    "Público alvo",
    "Temas para saúde",
    "Práticas em saúde - Outros procedimentos coletivos",
    "Práticas em saúde",
    "Temas para reunião",
]

SKIP_PATTERNS = re.compile(
    r"^(Descrição\s+Quantidade|Descrição|Quantidade|Total:|Dados processados|"
    r"O resultado|Impresso|FILTROS|MINISTÉRIO|ESTADO|MUNICÍPIO|Pág\.|"
    r"Nenhum|Relatório de at|Controle social$|paz$|equipe$|território$|"
    r"e-SUS|Atenção Primária).*",
    re.IGNORECASE,
)

MES_MAP = {
    "01": ("Janeiro",   1),  "02": ("Fevereiro", 2),
    "03": ("Março",     3),  "04": ("Abril",      4),
    "05": ("Maio",      5),  "06": ("Junho",      6),
    "07": ("Julho",     7),  "08": ("Agosto",     8),
    "09": ("Setembro",  9),  "10": ("Outubro",   10),
    "11": ("Novembro", 11),  "12": ("Dezembro",  12),
}

def _extract_lines(path: str):
    lines = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            w, h = page.width, page.height
            for bbox in [(0, 0, w * 0.5, h), (w * 0.5, 0, w, h)]:
                txt = page.within_bbox(bbox).extract_text() or ""
                lines += txt.splitlines()
    return lines

def parse_pdf(path: str) -> dict:
    lines = _extract_lines(path)
    periodo = ""
    for ln in lines:
        m = re.search(r"Período:\s*(.*?)(?:\s*\||$)", ln)
        if m:
            periodo = m.group(1).strip()
            break

    mes_num = "00"
    ano = "????"
    matches_datas = re.findall(r"\d{2}/(\d{2})/(\d{4})", periodo)
    if matches_datas:
        mes_num = matches_datas[-1][0]
        ano = matches_datas[-1][1]
    else:
        matches_curto = re.findall(r"(\d{1,2})[/-](\d{4})", periodo)
        if matches_curto:
            mes_num = matches_curto[-1][0].zfill(2)
            ano = matches_curto[-1][1]

    nome, ordem = MES_MAP.get(mes_num, ("Mês inválido", 0))
    mes_label = f"{mes_num} - {nome}/{ano}"

    sections: dict[str, dict] = {}
    current = None
    pending_label = None

    for raw in lines:
        ln = raw.strip()
        if not ln or SKIP_PATTERNS.match(ln):
            continue

        matched_sec = None
        for sec in SECOES:
            if ln == sec:
                matched_sec = sec
                break

        if matched_sec:
            current = matched_sec
            sections.setdefault(current, {})
            pending_label = None
            continue

        if current is None:
            continue

        m = re.match(r"^(.+?)\s+(\d+)\s*$", ln)
        if m:
            nome_item = m.group(1).strip()
            val = int(m.group(2))
            if pending_label:
                nome_item = f"{pending_label} {nome_item}"
                pending_label = None
            sections[current][nome_item] = val
        else:
            if len(ln) > 2 and not ln.startswith("- -"):
                pending_label = ln
            else:
                pending_label = None
                
    return {
        "arquivo":   Path(path).name,
        "periodo":   periodo,
        "mes_label": mes_label,
        "mes_num":   mes_num,
        "mes_order": ordem,
        "ano":       ano,
        "sections":  sections,
    }

def load_all(data_dir: str) -> list[dict]:
    pdfs = sorted(Path(data_dir).glob("*.pdf"))
    results = []
    for p in pdfs:
        try:
            results.append(parse_pdf(str(p)))
        except Exception as e:
            st.warning(f"Erro ao ler {p.name}: {e}")
    results.sort(key=lambda x: x["mes_order"])
    return results

def sec_series(records: list[dict], section: str) -> pd.DataFrame:
    rows = []
    for r in records:
        row = {"mes_label": r["mes_label"], "mes_order": r["mes_order"]}
        row.update(r["sections"].get(section, {}))
        rows.append(row)
    df = pd.DataFrame(rows).sort_values("mes_order").reset_index(drop=True)
    return df

def totals(records: list[dict], section: str) -> pd.DataFrame:
    rows = []
    for r in records:
        rows.append(r["sections"].get(section, {}))
    df = pd.DataFrame(rows).fillna(0)
    if df.empty:
        return pd.DataFrame(columns=["Item", "Total"])
    s = df.sum().reset_index()
    s.columns = ["Item", "Total"]
    s["Total"] = s["Total"].astype(int)
    return s.sort_values("Total", ascending=False).reset_index(drop=True)

# ══════════════════════════════════════════════════════════════
# PALETA TEMA CLARO & ESTILO
# ══════════════════════════════════════════════════════════════
C = dict(
    bg       = "#ffffff",
    grid     = "#e0e0e0",
    text     = "#333333",
    accent   = "#00BCD4",
    green    = "#4CAF50",
    orange   = "#FF9800",
    purple   = "#9C27B0",
    red      = "#F44336",
)
PAL = ["#00BCD4","#4CAF50","#FF9800","#9C27B0","#F44336","#2196F3","#FF5722",
       "#00E676","#E91E63","#FFEB3B","#00ACC1","#66BB6A"]

def qlayout(fig, height=360, showlegend=True):
    fig.update_layout(
        paper_bgcolor=C["bg"], plot_bgcolor=C["bg"],
        font=dict(color=C["text"], family="Inter, sans-serif", size=12),
        height=height, showlegend=showlegend,
        legend=dict(bgcolor="rgba(255,255,255,.9)", bordercolor=C["grid"],
                    borderwidth=1, font=dict(size=11)),
        margin=dict(l=8, r=8, t=42, b=8),
        title_font=dict(size=14, color="#111111", family="Inter, sans-serif"),
    )
    fig.update_xaxes(gridcolor=C["grid"], zeroline=False, tickfont=dict(color=C["text"]))
    fig.update_yaxes(gridcolor=C["grid"], zeroline=False, tickfont=dict(color=C["text"]))
    return fig

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, .stApp { font-family: 'Inter', sans-serif !important; background-color: #ffffff !important; color: #333333 !important; }
.material-symbols-rounded, .st-icon, [data-testid='stIconMaterial'] { font-family: 'Material Symbols Rounded' !important; }
[data-testid='stSidebar'] { background-color: #f8f9fa !important; border-right: 1px solid #e0e0e0 !important; }
h1, h2, h3, h4 { color: #111111 !important; font-weight: 600 !important; font-family: 'Inter', sans-serif !important; }
.kcard { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 1.1rem 1.3rem; text-align: center; transition: transform .2s; box-shadow: 0 2px 6px rgba(0,0,0,0.04); font-family: 'Inter', sans-serif !important; }
.kcard:hover { transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.08); }
.klabel { font-size: .68rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #666666; margin-bottom: .3rem; }
.kval { font-size: 2rem; font-weight: 700; color: #111111; line-height: 1.1; }
.kdelta { font-size: .74rem; margin-top: .25rem; font-weight: 500; }
.kdelta.pos { color: #4CAF50; }
.kdelta.neg { color: #F44336; }
.kdelta.neu { color: #888888; }
.sec { font-size: 1.1rem; font-weight: 600; color: #00BCD4; letter-spacing: .02em; margin: 1.5rem 0 .6rem; padding-bottom: .3rem; border-bottom: 2px solid #f0f0f0; font-family: 'Inter', sans-serif !important; }
hr { border-color: #e0e0e0 !important; }
[data-testid='stExpander'] details { background-color: #ffffff !important; border: 1px solid #e0e0e0 !important; border-radius: 8px; }
[data-testid='stExpander'] summary { background-color: #f8f9fa !important; border-radius: 8px; color: #333333 !important; }
[data-testid='stExpander'] summary:hover { background-color: #f0f2f5 !important; }
[data-testid='stExpanderDetails'] { background-color: #ffffff !important; }
[data-testid='collapsedControl'], [data-testid='stSidebarCollapseButton'] { display: none !important; }
section[data-testid='stSidebar'] > div:first-child { padding-top: 0 !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f0f0f0; }
::-webkit-scrollbar-thumb { background: #c0c0c0; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #a0a0a0; }
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# CARREGAR DADOS
# ══════════════════════════════════════════════════════════════
records = load_all(str(DATA_DIR))
records_data1 = load_all(str(DATA1_DIR))

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:18px 0 10px">
      <div style="font-size:2.8rem">🏥</div>
      <div style="color:#00BCD4;font-size:1.1rem;font-weight:700;margin-top:6px">e-SUS AB</div>
      <div style="color:#666;font-size:.8rem;margin-top:3px">Espinosa · MG</div>
      <div style="width:50px;height:3px;background:linear-gradient(90deg,#00BCD4,#4CAF50);margin:12px auto;border-radius:2px"></div>
    </div>""", unsafe_allow_html=True)

    if not records:
        st.warning("Nenhum PDF encontrado em `data/`.")
        st.stop()

    meses = [r["mes_label"] for r in records]
    st.markdown("#### 📅 Período")
    mes_sel = st.selectbox("Mês:", meses, index=len(meses)-1, label_visibility="collapsed")
    rec = next(r for r in records if r["mes_label"] == mes_sel)

    st.markdown(f"""
    <div style="background:#ffffff;padding:12px;border-radius:8px;border:1px solid #e0e0e0;font-size:.78rem;box-shadow:0 1px 3px rgba(0,0,0,0.05)">
      <b style="color:#00BCD4">Período:</b> <span style="color:#333">{rec['periodo']}</span>
    </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 🗺️ Navegação")
    secao = st.radio("", [
        "📊 Visão Geral",
        "👥 Público-Alvo",
        "🩺 Temas de Saúde",
        "📋 Atividades",
        "🌿 Práticas em Saúde",
        "📅 Comparativo Mensal",
    ], label_visibility="collapsed")

    st.markdown("---")
    st.markdown(f"""
    <div style="text-align:center;color:#888;font-size:.7rem;padding:6px 0">
      Geral: {len(records)} mês(es) em data/<br>
      Prat. Corporais: {len(records_data1)} mês(es) em data1/
    </div>""", unsafe_allow_html=True)

idx_sel = next(i for i, r in enumerate(records) if r["mes_label"] == mes_sel)
rec_ant = records[idx_sel - 1] if idx_sel > 0 else None

# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def kpi(icon, label, value, delta_val=None, delta_ref=None):
    delta_html = ""
    if delta_val is not None and delta_ref is not None and delta_ref != 0:
        pct = (delta_val - delta_ref) / delta_ref * 100
        sig = "+" if pct >= 0 else ""
        cls = "pos" if pct >= 0 else "neg"
        arr = "▲" if pct >= 0 else "▼"
        delta_html = f'<div class="kdelta {cls}">{arr} {sig}{pct:.1f}% vs anterior</div>'
    elif delta_val is not None:
        delta_html = '<div class="kdelta neu">— sem comparativo</div>'
    return f"""
    <div class="kcard" translate="no">
      <div style="font-size:1.5rem;margin-bottom:.2rem">{icon}</div>
      <div class="klabel">{label}</div>
      <div class="kval">{value}</div>
      {delta_html}
    </div>"""

def sec_title(txt):
    st.markdown(f'<div class="sec">{txt}</div>', unsafe_allow_html=True)

def bar_h(df_in: pd.DataFrame, col_x="Total", col_y="Item", title="", h=380, top_n=None, hide_zero=True):
    df = df_in.copy()
    if hide_zero: df = df[df[col_x] > 0]
    if top_n: df = df.head(top_n)
    if df.empty: return qlayout(go.Figure(), height=h)
    
    df = df.sort_values(col_x, ascending=True)
    fig = go.Figure(go.Bar(
        x=df[col_x], y=df[col_y], orientation="h",
        marker=dict(color=df[col_x], colorscale=[[0, "#80deea"], [1, "#0097a7"]], line=dict(width=0)),
        text=df[col_x], textposition="outside",
        textfont=dict(color="#333", size=11),
        hovertemplate="%{y}: <b>%{x}</b><extra></extra>",
    ))
    fig.update_layout(title=title)
    return qlayout(fig, height=h, showlegend=False)

def bar_v(df_in: pd.DataFrame, col_x="mes_label", col_y="Total", title="", h=340, color=C["accent"]):
    if df_in.empty: return qlayout(go.Figure(), height=h)
    fig = go.Figure(go.Bar(
        x=df_in[col_x], y=df_in[col_y],
        marker_color=color, marker_line_width=0,
        text=df_in[col_y], textposition="outside",
        textfont=dict(color="#333", size=11),
        hovertemplate="%{x}: <b>%{y}</b><extra></extra>",
    ))
    fig.update_layout(title=title)
    return qlayout(fig, height=h, showlegend=False)

def donut(df_in: pd.DataFrame, col_val="Total", col_name="Item", title="", h=340):
    df = df_in[df_in[col_val] > 0].copy()
    if df.empty: return go.Figure()
    
    fig = go.Figure(go.Pie(
        labels=df[col_name], values=df[col_val],
        hole=0.52, marker_colors=PAL[:len(df)],
        textfont=dict(size=11, color="white"),
        hovertemplate="%{label}: <b>%{value}</b> (%{percent})<extra></extra>",
        textinfo="percent",
    ))
    fig.update_layout(
        title=title, height=h,
        paper_bgcolor=C["bg"], plot_bgcolor=C["bg"],
        font=dict(color=C["text"], family="Inter, sans-serif", size=12),
        margin=dict(l=8, r=8, t=42, b=8),
        legend=dict(bgcolor="rgba(255,255,255,.9)", bordercolor=C["grid"], borderwidth=1, font=dict(size=11)),
        title_font=dict(size=14, color="#111", family="Inter, sans-serif"),
        annotations=[dict(text=f"<b>{df[col_val].sum():,}</b>", x=.5, y=.5, showarrow=False, font=dict(size=18, color="#111"))],
    )
    return fig

def stacked(df_in: pd.DataFrame, cats: list, title="", h=340):
    fig = go.Figure()
    if df_in.empty: return qlayout(fig, height=h)
    for i, cat in enumerate(cats):
        if cat in df_in.columns:
            fig.add_trace(go.Bar(
                x=df_in["mes_label"], y=df_in[cat],
                name=cat, marker_color=PAL[i % len(PAL)], marker_line_width=0,
                hovertemplate=f"{cat}: <b>%{{y}}</b><extra></extra>",
            ))
    fig.update_layout(barmode="stack", title=title)
    return qlayout(fig, height=h)

def line_multi(df_in: pd.DataFrame, cats: list, title="", h=340):
    fig = go.Figure()
    if df_in.empty: return qlayout(fig, height=h)
    for i, cat in enumerate(cats):
        if cat in df_in.columns and df_in[cat].sum() > 0:
            fig.add_trace(go.Scatter(
                x=df_in["mes_label"], y=df_in[cat], name=cat,
                mode="lines+markers", line=dict(color=PAL[i % len(PAL)], width=2),
                marker=dict(size=7), hovertemplate=f"{cat}: <b>%{{y}}</b><extra></extra>",
            ))
    fig.update_layout(title=title)
    return qlayout(fig, height=h)

# ══════════════════════════════════════════════════════════════
# HEADER PRINCIPAL
# ══════════════════════════════════════════════════════════════
st.markdown(f"""
<div style="margin-bottom:1.2rem">
  <h1 style="margin:0;font-size:1.75rem;color:#111">📋 Atividades Coletivas — Atenção Primária</h1>
  <p style="color:#666;margin:.4rem 0 0;font-size:.95rem">
    Espinosa · Minas Gerais &nbsp;|&nbsp;
    <span style="color:#00BCD4;font-weight:600">{mes_sel}</span>
  </p>
</div>
<hr>
""", unsafe_allow_html=True)

def gv(section, key, r=rec):
    return r["sections"].get(section, {}).get(key, 0)

def gva(section, key):
    return rec_ant["sections"].get(section, {}).get(key, 0) if rec_ant else None

# ══════════════════════════════════════════════════════════════
# ─────────────────── SEÇÕES ──────────────────────────────────
# ══════════════════════════════════════════════════════════════

if secao == "📊 Visão Geral":
    reg   = gv("Resumo de produção", "Total de registros")
    part  = gv("Número de participantes", "Total de participantes")
    ident = gv("Número de participantes", "Participantes identificados")
    manha = gv("Turno", "Manhã")
    noite = gv("Turno", "Noite")

    cols = st.columns(5)
    for col, html in zip(cols, [
        kpi("📋", "Total de Registros", f"{reg:,}", reg, gva("Resumo de produção","Total de registros")),
        kpi("👥", "Total Participantes", f"{part:,}", part, gva("Número de participantes","Total de participantes")),
        kpi("🎯", "Identificados", f"{ident:,}"),
        kpi("🌅", "Turnos Manhã", f"{manha:,}"),
        kpi("🌙", "Turnos Noite", f"{noite:,}"),
    ]):
        col.markdown(html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    sec_title("Distribuição por Turno e Tipo de Atividade")
    c1, c2 = st.columns(2)

    with c1:
        turnos = rec["sections"].get("Turno", {})
        df_t = pd.DataFrame([{"Item": k, "Total": v} for k, v in turnos.items() if k != "Não informado" and v > 0])
        if not df_t.empty:
            st.plotly_chart(donut(df_t, title="🕐 Turnos"), use_container_width=True)

    with c2:
        df_at = totals([rec], "Atividade")
        if not df_at.empty:
            df_at = df_at[df_at["Item"] != "Não informado"]
            st.plotly_chart(bar_h(df_at, title="⚡ Atividades Realizadas", h=360), use_container_width=True)

    sec_title("Programa Saúde na Escola · Temas de Reunião")
    c3, c4 = st.columns(2)

    with c3:
        df_pse = totals([rec], "Programa saúde na escola")
        st.plotly_chart(donut(df_pse, title="🏫 Saúde na Escola"), use_container_width=True)

    with c4:
        df_reu = totals([rec], "Temas para reunião")
        if not df_reu.empty:
            df_reu = df_reu[df_reu["Item"] != "Não informado"]
            st.plotly_chart(bar_h(df_reu, title="🤝 Temas de Reunião", h=360), use_container_width=True)

elif secao == "👥 Público-Alvo":
    df_pub = totals([rec], "Público alvo")
    if not df_pub.empty:
        df_pub = df_pub[df_pub["Item"] != "Não informado"]

    sec_title("Distribuição do Público-Alvo")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(bar_h(df_pub, title="👥 Público-Alvo — Quantidade", h=500), use_container_width=True)
    with c2:
        st.plotly_chart(donut(df_pub, title="📊 Proporção", h=500), use_container_width=True)

    sec_title("Destaques")
    if not df_pub.empty:
        df_top = df_pub[df_pub["Total"] > 0].head(3)
        cols = st.columns(len(df_top))
        for col, (_, row) in zip(cols, df_top.iterrows()):
            col.markdown(kpi("🎯", row["Item"], f"{row['Total']:,}"), unsafe_allow_html=True)

elif secao == "🩺 Temas de Saúde":
    df_temas = totals([rec], "Temas para saúde")
    if not df_temas.empty:
        df_temas = df_temas[~df_temas["Item"].isin(["Outros", "Não informado"])]

    sec_title("Temas para Saúde")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(bar_h(df_temas, title="🩺 Temas — Barras", h=500), use_container_width=True)
    with c2:
        st.plotly_chart(donut(df_temas, title="📊 Proporção", h=500), use_container_width=True)

    with st.expander("📋 Ver tabela completa"):
        df_show = totals([rec], "Temas para saúde").sort_values("Total", ascending=False)
        st.dataframe(df_show, use_container_width=True, hide_index=True)

elif secao == "📋 Atividades":
    sec_title("Tipos de Atividade Realizada")
    df_at_raw = totals([rec], "Atividade")
    total_at = df_at_raw["Total"].sum() if not df_at_raw.empty else 0
    
    df_at = df_at_raw.copy()
    if not df_at.empty:
        df_at = df_at[df_at["Item"] != "Não informado"]

    c1, c2 = st.columns([3, 2])
    with c1:
        fig = go.Figure(go.Bar(
            x=df_at["Item"], y=df_at["Total"],
            marker=dict(color=PAL[:len(df_at)], line=dict(width=0)),
            text=df_at["Total"], textposition="outside",
            textfont=dict(color="#333", size=11),
            hovertemplate="%{x}: <b>%{y}</b><extra></extra>",
        ))
        fig.update_layout(title="📋 Tipos de Atividade", xaxis_tickangle=-25)
        st.plotly_chart(qlayout(fig, height=420, showlegend=False), use_container_width=True)
    with c2:
        st.plotly_chart(donut(df_at, title="📊 Distribuição (%)"), use_container_width=True)

    sec_title("Temas para Reunião")
    df_reu_raw = totals([rec], "Temas para reunião")
    total_reu = df_reu_raw["Total"].sum() if not df_reu_raw.empty else 0
    
    df_reu = df_reu_raw.copy()
    if not df_reu.empty:
        df_reu = df_reu[df_reu["Item"] != "Não informado"]

    c3, c4 = st.columns([3, 2])
    with c3:
        st.plotly_chart(bar_h(df_reu, title="🤝 Temas de Reunião", h=360), use_container_width=True)
    with c4:
        top_reu = df_reu.iloc[0]["Item"] if not df_reu.empty else "—"
        st.markdown(f"""
        <div style="padding:1rem 0">
          {kpi("🤝", "Total de Reuniões", f"{total_reu:,}")}
          <div style="height:12px"></div>
          {kpi("🏆", "Tema mais frequente", top_reu)}
        </div>""", unsafe_allow_html=True)

elif secao == "🌿 Práticas em Saúde":
    sec_title("Práticas em Saúde Realizadas")
    
    # 1. Pega os dados totais brutos (com o 'Não informado') para calcular a soma exata igual ao PDF.
    df_pr_raw = totals([rec], "Práticas em saúde")
    total_pr = df_pr_raw["Total"].sum() if not df_pr_raw.empty else 0
    
    # 2. Faz uma cópia limpa apenas para não poluir os gráficos
    df_pr = df_pr_raw.copy()
    if not df_pr.empty:
        df_pr = df_pr[~df_pr["Item"].str.startswith("PNCT")]
        df_pr = df_pr[df_pr["Item"] != "Não informado"]

    top_pr = df_pr.iloc[0]["Item"] if not df_pr.empty else "—"

    rec1 = next((r for r in records_data1 if r["mes_label"] == mes_sel), None)
    part_corp = rec1["sections"].get("Número de participantes", {}).get("Total de participantes", 0) if rec1 else 0
        
    rec1_ant = None
    if rec_ant:
        rec1_ant = next((r for r in records_data1 if r["mes_label"] == rec_ant["mes_label"]), None)
    part_corp_ant = rec1_ant["sections"].get("Número de participantes", {}).get("Total de participantes", 0) if rec1_ant else None

    col1, col2, col3 = st.columns(3)
    col1.markdown(kpi("🌿", "Total de Práticas", f"{total_pr:,}"), unsafe_allow_html=True)
    col2.markdown(kpi("🏆", "Prática mais frequente", top_pr), unsafe_allow_html=True)
    col3.markdown(kpi("🤸", "Participantes (Prát. Corporais)", f"{part_corp:,}", part_corp, part_corp_ant), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(bar_h(df_pr, title="🌿 Práticas — Ranking", h=480), use_container_width=True)
    with c2:
        st.plotly_chart(donut(df_pr, title="📊 Proporção (Top Práticas)", h=480), use_container_width=True)

    with st.expander("📋 Ver todas as práticas"):
        st.dataframe(df_pr_raw, use_container_width=True, hide_index=True)

elif secao == "📅 Comparativo Mensal":
    if len(records) < 2:
        st.info("Adicione pelo menos 2 meses de dados para ver o comparativo.")
        st.stop()

    sec_title("Totais Acumulados — Todos os Meses")
    tot_reg  = sum(r["sections"].get("Resumo de produção",{}).get("Total de registros", 0) for r in records)
    tot_part = sum(r["sections"].get("Número de participantes",{}).get("Total de participantes",0) for r in records)
    tot_ident= sum(r["sections"].get("Número de participantes",{}).get("Participantes identificados",0) for r in records)
    cols = st.columns(4)
    for col, html in zip(cols, [
        kpi("📋", "Registros Totais", f"{tot_reg:,}"),
        kpi("👥", "Participantes Totais", f"{tot_part:,}"),
        kpi("🎯", "Identificados Totais", f"{tot_ident:,}"),
        kpi("📅", "Meses Analisados", str(len(records))),
    ]):
        col.markdown(html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    sec_title("Evolução de Registros e Participantes")
    df_ev = sec_series(records, "Resumo de produção")
    df_pa = sec_series(records, "Número de participantes")

    c1, c2 = st.columns(2)
    with c1:
        if "Total de registros" in df_ev.columns:
            st.plotly_chart(bar_v(
                df_ev.rename(columns={"Total de registros": "Total"}),
                title="📋 Registros por Mês", h=320, color=C["accent"],
            ), use_container_width=True)
    with c2:
        fig = go.Figure()
        for col_n, color, dash in [
            ("Total de participantes",   C["green"],  "solid"),
            ("Participantes identificados", C["accent"], "dot"),
        ]:
            if col_n in df_pa.columns:
                fig.add_trace(go.Scatter(
                    x=df_pa["mes_label"], y=df_pa[col_n], name=col_n,
                    mode="lines+markers", line=dict(color=color, width=2.5, dash=dash), marker=dict(size=8),
                ))
        fig.update_layout(title="👥 Participantes por Mês")
        st.plotly_chart(qlayout(fig, height=320), use_container_width=True)

    sec_title("Distribuição de Turnos ao Longo dos Meses")
    df_tu = sec_series(records, "Turno")
    st.plotly_chart(stacked(df_tu, ["Manhã", "Tarde", "Noite"], title="🌅 Turnos por Mês", h=320), use_container_width=True)

    sec_title("Tipos de Atividade por Mês")
    df_at_ev = sec_series(records, "Atividade")
    ativ_cats = ["Atendimento em grupo", "Educação em saúde", "Reunião de equipe",
                 "Avaliação / Procedimento coletivo", "Mobilização social", "Reunião com outras equipes de saúde"]
    st.plotly_chart(stacked(df_at_ev, ativ_cats, title="📋 Atividades por Mês", h=360), use_container_width=True)

    sec_title("Práticas Corporais e Atividade Física — Evolução")
    df_pc = sec_series(records, "Práticas em saúde")
    if "Práticas corporais e atividade física" in df_pc.columns:
        fig_pc = go.Figure()
        fig_pc.add_trace(go.Bar(
            x=df_pc["mes_label"], y=df_pc["Práticas corporais e atividade física"],
            marker_color=C["green"], marker_line_width=0,
            text=df_pc["Práticas corporais e atividade física"], textposition="outside", textfont=dict(color="#333"),
            name="Práticas Corporais (Eventos)",
        ))
        fig_pc.add_trace(go.Scatter(
            x=df_pc["mes_label"], y=df_pc["Práticas corporais e atividade física"],
            mode="lines+markers", line=dict(color="#00E676", width=2), marker=dict(size=8), name="Tendência",
        ))
        fig_pc.update_layout(title="🤸 Práticas Corporais (Eventos) por Mês")
        st.plotly_chart(qlayout(fig_pc, height=320), use_container_width=True)

    sec_title("Evolução do Público-Alvo")
    df_pub_ev = sec_series(records, "Público alvo")
    pub_cats = ["Mulher", "Pessoa idosa", "Adolescente", "Pessoas com doenças crônicas", "Comunidade em geral", "Homem"]
    st.plotly_chart(line_multi(df_pub_ev, pub_cats, title="👥 Público-Alvo por Mês", h=360), use_container_width=True)

    # =========================================================================
    # TABELA RESUMO EXPLICADA DE FORMA CLARA COM OS TOTAIS EXATOS DO PDF
    # =========================================================================
    sec_title("Tabela Resumo Comparativa")
    
    st.markdown("""
    <div style="background-color: #f8f9fa; border-left: 4px solid #00BCD4; padding: 12px; margin-bottom: 15px; border-radius: 4px; font-size: 0.95rem; color: #444;">
        <b>💡 Entenda os dados desta tabela:</b><br>
        • <b>Qtd. Fichas Registradas:</b> Total de formulários de atividades lançados no sistema e-SUS.<br>
        • <b>Total de Participantes:</b> Soma de todas as pessoas presentes nessas ações.<br>
        • <b>Tipos de Atividades Realizadas:</b> Somatório total da seção de atividades (ex: palestras, avaliações, reuniões).<br>
        • <b>Práticas Aplicadas:</b> Somatório total da seção de práticas de saúde (ex: escovação, exercícios, etc).
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📊 Abrir tabela mensal detalhada"):
        rows = []
        for r in records:
            sec_ativ = r["sections"].get("Atividade", {})
            sec_prat = r["sections"].get("Práticas em saúde", {})
            rows.append({
                "Mês / Período":                 r["mes_label"],
                "Qtd. Fichas Registradas":       r["sections"].get("Resumo de produção",{}).get("Total de registros",0),
                "Total de Participantes":        r["sections"].get("Número de participantes",{}).get("Total de participantes",0),
                # A soma aqui não tem mais nenhum filtro ("Não informado" entra na conta), batendo perfeitamente com o rodapé do PDF.
                "Tipos de Atividades Realizadas": sum(sec_ativ.values()),
                "Práticas Aplicadas":            sum(sec_prat.values()),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════
st.markdown(f"""
<hr>
<div style="text-align:center;color:#888;font-size:.75rem;padding:.5rem 0">
  Dashboard e-SUS AB · Espinosa · Minas Gerais &nbsp;|&nbsp;
  Atualizado em {datetime.now().strftime("%d/%m/%Y %H:%M")}
</div>
""", unsafe_allow_html=True)