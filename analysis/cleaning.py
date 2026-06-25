import os
import re

import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_price_war")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_engine():
    return create_engine(DB_URL)


def load_products(engine) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM products ORDER BY id", engine)


# ---------------------------------------------------------------------------
# Cleaning steps
# ---------------------------------------------------------------------------

def step_normalize_platform(df: pd.DataFrame, summary: dict) -> pd.DataFrame:
    changed = (df["platform"] != df["platform"].str.lower()).sum()
    df["platform"] = df["platform"].str.lower().str.strip()
    summary["normalize_platform"] = f"{changed} values lowercased"
    return df


def step_fill_brand_from_name(df: pd.DataFrame, summary: dict) -> pd.DataFrame:
    mask = df["brand"].isna() & df["product_name"].notna()
    count = mask.sum()

    def _first_word_title(name: str) -> str:
        # Strip leading non-alpha chars, take first word
        word = re.split(r"[\s\-/|]+", name.strip())[0]
        return word.title() if word else None

    df.loc[mask, "brand"] = df.loc[mask, "product_name"].apply(_first_word_title)
    summary["fill_brand_from_name"] = f"{count} brands extracted from product_name"
    return df


def step_cap_price_outliers(df: pd.DataFrame, summary: dict) -> pd.DataFrame:
    capped_total = 0
    for platform, group in df.groupby("platform"):
        if group["current_price"].notna().sum() == 0:
            continue
        p99 = group["current_price"].quantile(0.99)
        mask = df["platform"].eq(platform) & df["current_price"].gt(p99)
        count = mask.sum()
        if count:
            df.loc[mask, "current_price"] = p99
            capped_total += count
    summary["cap_price_outliers"] = f"{capped_total} current_price values capped at 99th pct per platform"
    return df


def step_fill_discount_pct(df: pd.DataFrame, summary: dict) -> pd.DataFrame:
    """Calculate discount_pct from prices where it is missing."""
    mask = (
        df["discount_pct"].isna()
        & df["current_price"].notna()
        & df["original_price"].notna()
        & df["original_price"].gt(0)
        & df["original_price"].gt(df["current_price"])
    )
    count = mask.sum()
    df.loc[mask, "discount_pct"] = (
        (df.loc[mask, "original_price"] - df.loc[mask, "current_price"])
        / df.loc[mask, "original_price"]
        * 100
    ).round(2)
    summary["fill_discount_pct"] = f"{count} discount_pct values calculated from prices"
    return df


def step_fill_original_price(df: pd.DataFrame, summary: dict) -> pd.DataFrame:
    """Reverse-calculate original_price from current_price and discount_pct."""
    mask = (
        df["original_price"].isna()
        & df["current_price"].notna()
        & df["discount_pct"].notna()
        & df["discount_pct"].gt(0)
        & df["discount_pct"].lt(100)
    )
    count = mask.sum()
    df.loc[mask, "original_price"] = (
        df.loc[mask, "current_price"] / (1 - df.loc[mask, "discount_pct"] / 100)
    ).round(2)
    summary["fill_original_price"] = f"{count} original_price values reverse-calculated"
    return df


def step_parse_scraped_at(df: pd.DataFrame, summary: dict) -> pd.DataFrame:
    before_nulls = df["scraped_at"].isna().sum()
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce", utc=False)
    after_nulls = df["scraped_at"].isna().sum()
    new_nulls = max(0, after_nulls - before_nulls)
    summary["parse_scraped_at"] = (
        f"scraped_at converted to datetime; {new_nulls} unparseable values set to NaT"
    )
    return df


def step_drop_junk_names(df: pd.DataFrame, summary: dict) -> pd.DataFrame:
    before = len(df)
    # Drop rows whose product_name is blank, a single character, or purely numeric
    junk = (
        df["product_name"].isna()
        | (df["product_name"].str.strip().str.len() <= 1)
        | df["product_name"].str.strip().str.match(r"^\d+$")
    )
    df = df[~junk].reset_index(drop=True)
    dropped = before - len(df)
    summary["drop_junk_names"] = f"{dropped} rows dropped (single char / numeric product_name)"
    return df


# ---------------------------------------------------------------------------
# Save + report
# ---------------------------------------------------------------------------

def save_cleaned(df: pd.DataFrame, engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS products_cleaned"))
    df.to_sql(
        "products_cleaned",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=500,
    )


def print_summary(rows_before: int, rows_after: int, summary: dict) -> None:
    print("\n" + "=" * 55)
    print("  CLEANING SUMMARY")
    print("=" * 55)
    print(f"  Rows before : {rows_before}")
    print(f"  Rows after  : {rows_after}")
    print(f"  Rows dropped: {rows_before - rows_after}")
    print("-" * 55)
    for step, message in summary.items():
        print(f"  [{step}]")
        print(f"    {message}")
    print("=" * 55)


def main():
    engine = get_engine()

    print("Loading products table …")
    df = load_products(engine)
    rows_before = len(df)
    print(f"  Loaded {rows_before} rows")

    summary: dict[str, str] = {}

    print("Running cleaning steps …")
    df = step_normalize_platform(df, summary)
    df = step_fill_brand_from_name(df, summary)
    df = step_cap_price_outliers(df, summary)
    df = step_fill_discount_pct(df, summary)
    df = step_fill_original_price(df, summary)
    df = step_parse_scraped_at(df, summary)
    df = step_drop_junk_names(df, summary)

    rows_after = len(df)

    print(f"Saving {rows_after} cleaned rows to products_cleaned …")
    save_cleaned(df, engine)
    print("  Done.")

    print_summary(rows_before, rows_after, summary)


if __name__ == "__main__":
    main()
