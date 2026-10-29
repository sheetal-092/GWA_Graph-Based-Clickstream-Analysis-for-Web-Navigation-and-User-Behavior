"""WebGraph Analytics - Graph-Based Clickstream Analysis for Web Navigation and User Behavior.

Run with:  streamlit run app.py

Every number on the dashboard is computed from the loaded dataset: the bundled
25,000-row clickstream file in ./data, or any CSV / Excel file uploaded from the
sidebar. Nothing is hard-coded.
"""
from __future__ import annotations

import io
import math
import re
from itertools import islice
from pathlib import Path
from types import SimpleNamespace

import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="WebGraph Analytics", page_icon="🕸️", layout="wide")

APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATASETS = [
    APP_DIR / "data" / "web_clickstream_25000_rows.xlsx",
    APP_DIR / "web_clickstream_25000_rows.xlsx",
    APP_DIR.parent / "web_clickstream_25000_rows.xlsx",
]

# Validated categorical palette (fixed order, never cycled) and a one-hue sequential ramp.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
BLUE_SCALE = [[0.0, "#cde2fb"], [0.5, "#3987e5"], [1.0, "#0d366b"]]
ACCENT, HIGHLIGHT, OTHER, GRID, INK, INK_2 = "#2a78d6", "#eb6834", "#a3a29c", "#ecebe7", "#0b0b0b", "#52514e"

SECTIONS = [
    "Overview", "Dataset", "Navigation Graph", "Dijkstra / Navigation Path",
    "Centrality Analysis", "PageRank", "Community Detection", "Web Analytics",
    "User Behavior", "Results / Insights",
]
SECTION_ICONS = ["🏠", "🗂️", "🕸️", "🧭", "🎯", "⭐", "🧩", "📊", "👤", "💡"]

CORE_ROLES = {
    "page": ("Webpage column", ["page_name", "page", "page_title", "pagename", "screen_name", "page_path", "page_url", "url"]),
    "user": ("User ID column", ["user_id", "userid", "user", "visitor_id", "customer_id", "client_id"]),
    "session": ("Session ID column", ["user_session", "session_id", "session", "sessionid", "visit_id"]),
    "time": ("Timestamp column", ["event_time", "timestamp", "event_timestamp", "datetime", "time", "date"]),
}
OPTIONAL_ROLES = {
    "event_type": ("Event type", ["event_type", "event", "event_name", "action"]),
    "traffic_source": ("Traffic source", ["traffic_source", "source", "utm_source", "channel", "referrer"]),
    "device": ("Device", ["device", "device_type", "device_category"]),
    "country": ("Country", ["country", "geo_country", "region"]),
    "browser": ("Browser", ["browser"]),
    "campaign": ("Campaign", ["campaign", "utm_campaign"]),
    "category": ("Product category", ["category", "product_category"]),
    "search_keyword": ("Search keyword", ["search_keyword", "keyword", "search_term", "query"]),
    "conversion": ("Conversion flag", ["conversion", "converted", "is_conversion"]),
    "session_duration": ("Session duration (sec)", ["session_duration_sec", "session_duration", "duration_sec", "duration"]),
    "pages_in_session": ("Pages in session", ["pages_in_session", "session_pages", "page_count"]),
}
NONE = "(none)"

JOURNEY_MODES = {
    "session_user": "Session (user + session id)",
    "session": "Session (session id only)",
    "user": "User journey (all events of a user, by time)",
}
COST_OPTIONS = {
    "cost_logp": "−log(transition probability)  — most likely route",
    "cost_inverse": "1 / transition count  — most travelled links",
}
FUNNEL_DEFAULT = ["Home", "Products", "Product_Details", "Cart", "Checkout", "Payment", "Order_Confirmation"]


# --------------------------------------------------------------------------- styling
st.markdown(
    """
<style>
.block-container {padding-top: 3.6rem; padding-bottom: 3rem; max-width: 1440px;}
.wg-hero {padding: 26px 30px; border-radius: 16px; margin-bottom: 18px; color: #fff;
          background: linear-gradient(135deg, #0d366b 0%, #1c5cab 55%, #2a78d6 100%);}
.wg-hero.compact {padding: 14px 22px;}
.wg-hero h1 {margin: 0; font-size: 2.2rem; color: #fff; letter-spacing: -0.5px; line-height: 1.15;}
.wg-hero.compact h1 {font-size: 1.35rem;}
.wg-hero p {margin: 6px 0 0; color: #dbe8fb; font-size: 1.02rem;}
.wg-kicker {text-transform: uppercase; letter-spacing: 1.4px; font-size: .74rem; color: #b7d3f6; margin-bottom: 4px;}
div[data-testid="stMetric"] {background: #ffffff; border: 1px solid #e6e5e0; border-radius: 12px; padding: 12px 16px;}
div[data-testid="stMetricLabel"] p {color: #52514e; font-size: .82rem;}
.wg-path {display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 6px 0 14px;}
.wg-chip {background: #ffffff; border: 1.5px solid #2a78d6; color: #0d366b; padding: 6px 12px;
          border-radius: 999px; font-weight: 600; font-size: .95rem;}
.wg-chip.end {background: #2a78d6; color: #fff;}
.wg-arrow {color: #eb6834; font-weight: 700;}
.wg-card {background: #fff; border: 1px solid #e6e5e0; border-radius: 12px; padding: 14px 18px; margin-bottom: 10px;}
.wg-card b {color: #0d366b;}
.wg-card .k {font-size: .75rem; text-transform: uppercase; letter-spacing: 1px; color: #52514e;}
</style>
""",
    unsafe_allow_html=True,
)


def hero(section: str) -> None:
    compact = section != "Overview"
    st.markdown(
        f'<div class="wg-hero{" compact" if compact else ""}">'
        f'<div class="wg-kicker">{"Graph-Based Clickstream Analysis" if not compact else section}</div>'
        f"<h1>WebGraph Analytics</h1>"
        f"<p>Clickstream Navigation • Graph Analysis • Centrality Insights</p></div>",
        unsafe_allow_html=True,
    )


def show(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def table(frame: pd.DataFrame, height: int | None = None, **kwargs) -> None:
    if height is None:
        height = min(36 * (len(frame) + 1) + 4, 460)
    st.dataframe(frame, hide_index=True, width="stretch", height=height, **kwargs)


def style(fig: go.Figure, title: str | None = None, height: int = 380, legend: bool = False) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height, showlegend=legend, colorway=PALETTE,
        margin=dict(l=8, r=16, t=48 if title else 16, b=56 if legend else 8),
        font=dict(family="Segoe UI, Inter, Arial, sans-serif", size=12, color=INK_2),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white", font_size=12, bordercolor=GRID),
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0, title=None),
        bargap=0.35,
    )
    if title:
        fig.update_layout(title=dict(text=title, x=0, xanchor="left", font=dict(size=15, color=INK)))
    try:
        fig.update_layout(barcornerradius=4)
    except ValueError:  # older plotly
        pass
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


def hbar(labels, values, title: str, value_label: str = "Count", fmt: str = ",.0f",
         color: str = ACCENT, height: int | None = None) -> go.Figure:
    data = pd.DataFrame({"label": [str(x) for x in labels], "value": list(values)}).sort_values("value")
    fig = go.Figure(go.Bar(
        x=data["value"], y=data["label"], orientation="h", marker_color=color,
        hovertemplate=f"<b>%{{y}}</b><br>{value_label}: %{{x:{fmt}}}<extra></extra>",
    ))
    fig.update_xaxes(title=value_label, tickformat=fmt if "%" in fmt else None)
    fig.update_yaxes(showgrid=False)
    return style(fig, title, height or max(260, 24 * len(data) + 90))


def count_bar(series: pd.Series, title: str, top: int = 15) -> go.Figure:
    vc = series.dropna().astype(str).value_counts().head(top)
    return hbar(vc.index, vc.values, title)


# --------------------------------------------------------------------------- data loading
def norm(name) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def detect(columns, candidates, taken=()) -> str | None:
    lookup = {}
    for c in columns:
        lookup.setdefault(norm(c), c)
    for cand in candidates:
        col = lookup.get(cand)
        if col is not None and col not in taken:
            return col
    return None


@st.cache_data(show_spinner="Reading dataset…")
def read_table(raw: bytes, name: str) -> pd.DataFrame:
    buf = io.BytesIO(raw)
    lower = name.lower()
    if lower.endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(buf)
    else:
        sep = "\t" if lower.endswith((".tsv", ".tab")) else None
        try:
            df = pd.read_csv(buf, sep=sep, engine="python" if sep is None else "c")
        except UnicodeDecodeError:
            buf.seek(0)
            df = pd.read_csv(buf, sep=sep, engine="python" if sep is None else "c", encoding="latin-1")
    df.columns = [str(c).strip() for c in df.columns]
    return df


@st.cache_data(show_spinner="Preparing clickstream…")
def prepare(df: pd.DataFrame, page: str, time: str | None) -> pd.DataFrame:
    d = df.copy()
    d["_row"] = np.arange(len(d))
    d = d[d[page].notna()].copy()
    d["_page"] = d[page].astype(str).str.strip()
    d = d[d["_page"] != ""]
    if time:
        try:
            d["_time"] = pd.to_datetime(d[time], errors="coerce", format="mixed")
        except (TypeError, ValueError):
            d["_time"] = pd.to_datetime(d[time], errors="coerce")
    else:
        d["_time"] = pd.NaT
    return d


