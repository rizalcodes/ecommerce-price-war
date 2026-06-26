# 🛒 E-Commerce Price War: Lazada vs Zalora Malaysia
## Fashion Category Price & Discount Analysis

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-2.x-150458?style=flat-square&logo=pandas&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-6.x-3F4F75?style=flat-square&logo=plotly&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)

---

## ❓ Problem

Malaysian online shoppers overpay for fashion items because they have no reliable way to compare real discount patterns across platforms. Prices fluctuate daily, discount labels are often misleading ("was RM1,500, now RM149"), and it's nearly impossible to know which platform actually offers better deals — or whether a "sale" price is genuinely below the market rate.

Without data, shoppers make decisions based on marketing copy, not reality.

---

## 💡 Solution

Built a full end-to-end data pipeline that cuts through the noise:

- **Scrapes live fashion product data** from Lazada & Zalora Malaysia using Selenium + undetected-chromedriver to bypass bot detection
- **Stores structured data** in a PostgreSQL database with proper indexing and idempotent upserts
- **Cleans and normalises** raw scraped data — fills missing fields, caps outliers, standardises platforms
- **Runs EDA** to surface real discount patterns, brand pricing strategies, and price tier distributions
- **Visualises findings** in 6 interactive Plotly charts and a live Streamlit dashboard

The result: a clear, data-backed answer to "which platform actually gives you a better deal?"

---

## 🔍 Key Findings

> Derived from actual scraped data across both platforms.

- **Zalora discounts far more aggressively** — avg discount of **28.4%** vs Lazada's **16.4%**, nearly double
- **Zalora is a discount-first marketplace** — **74%** of Zalora listings carry a discount vs only **13.9%** on Lazada
- **NEXT** is the most aggressive brand discounter, averaging **57.5% off** across its listings
- **Lazada and Zalora serve completely different markets** — Lazada avg price **RM 1,195** vs Zalora **RM 147**, revealing entirely different positioning and customer segments
- **6 products carry >50% discount**, pointing to flash-sale or clearance pricing rather than genuine everyday deals

---

## 📊 Dashboard



