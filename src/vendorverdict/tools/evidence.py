from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace

import requests

from vendorverdict.data_loader import load_fallback_vendors
from vendorverdict.models import SourceCheck, VendorEvidence
from vendorverdict.tools.evidence_extractor import extract_evidence_findings, summarize_findings


class EvidenceCollector:
    """Collect fallback and live official-source evidence for vendors.

    The fallback database is still the source of demo reliability. Live source
    checks are additive: if the internet, a vendor page, or a firewall fails,
    VendorVerdict still produces a useful procurement review.
    """

    SOURCE_LABELS = (
        ("security", "security_url"),
        ("pricing", "pricing_url"),
        ("privacy", "privacy_url"),
        ("docs", "docs_url"),
    )

    def __init__(self, use_live_checks: bool | None = None, timeout_seconds: float = 3.0) -> None:
        self._vendors = load_fallback_vendors()
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, VendorEvidence] = {}

        if use_live_checks is None:
            env_value = os.getenv("VENDORVERDICT_LIVE_EVIDENCE", "1").strip().lower()
            self.use_live_checks = env_value not in {"0", "false", "no", "off"}
        else:
            self.use_live_checks = use_live_checks

    @property
    def known_vendor_names(self) -> list[str]:
        return sorted((vendor.name for vendor in self._vendors.values()), key=str.lower)

    def get(self, vendor_name: str) -> VendorEvidence:
        normalized = vendor_name.lower().strip()
        if normalized in self._cache:
            return self._cache[normalized]

        vendor = self._vendors.get(normalized) or self._unknown_vendor(vendor_name)
        if self.use_live_checks:
            vendor = self.with_live_evidence(vendor)

        self._cache[normalized] = vendor
        return vendor

    def get_many(self, vendor_names: list[str] | tuple[str, ...]) -> list[VendorEvidence]:
        return [self.get(name) for name in vendor_names]

    def with_live_evidence(self, evidence: VendorEvidence) -> VendorEvidence:
        """Check official-source target URLs and merge the result into evidence."""
        targets = [
            (label, getattr(evidence, attr))
            for label, attr in self.SOURCE_LABELS
            if getattr(evidence, attr, "")
        ]
        if not targets:
            return replace(
                evidence,
                live_findings=("No official-source target URLs are configured yet.",),
            )

        checks: list[SourceCheck] = []
        with ThreadPoolExecutor(max_workers=min(4, len(targets))) as executor:
            futures = [executor.submit(self._check_url, evidence.name, label, url) for label, url in targets]
            for future in as_completed(futures):
                checks.append(future.result())

        checks.sort(key=lambda item: [label for label, _ in self.SOURCE_LABELS].index(item.label))
        reachable = sum(1 for check in checks if check.ok)
        total = len(checks)
        extracted_findings = tuple(finding for check in checks for finding in check.findings)
        findings = [f"Live official-source check: {reachable}/{total} configured sources reachable."]
        if extracted_findings:
            findings.append(summarize_findings(extracted_findings))
        else:
            findings.append("No concrete evidence signals were extracted from reachable official pages.")
        return replace(
            evidence,
            source_checks=tuple(checks),
            live_findings=tuple(findings),
            extracted_findings=extracted_findings,
        )

    def with_live_evidence_placeholder(self, evidence: VendorEvidence) -> VendorEvidence:
        """Backward-compatible alias kept for older skeleton code."""
        return self.with_live_evidence(evidence)

    def _check_url(self, vendor_name: str, label: str, url: str) -> SourceCheck:
        headers = {
            "User-Agent": "VendorVerdict/0.1 (+https://github.com/docoplycom-del/vendorverdict)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            # Use GET for production evidence extraction. Some sites reject HEAD,
            # and HEAD cannot provide page text for citations/snippets.
            response = requests.get(
                url,
                allow_redirects=True,
                timeout=self.timeout_seconds,
                headers=headers,
            )

            status = int(response.status_code)
            ok = 200 <= status < 400
            final_url = response.url or url
            redirected = final_url.rstrip("/") != url.rstrip("/")
            note = "reachable" if ok else f"returned HTTP {status}"
            if redirected:
                note = f"{note}; redirected"

            extracted = ()
            content_type = response.headers.get("content-type", "") if hasattr(response, "headers") else ""
            if ok and (not content_type or "text" in content_type or "html" in content_type):
                extracted = extract_evidence_findings(
                    response.text or "",
                    vendor=vendor_name,
                    source_url=final_url,
                    source_label=label,
                )

            return SourceCheck(
                label=label,
                url=url,
                ok=ok,
                status_code=status,
                note=note,
                final_url=final_url if redirected else None,
                findings=extracted,
            )
        except requests.RequestException as exc:
            return SourceCheck(
                label=label,
                url=url,
                ok=False,
                status_code=None,
                note=f"unreachable: {exc.__class__.__name__}",
            )

    def _unknown_vendor(self, vendor_name: str) -> VendorEvidence:
        # Unknown vendors should still produce a usable output with low confidence.
        return VendorEvidence(
            name=vendor_name.strip(),
            category="unknown SaaS",
            known_strengths=("Public evidence not yet collected; manual review recommended.",),
            known_risks=("No curated fallback data is available yet, so confidence is low.",),
            fallback_scores={
                "security": 60,
                "privacy": 60,
                "pricing_predictability": 60,
                "lock_in": 55,
                "sme_fit": 60,
                "operational_maturity": 55,
            },
        )
