import time
import random
import re
import os
import csv
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup


BASE_URL = "https://shopee.com.my"
SEARCH_URL = "https://shopee.com.my/search?keyword=fashion&page={page}"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")


class ShopeeScraper:
    def __init__(self, headless=False):
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Safari/537.36"
        )
        self.driver = uc.Chrome(options=options, version_main=149)
        self.wait = WebDriverWait(self.driver, 15)
        self.products = []

    def _random_sleep(self, min_sec=1.5, max_sec=3.5):
        time.sleep(random.uniform(min_sec, max_sec))

    def _scroll_page(self):
        height = self.driver.execute_script("return document.body.scrollHeight")
        step = max(height // 6, 300)
        for pos in range(0, height, step):
            self.driver.execute_script(f"window.scrollTo(0, {pos});")
            time.sleep(random.uniform(0.3, 0.7))
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        self._random_sleep(1.5, 2.5)
        # Scroll back up slightly to trigger any remaining lazy loads
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.8);")
        self._random_sleep(0.5, 1.0)

    def scrape_category_page(self, page: int) -> list[dict]:
        # Shopee search paginates via &page=N (0-indexed)
        url = SEARCH_URL.format(page=page - 1)
        self.driver.get(url)
        self._random_sleep(8.0, 10.0)

        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "li.shopee-search-item-result__item, div.col-xs-2-4")
                )
            )
        except Exception:
            self._random_sleep(2.0, 3.0)

        self._scroll_page()
        # Extra wait after scroll for JS-rendered prices to settle
        self._random_sleep(1.0, 2.0)

        soup = BeautifulSoup(self.driver.page_source, "lxml")

        # Try multiple known Shopee card container selectors
        cards = soup.select("li.shopee-search-item-result__item")
        if not cards:
            cards = soup.select("div.col-xs-2-4")
        if not cards:
            cards = soup.select("[data-sqe='item']")

        results = []
        for card in cards:
            product = self._parse_product(card)
            if product:
                results.append(product)

        return results

    def _parse_product(self, card) -> dict | None:
        try:
            # Product name
            name_el = card.select_one(
                "div._10Wbs-._2EWg9y, div.ie3A+n, [class*='ellipsis'], "
                "div[class*='name'], div[data-sqe='name']"
            )
            product_name = name_el.get_text(strip=True) if name_el else None

            # Product URL — Shopee item links live in an <a> wrapping the card
            link_el = card.select_one("a[href*='/product/'], a[href*='-i.']")
            if not link_el:
                link_el = card.find("a")
            href = link_el.get("href", "") if link_el else ""
            if href.startswith("/"):
                product_url = BASE_URL + href
            elif href.startswith("http"):
                product_url = href
            else:
                product_url = BASE_URL + "/" + href.lstrip("/")

            # Brand — Shopee rarely shows brand on category cards; attempt anyway
            brand_el = card.select_one("[class*='brand'], [class*='Brand']")
            brand = brand_el.get_text(strip=True) if brand_el else None

            # Current (discounted) price — the prominent price shown
            price_el = card.select_one(
                "span._341bF9, span[class*='price-section__current'], "
                "div[class*='price'] span:first-child, span[class*='_1xk7ak']"
            )
            current_price = self._clean_price(price_el.get_text(strip=True) if price_el else None)

            # Original price — struck-through price
            original_el = card.select_one(
                "span._1KaNOk, s, span[class*='price-before-discount'], "
                "div[class*='price'] span[class*='line-through']"
            )
            original_price = self._clean_price(
                original_el.get_text(strip=True) if original_el else None
            )

            # Discount badge e.g. "-30%"
            discount_el = card.select_one(
                "div._3_ISdg, span[class*='discount'], div[class*='rebates']"
            )
            discount_pct = self._clean_discount(
                discount_el.get_text(strip=True) if discount_el else None
            )

            # Rating — star value typically rendered as text or aria-label
            rating = None
            rating_el = card.select_one(
                "span._1lCF3A, div[class*='rating'] span, span[class*='shopee-rating-stars__score']"
            )
            if rating_el:
                m = re.search(r"[\d.]+", rating_el.get_text(strip=True))
                rating = float(m.group()) if m else None

            # Review / sold count
            review_el = card.select_one(
                "div._3-KSb6, span[class*='sold'], div[class*='rating-count']"
            )
            review_count = self._clean_number(
                review_el.get_text(strip=True) if review_el else None
            )

            if not product_name:
                return None

            return {
                "platform": "Shopee",
                "product_name": product_name,
                "brand": brand,
                "current_price": current_price,
                "original_price": original_price,
                "discount_pct": discount_pct,
                "rating": rating,
                "review_count": review_count,
                "product_url": product_url,
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
                "category": "fashion",
            }
        except Exception as e:
            print(f"  [warn] Failed to parse card: {e}")
            return None

    def _clean_price(self, text: str | None) -> float | None:
        if not text:
            return None
        # Handle price ranges like "RM10.00 - RM50.00" — take the lower bound
        text = text.split("-")[0]
        digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return float(digits) if digits else None
        except ValueError:
            return None

    def _clean_discount(self, text: str | None) -> float | None:
        if not text:
            return None
        m = re.search(r"[\d.]+", text)
        try:
            return float(m.group()) if m else None
        except ValueError:
            return None

    def _clean_number(self, text: str | None) -> int | None:
        if not text:
            return None
        text = text.strip().strip("()")
        # Handle "1.2k sold" style
        m = re.search(r"([\d.]+)\s*k", text, re.IGNORECASE)
        if m:
            return int(float(m.group(1)) * 1000)
        m = re.search(r"[\d,]+", text)
        if m:
            try:
                return int(m.group().replace(",", ""))
            except ValueError:
                return None
        return None

    def scrape_fashion(self, max_pages: int = 5) -> list[dict]:
        print(f"Starting Shopee fashion scrape — {max_pages} page(s)")
        for page in range(1, max_pages + 1):
            print(f"  Scraping page {page}/{max_pages} …")
            try:
                results = self.scrape_category_page(page)
                print(f"    Found {len(results)} products on page {page}")
                self.products.extend(results)
            except Exception as e:
                print(f"    [error] Page {page} failed: {e}")

            if page < max_pages:
                delay = random.uniform(4, 8)
                print(f"    Sleeping {delay:.1f}s before next page …")
                time.sleep(delay)

        print(f"Scrape complete. Total products collected: {len(self.products)}")
        return self.products

    def save_to_csv(self) -> str:
        if not self.products:
            print("No products to save.")
            return ""

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"shopee_fashion_{timestamp}.csv"
        filepath = os.path.join(OUTPUT_DIR, filename)

        fieldnames = [
            "platform", "product_name", "brand", "current_price", "original_price",
            "discount_pct", "rating", "review_count", "product_url", "scraped_at", "category",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.products)

        print(f"Saved {len(self.products)} records to {filepath}")
        return filepath

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    scraper = ShopeeScraper(headless=False)
    try:
        scraper.scrape_fashion(max_pages=3)
        scraper.save_to_csv()
    finally:
        scraper.close()