def conversion_flags(series: pd.Series) -> pd.Series:
    num = pd.to_numeric(series, errors="coerce")
    if num.notna().mean() > 0.5:
        return (num.fillna(0) > 0).astype(int)
    truthy = {"1", "yes", "y", "true", "converted", "purchase", "purchased"}
    return series.astype(str).str.strip().str.lower().isin(truthy).astype(int)


# --------------------------------------------------------------------------- journeys & graph
@st.cache_data(show_spinner="Ordering page navigation…")
def build_journeys(d: pd.DataFrame, keys: tuple, use_time: bool, collapse: bool, keep: tuple) -> pd.DataFrame:
    """Order page views inside each journey (session or user) and attach the next page."""
    keys = list(keys)
    extra = [c for c in keep if c not in keys]
    s = d.dropna(subset=keys) if keys else d
    s = s.sort_values(keys + (["_time"] if use_time else []) + ["_row"], kind="mergesort")
    s = s[keys + extra + ["_row", "_time", "_page"]].copy()
    s["_journey"] = s.groupby(keys, sort=False).ngroup().to_numpy() if keys else 0
    if collapse:  # a reload / repeated event on the same page is not a navigation
        prev = s.groupby("_journey", sort=False)["_page"].shift()
        s = s[~s["_page"].eq(prev).fillna(False).astype(bool)]
    grouped = s.groupby("_journey", sort=False)
    s["_step"] = grouped.cumcount()
    s["_next"] = grouped["_page"].shift(-1)
    s["_len"] = grouped["_page"].transform("size")
    return s.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def edge_table(j: pd.DataFrame) -> pd.DataFrame:
    t = j.dropna(subset=["_next"])
    e = (t.groupby(["_page", "_next"]).size().reset_index(name="weight")
         .rename(columns={"_page": "source", "_next": "target"}))
    e["probability"] = e["weight"] / e.groupby("source")["weight"].transform("sum")
    e["cost_logp"] = -np.log(e["probability"]) + 0.0
    e["cost_inverse"] = 1.0 / e["weight"]
    return e.sort_values(["weight", "source", "target"], ascending=[False, True, True], ignore_index=True)


def build_graph(edges: pd.DataFrame, pages, cost_col: str = "cost_logp") -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_nodes_from(pages)
    for r in edges.itertuples(index=False):
        G.add_edge(r.source, r.target, weight=int(r.weight), probability=float(r.probability),
                   cost=float(getattr(r, cost_col)))
    return G


def undirected_sum(G: nx.DiGraph) -> nx.Graph:
    """Undirected view where the weight of {u, v} is transitions u→v plus v→u."""
    U = nx.Graph()
    U.add_nodes_from(G)
    for u, v, w in G.edges(data="weight"):
        if u == v:
            continue
        if U.has_edge(u, v):
            U[u][v]["weight"] += w
        else:
            U.add_edge(u, v, weight=w)
    return U


def eigenvector_scores(G: nx.DiGraph):
    if G.number_of_edges() == 0:
        return {n: 0.0 for n in G}, "graph has no edges"
    try:
        return nx.eigenvector_centrality(G, weight="weight", max_iter=5000, tol=1e-9), "directed, weighted by transitions (in-links)"
    except (nx.PowerIterationFailedConvergence, nx.NetworkXException):
        pass
    U = undirected_sum(G)
    try:
        return nx.eigenvector_centrality_numpy(U, weight="weight"), "undirected fallback (directed version did not converge)"
    except Exception:  # noqa: BLE001 - disconnected / degenerate graphs
        return {n: 0.0 for n in G}, "could not be computed for this graph"


@st.cache_data(show_spinner="Computing centrality measures…")
def centrality_table(edges: pd.DataFrame, pages: tuple, cost_col: str, views: pd.Series):
    G = build_graph(edges, pages, cost_col)
    n = G.number_of_nodes()
    sample = None if n <= 400 else 300
    eig, eig_note = eigenvector_scores(G)
    m = pd.DataFrame({
        "degree": nx.degree_centrality(G) if n > 1 else {p: 0.0 for p in G},
        "in_degree": nx.in_degree_centrality(G) if n > 1 else {p: 0.0 for p in G},
        "out_degree": nx.out_degree_centrality(G) if n > 1 else {p: 0.0 for p in G},
        "in_strength": dict(G.in_degree(weight="weight")),
        "out_strength": dict(G.out_degree(weight="weight")),
        "closeness": nx.closeness_centrality(G, distance="cost"),
        "closeness_out": nx.closeness_centrality(G.reverse(copy=True), distance="cost"),
        "betweenness": nx.betweenness_centrality(G, weight="cost", normalized=True, k=sample, seed=42),
        "eigenvector": eig,
        "pagerank": nx.pagerank(G, alpha=0.85, weight="weight") if G.number_of_edges() else {p: 1 / n for p in G},
    })
    m.index.name = "page"
    m["page_views"] = views.reindex(m.index).fillna(0).astype(int)
    m["weighted_degree"] = m["in_strength"] + m["out_strength"]
    return m.reset_index(), eig_note


@st.cache_data(show_spinner=False)
def pagerank_scores(edges: pd.DataFrame, pages: tuple, alpha: float, weighted: bool) -> pd.Series:
    G = build_graph(edges, pages)
    if G.number_of_edges() == 0:
        return pd.Series({p: 1 / len(G) for p in G})
    return pd.Series(nx.pagerank(G, alpha=alpha, weight="weight" if weighted else None))


@st.cache_data(show_spinner="Detecting communities…")
def detect_communities(edges: pd.DataFrame, pages: tuple, algorithm: str, resolution: float):
    U = undirected_sum(build_graph(edges, pages))
    if U.number_of_edges() == 0:
        comms = [{n} for n in U]
    elif algorithm == "Louvain":
        comms = nx.community.louvain_communities(U, weight="weight", resolution=resolution, seed=42)
    elif algorithm == "Greedy modularity":
        comms = nx.community.greedy_modularity_communities(U, weight="weight", resolution=resolution)
    else:
        comms = nx.community.asyn_lpa_communities(U, weight="weight", seed=42)
    comms = sorted((sorted(c) for c in comms), key=lambda c: (-len(c), c[0]))
    modularity = nx.community.modularity(U, comms, weight="weight") if U.number_of_edges() else 0.0
    return comms, float(modularity)


@st.cache_data(show_spinner=False)
def top_paths(j: pd.DataFrame, length: int, top: int = 15) -> pd.DataFrame:
    g = j.groupby("_journey", sort=False)["_page"]
    parts = [j["_page"]] + [g.shift(-i) for i in range(1, length)]
    frame = pd.concat(parts, axis=1, keys=list(range(length))).dropna()
    if frame.empty:
        return pd.DataFrame(columns=["Navigation path", "Occurrences", "Share of paths"])
    counts = frame.groupby(list(range(length))).size().sort_values(ascending=False).head(top)
    return pd.DataFrame({
        "Navigation path": [" → ".join(k) for k in counts.index],
        "Occurrences": counts.to_numpy(),
        "Share of paths": counts.to_numpy() / len(frame),
    })


@st.cache_data(show_spinner=False)
def funnel_counts(j: pd.DataFrame, steps: tuple) -> list[int]:
    reached = [0] * len(steps)
    for seq in j.groupby("_journey", sort=False)["_page"].agg(list):
        k = 0
        for p in seq:
            if k < len(steps) and p == steps[k]:
                k += 1
        for i in range(k):
            reached[i] += 1
    return reached


@st.cache_data(show_spinner=False)
def layout_positions(edges: pd.DataFrame, pages: tuple, kind: str) -> dict:
    U = undirected_sum(build_graph(edges, pages))
    if len(U) == 0:
        return {}
    if kind == "Circular":
        pos = nx.circular_layout(U)
    elif kind == "Kamada-Kawai":
        pos = nx.kamada_kawai_layout(U, weight=None)
    else:
        pos = nx.spring_layout(U, weight="weight", seed=42, k=1.6 / math.sqrt(len(U)), iterations=300)
    return {n: (float(x), float(y)) for n, (x, y) in pos.items()}


