import os
import json
from datetime import datetime

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_price_war")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "eda_results.json")

PRICE_BUCKETS = [0, 50, 100, 200, 500, float("inf")]
BUCKET_LABELS = ["<50", "50-100", "100-200", "200-500", "500+"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_safe(obj):
    """Recursively convert numpy/pandas types to Python native for JSON dump."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# A. Platform Overview
# ---------------------------------------------------------------------------

def analyse_platform_overview(df: pd.DataFrame) -> dict:
    _section("A. PLATFORM OVERVIEW")

    results = {}
    for platform, grp in df.groupby("platform"):
        total = len(grp)
        avg_price = grp["current_price"].mean()
        avg_disc = grp["discount_pct"].mean()
        pct_discounted = grp["discount_pct"].notna().mean() * 100

        results[platform] = {
            "total_products": int(total),
            "avg_current_price": round(float(avg_price), 2) if pd.notna(avg_price) else None,
            "avg_discount_pct": round(float(avg_disc), 2) if pd.notna(avg_disc) else None,
            "pct_products_with_discount": round(pct_discounted, 2),
        }

        print(f"\n  [{platform.upper()}]")
        print(f"    Total products          : {total}")
        print(f"    Avg current price       : RM {avg_price:.2f}" if pd.notna(avg_price) else "    Avg current price       : N/A")
        print(f"    Avg discount %          : {avg_disc:.1f}%" if pd.notna(avg_disc) else "    Avg discount %          : N/A")
        print(f"    % with a discount       : {pct_discounted:.1f}%")

    return results


# ---------------------------------------------------------------------------
# B. Discount Behaviour
# ---------------------------------------------------------------------------

def analyse_discount_behaviour(df: pd.DataFrame) -> dict:
    _section("B. DISCOUNT BEHAVIOUR")

    disc = df["discount_pct"].dropna()
    dist = {
        "min": round(float(disc.min()), 2) if len(disc) else None,
        "max": round(float(disc.max()), 2) if len(disc) else None,
        "mean": round(float(disc.mean()), 2) if len(disc) else None,
        "median": round(float(disc.median()), 2) if len(disc) else None,
        "count_above_50pct": int((disc > 50).sum()),
    }

    print("\n  Discount distribution (all platforms):")
    print(f"    Min     : {dist['min']}%")
    print(f"    Max     : {dist['max']}%")
    print(f"    Mean    : {dist['mean']}%")
    print(f"    Median  : {dist['median']}%")
    print(f"    >50%    : {dist['count_above_50pct']} products")

    # Top 10 most discounted
    top10 = (
        df[df["discount_pct"].notna()]
        .nlargest(10, "discount_pct")[
            ["platform", "brand", "product_name", "current_price", "discount_pct"]
        ]
        .reset_index(drop=True)
    )
    top10_records = top10.to_dict("records")

    print("\n  Top 10 most discounted products:")
    for i, row in top10.iterrows():
        name = (row["product_name"] or "")[:55]
        print(f"    {i+1:>2}. [{row['platform']:<8}] {row['discount_pct']:>5.1f}%  RM {row['current_price']:>8.2f}  {name}")

    # >50% per platform
    over50_by_platform = (
        df[df["discount_pct"] > 50]
        .groupby("platform")
        .size()
        .to_dict()
    )
    over50_by_platform = {k: int(v) for k, v in over50_by_platform.items()}

    print("\n  Products with >50% discount per platform:")
    for platform, count in sorted(over50_by_platform.items()):
        print(f"    {platform:<12}: {count}")

    return {
        "distribution": dist,
        "top10_most_discounted": [_json_safe(r) for r in top10_records],
        "over_50pct_per_platform": over50_by_platform,
    }


# ---------------------------------------------------------------------------
# C. Brand Analysis
# ---------------------------------------------------------------------------

def analyse_brands(df: pd.DataFrame) -> dict:
    _section("C. BRAND ANALYSIS")

    brand_df = df[df["brand"].notna()]

    # Top 10 by product count
    top_by_count = (
        brand_df.groupby("brand")
        .size()
        .nlargest(10)
        .reset_index(name="product_count")
    )

    print("\n  Top 10 brands by product count:")
    for _, row in top_by_count.iterrows():
        print(f"    {row['brand']:<35} {row['product_count']:>5} products")

    # Top 10 by avg discount (min 3 products to be meaningful)
    brand_disc = (
        brand_df[brand_df["discount_pct"].notna()]
        .groupby("brand")
        .agg(avg_discount=("discount_pct", "mean"), count=("discount_pct", "count"))
        .query("count >= 3")
        .nlargest(10, "avg_discount")
        .reset_index()
    )
    brand_disc["avg_discount"] = brand_disc["avg_discount"].round(2)

    print("\n  Top 10 brands by avg discount % (min 3 products):")
    for _, row in brand_disc.iterrows():
        print(f"    {row['brand']:<35} {row['avg_discount']:>6.1f}%  ({int(row['count'])} products)")

    # Top 10 by avg price (min 3 products)
    brand_price = (
        brand_df[brand_df["current_price"].notna()]
        .groupby("brand")
        .agg(avg_price=("current_price", "mean"), count=("current_price", "count"))
        .query("count >= 3")
        .nlargest(10, "avg_price")
        .reset_index()
    )
    brand_price["avg_price"] = brand_price["avg_price"].round(2)

    print("\n  Top 10 brands by avg current price (min 3 products):")
    for _, row in brand_price.iterrows():
        print(f"    {row['brand']:<35} RM {row['avg_price']:>8.2f}  ({int(row['count'])} products)")

    return {
        "top10_by_product_count": top_by_count.to_dict("records"),
        "top10_by_avg_discount": brand_disc[["brand", "avg_discount", "count"]].to_dict("records"),
        "top10_by_avg_price": brand_price[["brand", "avg_price", "count"]].to_dict("records"),
    }


# ---------------------------------------------------------------------------
# D. Price Analysis
# ---------------------------------------------------------------------------

def analyse_prices(df: pd.DataFrame) -> dict:
    _section("D. PRICE ANALYSIS")

    priced = df[df["current_price"].notna()].copy()
    priced["price_bucket"] = pd.cut(
        priced["current_price"],
        bins=PRICE_BUCKETS,
        labels=BUCKET_LABELS,
        right=False,
    )

    # Overall bucket distribution
    bucket_counts = (
        priced.groupby("price_bucket", observed=True)
        .size()
        .reset_index(name="product_count")
    )

    print("\n  Price range buckets (all platforms):")
    for _, row in bucket_counts.iterrows():
        print(f"    RM {row['price_bucket']:<12} : {row['product_count']:>5} products")

    # Avg price per platform per bucket
    avg_by_bucket = (
        priced.groupby(["platform", "price_bucket"], observed=True)["current_price"]
        .mean()
        .round(2)
        .reset_index()
        .rename(columns={"current_price": "avg_price"})
    )

    print("\n  Avg price per platform per bucket:")
    for platform in sorted(avg_by_bucket["platform"].unique()):
        sub = avg_by_bucket[avg_by_bucket["platform"] == platform]
        print(f"\n    [{platform.upper()}]")
        for _, row in sub.iterrows():
            if pd.notna(row["avg_price"]):
                print(f"      RM {row['price_bucket']:<12} : RM {row['avg_price']:>8.2f}")

    # Most expensive / cheapest per platform
    extremes = {}
    print("\n  Most expensive vs cheapest per platform:")
    for platform, grp in priced.groupby("platform"):
        cheapest = grp.loc[grp["current_price"].idxmin()]
        priciest = grp.loc[grp["current_price"].idxmax()]
        extremes[platform] = {
            "cheapest": {
                "product_name": cheapest["product_name"],
                "brand": cheapest.get("brand"),
                "current_price": float(cheapest["current_price"]),
            },
            "most_expensive": {
                "product_name": priciest["product_name"],
                "brand": priciest.get("brand"),
                "current_price": float(priciest["current_price"]),
            },
        }
        print(f"\n    [{platform.upper()}]")
        print(f"      Cheapest  : RM {cheapest['current_price']:.2f} — {str(cheapest['product_name'])[:60]}")
        print(f"      Priciest  : RM {priciest['current_price']:.2f} — {str(priciest['product_name'])[:60]}")

    return {
        "bucket_counts": bucket_counts.to_dict("records"),
        "avg_price_per_platform_per_bucket": avg_by_bucket.to_dict("records"),
        "extremes_per_platform": extremes,
    }


# ---------------------------------------------------------------------------
# E. Key Insights
# ---------------------------------------------------------------------------

def derive_key_insights(df: pd.DataFrame, platform_ov: dict, disc_beh: dict) -> list[str]:
    _section("E. KEY INSIGHTS")

    insights = []

    # 1. Which platform has the deepest average discount?
    disc_platforms = {
        p: v["avg_discount_pct"]
        for p, v in platform_ov.items()
        if v["avg_discount_pct"] is not None
    }
    if disc_platforms:
        top_disc_platform = max(disc_platforms, key=lambda p: disc_platforms[p])
        insights.append(
            f"{top_disc_platform.title()} offers the deepest average discount at "
            f"{disc_platforms[top_disc_platform]:.1f}%, making it the most aggressive "
            f"discounter among the tracked platforms."
        )

    # 2. Platform with highest % of discounted products
    pct_disc = {
        p: v["pct_products_with_discount"]
        for p, v in platform_ov.items()
    }
    most_disc_pct_platform = max(pct_disc, key=lambda p: pct_disc[p])
    insights.append(
        f"{most_disc_pct_platform.title()} has the highest share of discounted products "
        f"({pct_disc[most_disc_pct_platform]:.1f}% of listings carry a discount), "
        f"suggesting a heavy promotional pricing strategy."
    )

    # 3. Products with extreme discounts
    extreme = disc_beh["distribution"]["count_above_50pct"]
    total_prods = len(df)
    insights.append(
        f"{extreme} products ({extreme/total_prods*100:.1f}% of the catalogue) carry "
        f"discounts greater than 50%, indicating widespread flash-sale or clearance pricing."
    )

    # 4. Price range observation — which bucket has the most listings?
    priced = df[df["current_price"].notna()].copy()
    priced["price_bucket"] = pd.cut(
        priced["current_price"],
        bins=PRICE_BUCKETS,
        labels=BUCKET_LABELS,
        right=False,
    )
    top_bucket = priced["price_bucket"].value_counts().idxmax()
    top_bucket_count = priced["price_bucket"].value_counts().max()
    insights.append(
        f"The RM {top_bucket} price range dominates the catalogue with {top_bucket_count} "
        f"products ({top_bucket_count/total_prods*100:.1f}%), reflecting a mass-market "
        f"mid-range pricing cluster."
    )

    # 5. Platform with highest average price
    avg_prices = {
        p: v["avg_current_price"]
        for p, v in platform_ov.items()
        if v["avg_current_price"] is not None
    }
    if avg_prices:
        premium_platform = max(avg_prices, key=lambda p: avg_prices[p])
        insights.append(
            f"{premium_platform.title()} carries the highest average price at "
            f"RM {avg_prices[premium_platform]:.2f}, positioning it as the most "
            f"premium platform in this comparison."
        )

    print()
    for i, insight in enumerate(insights, 1):
        print(f"  {i}. {insight}")

    return insights


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    engine = create_engine(DB_URL)

    print("Loading products_cleaned …")
    try:
        df = pd.read_sql("SELECT * FROM products_cleaned ORDER BY id", engine)
    except Exception as exc:
        print(f"[error] Could not load products_cleaned: {exc}")
        print("Hint: run analysis/cleaning.py first to create the products_cleaned table.")
        return

    print(f"  Loaded {len(df)} rows across {df['platform'].nunique()} platform(s): "
          f"{', '.join(sorted(df['platform'].unique()))}")

    results: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_rows": len(df),
    }

    results["platform_overview"] = analyse_platform_overview(df)
    results["discount_behaviour"] = analyse_discount_behaviour(df)
    results["brand_analysis"] = analyse_brands(df)
    results["price_analysis"] = analyse_prices(df)
    results["key_insights"] = derive_key_insights(
        df,
        results["platform_overview"],
        results["discount_behaviour"],
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(_json_safe(results), f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
