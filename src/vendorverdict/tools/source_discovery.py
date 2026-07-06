from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

from vendorverdict.models import DiscoveredSource


COMMON_SOURCE_PATHS: dict[str, tuple[str, ...]] = {
    "security": (
        "/security",
        "/trust",
        "/trust/security",
        "/security-and-compliance",
        "/company/trust-and-security",
    ),
    "pricing": (
        "/pricing",
        "/plans",
        "/pricing-and-plans",
    ),
    "privacy": (
        "/privacy",
        "/privacy-policy",
        "/legal/privacy",
        "/trust/privacy",
        "/company/privacy",
    ),
    "docs": (
        "/docs",
        "/help",
        "/support",
        "/help-center",
        "/hc/en-us",
    ),
    "status": (
        "/status",
    ),
}


@dataclass(frozen=True)
class SourceDiscoveryResult:
    vendor: str
    base_url: str | None = None
    discovered_by_label: dict[str, DiscoveredSource] = field(default_factory=dict)
    attempted_urls: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def found_any(self) -> bool:
        return bool(self.discovered_by_label)

    @property
    def security_url(self) -> str | None:
        source = self.discovered_by_label.get("security")
        return source.url if source else None

    @property
    def pricing_url(self) -> str | None:
        source = self.discovered_by_label.get("pricing")
        return source.url if source else None

    @property
    def privacy_url(self) -> str | None:
        source = self.discovered_by_label.get("privacy")
        return source.url if source else None

    @property
    def docs_url(self) -> str | None:
        source = self.discovered_by_label.get("docs")
        return source.url if source else None


class SourceDiscovery:
    """Deterministic discovery of likely official vendor source pages.

    This avoids external search APIs for the first production version. It checks
    common SaaS trust/security/pricing/privacy/docs paths on plausible official
    domains, validates reachability, and lets the normal EvidenceCollector fetch
    page content and extract findings.
    """

    def __init__(self, timeout_seconds: float = 1.5, max_domains: int = 8) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_domains = max_domains

    def discover(
        self,
        vendor_name: str,
        *,
        existing_urls: dict[str, str] | object | None = None,
        missing_labels: tuple[str, ...] = ("security", "pricing", "privacy", "docs"),
    ) -> SourceDiscoveryResult:
        configured = _coerce_configured_urls(existing_urls)
        labels = tuple(label for label in missing_labels if not configured.get(label))
        if not labels:
            return SourceDiscoveryResult(vendor=vendor_name, notes=("All requested source labels already have configured URLs.",))

        bases = infer_base_urls(vendor_name, configured.values(), max_domains=self.max_domains)
        if not bases:
            return SourceDiscoveryResult(vendor=vendor_name, notes=("No plausible official domain candidates could be inferred.",))

        candidates: list[tuple[str, str]] = []
        for label in labels:
            for base in bases:
                for path in COMMON_SOURCE_PATHS.get(label, ())[:4]:
                    candidates.append((label, _join_base_and_path(base, path)))

        discovered: dict[str, DiscoveredSource] = {}
        attempted: list[str] = []

        # Preserve deterministic candidate preference. A fully concurrent probe
        # can accept a less likely domain such as .io before a preferred .com
        # candidate simply because that request returned first. The candidate
        # set is intentionally small and uses short timeouts, so sequential
        # validation is acceptable for production V1.
        for label in labels:
            for base in bases:
                for path in COMMON_SOURCE_PATHS.get(label, ())[:4]:
                    candidate = _join_base_and_path(base, path)
                    result, attempted_url = self._validate_candidate(vendor_name, label, candidate)
                    attempted.append(attempted_url)
                    if result is not None:
                        discovered[label] = result
                        break
                if label in discovered:
                    break

        base_url = None
        for source in discovered.values():
            base_url = _base_from_url(source.url)
            if base_url:
                break

        if discovered:
            found_labels = ", ".join(sorted(discovered))
            notes = (f"Source Discovery Agent discovered {len(discovered)}/{len(labels)} requested source target(s): {found_labels}.",)
        else:
            notes = ("Source Discovery Agent did not find reachable official-source targets from deterministic URL patterns.",)

        return SourceDiscoveryResult(
            vendor=vendor_name,
            base_url=base_url,
            discovered_by_label=discovered,
            attempted_urls=tuple(attempted),
            notes=notes,
        )

    def _validate_candidate(self, vendor_name: str, label: str, url: str) -> tuple[DiscoveredSource | None, str]:
        try:
            response = requests.get(url, allow_redirects=True, timeout=self.timeout_seconds, headers=_headers())
        except requests.RequestException:
            return None, url

        status = int(response.status_code)
        if not (200 <= status < 400):
            return None, url

        final_url = response.url or url
        if not _redirect_is_plausible(url, final_url, label):
            return None, url

        redirected = final_url.rstrip("/") != url.rstrip("/")
        return (
            DiscoveredSource(
                vendor=vendor_name,
                label=label,
                url=url,
                ok=True,
                status_code=status,
                final_url=final_url if redirected else None,
                confidence="Medium",
                note="discovered reachable official-source candidate",
            ),
            url,
        )


