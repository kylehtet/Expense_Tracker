"""Extracts structured fields from a free-text affordability question."""

from __future__ import annotations

from typing import Literal, Optional

import anthropic
from pydantic import BaseModel

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = (
    "You extract structured facts from a user's question about whether they "
    "can afford a purchase. Extract only values the user actually stated - "
    "never guess or infer a number they didn't mention. If a field isn't "
    "stated, leave it null."
)

CORE_FIELDS = ("income", "purchase_type", "price")

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class ParsedQuery(BaseModel):
    income: Optional[float] = None
    purchase_type: Optional[Literal["house", "car", "rent", "other"]] = None
    price: Optional[float] = None
    location: Optional[str] = None
    current_savings: Optional[float] = None


def parse_user_query(text: str) -> dict:
    try:
        response = _get_client().messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
            output_format=ParsedQuery,
        )
        result = response.parsed_output.model_dump()
        error = None
    except anthropic.APIError as exc:
        result = ParsedQuery().model_dump()
        error = str(exc)

    result["missing_fields"] = [f for f in CORE_FIELDS if result[f] is None]
    result["error"] = error
    return result
