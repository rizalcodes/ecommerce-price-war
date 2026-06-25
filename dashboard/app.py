import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from sqlalchemy import create_engine
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config & constants
# ---------------------------------------------------------------------------

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
)

DB_URL = (
    f"postgresql+psycopg2://{os.getenv('DB_USER', 'postgres')}:"
    f"{os.getenv('DB_PASSWORD', '')}@"
    f"{os.getenv('DB_HOST', 'localhost')}:"
    f"{os.getenv('DB_PORT', '5432')}/"
    f"{os.getenv('DB_NAME', 'ecommerce_price_war')}"
)

THEME = "plotly_dark"

PLATFORM_COLORS = {
    "lazada": "#FF6900",
    "shopee": "#EE4D2D",
    "zalora": "#654FF0",
}

PRICE_BUCKETS = [0, 50, 100, 200, 500, float("inf")]
BUCKET_LABELS = ["<50", "50-100", "100-200", "200-500", "500+"]

st.set_page_config(
    page_title="E-Commerce Price War: Lazada vs Zalora",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject dark-mode overrides so the Streamlit chrome matches plotly_dark
st.markdown(
    """
    <style>
        [data-testid="stAppViewContainer"] { background-color: #0e1117; }
        [data-testid="stSidebar"]          { background-color: #161b22; }
        .kpi-card {
            background: #1e2530;
            border-radius: 10px;
            padding: 18px 22px;
            text-align: center;
        }
        .kpi-label { color: #8b9ab5; font-size: 13px; margin-bottom: 4px; }
        .kpi-value { color: #ffffff; font-size: 30px; font-weight: 700; }
        .kpi-sub   { color: #6ee7b7; font-size: 12px; margin-top: 2px; }
        .section-header {
            color: #c9d1e0;
            font-size: 17px;
            font-weight: 600;
            border-bottom: 1px solid #2d3748;
            padding-bottom: 6px;
            margin-bottom: 16px;
        }
        footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner="Loading data from database …")
def load_data() -> pd.DataFrame:
    try:
        engine = create_engine(DB_URL)
        df = pd.read_sql("SELECT * FROM products_cleaned ORDER BY id", engine)
        return df
    except Exception as exc:
        st.error(f"Database connection failed: {exc}")
        st.stop()


def _platform_color_seq(platforms):
    return [PLATFORM_COLORS.get(p, "#888888") for p in platforms]


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

def build_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.title("Filters")

    # Platform
    all_platforms = sorted(df["platform"].dropna().unique().tolist())
    selected_platforms = st.sidebar.multiselect(
        "Platform",
        options=all_platforms,
        default=all_platforms,
        format_func=str.title,
    )

    # Price range
    max_price = float(df["current_price"].max() or 1000)
    price_min, price_max = st.sidebar.slider(
        "Price Range (RM)",
        min_value=0.0,
        max_value=max_price,
        value=(0.0, max_price),
        step=10.0,
        format="RM%.0f",
    )

    # Top-20 brands
    top20_brands = (
        df[df["brand"].notna()]
        .groupby("brand")
        .size()
        .nlargest(20)
        .index.tolist()
    )
    selected_brands = st.sidebar.multiselect(
        "Brand (top 20)",
        options=top20_brands,
        default=[],
        placeholder="All brands",
    )

    # Min discount
    min_discount = st.sidebar.slider(
        "Minimum Discount %",
        min_value=0,
        max_value=80,
        value=0,
        step=5,
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("Data scraped from Lazada & Zalora Malaysia")

    # Apply filters
    mask = (
        df["platform"].isin(selected_platforms)
        & df["current_price"].between(price_min, price_max, inclusive="both")
    )
    if selected_brands:
        mask &= df["brand"].isin(selected_brands)
    if min_discount > 0:
        mask &= df["discount_pct"].fillna(0) >= min_discount

    return df[mask].copy()


# ---------------------------------------------------------------------------
# Section 1 — KPI Cards
# ---------------------------------------------------------------------------

def render_kpi_cards(df: pd.DataFrame) -> None:
    st.markdown('<p class="section-header">Overview</p>', unsafe_allow_html=True)

    total = len(df)
    avg_price = df["current_price"].mean()
    avg_disc = df["discount_pct"].mean()
    pct_disc = df["discount_pct"].notna().mean() * 100

    c1, c2, c3, c4 = st.columns(4)

    def _card(col, label, value, sub=""):
        col.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-sub">{sub}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    _card(c1, "Total Products", f"{total:,}", "in filtered view")
    _card(
        c2,
        "Avg Price",
        f"RM {avg_price:.2f}" if pd.notna(avg_price) else "—",
        "current price",
    )
    _card(
        c3,
        "Avg Discount",
        f"{avg_disc:.1f}%" if pd.notna(avg_disc) else "—",
        "across discounted items",
    )
    _card(c4, "% With Discount", f"{pct_disc:.1f}%", "of filtered products")


# ---------------------------------------------------------------------------
# Section 2 — Platform Comparison
# ---------------------------------------------------------------------------

def render_platform_comparison(df: pd.DataFrame) -> None:
    st.markdown('<p class="section-header">Platform Comparison</p>', unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    # Box plot — price distribution
    with col_left:
        priced = df[df["current_price"].notna()]
        platforms = sorted(priced["platform"].unique())
        fig = go.Figure()
        for p in platforms:
            fig.add_trace(
                go.Box(
                    y=priced[priced["platform"] == p]["current_price"],
                    name=p.title(),
                    marker_color=PLATFORM_COLORS.get(p, "#888"),
                    boxpoints="outliers",
                    line_width=1.5,
                )
            )
        fig.update_layout(
            template=THEME,
            title="Price Distribution by Platform",
            yaxis_title="Current Price (RM)",
            showlegend=False,
            height=400,
            margin=dict(t=50, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Bar chart — avg discount by platform
    with col_right:
        disc_df = (
            df[df["discount_pct"].notna()]
            .groupby("platform")["discount_pct"]
            .mean()
            .round(2)
            .reset_index()
            .sort_values("discount_pct", ascending=False)
        )
        fig2 = go.Figure(
            go.Bar(
                x=[p.title() for p in disc_df["platform"]],
                y=disc_df["discount_pct"],
                marker_color=_platform_color_seq(disc_df["platform"]),
                text=disc_df["discount_pct"].apply(lambda v: f"{v:.1f}%"),
                textposition="outside",
            )
        )
        fig2.update_layout(
            template=THEME,
            title="Avg Discount % by Platform",
            yaxis_title="Avg Discount (%)",
            showlegend=False,
            height=400,
            margin=dict(t=50, b=30),
        )
        st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Section 3 — Brand Analysis
# ---------------------------------------------------------------------------

def render_brand_analysis(df: pd.DataFrame) -> None:
    st.markdown('<p class="section-header">Brand Analysis</p>', unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    brand_df = df[df["brand"].notna()]

    # Top 10 brands — horizontal bar
    with col_left:
        top10 = (
            brand_df.groupby("brand")
            .size()
            .nlargest(10)
            .sort_values(ascending=True)   # ascending so largest is at top
            .reset_index(name="count")
        )
        fig = go.Figure(
            go.Bar(
                x=top10["count"],
                y=top10["brand"],
                orientation="h",
                marker_color="#654FF0",
                text=top10["count"],
                textposition="outside",
            )
        )
        fig.update_layout(
            template=THEME,
            title="Top 10 Brands by Product Count",
            xaxis_title="Number of Products",
            height=420,
            margin=dict(t=50, l=140, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Bubble chart — price vs discount
    with col_right:
        bubble = (
            brand_df[brand_df["current_price"].notna() & brand_df["discount_pct"].notna()]
            .groupby("brand")
            .agg(
                avg_price=("current_price", "mean"),
                avg_discount=("discount_pct", "mean"),
                count=("brand", "count"),
            )
            .query("count >= 3")
            .reset_index()
        )

        if bubble.empty:
            st.info("Not enough brand data for bubble chart (need ≥3 products per brand).")
        else:
            bubble["avg_price"] = bubble["avg_price"].round(2)
            bubble["avg_discount"] = bubble["avg_discount"].round(2)
            sizeref = 2.0 * bubble["count"].max() / (40 ** 2)

            fig2 = go.Figure(
                go.Scatter(
                    x=bubble["avg_price"],
                    y=bubble["avg_discount"],
                    mode="markers+text",
                    text=bubble["brand"],
                    textposition="top center",
                    textfont=dict(size=8),
                    marker=dict(
                        size=bubble["count"],
                        sizemode="area",
                        sizeref=sizeref,
                        sizemin=5,
                        color=bubble["avg_discount"],
                        colorscale="Plasma",
                        showscale=True,
                        colorbar=dict(title="Avg %", thickness=12),
                        line=dict(width=0.5, color="white"),
                    ),
                    customdata=bubble[["count", "avg_price", "avg_discount"]].values,
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        "Avg Price: RM %{customdata[1]:.2f}<br>"
                        "Avg Discount: %{customdata[2]:.1f}%<br>"
                        "Products: %{customdata[0]}<extra></extra>"
                    ),
                )
            )
            fig2.update_layout(
                template=THEME,
                title="Brand: Price vs Discount Aggressiveness",
                xaxis_title="Avg Price (RM)",
                yaxis_title="Avg Discount (%)",
                height=420,
                margin=dict(t=50, b=30),
            )
            st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Section 4 — Price Distribution
# ---------------------------------------------------------------------------

def render_price_distribution(df: pd.DataFrame) -> None:
    st.markdown('<p class="section-header">Price Distribution</p>', unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    priced = df[df["current_price"].notna()].copy()
    priced["bucket"] = pd.cut(
        priced["current_price"],
        bins=PRICE_BUCKETS,
        labels=BUCKET_LABELS,
        right=False,
    )
    bucket_counts = (
        priced.groupby("bucket", observed=True)
        .size()
        .reset_index(name="count")
    )

    # Donut chart
    with col_left:
        fig = go.Figure(
            go.Pie(
                labels=["RM " + str(b) for b in bucket_counts["bucket"]],
                values=bucket_counts["count"],
                hole=0.45,
                textinfo="label+percent",
                textposition="outside",
                marker=dict(
                    colors=px.colors.sequential.Plasma_r[: len(bucket_counts)],
                    line=dict(color="#0e1117", width=2),
                ),
                hovertemplate="<b>%{label}</b><br>%{value} products (%{percent})<extra></extra>",
            )
        )
        fig.update_layout(
            template=THEME,
            title="Price Range Distribution",
            height=420,
            margin=dict(t=50, b=30),
            annotations=[
                dict(
                    text=f"<b>{len(priced):,}</b><br>products",
                    x=0.5, y=0.5,
                    font=dict(size=13, color="white"),
                    showarrow=False,
                )
            ],
        )
        st.plotly_chart(fig, use_container_width=True)

    # Discount histogram
    with col_right:
        disc = df[df["discount_pct"].notna()]
        platforms = sorted(disc["platform"].unique())
        fig2 = go.Figure()
        for p in platforms:
            sub = disc[disc["platform"] == p]["discount_pct"]
            fig2.add_trace(
                go.Histogram(
                    x=sub,
                    name=p.title(),
                    marker_color=PLATFORM_COLORS.get(p, "#888"),
                    opacity=0.7,
                    xbins=dict(start=0, end=100, size=5),
                )
            )
        fig2.update_layout(
            template=THEME,
            title="Discount % Distribution by Platform",
            xaxis_title="Discount (%)",
            yaxis_title="Number of Products",
            barmode="overlay",
            legend=dict(title="Platform"),
            height=420,
            margin=dict(t=50, b=30),
        )
        st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Section 5 — Raw Data Table
# ---------------------------------------------------------------------------

def render_data_table(df: pd.DataFrame) -> None:
    st.markdown('<p class="section-header">Raw Data</p>', unsafe_allow_html=True)

    # Search box
    search = st.text_input(
        "Search product name or brand",
        placeholder="e.g. dress, H&M, Nike …",
    )

    display_cols = [
        "platform", "brand", "product_name",
        "current_price", "original_price", "discount_pct",
        "rating", "review_count", "category", "scraped_at",
    ]
    display_cols = [c for c in display_cols if c in df.columns]

    view = df[display_cols].copy()

    if search.strip():
        term = search.strip().lower()
        name_match = view["product_name"].str.lower().str.contains(term, na=False)
        brand_match = view["brand"].str.lower().str.contains(term, na=False) if "brand" in view.columns else pd.Series(False, index=view.index)
        view = view[name_match | brand_match]

    st.caption(f"Showing {len(view):,} of {len(df):,} products")
    st.dataframe(view, use_container_width=True, height=380)

    csv_bytes = view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download as CSV",
        data=csv_bytes,
        file_name="ecommerce_price_war_filtered.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# App entry point
# ---------------------------------------------------------------------------

def main():
    # Header
    st.title("E-Commerce Price War: Lazada vs Zalora")
    st.caption("Live data from products_cleaned · refresh every 5 minutes")

    df_full = load_data()
    df = build_sidebar(df_full)

    if df.empty:
        st.warning("No products match the current filters. Try widening your selection.")
        return

    st.markdown("---")
    render_kpi_cards(df)

    st.markdown("---")
    render_platform_comparison(df)

    st.markdown("---")
    render_brand_analysis(df)

    st.markdown("---")
    render_price_distribution(df)

    st.markdown("---")
    render_data_table(df)

    # Footer
    st.markdown(
        """
        <div style="text-align:center; color:#4a5568; font-size:12px; margin-top:48px; padding-top:16px; border-top:1px solid #2d3748;">
            Data scraped from Lazada &amp; Zalora Malaysia &nbsp;|&nbsp; Built with Python + Streamlit
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