**Live demo:** [E-Commerce Price War Dashboard](https://ecommerce-price-war-vhor8gqnhrgedkyqeejykx.streamlit.app)

The dashboard features real-time sidebar filtering by platform, price range, brand, and minimum discount — all charts update instantly without re-querying the database.

---

## 🏗️ How It Works

```
Scraper (Selenium + BS4)
        │
        ▼
  Raw CSV Files          ← data/raw/*.csv
        │
        ▼
  PostgreSQL DB          ← database/schema.sql + insert_data.py
        │
        ▼
  Data Cleaning          ← analysis/cleaning.py  →  products_cleaned table
        │
        ▼
  EDA & Stats            ← analysis/eda.py  →  data/eda_results.json
        │
        ▼
  Plotly Charts          ← analysis/visualizations.py  →  data/charts/*.html
        │
        ▼
  Streamlit Dashboard    ← dashboard/pp.py
```

---

## 🛠️ Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Scraping | Selenium 4 + undetected-chromedriver | Headless browser automation with bot-detection bypass |
| Scraping | BeautifulSoup 4 + lxml | HTML parsing after JavaScript render |
| Storage | PostgreSQL 16 | Relational store with indexed queries and UPSERT support |
| ORM / Connector | SQLAlchemy 2 + psycopg2 | DB connection for both bulk inserts and pandas reads |
| Analysis | Python 3.11, Pandas 2, NumPy | Data cleaning, aggregation, outlier handling |
| Visualisation | Plotly 6 | Interactive charts — box plots, histograms, bubble charts, donuts |
| Dashboard | Streamlit 1 | Live interactive web app with sidebar filters |
| Config | python-dotenv | `.env`-based credential management |

---

## 📁 Project Structure

```
ecommerce-price-war/
│
├── scraper/
│   ├── lazada_scraper.py       # Lazada fashion category scraper (undetected-chromedriver)
│   ├── shopee_scraper.py       # Shopee fashion search scraper
│   └── zalora_scraper.py       # Zalora fashion category scraper (data-test-id selectors)
│
├── database/
│   ├── schema.sql              # PostgreSQL table, indexes, and products_with_discount view
│   └── insert_data.py          # Bulk CSV → PostgreSQL with ON CONFLICT DO NOTHING
│
├── analysis/
│   ├── cleaning.py             # 7-step cleaning pipeline → products_cleaned table
│   ├── eda.py                  # Platform, brand, price, and discount analysis → JSON
│   └── visualizations.py       # 6 Plotly charts saved as standalone HTML
│
├── dashboard/
│   └── app.py                  # Streamlit dashboard with sidebar filters + KPI cards
│
├── data/
│   ├── raw/                    # Timestamped CSV files from each scraper run
│   ├── charts/                 # chart1_*.html … chart6_*.html (Plotly exports)
│   └── eda_results.json        # Pre-computed EDA stats for dashboard and charts
│
├── requirements.txt            # Pinned dependencies
└── .env                        # DB credentials (not committed)
```

---

## ⚡ Quick Start

### 1. Clone & set up environment

```bash
git clone https://github.com/rizalcodes/ecommerce-price-war.git
cd ecommerce-price-war

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure database credentials

Create a `.env` file in the project root:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ecommerce_price_war
DB_USER=postgres
DB_PASSWORD=your_password
```

Apply the schema to your PostgreSQL instance:

```bash
psql -U postgres -d ecommerce_price_war -f database/schema.sql
```

### 3. Scrape data

```bash
python scraper/lazada_scraper.py
python scraper/zalora_scraper.py
```

Each run saves a timestamped CSV to `data/raw/`.

### 4. Load into PostgreSQL

```bash
python database/insert_data.py
```

Prints a per-platform insert summary. Duplicate URLs are silently skipped.

### 5. Clean the data

```bash
python analysis/cleaning.py
```

Creates the `products_cleaned` table with 7 normalisation steps applied.

### 6. Run EDA

```bash
python analysis/eda.py
```

Prints platform, brand, and price analysis to console. Saves `data/eda_results.json`.

### 7. Generate charts

```bash
python analysis/visualizations.py
```

Saves 6 standalone HTML charts to `data/charts/`.

### 8. Launch the dashboard

```bash
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501`.

---

## 💬 Insights & Conclusion

**Which platform gives better deals?**
Zalora wins on discounts — 74% of its listings are marked down, and the average reduction is 28.4%. But "better deal" depends on what you're buying. Lazada's average product costs RM 1,195, meaning its customer base skews toward premium or branded goods where even a 16% discount represents significant savings in absolute terms. For everyday fashion under RM 200, Zalora is the clear winner. For higher-end items, Lazada's smaller discount percentage still translates to more money off.

**Which brands are most aggressive in pricing?**
NEXT stands out with an average discount of 57.5%, consistently pricing items well below their listed originals. This pattern is common among international fast-fashion brands establishing market share in Malaysia — they list at an elevated "original" price and maintain near-permanent sale pricing to create urgency. Brands with lower average discounts (under 20%) tend to hold price integrity and rely on brand equity rather than promotional mechanics.

**When is the best time to buy?**
The scraper captures a point-in-time snapshot, but the data signals that Zalora maintains heavy promotional pricing as a default state — not a seasonal event. This means there's rarely a "better" moment to wait for on Zalora; the discount is likely already applied. On Lazada, the pattern is different: fewer items are discounted at any given time, suggesting that promotions are more event-driven (Mega Sales, 11.11, 12.12). Timing your Lazada purchases around these campaigns would yield the deepest savings.

**Is there a gap between original price and real market price?**
Yes, and it's significant. The reverse price calculation in the cleaning pipeline shows that several products carry `original_price` values that are far above any plausible retail price — a common dark pattern where platforms inflate the reference price to make a modest discount appear dramatic. The 99th-percentile capping and discount recalculation steps in `cleaning.py` help surface these cases. A genuine deal is one where `current_price` sits below the platform's own average for that category — not just below a self-reported "original."

---

## 👤 Author

**Rizal**

[![Portfolio](https://img.shields.io/badge/Portfolio-rizalcodes.github.io-0A66C2?style=flat-square)](https://rizalcodes.github.io)
[![GitHub](https://img.shields.io/badge/GitHub-rizalcodes-181717?style=flat-square&logo=github)](https://github.com/rizalcodes)
[![Twitter/X](https://img.shields.io/badge/X-@rizalcodes_-000000?style=flat-square&logo=x)](https://x.com/rizalcodes_)

---

*Built with Python, PostgreSQL, and too many browser tabs open comparing prices.*