def grouped_circle(groups: list[list[str]]) -> dict:
    order = [p for g in groups for p in g]
    n = max(len(order), 1)
    return {p: (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i, p in enumerate(order)}


# --------------------------------------------------------------------------- network figure
def network_figure(G: nx.DiGraph, pos: dict, size_values: dict, node_colors, edge_list, node_hover=None,
                   highlight: set | None = None, height: int = 640, legend_items=None) -> go.Figure:
    nodes = [n for n in G.nodes if n in pos]
    vals = np.array([float(size_values.get(n, 0)) for n in nodes]) if nodes else np.array([0.0])
    spread = vals.max() - vals.min()
    sizes = 18 + 30 * ((vals - vals.min()) / spread if spread > 0 else np.full(len(vals), 0.5))
    size_of = dict(zip(nodes, sizes))
    wmax = max((w for _, _, w in edge_list), default=1)
    highlight = highlight or set()

    annotations, mx, my, mtext = [], [], [], []
    ordered = sorted(edge_list, key=lambda e: ((e[0], e[1]) in highlight, e[2]))
    for u, v, w in ordered:
        if u == v or u not in pos or v not in pos:
            continue
        (x0, y0), (x1, y1) = pos[u], pos[v]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1.0
        ox, oy = -dy / length * 0.018, dx / length * 0.018  # keep u→v and v→u apart
        on_path = (u, v) in highlight
        if on_path:
            color, width = HIGHLIGHT, 4.5
        elif highlight:
            color, width = "rgba(140,140,140,0.16)", 0.8
        else:
            color, width = f"rgba(42,120,214,{0.15 + 0.55 * w / wmax:.2f})", 0.6 + 3.2 * w / wmax
        annotations.append(dict(
            x=x1 + ox, y=y1 + oy, ax=x0 + ox, ay=y0 + oy, xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowsize=1.0 if on_path else 0.8, arrowwidth=width,
            arrowcolor=color, standoff=size_of[v] / 2 + 2, startstandoff=size_of[u] / 2, text="",
        ))
        mx.append(x0 + dx * 0.5 + ox)
        my.append(y0 + dy * 0.5 + oy)
        prob = G[u][v].get("probability", 0)
        mtext.append(f"<b>{u} → {v}</b><br>Transitions: {w:,}<br>P(next = {v} | {u}): {prob:.1%}")

    traces = [go.Scatter(x=mx, y=my, mode="markers", marker=dict(size=12, color="rgba(0,0,0,0)"),
                         hovertext=mtext, hoverinfo="text", showlegend=False)]
    traces.append(go.Scatter(
        x=[pos[n][0] for n in nodes], y=[pos[n][1] for n in nodes], mode="markers+text",
        text=nodes, textposition="top center", textfont=dict(size=12, color=INK),
        marker=dict(size=sizes, color=node_colors, line=dict(color="white", width=2)),
        hovertext=node_hover or nodes, hoverinfo="text", showlegend=False,
    ))
    for name, color in legend_items or []:
        traces.append(go.Scatter(x=[None], y=[None], mode="markers", name=name,
                                 marker=dict(size=12, color=color), showlegend=True))
    fig = go.Figure(traces)
    fig.update_layout(annotations=annotations)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    style(fig, height=height, legend=bool(legend_items))
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), hovermode="closest")
    return fig


def node_hover_text(c, nodes) -> list[str]:
    m = c.metrics.set_index("page")
    out = []
    for n in nodes:
        r = m.loc[n]
        out.append(f"<b>{n}</b><br>Page views: {int(r.page_views):,}<br>Incoming transitions: {int(r.in_strength):,}"
                   f"<br>Outgoing transitions: {int(r.out_strength):,}<br>PageRank: {r.pagerank:.4f}")
    return out


def path_chips(path: list[str]) -> str:
    parts = []
    for i, p in enumerate(path):
        cls = "wg-chip end" if i in (0, len(path) - 1) else "wg-chip"
        parts.append(f'<span class="{cls}">{p}</span>')
    return '<div class="wg-path">' + '<span class="wg-arrow">→</span>'.join(parts) + "</div>"


def pick_default(options: list, preferred: list, fallback_index: int = 0) -> int:
    for p in preferred:
        if p in options:
            return options.index(p)
    return min(fallback_index, max(len(options) - 1, 0))


# --------------------------------------------------------------------------- sections
def journey_notice(c) -> None:
    unit = "sessions" if c.mode != "user" else "user journeys"
    order = f"`{c.time}`" if c.time else "file row order (no timestamp column selected)"
    msg = (f"**How navigation order is built:** page views are grouped into **{JOURNEY_MODES[c.mode]}** "
           f"and sorted by {order}. Each consecutive pair of pages inside one of the "
           f"{c.j['_journey'].nunique():,} {unit} becomes a directed edge; the edge weight is how often that move happened.")
    if c.collapse:
        msg += " Consecutive repeats of the same page are collapsed (a reload is not a navigation)."
    st.info(msg)
    if c.auto and c.fallback_reason:
        st.warning(c.fallback_reason)
    with st.expander("Transitions produced by each grouping option (computed from this dataset)"):
        table(pd.DataFrame([
            {"Grouping": JOURNEY_MODES[m], "Journeys": s["journeys"], "Journeys with ≥ 2 pages": s["multi"],
             "Page transitions": s["transitions"], "Used": "✅" if m == c.mode else ""}
            for m, s in c.mode_stats.items()
        ]))


def section_overview(c) -> None:
    d, e = c.d, c.edges
    k = st.columns(5)
    k[0].metric("Total records", f"{len(c.df):,}")
    k[1].metric("Total users", f"{d[c.user].nunique():,}" if c.user else "—")
    k[2].metric("Total sessions", f"{d[c.session].nunique():,}" if c.session else "—")
    k[3].metric("Total page views", f"{len(d):,}")
    k[4].metric("Unique webpages (nodes)", f"{c.G.number_of_nodes():,}")
    k = st.columns(5)
    k[0].metric("Navigation transitions", f"{int(e['weight'].sum()):,}")
    k[1].metric("Directed edges", f"{c.G.number_of_edges():,}")
    k[2].metric("Graph density", f"{nx.density(c.G):.3f}" if c.G.number_of_nodes() > 1 else "—")
    if c.conv is not None:
        k[3].metric("Conversions", f"{int(c.conv.sum()):,}")
        k[4].metric("Conversion rate", f"{c.conv.mean():.2%}")
    else:
        k[3].metric("Conversions", "—")
        k[4].metric("Conversion rate", "—")

    journey_notice(c)

    left, right = st.columns(2)
    with left:
        views = c.views.head(15)
        show(hbar(views.index, views.values, "Most visited webpages", "Page views"))
    with right:
        top = e.head(12)
        show(hbar(top["source"] + " → " + top["target"], top["weight"], "Most frequent page transitions", "Transitions"))

    st.markdown("#### Analysis pipeline")
    steps = st.columns(4)
    notes = [
        ("1 · Clickstream", f"{len(c.df):,} records, {len(c.df.columns)} columns from **{c.source_name}**."),
        ("2 · Journeys", f"Events ordered by {c.time or 'row order'} inside each {'session' if c.mode != 'user' else 'user'}."),
        ("3 · Directed graph", f"{c.G.number_of_nodes()} pages as nodes, {c.G.number_of_edges()} weighted directed edges."),
        ("4 · Graph analytics", "Dijkstra, degree, closeness, betweenness, eigenvector, PageRank, communities."),
    ]
    for col, (head, body) in zip(steps, notes):
        col.markdown(f'<div class="wg-card"><div class="k">{head}</div>{body}</div>', unsafe_allow_html=True)


def section_dataset(c) -> None:
    df = c.df
    k = st.columns(4)
    k[0].metric("Rows", f"{len(df):,}")
    k[1].metric("Columns", f"{len(df.columns):,}")
    k[2].metric("Missing cells", f"{int(df.isna().sum().sum()):,}")
    k[3].metric("Memory", f"{df.memory_usage(deep=True).sum() / 1e6:.1f} MB")
    st.caption(f"Source: **{c.source_name}**")

    st.markdown("#### Column mapping used by the dashboard")
    mapping = [{"Role": CORE_ROLES[r][0], "Column": col or NONE} for r, col in
               (("page", c.page), ("user", c.user), ("session", c.session), ("time", c.time))]
    mapping += [{"Role": OPTIONAL_ROLES[r][0], "Column": col or NONE} for r, col in c.opt.items()]
    table(pd.DataFrame(mapping))

    st.markdown("#### Data preview")
    n = st.slider("Rows to show", 10, min(1000, max(len(df), 10)), min(50, len(df)), step=10, key=f"prev-{c.key}")
    st.dataframe(df.head(n), width="stretch", height=380)

    st.markdown("#### Column profile")
    profile = pd.DataFrame({
        "Column": df.columns,
        "Type": [str(t) for t in df.dtypes],
        "Non-null": df.notna().sum().to_numpy(),
        "Missing": df.isna().sum().to_numpy(),
        "Missing %": (df.isna().mean() * 100).round(2).to_numpy(),
        "Unique values": df.nunique().to_numpy(),
        "Example": [str(df[col].dropna().iloc[0]) if df[col].notna().any() else "" for col in df.columns],
    })
    table(profile)

    miss = df.isna().sum()
    miss = miss[miss > 0]
    left, right = st.columns(2)
    with left:
        if len(miss):
            show(hbar(miss.index, miss.values, "Missing values per column", "Missing cells", color=HIGHLIGHT))
        else:
            st.success("No missing values in this dataset.")
    with right:
        num = df.select_dtypes("number")
        if not num.empty:
            st.markdown("**Numeric summary**")
            st.dataframe(num.describe().T.round(2), width="stretch")


