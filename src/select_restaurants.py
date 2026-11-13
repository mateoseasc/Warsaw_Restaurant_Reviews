"""Select the Polish restaurants to analyse from the gosom candidate list.

Fixed rules (no hand-picking):
  1. District (Google 'borough') is one of DISTRICTS.
  2. Main category is Polish cuisine / pierogi, OR main category is a generic
     restaurant type explicitly tagged 'Kuchnia polska'.
  3. Not a milk bar (different, subsidised business model; checked in categories
     and name) and not closed.
  4. At least MIN_REVIEWS reviews on Google Maps.
  5. Districts are grouped into AREAS (Praga-Północ + Praga-Południe = Praga,
     because Praga-Północ alone has fewer than 10 eligible restaurants).
  6. Random sample of N_PER_AREA per area (seed RANDOM_STATE).

Input : data/raw/gosom_polish_2026-11-13.json  (JSON lines, one place per line)
Output: data/processed/selected_restaurants.csv (committed to the repo)

Usage:
    python src/select_restaurants.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "gosom_polish_2026-11-13.json"
OUT = ROOT / "data" / "processed" / "selected_restaurants.csv"

DISTRICT_TO_AREA = {
    "Śródmieście": "Śródmieście",
    "Mokotów": "Mokotów",
    "Wola": "Wola",
    "Praga-Północ": "Praga",
    "Praga-Południe": "Praga",
}
DISTRICTS = list(DISTRICT_TO_AREA)
AREAS = ["Śródmieście", "Mokotów", "Wola", "Praga"]
POLISH_CATEGORIES = {"Kuchnia polska", "Pierogarnia"}
GENERIC_CATEGORIES = {"Restauracja", "Bistro"}
MIN_REVIEWS = 100
N_PER_AREA = 13
RANDOM_STATE = 42


def load_places(path):
    """Read gosom JSON-lines output into a flat DataFrame, one row per place."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            p = json.loads(line)
            rows.append({
                "place_id": p.get("place_id"),
                "name": p.get("title"),
                "district": (p.get("complete_address") or {}).get("borough"),
                "category": p.get("category"),
                "categories": p.get("categories") or [],
                "review_count": p.get("review_count") or 0,
                "rating": p.get("review_rating"),
                "status": p.get("status") or "",
                "url": p.get("link"),
            })
    return pd.DataFrame(rows).drop_duplicates("place_id")


def is_polish(row):
    """Main category is Polish/pierogi, or a generic restaurant explicitly tagged
    'Kuchnia polska'. 'Pierogarnia' alone is not enough for generic places, since
    Google also uses it for Asian dumpling restaurants."""
    if row["category"] in POLISH_CATEGORIES:
        return True
    return row["category"] in GENERIC_CATEGORIES and "Kuchnia polska" in row["categories"]


def is_milk_bar(row):
    """Milk bars are often tagged only 'Kuchnia polska', so also check the name."""
    texts = [row["name"] or ""] + row["categories"]
    return any("mleczn" in t.lower() for t in texts)


def is_closed(row):
    return "zamknięte" in row["status"].lower()


def filter_eligible(df):
    """Apply rules 1-4, printing how many places each rule removes."""
    steps = [
        ("in target districts", df["district"].isin(DISTRICTS)),
        ("Polish restaurant", df.apply(is_polish, axis=1)),
        ("not a milk bar", ~df.apply(is_milk_bar, axis=1)),
        ("not closed", ~df.apply(is_closed, axis=1)),
        (f">= {MIN_REVIEWS} reviews", df["review_count"] >= MIN_REVIEWS),
    ]
    mask = pd.Series(True, index=df.index)
    print(f"{'candidates':<22}{len(df):>5}")
    for label, cond in steps:
        mask &= cond
        print(f"{label:<22}{mask.sum():>5}")
    return df[mask]


def sample_per_area(df):
    """Rule 6. Sort by place_id first so the result does not depend on scrape order."""
    df = df.sort_values("place_id")
    parts = []
    for area in AREAS:
        g = df[df["area"] == area]
        parts.append(g.sample(n=min(N_PER_AREA, len(g)), random_state=RANDOM_STATE))
    return pd.concat(parts).sort_values(["area", "district", "name"])


def main():
    places = load_places(RAW)
    eligible = filter_eligible(places).copy()
    eligible["area"] = eligible["district"].map(DISTRICT_TO_AREA)
    print("\neligible per area:", eligible["area"].value_counts().reindex(AREAS).to_dict())

    selected = sample_per_area(eligible)
    print("selected per area:", selected["area"].value_counts().reindex(AREAS).to_dict())
    print("selected per district:", selected["district"].value_counts().to_dict())
    cols = ["place_id", "name", "area", "district", "category", "review_count", "rating", "url"]
    selected[cols].to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n{len(selected)} restaurants -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
