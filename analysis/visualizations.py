import os
import json

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_price_war")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CHARTS_DIR = os.path.join(DATA_DIR, "charts")
EDA_JSON = os.path.join(DATA_DIR, "eda_results.json")

THEME = "plotly_dark"

PRICE_BUCKETS = [0, 50, 100, 200, 500, float("inf")]
BUCKET_LABELS = ["<50", "50-100", "100-200", "200-500", "500+"]

# Consistent palette — one colour per platform
PLATFORM_COLORS = {
    "lazada": "#FF6900",
    "shopee": "#EE4D2D",
    "zalora": "#654FF0",
}


def _platform_color_seq(platforms: list[str]) -> list[str]:
    return [PLATFORM_COLORS.get(p, "#888888") for p in platforms]


def _save(fig: go.Figure, filename: str) -> None:
    os.makedirs(CHARTS_DIR, exist_ok=True)
    path = os.path.join(CHARTS_DIR, filename)
    fig.write_html(path, include_plotlyjs="cdn")
    print(f"  Saved → {path}")


# ---------------------------------------------------------------------------
# Chart 1 — Platform Price Comparison (Box Plot)
# ---------------------------------------------------------------------------

def chart_price_box(df: pd.DataFrame) -> None:
    priced = df[df["current_price"].notna()].copy()
    platforms = sorted(priced["platform"].unique())

    fig = go.Figure()
    for platform in platforms:
        sub = priced[priced["platform"] == platform]["current_price"]
        fig.add_trace(
            go.Box(
                y=sub,
                name=platform.title(),
                marker_color=PLATFORM_COLORS.get(platform, "#888"),
                boxpoints="outliers",
                line_width=1.5,
            )
        )

    fig.update_layout(
        template=THEME,
        title=dict(text="Price Distribution: Lazada vs Zalora", x=0.5, xanchor="center"),
        yaxis_title="Current Price (RM)",
        xaxis_title="Platform",
        showlegend=False,
        height=550,
    )

    _save(fig, "chart1_price_box.html")


# ---------------------------------------------------------------------------
# Chart 2 — Discount Distribution (Histogram, overlay)
# ---------------------------------------------------------------------------

def chart_discount_histogram(df: pd.DataFrame) -> None:
    disc = df[df["discount_pct"].notna()].copy()
    platforms = sorted(disc["platform"].unique())

    fig = go.Figure()
    for platform in platforms:
        sub = disc[disc["platform"] == platform]["discount_pct"]
        fig.add_trace(
            go.Histogram(
                x=sub,
                name=platform.title(),
                marker_color=PLATFORM_COLORS.get(platform, "#888"),
                opacity=0.7,
                xbins=dict(start=0, end=100, size=5),
            )
        )

    fig.update_layout(
        template=THEME,
        title=dict(text="Discount % Distribution by Platform", x=0.5, xanchor="center"),
        xaxis_title="Discount (%)",
        yaxis_title="Number of Products",
        barmode="overlay",
        legend=dict(title="Platform"),
        height=500,
    )

    _save(fig, "chart2_discount_histogram.html")


# ---------------------------------------------------------------------------
# Chart 3 — Top 10 Brands by Product Count (Horizontal Bar, split by platform)
# ---------------------------------------------------------------------------

