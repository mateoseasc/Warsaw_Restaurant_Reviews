"""Download Google Maps reviews for the selected restaurants via Apify.

Actor : compass/Google-Maps-Reviews-Scraper
Input : data/processed/selected_restaurants.csv
Output: data/raw/apify_reviews_<YYYY-MM-DD>.json  (raw items, exactly as returned)

Reviews are sorted by newest, reviewer personal data is not requested, and the
run has a hard spending cap. The Apify token is read from .env (APIFY_TOKEN).

Usage:
    python src/collect.py --limit 1 --max-reviews 10   # cheap test run
    python src/collect.py                              # full run
"""
import argparse
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
from apify_client import ApifyClient
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SELECTED = ROOT / "data" / "processed" / "selected_restaurants.csv"
RAW_DIR = ROOT / "data" / "raw"

ACTOR_ID = "compass/Google-Maps-Reviews-Scraper"
MAX_REVIEWS = 100
MAX_CHARGE_USD = Decimal("4.50")


def build_input(urls, max_reviews):
    return {
        "startUrls": [{"url": u} for u in urls],
        "maxReviews": max_reviews,
        "reviewsSort": "newest",
        "reviewsOrigin": "google",
        "language": "pl",
        "personalData": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="only the first N restaurants (for testing)")
    parser.add_argument("--max-reviews", type=int, default=MAX_REVIEWS)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise SystemExit("APIFY_TOKEN not found. Add it to .env in the project root.")

    restaurants = pd.read_csv(SELECTED)
    if args.limit:
        restaurants = restaurants.head(args.limit)
    urls = restaurants["url"].tolist()
    print(f"Requesting up to {args.max_reviews} reviews for {len(urls)} restaurants...")

    client = ApifyClient(token)
    run = client.actor(ACTOR_ID).call(
        run_input=build_input(urls, args.max_reviews),
        max_total_charge_usd=MAX_CHARGE_USD,
    )
    if run is None:
        raise SystemExit("Apify run did not start.")
    print(f"Run {run.id} finished with status {run.status}; cost ${run.usage_total_usd}")

    items = list(client.dataset(run.default_dataset_id).iterate_items())

    suffix = "_test" if args.limit else ""
    out = RAW_DIR / f"apify_reviews_{date.today().isoformat()}{suffix}.json"
    out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} items -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
