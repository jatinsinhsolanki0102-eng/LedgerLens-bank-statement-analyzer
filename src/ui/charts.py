"""Shared Plotly figures and visual theme."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.utils.amount_utils import format_currency

TEAL = "#0F8B8D"
TEAL_LIGHT = "#73C7C2"
CORAL = "#D96C5F"
GOLD = "#D9A441"
NAVY = "#102A43"
MUTED = "#627D98"
GRID = "#E7EEF4"
PALETTE = (
    TEAL,
    CORAL,
    GOLD,
    "#5C7AEA",
    "#8E6BBF",
    "#4FA3D1",
    "#E0836B",
    "#4C9F70",
    "#B07AA1",
    "#9C8A6B",
    "#5B8C85",
    "#CC8A2E",
    "#7B8794",
    "#A66DD4",
    "#3BA99C",
)

PLOTLY_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
}


def apply_chart_theme(
    figure: go.Figure, height: int = 340, show_legend: bool = True
) -> go.Figure:
    figure.update_layout(
        height=height,
        margin={"l": 12, "r": 18, "t": 24, "b": 12},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, Segoe UI, sans-serif", "color": NAVY, "size": 12},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"size": 11},
        },
        showlegend=show_legend,
        hoverlabel={"bgcolor": "white", "font_color": NAVY, "bordercolor": GRID},
    )
    figure.update_xaxes(
        showgrid=False,
        zeroline=False,
        tickfont={"color": MUTED, "size": 11},
        title_font={"color": MUTED, "size": 11},
    )
    figure.update_yaxes(
        gridcolor=GRID,
        zeroline=False,
        tickfont={"color": MUTED, "size": 11},
        title_font={"color": MUTED, "size": 11},
    )
    return figure


def category_expense_bar(category_data: pd.DataFrame, height: int = 360) -> go.Figure:
    """Horizontal ranked bar chart for debit spend by category."""

    dataframe = category_data.sort_values("Amount", ascending=True).tail(12)
    colors = [PALETTE[index % len(PALETTE)] for index in range(len(dataframe))]
    figure = go.Figure(
        go.Bar(
            x=dataframe["Amount"],
            y=dataframe["Category"],
            orientation="h",
            marker={"color": colors, "line": {"width": 0}},
            text=[format_currency(value) for value in dataframe["Amount"]],
            textposition="outside",
            textfont={"size": 10, "color": MUTED},
            hovertemplate="%{y}<br>%{x:,.2f}<extra></extra>",
        )
    )
    figure.update_layout(xaxis_title="Expense amount", yaxis_title=None)
    return apply_chart_theme(figure, height=height, show_legend=False)


def category_donut(category_data: pd.DataFrame, height: int = 360) -> go.Figure:
    dataframe = category_data.sort_values("Amount", ascending=False)
    figure = go.Figure(
        go.Pie(
            labels=dataframe["Category"],
            values=dataframe["Amount"],
            hole=0.62,
            marker={"colors": list(PALETTE[: len(dataframe)])},
            textinfo="percent",
            textfont={"size": 11},
            hovertemplate="%{label}<br>%{value:,.2f}<br>%{percent}<extra></extra>",
        )
    )
    return apply_chart_theme(figure, height=height)


def monthly_cashflow_bar(monthly_data: pd.DataFrame, height: int = 360) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=monthly_data["Month"],
            y=monthly_data["Income"],
            name="Income",
            marker_color=TEAL,
            hovertemplate="%{x}<br>Income: %{y:,.2f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            x=monthly_data["Month"],
            y=monthly_data["Expenses"],
            name="Expenses",
            marker_color=CORAL,
            hovertemplate="%{x}<br>Expenses: %{y:,.2f}<extra></extra>",
        )
    )
    figure.update_layout(barmode="group", xaxis_title=None, yaxis_title="Amount")
    return apply_chart_theme(figure, height=height)


def monthly_net_line(monthly_data: pd.DataFrame, height: int = 320) -> go.Figure:
    colors = [TEAL if value >= 0 else CORAL for value in monthly_data["Net"]]
    figure = go.Figure(
        go.Bar(
            x=monthly_data["Month"],
            y=monthly_data["Net"],
            marker_color=colors,
            hovertemplate="%{x}<br>Net: %{y:,.2f}<extra></extra>",
        )
    )
    figure.add_hline(y=0, line_color="#9FB3C8", line_width=1)
    figure.update_layout(xaxis_title=None, yaxis_title="Net cash flow")
    return apply_chart_theme(figure, height=height, show_legend=False)


def balance_trend(transactions: list, height: int = 320) -> go.Figure:
    dated = [
        transaction
        for transaction in transactions
        if transaction.transaction_date is not None and transaction.balance is not None
    ]
    dated = sorted(dated, key=lambda item: (item.transaction_date, item.source_page or 0))
    figure = go.Figure(
        go.Scatter(
            x=[transaction.transaction_date for transaction in dated],
            y=[transaction.balance for transaction in dated],
            mode="lines+markers",
            line={"color": TEAL, "width": 2.4},
            marker={"size": 5, "color": TEAL},
            fill="tozeroy",
            fillcolor="rgba(15, 139, 141, 0.10)",
            hovertemplate="%{x|%d %b %Y}<br>Balance: %{y:,.2f}<extra></extra>",
        )
    )
    figure.update_layout(xaxis_title=None, yaxis_title="Balance")
    return apply_chart_theme(figure, height=height, show_legend=False)


def debit_credit_distribution(transactions: list, height: int = 320) -> go.Figure:
    debit_count = sum(1 for transaction in transactions if (transaction.debit or 0) > 0)
    credit_count = sum(1 for transaction in transactions if (transaction.credit or 0) > 0)
    figure = go.Figure(
        go.Bar(
            x=["Debit", "Credit"],
            y=[debit_count, credit_count],
            marker_color=[CORAL, TEAL],
            text=[debit_count, credit_count],
            textposition="outside",
            hovertemplate="%{x}<br>%{y} transactions<extra></extra>",
        )
    )
    figure.update_layout(xaxis_title=None, yaxis_title="Transactions")
    return apply_chart_theme(figure, height=height, show_legend=False)