def chart_top_brands_bar(df: pd.DataFrame) -> None:
    brand_df = df[df["brand"].notna()].copy()

    # Get top-10 brands by total count
    top10_names = (
        brand_df.groupby("brand")
        .size()
        .nlargest(10)
        .index.tolist()
    )

    # Break down each brand by platform
    subset = brand_df[brand_df["brand"].isin(top10_names)]
    pivot = (
        subset.groupby(["brand", "platform"])
        .size()
        .reset_index(name="count")
    )

    # Order brands by total descending
    brand_order = (
        pivot.groupby("brand")["count"]
        .sum()
        .sort_values(ascending=True)   # ascending so largest is at top of horizontal bar
        .index.tolist()
    )

    platforms = sorted(pivot["platform"].unique())
    fig = go.Figure()

    for platform in platforms:
        sub = pivot[pivot["platform"] == platform].set_index("brand")["count"]
        counts = [int(sub.get(b, 0)) for b in brand_order]
        fig.add_trace(
            go.Bar(
                x=counts,
                y=brand_order,
                name=platform.title(),
                orientation="h",
                marker_color=PLATFORM_COLORS.get(platform, "#888"),
            )
        )

    fig.update_layout(
        template=THEME,
        title=dict(
            text="Top 10 Brands in Malaysian Fashion E-Commerce",
            x=0.5,
            xanchor="center",
        ),
        xaxis_title="Number of Products",
        yaxis_title="Brand",
        barmode="stack",
        legend=dict(title="Platform"),
        height=520,
        margin=dict(l=160),
    )

    _save(fig, "chart3_top_brands_bar.html")


# ---------------------------------------------------------------------------
# Chart 4 — Brand vs Avg Discount Bubble Chart
# ---------------------------------------------------------------------------

