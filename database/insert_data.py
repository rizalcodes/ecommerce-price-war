import os
import csv
import glob
from collections import defaultdict

import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "ecommerce_price_war"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")

INSERT_SQL = """
    INSERT INTO products (
        platform, product_name, brand,
        current_price, original_price, discount_pct,
        rating, review_count, product_url,
        scraped_at, category
    ) VALUES (
        %(platform)s, %(product_name)s, %(brand)s,
        %(current_price)s, %(original_price)s, %(discount_pct)s,
        %(rating)s, %(review_count)s, %(product_url)s,
        %(scraped_at)s, %(category)s
    )
    ON CONFLICT (product_url) DO NOTHING;
"""

NUMERIC_FIELDS = {"current_price", "original_price", "discount_pct", "rating"}
INT_FIELDS     = {"review_count"}


def _coerce_row(row: dict) -> dict:
    """Convert empty strings to None and cast numeric fields."""
    out = {}
    for key, val in row.items():
        if val == "" or val is None:
            out[key] = None
        elif key in NUMERIC_FIELDS:
            try:
                out[key] = float(val)
            except (ValueError, TypeError):
                out[key] = None
        elif key in INT_FIELDS:
            try:
                out[key] = int(float(val))
            except (ValueError, TypeError):
                out[key] = None
        else:
            out[key] = val
    return out


def read_csv_files() -> list[dict]:
    pattern = os.path.join(RAW_DIR, "*.csv")
    files = glob.glob(pattern)
    if not files:
        print(f"No CSV files found in {RAW_DIR}")
        return []

    rows = []
    for filepath in sorted(files):
        filename = os.path.basename(filepath)
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            file_rows = [_coerce_row(r) for r in reader]
        print(f"  Read {len(file_rows):>5} rows from {filename}")
        rows.extend(file_rows)

    return rows


def insert_rows(rows: list[dict]) -> dict[str, int]:
    """Insert rows and return count of rows inserted per platform."""
    if not rows:
        return {}

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn:
            with conn.cursor() as cur:
                # Track inserts per platform by counting before and after
                cur.execute("SELECT platform, COUNT(*) FROM products GROUP BY platform")
                before = dict(cur.fetchall())

                execute_batch(cur, INSERT_SQL, rows, page_size=500)

                cur.execute("SELECT platform, COUNT(*) FROM products GROUP BY platform")
                after = dict(cur.fetchall())

        inserted_per_platform = {}
        all_platforms = set(before) | set(after)
        for platform in all_platforms:
            inserted_per_platform[platform] = after.get(platform, 0) - before.get(platform, 0)

        # Also capture platforms present in rows but with 0 net inserts
        for row in rows:
            p = row.get("platform")
            if p and p not in inserted_per_platform:
                inserted_per_platform[p] = 0

        return inserted_per_platform
    finally:
        conn.close()


def main():
    print(f"Reading CSV files from {RAW_DIR} …")
    rows = read_csv_files()
    if not rows:
        return

    total = len(rows)
    platform_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        platform_counts[r.get("platform", "unknown")] += 1

    print(f"\nTotal rows to insert: {total}")
    for platform, count in sorted(platform_counts.items()):
        print(f"  {platform}: {count} rows")

    print("\nConnecting to database …")
    try:
        inserted = insert_rows(rows)
    except psycopg2.OperationalError as exc:
        print(f"[error] Could not connect to database: {exc}")
        return

    print("\nInsert summary (new rows added per platform):")
    total_inserted = 0
    for platform, count in sorted(inserted.items()):
        print(f"  {platform}: {count} inserted")
        total_inserted += count

    skipped = total - total_inserted
    print(f"\n  Total inserted : {total_inserted}")
    print(f"  Skipped (dupes): {skipped}")


if __name__ == "__main__":
    main()
