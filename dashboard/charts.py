"""Accessible Plotly styling and reusable chart constructors."""
from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PALETTE = ["#087F8C", "#334E68", "#CB6D35", "#7964A5", "#469C83", "#B14D65"]


def style(fig: go.Figure, height: int = 330) -> go.Figure:
    fig.update_layout(template="plotly_white", height=height, font=dict(family="Arial, sans-serif", color="#243B53", size=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=16, t=18, b=10), colorway=PALETTE,
        legend=dict(title_text="", orientation="h", y=-.22), hoverlabel=dict(font_size=13))
    fig.update_xaxes(showgrid=False, title_font_size=11)
    fig.update_yaxes(gridcolor="#E5EBF0", zeroline=False, title_font_size=11)
    return fig


def line(data: pd.DataFrame, x: str, y: str, currency: bool = False) -> go.Figure:
    fig = px.line(data, x=x, y=y, markers=True, color_discrete_sequence=PALETTE)
    fig.update_traces(line_width=3, marker_size=7,
        hovertemplate=("%{x}<br>GBP %{y:,.2f}<extra></extra>" if currency else "%{x}<br>%{y:,.0f}<extra></extra>"))
    fig.update_yaxes(title="GBP" if currency else y, tickprefix="£" if currency else "")
    return style(fig)


def bar(data: pd.DataFrame, x: str, y: str, horizontal: bool = False, currency: bool = False) -> go.Figure:
    fig = px.bar(data, x=x, y=y, orientation="h" if horizontal else "v", color_discrete_sequence=PALETTE)
    if horizontal:
        fig.update_yaxes(categoryorder="total ascending")
    axis = "x" if horizontal else "y"
    fig.update_traces(hovertemplate=(f"%{{{'y' if horizontal else 'x'}}}<br>"
        + ("GBP " if currency else "") + f"%{{{axis}:,.2f}}<extra></extra>"))
    return style(fig)


def pareto(products: pd.DataFrame) -> go.Figure:
    shares = products.Revenue.cumsum() / products.Revenue.sum()
    fig = go.Figure(go.Scatter(x=list(range(1, len(shares) + 1)), y=shares, mode="lines",
        line=dict(color=PALETTE[0], width=3), fill="tozeroy", fillcolor="rgba(8,127,140,.08)",
        hovertemplate="Stock codes: %{x:,}<br>Revenue share: %{y:.1%}<extra></extra>"))
    fig.add_hline(y=.8, line_dash="dash", line_color=PALETTE[2], annotation_text="80% of revenue")
    fig.update_yaxes(tickformat=".0%", range=[0, 1.05], title="Cumulative revenue share")
    fig.update_xaxes(title="Stock codes ranked by positive revenue")
    return style(fig)


def retention_heatmap(retention: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Heatmap(z=retention.to_numpy(), x=retention.columns.tolist(),
        y=retention.index.astype(str).tolist(), zmin=0, zmax=1,
        colorscale=[[0, "#EFF7F8"], [.5, "#63B5BC"], [1, "#15596A"]],
        colorbar=dict(tickformat=".0%", title="Share"),
        texttemplate="%{z:.0%}", textfont=dict(size=11), hoverongaps=False,
        hovertemplate="Cohort %{y}<br>Month %{x}<br>Active: %{z:.1%}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", title="First observed purchase month", type="category",
                     tickmode="array", tickvals=retention.index.astype(str).tolist())
    fig.update_xaxes(title="Months since first observed purchase", dtick=1)
    return style(fig, height=max(360, len(retention) * 28 + 110))
