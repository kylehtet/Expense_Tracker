"""RAG retrieval layer backed by a local Chroma collection.

Mortgage rates come from FRED's MORTGAGE30US / MORTGAGE15US series rather than
scraping freddiemac.com directly: Freddie Mac's own historical-data download
link (freddiemac.com/pmms/docs/historicalweeklydata.xls) returns a dead-link
error page as of 2026-08, while FRED re-publishes the same Freddie Mac PMMS
survey as a stable, unauthenticated CSV endpoint. If that fetch fails (e.g. no
network), we fall back to a cached snapshot in data/mortgage_rates_fallback.json
and mark the fact "stale" so callers can show it.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import chromadb
import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_data"
COLLECTION_NAME = "affordability_facts"

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

_client: chromadb.ClientAPI | None = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def _get_collection():
    return _get_client().get_or_create_collection(COLLECTION_NAME)


def _fetch_fred_series(series_id: str, timeout: float) -> tuple[str, float]:
    response = requests.get(FRED_CSV_URL.format(series_id=series_id), timeout=timeout)
    response.raise_for_status()
    rows = list(csv.reader(io.StringIO(response.text)))
    data_rows = [row for row in rows[1:] if len(row) == 2 and row[1] not in ("", ".")]
    if not data_rows:
        raise ValueError(f"FRED series {series_id} returned no usable rows")
    as_of_date, value = data_rows[-1]
    return as_of_date, float(value)


def fetch_mortgage_rates(timeout: float = 8.0) -> list[dict]:
    with open(DATA_DIR / "mortgage_rates_fallback.json") as f:
        fallback = json.load(f)["rates"]

    rates = []
    for entry in fallback:
        try:
            as_of_date, rate_percent = _fetch_fred_series(entry["series_id"], timeout)
            rates.append(
                {
                    "label": entry["label"],
                    "rate_percent": rate_percent,
                    "rate_decimal": round(rate_percent / 100, 5),
                    "as_of_date": as_of_date,
                    "source": f"FRED series {entry['series_id']} (mirrors Freddie Mac PMMS)",
                    "stale": False,
                }
            )
        except Exception:
            rates.append(
                {
                    "label": entry["label"],
                    "rate_percent": entry["rate_percent"],
                    "rate_decimal": round(entry["rate_percent"] / 100, 5),
                    "as_of_date": entry["as_of_date"],
                    "source": f"{entry['source']} [cached fallback, live fetch failed]",
                    "stale": True,
                }
            )
    return rates


def load_property_tax_insurance() -> list[dict]:
    with open(DATA_DIR / "property_tax_insurance.json") as f:
        data = json.load(f)
    for state in data["states"]:
        state["source"] = data["source"]
        state["last_updated"] = data["last_updated"]
    return data["states"]


def load_cost_of_living() -> list[dict]:
    with open(DATA_DIR / "cost_of_living.json") as f:
        data = json.load(f)
    for city in data["cities"]:
        city["source"] = data["source"]
        city["last_updated"] = data["last_updated"]
    return data["cities"]


def _build_documents() -> list[dict]:
    documents = []

    for rate in fetch_mortgage_rates():
        label_text = rate["label"].replace("_", " ")
        documents.append(
            {
                "id": f"mortgage_rate::{rate['label']}",
                "text": (
                    f"The average {label_text} mortgage interest rate is "
                    f"{rate['rate_percent']}% as of {rate['as_of_date']}, per {rate['source']}."
                ),
                "metadata": {
                    "category": "mortgage_rate",
                    "location": "national",
                    "label": rate["label"],
                    "rate_percent": rate["rate_percent"],
                    "rate_decimal": rate["rate_decimal"],
                    "last_updated": rate["as_of_date"],
                    "source": rate["source"],
                    "stale": rate["stale"],
                },
            }
        )

    for state in load_property_tax_insurance():
        documents.append(
            {
                "id": f"tax_insurance::{state['state']}",
                "text": (
                    f"In {state['state_name']} ({state['state']}), the average effective "
                    f"property tax rate is {state['property_tax_rate'] * 100:.2f}% of home "
                    f"value per year, and average annual homeowners insurance is "
                    f"${state['avg_annual_homeowners_insurance']:,}."
                ),
                "metadata": {
                    "category": "property_tax_insurance",
                    "location": state["state"],
                    "state_name": state["state_name"],
                    "property_tax_rate": state["property_tax_rate"],
                    "avg_annual_homeowners_insurance": state["avg_annual_homeowners_insurance"],
                    "last_updated": state["last_updated"],
                    "source": state["source"],
                    "stale": False,
                },
            }
        )

    for city in load_cost_of_living():
        documents.append(
            {
                "id": f"cost_of_living::{city['city']}_{city['state']}",
                "text": (
                    f"In {city['city']}, {city['state']}, the median 1-bedroom rent is "
                    f"${city['median_1br_rent']:,}/month, median home price is "
                    f"${city['median_home_price']:,}, and the cost of living index is "
                    f"{city['cost_of_living_index']} (100 = national average)."
                ),
                "metadata": {
                    "category": "cost_of_living",
                    "location": f"{city['city']}, {city['state']}",
                    "city": city["city"],
                    "state": city["state"],
                    "median_1br_rent": city["median_1br_rent"],
                    "median_home_price": city["median_home_price"],
                    "cost_of_living_index": city["cost_of_living_index"],
                    "last_updated": city["last_updated"],
                    "source": city["source"],
                    "stale": False,
                },
            }
        )

    return documents


def ingest() -> int:
    """(Re)build the Chroma collection from live + seed sources. Returns doc count."""
    documents = _build_documents()
    collection = _get_collection()
    collection.upsert(
        ids=[d["id"] for d in documents],
        documents=[d["text"] for d in documents],
        metadatas=[d["metadata"] for d in documents],
    )
    return len(documents)


def _location_matches(metadata: dict, location: str) -> bool:
    location_lower = location.lower()
    haystack = " ".join(
        str(metadata.get(field, ""))
        for field in ("location", "city", "state", "state_name")
    ).lower()
    return location_lower in haystack or any(
        part and part in haystack for part in location_lower.replace(",", " ").split()
    )


def retrieve_context(query: str, location: str = "", k: int = 5) -> list[dict]:
    """Top-k relevant facts for `query`, boosted toward `location` when given.
    National facts (e.g. mortgage rates) are never filtered out by location."""
    collection = _get_collection()
    if collection.count() == 0:
        ingest()

    query_text = f"{query} {location}".strip() if location else query
    n_results = min(max(k * 3, 10), collection.count())
    raw = collection.query(query_texts=[query_text], n_results=n_results)

    candidates = []
    for doc_id, text, metadata, distance in zip(
        raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
    ):
        candidates.append(
            {
                "id": doc_id,
                "text": text,
                "category": metadata.get("category"),
                "location": metadata.get("location"),
                "last_updated": metadata.get("last_updated"),
                "source": metadata.get("source"),
                "stale": metadata.get("stale", False),
                "facts": {
                    key: value
                    for key, value in metadata.items()
                    if key not in ("category", "location", "last_updated", "source", "stale")
                },
                "distance": distance,
            }
        )

    if location:
        candidates.sort(
            key=lambda r: (
                not (r["category"] == "mortgage_rate" or _location_matches(r, location)),
                r["distance"],
            )
        )
    else:
        candidates.sort(key=lambda r: r["distance"])

    return candidates[:k]


if __name__ == "__main__":
    count = ingest()
    print(f"Ingested {count} documents into Chroma collection '{COLLECTION_NAME}'.")