def section_graph(c) -> None:
    G, e = c.G, c.edges
    if G.number_of_edges() == 0:
        st.error("No page transitions were found, so the navigation graph is empty. Try another grouping in the sidebar.")
        journey_notice(c)
        return
    k = st.columns(6)
    k[0].metric("Nodes (webpages)", f"{G.number_of_nodes():,}")
    k[1].metric("Directed edges", f"{G.number_of_edges():,}")
    k[2].metric("Total transitions", f"{int(e['weight'].sum()):,}")
    k[3].metric("Density", f"{nx.density(G):.3f}")
    k[4].metric("Reciprocity", f"{nx.reciprocity(G):.2f}")
    k[5].metric("Strongly connected", "Yes" if nx.is_strongly_connected(G) else
                f"No ({nx.number_strongly_connected_components(G)} parts)")

    n_nodes = G.number_of_nodes()
    ctrl = st.columns(4)
    layout = ctrl[0].selectbox("Layout", ["Circular", "Spring (force-directed)", "Kamada-Kawai"],
                               index=0 if n_nodes <= 30 else 1, key=f"lay-{c.key}")
    max_nodes = ctrl[1].slider("Pages shown (most visited)", 2, max(n_nodes, 2), min(n_nodes, 40), key=f"mn-{c.key}") if n_nodes > 2 else n_nodes
    keep = set(c.views.index[:max_nodes]) & set(G.nodes)
    sub_edges = e[e["source"].isin(keep) & e["target"].isin(keep) & (e["source"] != e["target"])]
    max_edges = max(len(sub_edges), 1)
    n_edges = ctrl[2].slider("Edges drawn (strongest first)", 1, max_edges, min(max_edges, 80), key=f"ne-{c.key}")
    size_by = ctrl[3].selectbox("Node size", ["Page views", "PageRank", "Weighted degree"], key=f"sz-{c.key}")

    H = G.subgraph(keep).copy()
    pos = layout_positions(c.edges, c.pages, layout.split(" ")[0])
    col = {"Page views": "page_views", "PageRank": "pagerank", "Weighted degree": "weighted_degree"}[size_by]
    size_values = c.metrics.set_index("page")[col].to_dict()
    drawn = [(r.source, r.target, int(r.weight)) for r in sub_edges.head(n_edges).itertuples()]
    fig = network_figure(H, pos, size_values, ACCENT, drawn, node_hover_text(c, list(H.nodes)))
    show(fig)
    st.caption(f"Showing {len(drawn)} of {len(sub_edges)} edges between the {len(keep)} most visited pages. "
               "Arrow thickness and opacity follow the transition count; hover an edge midpoint or a node for values.")

    tabs = st.tabs(["Transition matrix", "Flow (Sankey)", "Common navigation paths", "Edge list"])
    with tabs[0]:
        use_prob = st.toggle("Show transition probability instead of counts", key=f"prob-{c.key}")
        top_pages = [p for p in c.views.index[:30] if p in G]
        value = "probability" if use_prob else "weight"
        mat = (e.pivot_table(index="source", columns="target", values=value, aggfunc="sum")
               .reindex(index=top_pages, columns=top_pages))
        fmt = ".1%" if use_prob else ",.0f"
        fig = go.Figure(go.Heatmap(
            z=mat.to_numpy(), x=mat.columns, y=mat.index, colorscale=BLUE_SCALE, xgap=2, ygap=2,
            hovertemplate=f"<b>%{{y}} → %{{x}}</b><br>{'Probability' if use_prob else 'Transitions'}: %{{z:{fmt}}}<extra></extra>",
            colorbar=dict(title="P(next)" if use_prob else "Transitions", tickformat=fmt if use_prob else None),
        ))
        fig.update_yaxes(autorange="reversed", title="From page")
        fig.update_xaxes(title="To page", tickangle=-40)
        show(style(fig, "Page-to-page transition matrix", height=max(420, 28 * len(top_pages) + 160)))
    with tabs[1]:
        n_flow = st.slider("Transitions in the flow", 5, max(min(len(e), 100), 5), min(len(e), 30), key=f"sk-{c.key}")
        top = e[e["source"] != e["target"]].head(n_flow)
        src, tgt = sorted(set(top["source"])), sorted(set(top["target"]))
        si = {p: i for i, p in enumerate(src)}
        ti = {p: i + len(src) for i, p in enumerate(tgt)}
        fig = go.Figure(go.Sankey(
            node=dict(label=src + tgt, pad=14, thickness=16, line=dict(width=0),
                      color=[ACCENT] * len(src) + [PALETTE[2]] * len(tgt)),
            link=dict(source=top["source"].map(si), target=top["target"].map(ti), value=top["weight"],
                      color="rgba(42,120,214,0.22)",
                      hovertemplate="%{source.label} → %{target.label}<br>Transitions: %{value:,}<extra></extra>"),
        ))
        show(style(fig, "Strongest navigation flows (left: from page, right: next page)", height=560))
    with tabs[2]:
        length = st.slider("Path length (pages)", 2, 6, 3, key=f"pl-{c.key}")
        paths = top_paths(c.j, length, 20)
        if paths.empty:
            st.info(f"No journey contains {length} consecutive pages.")
        else:
            left, right = st.columns([3, 2])
            with left:
                show(hbar(paths["Navigation path"].head(12), paths["Occurrences"].head(12),
                          f"Most common {length}-page navigation paths", "Occurrences"))
            with right:
                table(paths, column_config={"Share of paths": st.column_config.NumberColumn(format="percent")})
    with tabs[3]:
        out = e.rename(columns={"source": "From page", "target": "To page", "weight": "Transitions",
                                "probability": "P(next | from)", "cost_logp": "Cost −log(p)",
                                "cost_inverse": "Cost 1/count"})
        table(out, height=420, column_config={
            "P(next | from)": st.column_config.NumberColumn(format="percent"),
            "Cost −log(p)": st.column_config.NumberColumn(format="%.4f"),
            "Cost 1/count": st.column_config.NumberColumn(format="%.5f"),
        })


def section_dijkstra(c) -> None:
    G = c.G
    if G.number_of_edges() == 0:
        st.error("The navigation graph has no edges, so no path can be computed.")
        return
    pages = sorted(G.nodes)
    st.markdown(
        "Dijkstra finds the lowest-cost route between two webpages. A frequent transition must be **cheap**, "
        "so the cost is derived from the data instead of using the raw count as a distance:\n\n"
        "- **−log(p)**, where *p* = transitions(A→B) ÷ all transitions leaving A. Adding costs multiplies "
        "probabilities, so the shortest path is the **most likely navigation route**.\n"
        "- **1 / count**: links used more often cost less.\n\n"
        f"Current cost (change in the sidebar): **{COST_OPTIONS[c.cost_col]}**"
    )
    a, b = st.columns(2)
    src = a.selectbox("Source webpage", pages, index=pick_default(pages, ["Home"]), key=f"src-{c.key}")
    dst = b.selectbox("Destination webpage", pages,
                      index=pick_default(pages, ["Payment", "Order_Confirmation", "Checkout"], 1), key=f"dst-{c.key}")
    if src == dst:
        st.warning("Choose two different webpages.")
        return
    try:
        cost, path = nx.single_source_dijkstra(G, src, dst, weight="cost")
    except nx.NetworkXNoPath:
        st.error(f"No navigation path exists from **{src}** to **{dst}** in this dataset.")
        return

    steps = [{"Step": i + 1, "From": u, "To": v, "Transitions": G[u][v]["weight"],
              "P(next | from)": G[u][v]["probability"], "Edge cost": G[u][v]["cost"]}
             for i, (u, v) in enumerate(zip(path, path[1:]))]
    prob = float(np.prod([s["P(next | from)"] for s in steps]))
    hops = nx.shortest_path_length(G, src, dst)

    st.markdown(f"#### Shortest navigation path: {src} → {dst}")
    st.markdown(path_chips(path), unsafe_allow_html=True)
    k = st.columns(4)
    k[0].metric("Pages on path", len(path))
    k[1].metric("Total path cost", f"{cost:.4f}")
    k[2].metric("Path probability", f"{prob:.3%}")
    k[3].metric("Fewest possible clicks", hops)
    if G.has_edge(src, dst) and len(path) > 2:
        direct = G[src][dst]
        st.caption(f"A direct link {src} → {dst} exists (p = {direct['probability']:.2%}, cost = {direct['cost']:.4f}), "
                   f"but the route above has a lower total cost ({cost:.4f}).")
    elif len(path) == 2:
        st.caption("The direct link is the cheapest route.")

    left, right = st.columns([3, 2])
    with left:
        pos = layout_positions(c.edges, c.pages, "Circular" if G.number_of_nodes() <= 30 else "Spring")
        on_path = set(zip(path, path[1:]))
        others = [(u, v, d["weight"]) for u, v, d in G.edges(data=True) if (u, v) not in on_path]
        others = sorted(others, key=lambda x: -x[2])[:120]
        drawn = others + [(u, v, G[u][v]["weight"]) for u, v in on_path]
        colors = [HIGHLIGHT if n in path else "#9ec5f4" for n in G.nodes]
        size_values = {n: (1 if n in path else 0) for n in G.nodes}
        show(network_figure(G, pos, size_values, colors, drawn, node_hover_text(c, list(G.nodes)),
                            highlight=on_path, height=560))
    with right:
        st.markdown("**Path steps**")
        table(pd.DataFrame(steps), column_config={
            "P(next | from)": st.column_config.NumberColumn(format="percent"),
            "Edge cost": st.column_config.NumberColumn(format="%.4f")})
        st.markdown("**Alternative routes (next cheapest)**")
        alts = []
        for rank, p in enumerate(islice(nx.shortest_simple_paths(G, src, dst, weight="cost"), 5), 1):
            pairs = list(zip(p, p[1:]))
            alts.append({"Rank": rank, "Route": " → ".join(p), "Clicks": len(p) - 1,
                         "Cost": sum(G[u][v]["cost"] for u, v in pairs),
                         "Probability": float(np.prod([G[u][v]["probability"] for u, v in pairs]))})
        table(pd.DataFrame(alts), column_config={
            "Cost": st.column_config.NumberColumn(format="%.4f"),
            "Probability": st.column_config.NumberColumn(format="percent")})

    st.markdown(f"#### Cheapest route from {src} to every other page")
    dist, routes = nx.single_source_dijkstra(G, src, weight="cost")
    rows = [{"Destination": t, "Cost": dist[t], "Clicks": len(routes[t]) - 1, "Route": " → ".join(routes[t])}
            for t in sorted(dist, key=dist.get) if t != src]
    unreachable = [p for p in pages if p not in dist]
    table(pd.DataFrame(rows), column_config={"Cost": st.column_config.NumberColumn(format="%.4f")})
    if unreachable:
        st.caption("Not reachable from the source: " + ", ".join(unreachable))


