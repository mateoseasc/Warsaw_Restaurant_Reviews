"""Turn the raw Apify reviews into one clean table, one row per review.

Steps:
  1. Keep only the fields used in the analysis (no reviewer data).
  2. Attach area / district from our own restaurant list (not Apify's 'neighborhood').
  3. Clean the text: <br> tags -> space, collapse whitespace.
  4. Detect the language ourselves with lingua (Google's label is kept for comparison).
  5. Parse 'Cena za osobę' ("80–100 zł", "Ponad 200 zł") into a number (range midpoint).
     Each restaurant's price level = median price reported by its diners, computed on ALL
     its reviews (also those without text), since price belongs to the restaurant.
  6. Keep only reviews with at least MIN_WORDS words: the analysis is about text, and
     shorter ones ("Ok", "Super") carry no aspect and are where language detection fails.
  7. Group languages into pl / en / other, and into polish / foreign (any other language).

Input : data/raw/apify_reviews_2026-11-13.json
        data/processed/selected_restaurants.csv
Output: data/processed/reviews_clean.csv  (contains review text: gitignored)

Usage:
    python src/clean.py
"""
import json
import re
from pathlib import Path

import pandas as pd
from lingua import LanguageDetectorBuilder

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "apify_reviews_2026-11-13.json"
SELECTED = ROOT / "data" / "processed" / "selected_restaurants.csv"
OUT = ROOT / "data" / "processed" / "reviews_clean.csv"

SUBRATINGS = {"Jedzenie": "food", "Obsługa": "service", "Klimat": "atmosphere"}
MIN_WORDS = 3
# Price level from the restaurant's median price per person (PLN). The cut points follow the
# natural gaps in the data: budget = the "20–40 zł" bracket (pierogarnias, home-style bistros).
PRICE_BINS = [0, 40, 80, float("inf")]
PRICE_LEVELS = ["budget", "mid-range", "upscale"]


def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def parse_price(label):
    """'80–100 zł' -> 90.0 (midpoint); 'Ponad 200 zł' (over 200) -> 200.0 (lower bound)."""
    if not label:
        return None
    numbers = [int(n) for n in re.findall(r"\d+", label)]
    if len(numbers) == 2:
        return sum(numbers) / 2
    if len(numbers) == 1:
        return float(numbers[0])
    return None


def flatten(items):
    rows = []
    for r in items:
        detailed = r.get("reviewDetailedRating") or {}
        price_label = (r.get("reviewContext") or {}).get("Cena za osobę")
        if price_label:
            price_label = price_label.replace("\xa0", " ")
        row = {
            "place_id": r.get("placeId"),
            "review_id": r.get("reviewId"),
            "date": (r.get("publishedAtDate") or "")[:10],
            "stars": r.get("stars"),
            "text": clean_text(r.get("text")),
            "lang_google": r.get("originalLanguage") or None,
            "price_label": price_label,
            "price_pln": parse_price(price_label),
            "owner_replied": bool(r.get("responseFromOwnerText")),
        }
        for pl, en in SUBRATINGS.items():
            row[en] = detailed.get(pl)
        rows.append(row)
    return pd.DataFrame(rows)


def restaurant_price_levels(df):
    """One row per restaurant: how many diners reported a price, the median, and the level."""
    prices = df.groupby("place_id")["price_pln"].agg(n_price="count", median_price="median")
    prices["price_level"] = pd.cut(prices["median_price"], PRICE_BINS, labels=PRICE_LEVELS)
    return prices


def detect_languages(texts):
    """ISO 639-1 code per text ('pl', 'en', ...); None for empty or undecidable texts."""
    detector = LanguageDetectorBuilder.from_all_languages().with_preloaded_language_models().build()
    codes = []
    for t in texts:
        lang = detector.detect_language_of(t) if t else None
        codes.append(lang.iso_code_639_1.name.lower() if lang else None)
    return codes


def main():
    items = json.loads(RAW.read_text(encoding="utf-8"))
    df = flatten(items)

    restaurants = pd.read_csv(SELECTED)[["place_id", "name", "area", "district"]]
    df = df.merge(restaurants.rename(columns={"name": "restaurant"}), on="place_id", how="left")
    assert df["area"].notna().all(), "some reviews do not match a selected restaurant"

    # Before filtering by text: price level uses every review that reports a price
    prices = restaurant_price_levels(df)
    df = df.merge(prices[["price_level"]], left_on="place_id", right_index=True, how="left")

    df["n_words"] = df["text"].str.split().str.len()
    print(f"{'all reviews':<22}{len(df):>6}")
    df = df[df["n_words"] > 0]
    print(f"{'with text':<22}{len(df):>6}")
    df = df[df["n_words"] >= MIN_WORDS].copy()
    print(f"{f'>= {MIN_WORDS} words':<22}{len(df):>6}")

    print("Detecting languages (takes a minute)...")
    df["lang"] = detect_languages(df["text"])
    df["lang_group"] = df["lang"].where(df["lang"].isin(["pl", "en"]), "other")
    # A4 compares Polish-language vs. foreign-language reviewers. Language is not residence
    # (expats write in English, Poles from elsewhere in Polish), so no local/tourist label.
    df["reviewer_group"] = df["lang"].map(lambda l: "polish" if l == "pl" else "foreign")

    cols = ["place_id", "restaurant", "area", "district", "review_id", "date", "stars",
            "text", "n_words", "lang", "lang_group", "reviewer_group", "lang_google",
            "food", "service", "atmosphere", "price_label", "price_pln", "price_level", "owner_replied"]
    df = df[cols].sort_values(["area", "restaurant", "date"], ascending=[True, True, False])
    df.to_csv(OUT, index=False, encoding="utf-8-sig")

    print(f"\n{len(df)} reviews -> {OUT.relative_to(ROOT)}")
    print("lang_group:", df["lang_group"].value_counts().to_dict())
    print("restaurants per price level:", prices["price_level"].value_counts().reindex(PRICE_LEVELS).to_dict())
    agree = (df["lang"] == df["lang_google"]).mean()
    print(f"lingua agrees with Google's label on {agree:.1%} of texts")


if __name__ == "__main__":
    main()
