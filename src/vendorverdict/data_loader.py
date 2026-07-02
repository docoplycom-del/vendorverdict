from __future__ import annotations

import json
from pathlib import Path

from .models import VendorEvidence


_DATA_PATH = Path(__file__).resolve().parent / "data" / "fallback_vendors.json"


def load_fallback_vendors() -> dict[str, VendorEvidence]:
    """Load curated fallback vendor data keyed by lowercase vendor name."""
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    vendors: dict[str, VendorEvidence] = {}
    for row in raw:
        evidence = VendorEvidence(
            name=row["name"],
            category=row["category"],
            security_url=row.get("security_url", ""),
            pricing_url=row.get("pricing_url", ""),
            privacy_url=row.get("privacy_url", ""),
            docs_url=row.get("docs_url", ""),
            known_strengths=tuple(row.get("known_strengths", [])),
            known_risks=tuple(row.get("known_risks", [])),
            fallback_scores=dict(row.get("fallback_scores", {})),
        )
        vendors[evidence.name.lower()] = evidence
    return vendors