MEASURES = {
    "degree": ("Degree centrality", "Share of other pages a page links to or from: (in + out links) ÷ (n − 1). Ignores how often links are used."),
    "closeness": ("Closeness centrality", "How cheaply a page is **reached from** all other pages, using the navigation cost as distance (higher = easier to reach)."),
    "betweenness": ("Betweenness centrality", "Share of cheapest paths between other pages that pass **through** this page; high values mark bridge pages."),
    "eigenvector": ("Eigenvector centrality", "A page is important if it receives traffic from other important pages (weighted by transitions)."),
    "pagerank": ("PageRank", "Probability that a random visitor following observed transitions (85% of the time) lands on the page."),
}


def measure_block(c, key: str, extra_cols: list[str], fmt: str = "%.4f") -> None:
    title, desc = MEASURES[key]
    m = c.metrics.sort_values(key, ascending=False)
    st.markdown(f"**{title}.** {desc}")
    left, right = st.columns([3, 2])
    with left:
        show(hbar(m["page"], m[key], f"{title} by webpage", title, fmt=",.4f"))
    with right:
        cols = ["page", key] + extra_cols
        view = m[cols].rename(columns={"page": "Webpage"})
        view.insert(0, "Rank", range(1, len(view) + 1))
        cfg = {key: st.column_config.ProgressColumn(title, format=fmt, min_value=0.0,
                                                    max_value=float(max(m[key].max(), 1e-12)))}
        cfg.update({x: st.column_config.NumberColumn(format="%.4f") for x in extra_cols
                    if x in ("in_degree", "out_degree", "closeness_out")})
        table(view, column_config=cfg)
    spread = m[key].max() - m[key].min()
    if spread < 1e-9:
        st.info(f"Every page has the same {title.lower()} ({m[key].iloc[0]:.4f}). In this graph the measure "
                "does not separate pages; see the weighted measures.")
    else:
        st.caption(f"Range {m[key].min():.4f} – {m[key].max():.4f}; highest: **{m['page'].iloc[0]}**, lowest: **{m['page'].iloc[-1]}**.")


def section_centrality(c) -> None:
    if c.G.number_of_edges() == 0:
        st.error("The navigation graph has no edges, so centrality cannot be computed.")
        return
    st.caption(f"Closeness and betweenness use the navigation cost **{COST_OPTIONS[c.cost_col]}** as edge distance. "
               f"Eigenvector: {c.eig_note}.")
    tabs = st.tabs(["Degree", "Closeness", "Betweenness", "Eigenvector", "PageRank", "Comparison"])
    with tabs[0]:
        measure_block(c, "degree", ["in_degree", "out_degree"])
        m = c.metrics.sort_values("weighted_degree", ascending=False)
        fig = go.Figure([
            go.Bar(name="Incoming transitions", y=m["page"], x=m["in_strength"], orientation="h", marker_color=PALETTE[0],
                   hovertemplate="<b>%{y}</b><br>Incoming: %{x:,}<extra></extra>"),
            go.Bar(name="Outgoing transitions", y=m["page"], x=m["out_strength"], orientation="h", marker_color=PALETTE[1],
                   hovertemplate="<b>%{y}</b><br>Outgoing: %{x:,}<extra></extra>"),
        ])
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08)
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(title="Transitions")
        show(style(fig, "Weighted degree: transitions into and out of each page", height=max(320, 34 * len(m) + 110), legend=True))
    with tabs[1]:
        measure_block(c, "closeness", ["closeness_out"])
        st.caption("closeness_out = closeness in the other direction (how cheaply the page reaches all others).")
    with tabs[2]:
        measure_block(c, "betweenness", ["page_views"])
    with tabs[3]:
        measure_block(c, "eigenvector", ["in_strength"])
    with tabs[4]:
        measure_block(c, "pagerank", ["page_views"])
    with tabs[5]:
        cols = ["degree", "closeness", "betweenness", "eigenvector", "pagerank"]
        m = c.metrics.set_index("page")[cols + ["weighted_degree", "page_views"]].sort_values("pagerank", ascending=False)
        ranks = m[cols].rank(ascending=False, method="min").astype(int).add_suffix(" rank")
        full = pd.concat([m, ranks], axis=1).reset_index().rename(columns={"page": "Webpage"})
        table(full, column_config={x: st.column_config.NumberColumn(format="%.4f") for x in cols})
        norm_m = m[cols].apply(lambda s: (s - s.min()) / (s.max() - s.min()) if s.max() > s.min() else s * 0)
        fig = go.Figure(go.Heatmap(
            z=norm_m.to_numpy(), x=[MEASURES[x][0] for x in cols], y=norm_m.index, colorscale=BLUE_SCALE,
            xgap=2, ygap=2, customdata=m[cols].to_numpy(),
            hovertemplate="<b>%{y}</b><br>%{x}: %{customdata:.4f}<br>Scaled: %{z:.2f}<extra></extra>",
            colorbar=dict(title="Scaled<br>0–1")))
        fig.update_yaxes(autorange="reversed")
        left, right = st.columns([3, 2])
        with left:
            show(style(fig, "Centrality profile (each measure min–max scaled)", height=max(380, 28 * len(m) + 140)))
        with right:
            varying = [x for x in cols if m[x].nunique() > 1]
            if len(varying) >= 2:
                corr = m[varying].rank().corr()  # Spearman ρ
                labels = [MEASURES[x][0].replace(" centrality", "") for x in varying]
                fig = go.Figure(go.Heatmap(
                    z=corr.to_numpy(), x=labels, y=labels, zmin=-1, zmax=1, xgap=2, ygap=2,
                    colorscale=[[0, "#e34948"], [0.5, "#f0efec"], [1, "#2a78d6"]],
                    text=np.round(corr.to_numpy(), 2), texttemplate="%{text}",
                    hovertemplate="%{y} vs %{x}<br>Spearman ρ = %{z:.2f}<extra></extra>"))
                fig.update_yaxes(autorange="reversed")
                show(style(fig, "Rank agreement between measures (Spearman ρ)", height=400))
            constant = [MEASURES[x][0] for x in cols if x not in varying]
            if constant:
                st.caption("Identical for every page (left out of the correlation): " + ", ".join(constant) + ".")


def section_pagerank(c) -> None:
    if c.G.number_of_edges() == 0:
        st.error("The navigation graph has no edges, so PageRank cannot be computed.")
        return
    a, b = st.columns([2, 1])
    alpha = a.slider("Damping factor (probability of following a link)", 0.50, 0.99, 0.85, 0.01, key=f"alpha-{c.key}")
    weighted = b.toggle("Weight links by transition count", value=True, key=f"prw-{c.key}")
    pr = pagerank_scores(c.edges, c.pages, alpha, weighted).sort_values(ascending=False)
    views = c.views.reindex(pr.index).fillna(0)
    k = st.columns(4)
    k[0].metric("Top page", pr.index[0])
    k[1].metric("Highest PageRank", f"{pr.iloc[0]:.4f}")
    k[2].metric("Lowest PageRank", f"{pr.iloc[-1]:.4f}")
    k[3].metric("Uniform baseline (1/n)", f"{1 / len(pr):.4f}")

    left, right = st.columns([3, 2])
    with left:
        show(hbar(pr.index, pr.values, f"PageRank (d = {alpha:.2f}{', weighted' if weighted else ''})", "PageRank", fmt=",.4f"))
    with right:
        out = pd.DataFrame({"Rank": range(1, len(pr) + 1), "Webpage": pr.index, "PageRank": pr.values,
                            "Page views": views.astype(int).values,
                            "Share of page views": (views / max(views.sum(), 1)).values})
        table(out, column_config={
            "PageRank": st.column_config.ProgressColumn(format="%.4f", min_value=0.0, max_value=float(pr.max())),
            "Share of page views": st.column_config.NumberColumn(format="percent")})

    fig = go.Figure(go.Scatter(
        x=views.values, y=pr.values, mode="markers+text", text=pr.index if len(pr) <= 25 else None,
        textposition="top center", textfont=dict(color=INK_2, size=11),
        marker=dict(size=11, color=ACCENT, line=dict(color="white", width=2)),
        hovertemplate="<b>%{text}</b><br>Page views: %{x:,}<br>PageRank: %{y:.4f}<extra></extra>" if len(pr) <= 25
        else "Page views: %{x:,}<br>PageRank: %{y:.4f}<extra></extra>"))
    fig.update_xaxes(title="Page views")
    fig.update_yaxes(title="PageRank")
    show(style(fig, "PageRank vs raw page views", height=440))
    corr = pd.Series(pr.values).rank().corr(pd.Series(views.values).rank())  # Spearman ρ without scipy.stats
    st.caption(f"Spearman rank correlation between PageRank and page views: **{corr:.2f}**. PageRank values sum to "
               f"{pr.sum():.4f}. A page ranks above its raw popularity when it receives traffic from other high-ranking pages.")