def discover_vendor_sources(
    vendor_name: str,
    *,
    configured_urls: dict[str, str] | None = None,
    timeout_seconds: float = 1.5,
    labels: tuple[str, ...] = ("security", "pricing", "privacy", "docs"),
) -> tuple[DiscoveredSource, ...]:
    result = SourceDiscovery(timeout_seconds=timeout_seconds).discover(
        vendor_name,
        existing_urls=configured_urls or {},
        missing_labels=labels,
    )
    return tuple(result.discovered_by_label[label] for label in labels if label in result.discovered_by_label)


def infer_base_urls(vendor_name: str, configured_urls: object = (), max_domains: int = 8) -> tuple[str, ...]:
    bases: list[str] = []

    for url in configured_urls or ():
        base = _base_from_url(str(url))
        if base and base not in bases:
            bases.append(base)

    slug = slugify_vendor_name(vendor_name)
    if slug:
        if "." in slug:
            candidates = [slug]
        else:
            candidates = [
                f"{slug}.com",
                f"www.{slug}.com",
                f"{slug}.io",
                f"www.{slug}.io",
                f"{slug}.app",
                f"www.{slug}.app",
                f"{slug}.ai",
                f"www.{slug}.ai",
            ]
        for domain in candidates:
            base = f"https://{domain}"
            if base not in bases:
                bases.append(base)

    return tuple(bases[:max_domains])


def slugify_vendor_name(vendor_name: str) -> str:
    value = (vendor_name or "").strip().lower()
    value = value.replace("&", " and ")
    value = re.sub(
        r"\b(software|systems|technologies|technology|tech|inc|ltd|llc|limited|corp|corporation|company|co)\b",
        "",
        value,
    )
    if re.search(r"\.[a-z]{2,}$", value):
        value = re.sub(r"[^a-z0-9.-]", "", value)
    else:
        value = re.sub(r"[^a-z0-9]", "", value)
    return value.strip(".-")


# Backward-compatible alias used by early tests/docs.
def normalize_vendor_slug(vendor_name: str) -> str:
    return slugify_vendor_name(vendor_name)


def vendor_slug(vendor_name: str) -> str:
    return slugify_vendor_name(vendor_name)


def extract_domain(value: str) -> str | None:
    candidate = (value or "").strip()
    if not candidate:
        return None
    parsed = urlparse(candidate if candidate.startswith(("http://", "https://")) else f"https://{candidate}")
    host = parsed.netloc.lower().removeprefix("www.")
    if not host or "." not in host:
        return None
    return host


def _coerce_configured_urls(existing_urls: object) -> dict[str, str]:
    if isinstance(existing_urls, dict):
        return {str(label): str(url) for label, url in existing_urls.items() if url}
    return {f"configured_{idx}": str(url) for idx, url in enumerate(existing_urls or ()) if url}


def _validate_candidate(label: str, url: str, timeout_seconds: float) -> DiscoveredSource | None:
    result, _ = SourceDiscovery(timeout_seconds=timeout_seconds)._validate_candidate("unknown", label, url)
    return result


def _base_from_url(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
    if not parsed.netloc:
        return None
    return f"{parsed.scheme or 'https'}://{parsed.netloc}"


def _join_base_and_path(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "VendorVerdict/0.1 (+https://github.com/docoplycom-del/vendorverdict)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def _redirect_is_plausible(original_url: str, final_url: str, label: str) -> bool:
    original = urlparse(original_url)
    final = urlparse(final_url)
    if not original.netloc or not final.netloc:
        return True
    original_host = original.netloc.lower().removeprefix("www.")
    final_host = final.netloc.lower().removeprefix("www.")
    if final_host == original_host or final_host.endswith("." + original_host):
        return True
    return label in {"privacy", "docs"}
