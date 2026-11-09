"""Flatten the raw Apify sample into an anonymised, one-row-per-review CSV.

Usage:
    python src/make_sample.py
"""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "apify_sample_2026-11-09.json"
OUT = ROOT / "data" / "processed" / "sample_reviews.csv"


def clean_text(text):
    """Replace <br> tags with spaces and collapse whitespace."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def flatten(places):
    """One row per review, with place-level info copied onto each row.

    Reviewer name, ID, profile URL and photo are deliberately not kept.
    """
    rows = []
    for place in places:
        for r in place.get("reviews", []):
            detailed = r.get("reviewDetailedRating") or {}
            context = r.get("reviewContext") or {}
            text = clean_text(r.get("text"))
            rows.append({
                "place_id": place.get("placeId"),
                "restaurant": place.get("title"),
                "category": place.get("categoryName"),
                "district": place.get("neighborhood"),
                "review_id": r.get("reviewId"),
                "stars": r.get("stars"),
                "date": (r.get("publishedAtDate") or "")[:10],
                "lang_google": r.get("originalLanguage") or None,
                "text": text,
                "has_text": bool(text),
                "food": detailed.get("Jedzenie"),
                "service": detailed.get("Obsługa"),
                "atmosphere": detailed.get("Klimat"),
                "price_per_person": context.get("Cena za osobę"),
                "owner_replied": bool(r.get("responseFromOwnerText")),
            })
    return pd.DataFrame(rows)


def main():
    places = json.loads(RAW.read_text(encoding="utf-8"))
    df = flatten(places)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel shows Polish characters correctly
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"{len(df)} reviews from {df['place_id'].nunique()} places -> {OUT.relative_to(ROOT)}")
    print(f"with text: {df['has_text'].sum()} | languages: {df['lang_google'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