def section_communities(c) -> None:
    if c.G.number_of_edges() == 0:
        st.error("The navigation graph has no edges, so communities cannot be detected.")
        return
    a, b = st.columns(2)
    algo = a.selectbox("Algorithm", ["Louvain", "Greedy modularity", "Label propagation"], key=f"alg-{c.key}")
    res = b.slider("Resolution (higher → more, smaller communities)", 0.5, 2.0, 1.0, 0.05, key=f"res-{c.key}",
                   disabled=algo == "Label propagation")
    comms, modularity = detect_communities(c.edges, c.pages, algo, res)
    comm_of = {p: i + 1 for i, g in enumerate(comms) for p in g}
    e = c.edges.assign(c_from=c.edges["source"].map(comm_of), c_to=c.edges["target"].map(comm_of))
    intra = e.loc[e["c_from"] == e["c_to"], "weight"].sum() / max(e["weight"].sum(), 1)

    k = st.columns(4)
    k[0].metric("Communities", len(comms))
    k[1].metric("Modularity (Q)", f"{modularity:.4f}")
    k[2].metric("Largest community", f"{len(comms[0])} pages")
    k[3].metric("Transitions inside communities", f"{intra:.1%}")
    if len(comms) == 1:
        st.info("No split of the pages improves modularity at this resolution: navigation is spread almost evenly "
                "across all page pairs, so every page falls into one community. Raise the resolution to force finer groups "
                "and compare their modularity.")
    elif modularity < 0.1:
        st.info(f"Modularity Q = {modularity:.3f} is low. Navigation between these groups is almost as common as "
                "navigation inside them, so the groups are weak. Q above about 0.3 usually means clear structure.")

    pr = c.metrics.set_index("page")["pagerank"]
    rows = []
    for i, g in enumerate(comms, 1):
        internal = int(e.loc[(e["c_from"] == i) & (e["c_to"] == i), "weight"].sum())
        rows.append({"Community": i, "Pages": len(g), "Webpages": ", ".join(g),
                     "Internal transitions": internal, "Top page (PageRank)": pr.reindex(g).idxmax(),
                     "Page views": int(c.views.reindex(g).fillna(0).sum())})
    table(pd.DataFrame(rows))

    left, right = st.columns([3, 2])
    with left:
        colors = {i: (PALETTE[i - 1] if i <= len(PALETTE) else OTHER) for i in range(1, len(comms) + 1)}
        legend = [(f"Community {i}", colors[i]) for i in range(1, min(len(comms), len(PALETTE)) + 1)]
        if len(comms) > len(PALETTE):
            legend.append((f"Communities {len(PALETTE) + 1}+ (other)", OTHER))
        pos = grouped_circle(comms) if len(c.G) <= 60 else layout_positions(c.edges, c.pages, "Spring")
        top_n = min(len(e), 90)
        drawn = [(r.source, r.target, int(r.weight)) for r in e[e["source"] != e["target"]].head(top_n).itertuples()]
        show(network_figure(c.G, pos, c.metrics.set_index("page")["pagerank"].to_dict(),
                            [colors[comm_of[n]] for n in c.G.nodes], drawn,
                            node_hover_text(c, list(c.G.nodes)), height=600, legend_items=legend))
        st.caption(f"Pages grouped around the circle by community; the {len(drawn)} strongest edges are drawn; node size = PageRank.")
    with right:
        mat = e.pivot_table(index="c_from", columns="c_to", values="weight", aggfunc="sum", fill_value=0)
        if len(comms) == 1:
            st.caption("Only one community, so there is no between-community traffic to show.")
            return
        labels = [f"C{i}" for i in mat.index]
        fig = go.Figure(go.Heatmap(
            z=mat.to_numpy(), x=[f"C{i}" for i in mat.columns], y=labels, colorscale=BLUE_SCALE, xgap=2, ygap=2,
            hovertemplate="From %{y} to %{x}<br>Transitions: %{z:,}<extra></extra>", colorbar=dict(title="Transitions")))
        fig.update_yaxes(autorange="reversed", title="From community")
        fig.update_xaxes(title="To community")
        show(style(fig, "Transitions between communities", height=420))
        sizes = pd.Series({f"Community {i}": len(g) for i, g in enumerate(comms, 1)})
        show(hbar(sizes.index, sizes.values, "Pages per community", "Pages", height=max(220, 30 * len(sizes) + 90)))


def section_web_analytics(c) -> None:
    d, o = c.d, c.opt
    k = st.columns(6)
    k[0].metric("Total users", f"{d[c.user].nunique():,}" if c.user else "—")
    k[1].metric("Total sessions", f"{d[c.session].nunique():,}" if c.session else "—")
    k[2].metric("Total page views", f"{len(d):,}")
    if o["event_type"]:
        pv = (d[o["event_type"]].astype(str).str.lower() == "page_view").sum()
        k[3].metric("'page_view' events", f"{int(pv):,}")
    else:
        k[3].metric("'page_view' events", "—")
    k[4].metric("Conversion rate", f"{c.conv.mean():.2%}" if c.conv is not None else "—")
    if o["session_duration"]:
        dur = session_level(c, o["session_duration"])
        k[5].metric("Avg session duration", f"{dur.mean() / 60:.1f} min" if len(dur) else "—")
    else:
        k[5].metric("Avg session duration", "—")

    charts = [("Popular webpages", c.views, None)]
    for role in ["event_type", "traffic_source", "device", "country", "browser", "campaign", "category", "search_keyword"]:
        if o[role]:
            charts.append((OPTIONAL_ROLES[role][0] + ("s" if not OPTIONAL_ROLES[role][0].endswith("y") else ""), None, o[role]))
    for i in range(0, len(charts), 2):
        cols = st.columns(2)
        for col, (title, series, colname) in zip(cols, charts[i:i + 2]):
            with col:
                if series is not None:
                    show(hbar(series.head(15).index, series.head(15).values, title, "Page views"))
                else:
                    show(count_bar(d[colname], title))
    missing = [OPTIONAL_ROLES[r][0] for r, col in o.items() if col is None]
    if missing:
        st.caption("Not in this dataset (charts skipped): " + ", ".join(missing))

    if c.conv is not None:
        st.markdown("#### Conversion")
        dims = [r for r in ["traffic_source", "device", "country", "event_type", "campaign", "browser"] if o[r]]
        dims = [("page", "Webpage")] + [(r, OPTIONAL_ROLES[r][0]) for r in dims]
        for i in range(0, len(dims), 2):
            cols = st.columns(2)
            for col, (role, label) in zip(cols, dims[i:i + 2]):
                key = d["_page"] if role == "page" else d[o[role]].astype(str).where(d[o[role]].notna())
                rate = pd.DataFrame({"k": key, "c": c.conv}).dropna().groupby("k")["c"].mean().sort_values(ascending=False)
                with col:
                    show(hbar(rate.index[:15], rate.values[:15], f"Conversion rate by {label.lower()}",
                              "Conversion rate", fmt=".1%", color=PALETTE[2]))

    st.markdown("#### Session duration & pages per session")
    cols = st.columns(2)
    if o["session_duration"]:
        dur = session_level(c, o["session_duration"])
        with cols[0]:
            fig = go.Figure(go.Histogram(x=dur, nbinsx=40, marker_color=ACCENT,
                                         hovertemplate="Duration %{x} sec<br>Sessions: %{y:,}<extra></extra>"))
            fig.update_layout(bargap=0.04)
            fig.update_xaxes(title="Session duration (seconds)")
            fig.update_yaxes(title="Sessions")
            show(style(fig, f"Session duration (mean {dur.mean():,.0f}s, median {dur.median():,.0f}s)"))
        if o["device"]:
            with cols[1]:
                frame = d.drop_duplicates(c.session) if c.session else d
                fig = go.Figure()
                for i, (dev, grp) in enumerate(frame.groupby(o["device"])):
                    vals = pd.to_numeric(grp[o["session_duration"]], errors="coerce").dropna()
                    fig.add_trace(go.Box(y=vals, name=str(dev), marker_color=PALETTE[i % 3] if i < 3 else OTHER,
                                         boxmean=True, line=dict(width=1.5)))
                fig.update_yaxes(title="Seconds")
                show(style(fig, "Session duration by device"))
    if o["pages_in_session"]:
        pis = session_level(c, o["pages_in_session"])
        with (cols[1] if not (o["session_duration"] and o["device"]) else st.columns(2)[0]):
            vc = pis.round().astype(int).value_counts().sort_index()
            fig = go.Figure(go.Bar(x=vc.index, y=vc.values, marker_color=ACCENT,
                                   hovertemplate="%{x} pages<br>Sessions: %{y:,}<extra></extra>"))
            fig.update_xaxes(title="Pages in session (reported)", dtick=1)
            fig.update_yaxes(title="Sessions")
            show(style(fig, f"Pages in session (mean {pis.mean():.1f})"))

    if d["_time"].notna().any():
        st.markdown("#### Activity over time")
        t = d.dropna(subset=["_time"])
        cols = st.columns([3, 2])
        with cols[0]:
            span = (t["_time"].max() - t["_time"].min()).days
            freq, label = ("D", "day") if span <= 400 else ("W", "week")
            series = t.set_index("_time").resample(freq).size()
            fig = go.Figure(go.Scatter(x=series.index, y=series.values, mode="lines", line=dict(color=ACCENT, width=2),
                                       hovertemplate="%{x|%d %b %Y}<br>Events: %{y:,}<extra></extra>"))
            fig.update_yaxes(title=f"Events per {label}")
            fig.update_layout(hovermode="x unified")
            show(style(fig, f"Events per {label}"))
        with cols[1]:
            hours = t["_time"].dt.hour.value_counts().reindex(range(24), fill_value=0)
            fig = go.Figure(go.Bar(x=hours.index, y=hours.values, marker_color=ACCENT,
                                   hovertemplate="%{x}:00<br>Events: %{y:,}<extra></extra>"))
            fig.update_xaxes(title="Hour of day", dtick=3)
            fig.update_yaxes(title="Events")
            show(style(fig, "Events by hour of day"))


