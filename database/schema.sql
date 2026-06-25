-- Products table
CREATE TABLE IF NOT EXISTS products (
    id             SERIAL PRIMARY KEY,
    platform       VARCHAR(50)    NOT NULL,
    product_name   TEXT           NOT NULL,
    brand          VARCHAR(255),
    current_price  NUMERIC(10,2),
    original_price NUMERIC(10,2),
    discount_pct   NUMERIC(5,2),
    rating         NUMERIC(3,2),
    review_count   INTEGER,
    product_url    TEXT UNIQUE,
    scraped_at     TIMESTAMP,
    category       VARCHAR(100),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_products_platform   ON products (platform);
CREATE INDEX IF NOT EXISTS idx_products_brand      ON products (brand);
CREATE INDEX IF NOT EXISTS idx_products_category   ON products (category);
CREATE INDEX IF NOT EXISTS idx_products_scraped_at ON products (scraped_at);

-- View: only rows that have a discount
CREATE OR REPLACE VIEW products_with_discount AS
    SELECT *
    FROM products
    WHERE discount_pct IS NOT NULL;
