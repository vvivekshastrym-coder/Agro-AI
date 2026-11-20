"""Webpage and API extraction service with strict SSRF protection, timeouts, and HTML sanitization."""
import ipaddress
import logging
import socket
import urllib.parse
from typing import Optional, Dict, Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Approved government, APMC, and verified agricultural market domains
APPROVED_SOURCE_DOMAINS = {
    "agmarknet.gov.in",
    "enam.gov.in",
    "krishimaratavahini.kar.nic.in",
    "data.gov.in",
    "api.data.gov.in",
    "commoditiescontrol.com",
    "khethisamachar.com",
    "mandirates.in",
    "commodityonline.com",
    "krishijagran.com",
}

DEFAULT_TIMEOUT_SECS = 10.0
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB maximum response size to prevent resource exhaustion


def is_safe_url(url: str) -> bool:
    """Validate URL protocol, domain, and resolve destination IP to block SSRF, loopback, and private IPs."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            logger.warning("SSRF blocked unsafe scheme: %s", parsed.scheme)
            return False

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False

        # Domain must match or be a subdomain of an approved market source domain
        is_approved = any(
            hostname == d or hostname.endswith("." + d)
            for d in APPROVED_SOURCE_DOMAINS
        )
        if not is_approved:
            logger.warning("SSRF blocked non-approved source domain: %s", hostname)
            return False

        # Resolve hostname to IPv4/IPv6 and verify not private, loopback, or link-local
        addrs = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addrs:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or str(ip).startswith("169.254.")
            ):
                logger.warning("SSRF blocked private/loopback destination IP: %s (%s)", ip_str, hostname)
                return False

        return True
    except Exception as exc:
        logger.warning("URL safety verification error for %s: %s", url, exc)
        return False


def sanitize_html(raw_html: str) -> BeautifulSoup:
    """Safely parse HTML and strip executable or malicious tags (<script>, <iframe>, <style>, etc.)."""
    soup = BeautifulSoup(raw_html, "html.parser")
    for dangerous_tag in soup(["script", "style", "iframe", "object", "embed", "applet"]):
        dangerous_tag.decompose()
    return soup


async def fetch_market_url(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT_SECS,
) -> Optional[str]:
    """Securely fetches content from an approved URL with SSRF protection, size caps, and timeouts."""
    if not is_safe_url(url):
        logger.error("Rejected fetch request to unsafe/blocked URL: %s", url)
        return None

    req_headers = {
        "User-Agent": "AgroAI-MandiMarkets/2.0 (Official Agricultural Price Fetcher; contact@agroai.live)",
        "Accept": "text/html,application/xhtml+xml,application/json,*/*",
    }
    if headers:
        req_headers.update(headers)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=req_headers)
            if resp.status_code != 200:
                logger.warning("Source returned non-200 status %d for %s", resp.status_code, url)
                return None

            content = resp.content
            if len(content) > MAX_RESPONSE_BYTES:
                logger.error("Response size %d exceeded limit of %d bytes for %s", len(content), MAX_RESPONSE_BYTES, url)
                return None

            return content.decode(resp.encoding or "utf-8", errors="replace")
    except httpx.TimeoutException:
        logger.warning("Timeout fetching mandi data from %s", url)
        return None
    except Exception as exc:
        logger.error("HTTP error fetching %s: %s", url, exc)
        return None