def session_level(c, col: str) -> pd.Series:
    """Per-session attribute: one value per session (first record), else per record."""
    frame = c.d.drop_duplicates(c.session) if c.session else c.d
    return pd.to_numeric(frame[col], errors="coerce").dropna()


def section_behavior(c) -> None:
    j = c.j
    if j.empty:
        st.error("No journeys could be built from this dataset.")
        return
    per = j.groupby("_journey", sort=False)
    lengths = per["_page"].size()
    distinct = per["_page"].nunique()
    unit = "Session" if c.mode != "user" else "User journey"
    k = st.columns(5)
    k[0].metric(f"{unit}s analysed", f"{len(lengths):,}")
    k[1].metric("Avg pages per journey", f"{lengths.mean():.2f}")
    k[2].metric("Median pages", f"{lengths.median():.0f}")
    k[3].metric("Single-page journeys", f"{(lengths == 1).mean():.1%}")
    k[4].metric("Avg distinct pages", f"{distinct.mean():.2f}")

    cols = st.columns(2)
    with cols[0]:
        vc = lengths.value_counts().sort_index()
        fig = go.Figure(go.Bar(x=vc.index, y=vc.values, marker_color=ACCENT,
                               hovertemplate="%{x} pages<br>Journeys: %{y:,}<extra></extra>"))
        fig.update_xaxes(title="Pages in journey", dtick=1 if vc.index.max() <= 30 else None)
        fig.update_yaxes(title="Journeys")
        show(style(fig, "Journey length distribution"))
    with cols[1]:
        firsts = j[j["_step"] == 0]["_page"].value_counts()
        lasts = j[j["_step"] == j["_len"] - 1]["_page"].value_counts()
        both = pd.DataFrame({"Entry": firsts, "Exit": lasts}).fillna(0).sort_values("Entry", ascending=False).head(15)
        fig = go.Figure([
            go.Bar(name="Entry page", y=both.index, x=both["Entry"], orientation="h", marker_color=PALETTE[0],
                   hovertemplate="<b>%{y}</b><br>Journeys starting here: %{x:,}<extra></extra>"),
            go.Bar(name="Exit page", y=both.index, x=both["Exit"], orientation="h", marker_color=PALETTE[1],
                   hovertemplate="<b>%{y}</b><br>Journeys ending here: %{x:,}<extra></extra>"),
        ])
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08)
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(title="Journeys")
        show(style(fig, "Entry and exit pages", height=max(380, 32 * len(both) + 110), legend=True))

    st.markdown("#### Navigation funnel")
    pages = sorted(c.G.nodes)
    default = [p for p in FUNNEL_DEFAULT if p in pages] or list(c.views.index[:5])
    steps = st.multiselect("Funnel steps (in order)", pages, default=default, key=f"fun-{c.key}")
    if len(steps) >= 2:
        counts = funnel_counts(j, tuple(steps))
        left, right = st.columns([3, 2])
        with left:
            fig = go.Figure(go.Funnel(y=steps, x=counts, marker=dict(color=ACCENT), textinfo="value+percent initial",
                                      connector=dict(line=dict(color=GRID)),
                                      hovertemplate="<b>%{y}</b><br>Journeys: %{x:,}<extra></extra>"))
            show(style(fig, "Journeys reaching each step in order", height=max(320, 50 * len(steps) + 80)))
        with right:
            out = pd.DataFrame({"Step": steps, "Journeys": counts})
            out["% of first step"] = out["Journeys"] / max(counts[0], 1)
            out["% of previous step"] = out["Journeys"] / out["Journeys"].shift().replace(0, np.nan)
            table(out, column_config={c_: st.column_config.NumberColumn(format="percent")
                                      for c_ in ["% of first step", "% of previous step"]})
            st.caption("A journey counts for a step if it visited every earlier step first, in order; other pages may appear in between.")
    else:
        st.info("Pick at least two steps.")

    if c.conv is not None and c.user:
        st.markdown("#### Converted vs non-converted users")
        conv_user = pd.DataFrame({"u": c.d[c.user], "c": c.conv}).groupby("u")["c"].max()
        events = c.d.groupby(c.user).size()
        frame = pd.DataFrame({"converted": conv_user, "events": events})
        summary = frame.groupby("converted")["events"].agg(["count", "mean", "median"])
        cols = st.columns(3)
        cols[0].metric("Users with ≥ 1 conversion", f"{int(conv_user.sum()):,} ({conv_user.mean():.1%})")
        if 1 in summary.index:
            cols[1].metric("Avg events · converted users", f"{summary.loc[1, 'mean']:.2f}")
        if 0 in summary.index:
            cols[2].metric("Avg events · non-converted users", f"{summary.loc[0, 'mean']:.2f}")

    st.markdown("#### Journey explorer")
    id_col = c.user or c.session
    if id_col:
        activity = c.d[id_col].value_counts()
        options = activity.index[:5000].tolist()
        chosen = st.selectbox(f"Pick a {id_col} (most active first)", options, key=f"exp-{c.key}")
        rows = c.d[c.d[id_col] == chosen].sort_values(["_time", "_row"])
        seq = rows["_page"].tolist()
        st.markdown(path_chips(seq[:40]) + ("…" if len(seq) > 40 else ""), unsafe_allow_html=True)
        show_cols = [x for x in [c.time, c.session, c.page, c.opt["event_type"], c.opt["device"], c.opt["traffic_source"],
                                 c.opt["conversion"]] if x]
        table(rows[list(dict.fromkeys(show_cols))], height=min(36 * (len(rows) + 1) + 4, 380))


