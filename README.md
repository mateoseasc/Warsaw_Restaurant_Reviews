# What Warsaw diners really think about Polish restaurants

Text mining of 5,200 Google Maps reviews of 52 Polish restaurants in Warsaw: what diners complain about and praise beyond the star rating, and how it differs by area, price level and reviewer language (Polish vs. English).

The point of view is a restaurant owner's: *what do customers dislike most about my place, and how do I compare with my competitors?*

> Course project for **Text and Social Media Mining**, University of Warsaw, winter semester 2026/27. Work in progress.

## Project structure

```
data/
  raw/
    gosom_queries.txt            Google Maps searches used to find candidate restaurants
    gosom_polish_<date>.json     candidate restaurants (not published)
    apify_reviews_<date>.json    raw reviews (not published)
  processed/
    selected_restaurants.csv     the 52 restaurants analysed
    reviews_clean.csv            clean reviews, one row per review (not published)
src/
  select_restaurants.py          selection rules and random sample
  collect.py                     review collection via Apify
  clean.py                       cleaning, language detection, filtering
notebooks/
  analysis.ipynb                 the analysis: data, modelling, evaluation, conclusions
```

## Data

- **Source:** public Google Maps reviews, collected on 13 November 2026.
- **Sample:** 52 Polish restaurants (13 in each of Śródmieście, Mokotów, Wola and Praga), selected at random from all eligible restaurants with fixed rules. See `src/select_restaurants.py`.
- **Reviews:** the 100 newest per restaurant (5,200), of which 3,519 have at least 3 words of text and are analysed.
- **Privacy:** no reviewer names, IDs or photos are collected. Review text is not published in this repository; the frozen dataset is available to the course instructor.

## How to reproduce

**Setup** (Windows / PowerShell, Python 3.12):

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

**Pipeline**, run from the project root:

| Step | Command | Output |
|---|---|---|
| 1. Find candidate restaurants | `docker run --rm -v "${PWD}/data:/data" gosom/google-maps-scraper -input /data/raw/gosom_queries.txt -results /data/raw/gosom_polish_2026-11-13.json -json -lang pl -depth 10 -exit-on-inactivity 3m` | `data/raw/gosom_polish_2026-11-13.json` |
| 2. Select restaurants | `.venv\Scripts\python src\select_restaurants.py` | `data/processed/selected_restaurants.csv` |
| 3. Collect reviews | `.venv\Scripts\python src\collect.py` | `data/raw/apify_reviews_2026-11-13.json` |
| 4. Clean | `.venv\Scripts\python src\clean.py` | `data/processed/reviews_clean.csv` |

Then open `notebooks/analysis.ipynb` with the `.venv` kernel.

- Step 1 needs [Docker](https://www.docker.com/) and uses [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper).
- Step 3 needs an [Apify](https://apify.com/) account and a `.env` file in the project root with `APIFY_TOKEN=<your token>`. The full run costs about $3.
- Steps 1 and 3 scrape Google Maps as it is on the day they run, so re-running them gives different restaurants and reviews. The analysis uses the frozen files from 13 November 2026; steps 2 and 4 are deterministic given those files (fixed rules, `random_state=42`).