def chart_brand_bubble(df: pd.DataFrame) -> None:
    brand_df = df[df["brand"].notna() & df["current_price"].notna() & df["discount_pct"].notna()].copy()

    agg = (
        brand_df.groupby("brand")
        .agg(
            avg_price=("current_price", "mean"),
            avg_discount=("discount_pct", "mean"),
            product_count=("brand", "count"),
        )
        .query("product_count >= 3")
        .reset_index()
    )
    agg["avg_price"] = agg["avg_price"].round(2)
    agg["avg_discount"] = agg["avg_discount"].round(2)

    if agg.empty:
        print("  [skip] chart4 — not enough brand data (need ≥3 products per brand)")
        return

    fig = go.Figure(
        go.Scatter(
            x=agg["avg_price"],
            y=agg["avg_discount"],
            mode="markers+text",
            text=agg["brand"],
            textposition="top center",
            textfont=dict(size=9),
            marker=dict(
                size=agg["product_count"],
                sizemode="area",
                sizeref=2.0 * agg["product_count"].max() / (40 ** 2),
                sizemin=6,
                color=agg["avg_discount"],
                colorscale="Plasma",
                showscale=True,
                colorbar=dict(title="Avg Discount %"),
                line=dict(width=0.5, color="white"),
            ),
            customdata=agg[["product_count", "avg_price", "avg_discount"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Avg Price: RM %{customdata[1]:.2f}<br>"
                "Avg Discount: %{customdata[2]:.1f}%<br>"
                "Products: %{customdata[0]}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        template=THEME,
        title=dict(
            text="Brand Pricing Strategy: Price vs Discount Aggressiveness",
            x=0.5,
            xanchor="center",
        ),
        xaxis_title="Average Price (RM)",
        yaxis_title="Average Discount (%)",
        height=600,
    )

    _save(fig, "chart4_brand_bubble.html")


# ---------------------------------------------------------------------------
# Chart 5 — Price Range Distribution (Donut)
# ---------------------------------------------------------------------------

def chart_price_donut(df: pd.DataFrame) -> None:
    priced = df[df["current_price"].notna()].copy()
    priced["bucket"] = pd.cut(
        priced["current_price"],
        bins=PRICE_BUCKETS,
        labels=BUCKET_LABELS,
        right=False,
    )

    counts = (
        priced.groupby("bucket", observed=True)
        .size()
        .reset_index(name="count")
    )

    fig = go.Figure(
        go.Pie(
            labels=["RM " + str(b) for b in counts["bucket"]],
            values=counts["count"],
            hole=0.45,
            textinfo="label+percent",
            textposition="outside",
            marker=dict(
                colors=px.colors.sequential.Plasma_r[: len(counts)],
                line=dict(color="#1e1e1e", width=2),
            ),
            hovertemplate="<b>%{label}</b><br>%{value} products (%{percent})<extra></extra>",
        )
    )

    fig.update_layout(
        template=THEME,
        title=dict(
            text="Price Range Distribution (All Platforms)",
            x=0.5,
            xanchor="center",
        ),
        height=520,
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=0.5),
        annotations=[
            dict(
                text=f"<b>{priced['current_price'].count()}</b><br>products",
                x=0.5, y=0.5,
                font=dict(size=14, color="white"),
                showarrow=False,
            )
        ],
    )

    _save(fig, "chart5_price_donut.html")


# ---------------------------------------------------------------------------
# Chart 6 — Platform KPI Summary (Grouped Bar)
# ---------------------------------------------------------------------------

def chart_platform_kpi(eda: dict) -> None:
    overview = eda.get("platform_overview", {})
    if not overview:
        print("  [skip] chart6 — platform_overview missing from eda_results.json")
        return

    platforms = sorted(overview.keys())
    avg_prices = [overview[p]["avg_current_price"] or 0 for p in platforms]
    avg_discs = [overview[p]["avg_discount_pct"] or 0 for p in platforms]
    pct_disc = [overview[p]["pct_products_with_discount"] or 0 for p in platforms]

    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=["Avg Price (RM)", "Avg Discount (%)", "% Products Discounted"],
        shared_yaxes=False,
    )

    bar_kwargs = dict(showlegend=False)

    for col_idx, (values, fmt) in enumerate(
        [(avg_prices, ".2f"), (avg_discs, ".1f"), (pct_disc, ".1f")], start=1
    ):
        for platform, val in zip(platforms, values):
            fig.add_trace(
                go.Bar(
                    x=[platform.title()],
                    y=[val],
                    name=platform.title(),
                    marker_color=PLATFORM_COLORS.get(platform, "#888"),
                    text=[f"{val:{fmt}}"],
                    textposition="outside",
                    showlegend=(col_idx == 1),
                ),
                row=1, col=col_idx,
            )

    fig.update_layout(
        template=THEME,
        title=dict(
            text="Platform KPI Comparison: Lazada vs Zalora",
            x=0.5,
            xanchor="center",
        ),
        barmode="group",
        height=480,
        legend=dict(title="Platform", orientation="h", x=0.5, xanchor="center", y=-0.15),
        margin=dict(t=100, b=80),
    )

    _save(fig, "chart6_platform_kpi.html")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Load DB data
    engine = create_engine(DB_URL)
    print("Loading products_cleaned …")
    try:
        df = pd.read_sql("SELECT * FROM products_cleaned ORDER BY id", engine)
    except Exception as exc:
        print(f"[error] Could not load products_cleaned: {exc}")
        print("Hint: run analysis/cleaning.py first.")
        return
    print(f"  Loaded {len(df)} rows")

    # Load pre-computed EDA stats
    if os.path.exists(EDA_JSON):
        with open(EDA_JSON, encoding="utf-8") as f:
            eda = json.load(f)
        print(f"  Loaded EDA results from {EDA_JSON}")
    else:
        print(f"  [warn] {EDA_JSON} not found — charts that depend on it will be skipped")
        eda = {}

    print(f"\nGenerating charts → {CHARTS_DIR}")

    print("\nChart 1 — Price Distribution Box Plot")
    chart_price_box(df)

    print("Chart 2 — Discount Histogram")
    chart_discount_histogram(df)

    print("Chart 3 — Top 10 Brands Bar")
    chart_top_brands_bar(df)

    print("Chart 4 — Brand Bubble Chart")
    chart_brand_bubble(df)

    print("Chart 5 — Price Range Donut")
    chart_price_donut(df)

    print("Chart 6 — Platform KPI Summary")
    chart_platform_kpi(eda)

    print(f"\nAll charts saved to {CHARTS_DIR}")


if __name__ == "__main__":
    main()