def section_insights(c) -> None:
    G, e, m = c.G, c.edges, c.metrics.set_index("page")
    if G.number_of_edges() == 0:
        st.error("The navigation graph has no edges, so graph insights cannot be derived.")
        return
    comms, modularity = detect_communities(c.edges, c.pages, "Louvain", 1.0)
    paths3 = top_paths(c.j, 3, 1)
    views = c.views
    top_edge = e.iloc[0]
    lengths = c.j.groupby("_journey")["_page"].size()
    firsts = c.j[c.j["_step"] == 0]["_page"].value_counts()
    lasts = c.j[c.j["_step"] == c.j["_len"] - 1]["_page"].value_counts()
    pr = m["pagerank"].sort_values(ascending=False)

    findings = [
        ("Most visited page", f"<b>{views.index[0]}</b> has {views.iloc[0]:,} page views "
                              f"({views.iloc[0] / views.sum():.1%} of all views); the least visited is <b>{views.index[-1]}</b> ({views.iloc[-1]:,})."),
        ("Strongest navigation link", f"<b>{top_edge.source} → {top_edge.target}</b> occurs {int(top_edge.weight):,} times; "
                                      f"{top_edge.probability:.1%} of the moves out of {top_edge.source} go there."),
        ("Most important page (PageRank)", f"<b>{pr.index[0]}</b> ({pr.iloc[0]:.4f}) vs lowest <b>{pr.index[-1]}</b> ({pr.iloc[-1]:.4f}); "
                                           f"the top page scores {pr.iloc[0] / pr.iloc[-1]:.2f}× the lowest."),
        ("Bridge page (betweenness)", f"<b>{m['betweenness'].idxmax()}</b> lies on the largest share of cheapest paths "
                                      f"({m['betweenness'].max():.4f})." if m["betweenness"].max() > 0 else
                                      "No page acts as a bridge (betweenness is 0 for every page): the cheapest route between "
                                      "any two pages is their direct link."),
        ("Easiest to reach (closeness)", f"<b>{m['closeness'].idxmax()}</b> ({m['closeness'].max():.4f}); "
                                         f"eigenvector leader: <b>{m['eigenvector'].idxmax()}</b> ({m['eigenvector'].max():.4f})."),
        ("Communities", f"Louvain (resolution 1.0) finds <b>{len(comms)}</b> communit{'y' if len(comms) == 1 else 'ies'} with modularity Q = {modularity:.3f}"
                        f"{' (weak structure)' if modularity < 0.1 else ' (clear structure)' if modularity >= 0.3 else ' (moderate structure)'}. "
                        f"Largest: {', '.join(comms[0][:6])}{'…' if len(comms[0]) > 6 else ''}."),
        ("Graph structure", f"{G.number_of_nodes()} pages, {G.number_of_edges()} directed links, density {nx.density(G):.3f}, "
                            f"{'strongly connected' if nx.is_strongly_connected(G) else 'not strongly connected'}; reciprocity {nx.reciprocity(G):.2f}."),
    ]
    if not paths3.empty:
        findings.append(("Most common 3-page path", f"<b>{paths3.iloc[0]['Navigation path']}</b> "
                                                    f"({int(paths3.iloc[0]['Occurrences']):,} times)."))
    findings.append(("Entry & exit", f"Journeys most often start on <b>{firsts.index[0]}</b> ({firsts.iloc[0]:,}) and end on "
                                     f"<b>{lasts.index[0]}</b> ({lasts.iloc[0]:,}); average journey length {lengths.mean():.2f} pages."))
    if c.conv is not None:
        text = f"Overall conversion rate is <b>{c.conv.mean():.2%}</b> ({int(c.conv.sum()):,} conversions)."
        for role in ["traffic_source", "device"]:
            col = c.opt[role]
            if col:
                r = pd.DataFrame({"k": c.d[col], "c": c.conv}).dropna().groupby("k")["c"].mean()
                text += f" Best {OPTIONAL_ROLES[role][0].lower()}: <b>{r.idxmax()}</b> ({r.max():.2%}); lowest: {r.idxmin()} ({r.min():.2%})."
        findings.append(("Conversion", text))
    findings.append(("Data note", f"Navigation order was built from <b>{JOURNEY_MODES[c.mode]}</b>. "
                                  + (c.fallback_reason or "Session grouping produced enough transitions.")))

    cols = st.columns(2)
    for i, (head, body) in enumerate(findings):
        cols[i % 2].markdown(f'<div class="wg-card"><div class="k">{head}</div>{body}</div>', unsafe_allow_html=True)

    st.markdown("#### Summary table: top pages by each measure")
    rows = []
    for key, (title, _) in MEASURES.items():
        s = m[key].sort_values(ascending=False)
        rows.append({"Measure": title, "1st": f"{s.index[0]} ({s.iloc[0]:.4f})",
                     "2nd": f"{s.index[1]} ({s.iloc[1]:.4f})" if len(s) > 1 else "",
                     "3rd": f"{s.index[2]} ({s.iloc[2]:.4f})" if len(s) > 2 else "",
                     "Spread (max − min)": s.iloc[0] - s.iloc[-1]})
    table(pd.DataFrame(rows), column_config={"Spread (max − min)": st.column_config.NumberColumn(format="%.4f")})

    st.markdown("#### Download results")
    comm_df = pd.DataFrame([{"page": p, "community": i} for i, g in enumerate(comms, 1) for p in g])
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button("Edges / transitions (CSV)", e.to_csv(index=False).encode(), "navigation_edges.csv", "text/csv")
    d2.download_button("Centrality & PageRank (CSV)", c.metrics.to_csv(index=False).encode(), "centrality_results.csv", "text/csv")
    d3.download_button("Communities (CSV)", comm_df.to_csv(index=False).encode(), "community_results.csv", "text/csv")
    journeys = c.j.drop(columns=["_row"]).rename(columns={"_journey": "journey", "_step": "step", "_page": "page",
                                                           "_next": "next_page", "_time": "time", "_len": "journey_length"})
    d4.download_button("Ordered journeys (CSV)", journeys.to_csv(index=False).encode(), "journeys.csv", "text/csv")


# --------------------------------------------------------------------------- main
def main() -> None:
    sb = st.sidebar
    sb.markdown("## 🕸️ WebGraph Analytics")
    section = sb.radio("Dashboard sections", SECTIONS, format_func=lambda s: f"{SECTION_ICONS[SECTIONS.index(s)]}  {s}")

    sb.markdown("---")
    sb.markdown("#### Dataset")
    upload = sb.file_uploader("Upload a clickstream file (CSV or Excel)", type=["csv", "xlsx", "xls", "xlsm", "tsv", "txt"])
    if upload is not None:
        raw, source_name = upload.getvalue(), upload.name
    else:
        path = next((p for p in DEFAULT_DATASETS if p.exists()), None)
        if path is None:
            hero(section)
            st.info("Upload a clickstream CSV or Excel file from the sidebar to begin.")
            return
        raw, source_name = path.read_bytes(), path.name
    sb.caption(f"Using: **{source_name}**" + ("" if upload else " (bundled)"))

    try:
        df = read_table(raw, source_name)
    except Exception as exc:  # noqa: BLE001 - show any parse error to the user
        hero(section)
        st.error(f"Could not read **{source_name}**: {exc}")
        return
    key = f"{source_name}-{len(raw)}"
    cols = list(df.columns)

    with sb.expander("Column mapping", expanded=upload is not None):
        chosen = {}
        taken = []
        for role, (label, cands) in CORE_ROLES.items():
            guess = detect(cols, cands, taken)
            options = cols if role == "page" else [NONE] + cols
            idx = options.index(guess) if guess in options else 0
            val = st.selectbox(label, options, index=idx, key=f"map-{role}-{key}")
            chosen[role] = None if val == NONE else val
            if chosen[role]:
                taken.append(chosen[role])
        opt = {}
        for role, (label, cands) in OPTIONAL_ROLES.items():
            guess = detect(cols, cands, taken)
            options = [NONE] + cols
            val = st.selectbox(label, options, index=options.index(guess) if guess in options else 0,
                               key=f"map-{role}-{key}")
            opt[role] = None if val == NONE else val

    page, user, session, time = chosen["page"], chosen["user"], chosen["session"], chosen["time"]
    if not page:
        hero(section)
        st.error("Select the column that holds the webpage name.")
        return

    d = prepare(df, page, time)
    if d.empty:
        hero(section)
        st.error(f"Column `{page}` has no values.")
        return

    sb.markdown("#### Graph settings")
    available = []
    if user and session:
        available.append("session_user")
    if session:
        available.append("session")
    if user:
        available.append("user")
    if not available:
        hero(section)
        st.error("Select a user ID and/or session ID column so page views can be grouped into journeys.")
        return
    mode_choice = sb.selectbox("Navigation sequence", ["auto"] + available,
                               format_func=lambda m: "Auto (session, else user)" if m == "auto" else JOURNEY_MODES[m],
                               key=f"mode-{key}")
    collapse = sb.checkbox("Collapse repeated consecutive pages", value=True, key=f"col-{key}")
    cost_col = sb.selectbox("Navigation cost (Dijkstra, closeness, betweenness)", list(COST_OPTIONS),
                            format_func=COST_OPTIONS.get, key=f"cost-{key}")

    keys_for = {"session_user": (user, session), "session": (session,), "user": (user,)}
    keep = tuple(x for x in (user, session) if x)
    mode_stats = {}
    for m_ in available:
        jj = build_journeys(d, keys_for[m_], bool(time), collapse, keep)
        lens = jj.groupby("_journey").size()
        mode_stats[m_] = {"journeys": int(len(lens)), "multi": int((lens >= 2).sum()),
                          "transitions": int(jj["_next"].notna().sum())}

    fallback_reason = ""
    if mode_choice == "auto":
        session_modes = [m_ for m_ in available if m_ != "user"]
        good = [m_ for m_ in session_modes if mode_stats[m_]["transitions"] >= 0.10 * len(d)]
        if good:
            mode = good[0]
        else:
            mode = "user" if "user" in available else max(available, key=lambda m_: mode_stats[m_]["transitions"])
            if session_modes and mode == "user":
                best = max(session_modes, key=lambda m_: mode_stats[m_]["transitions"])
                s_ = mode_stats[best]
                fallback_reason = (
                    f"Session-level grouping gives only {s_['transitions']:,} transitions: "
                    f"{s_['journeys'] - s_['multi']:,} of {s_['journeys']:,} sessions contain a single page view. "
                    f"Navigation order therefore uses each user's events ordered by time "
                    f"({mode_stats['user']['transitions']:,} transitions).")
    else:
        mode = mode_choice

    j = build_journeys(d, keys_for[mode], bool(time), collapse, keep)
    edges = edge_table(j)
    views = d["_page"].value_counts()
    pages = tuple(sorted(set(j["_page"])))
    G = build_graph(edges, pages, cost_col)
    metrics, eig_note = centrality_table(edges, pages, cost_col, views)
    conv = conversion_flags(d[opt["conversion"]]) if opt["conversion"] else None

    c = SimpleNamespace(df=df, d=d, j=j, edges=edges, G=G, pages=pages, views=views, metrics=metrics,
                        eig_note=eig_note, conv=conv, page=page, user=user, session=session, time=time, opt=opt,
                        mode=mode, auto=mode_choice == "auto", mode_stats=mode_stats, fallback_reason=fallback_reason,
                        collapse=collapse, cost_col=cost_col, key=key, source_name=source_name)

    sb.markdown("---")
    sb.caption(f"{len(df):,} rows · {G.number_of_nodes()} pages · {G.number_of_edges()} edges")

    hero(section)
    {
        "Overview": section_overview,
        "Dataset": section_dataset,
        "Navigation Graph": section_graph,
        "Dijkstra / Navigation Path": section_dijkstra,
        "Centrality Analysis": section_centrality,
        "PageRank": section_pagerank,
        "Community Detection": section_communities,
        "Web Analytics": section_web_analytics,
        "User Behavior": section_behavior,
        "Results / Insights": section_insights,
    }[section](c)


main()
