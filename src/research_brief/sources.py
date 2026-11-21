"""Bounded source acquisition for the agent's single read-only tool."""

from codecs import getincrementaldecoder
from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import socket
from time import monotonic

from bs4 import BeautifulSoup
import httpx


MAX_SOURCES = 4
MAX_EXCERPT = 1200
MAX_BYTES = 512 * 1024
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = (
    "ResearchBriefAgent/0.1 (https://github.com/ZQ051031/cortensor-hackathon-5)"
)


@dataclass(frozen=True)
class Source:
    id: str
    label: str
    excerpt: str
    url: str = ""
    truncated: bool = False


class SourceError(ValueError):
    """A source could not be read as public HTTPS or local text."""


def public_url(raw: str) -> httpx.URL:
    url = httpx.URL(raw)
    if (
        url.scheme != "https"
        or not url.host
        or url.userinfo
        or url.port not in (None, 443)
    ):
        raise SourceError("Use an HTTPS URL on port 443 without credentials.")
    try:
        addresses = socket.getaddrinfo(url.host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise SourceError("The source host could not be resolved.") from exc
    if not addresses or any(
        not ipaddress.ip_address(address[4][0]).is_global for address in addresses
    ):
        raise SourceError("The source host must resolve to public addresses.")
    return url.copy_with(fragment=None)


def download(
    client: httpx.Client, url: httpx.URL | str
) -> tuple[bytes, str, str, bool]:
    deadline = monotonic() + 12
    with client.stream("GET", url) as response:
        if response.is_redirect:
            raise SourceError("Redirects are disabled. Supply the final HTTPS URL.")
        if not response.is_success:
            raise SourceError(f"Source returned HTTP {response.status_code}.")
        media_type = response.headers.get("content-type", "").split(";")[0].lower()
        if media_type not in {
            "text/plain",
            "text/markdown",
            "text/html",
            "application/xhtml+xml",
            "application/json",
        }:
            raise SourceError("Unsupported source content type. Supply text or HTML.")
        body = bytearray()
        for chunk in response.iter_bytes(chunk_size=8192):
            if monotonic() > deadline:
                raise SourceError("Reading the source took too long.")
            body.extend(chunk[: MAX_BYTES + 1 - len(body)])
            if len(body) > MAX_BYTES:
                break
        return (
            bytes(body[:MAX_BYTES]),
            media_type,
            response.encoding or "utf-8",
            (len(body) > MAX_BYTES),
        )


def excerpt(
    source_id: str, label: str, content: str, url: str = "", clipped: bool = False
) -> Source:
    text = " ".join(content.split())
    if not text:
        raise SourceError("The source contained no readable text.")
    return Source(
        source_id, label, text[:MAX_EXCERPT], url, clipped or len(text) > MAX_EXCERPT
    )


def fetch_source(client: httpx.Client, source_id: str, raw_url: str) -> Source:
    url = public_url(raw_url)
    body, media_type, encoding, clipped = download(client, url)
    text = body.decode(encoding, errors="replace")
    label = str(url)
    if media_type in {"text/html", "application/xhtml+xml"}:
        soup = BeautifulSoup(text, "html.parser")
        if soup.title:
            label = soup.title.get_text(" ", strip=True) or label
        for element in soup.select("script, style, nav, header, footer, aside"):
            element.decompose()
        text = (soup.find("article") or soup.find("main") or soup).get_text(
            " ", strip=True
        )
    return excerpt(source_id, label, text, str(url), clipped)


def read_note(source_id: str, path: Path) -> Source:
    if not path.is_file():
        raise SourceError("Supply a regular UTF-8 text file.")
    with path.open("rb") as file:
        body = file.read(MAX_BYTES + 1)
    data = body[:MAX_BYTES]
    if b"\0" in data:
        raise SourceError("The note contains binary data.")
    # Decode the bounded prefix without treating a partial final code point as invalid.
    clipped = len(body) > MAX_BYTES
    text = getincrementaldecoder("utf-8-sig")().decode(data, final=not clipped)
    return excerpt(source_id, path.name, text, clipped=clipped)


def discover(client: httpx.Client, query: str) -> list[Source]:
    url = httpx.URL(
        WIKIPEDIA_API,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query[:240],
            "gsrnamespace": 0,
            "gsrlimit": 2,
            "prop": "extracts|info",
            "inprop": "url",
            "exintro": 1,
            "explaintext": 1,
            "exsentences": 8,
            "format": "json",
            "formatversion": 2,
        },
    )
    body, _, _, clipped = download(client, url)
    if clipped:
        raise SourceError("The Wikipedia response exceeded the size limit.")
    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SourceError("Wikipedia returned invalid JSON.") from exc
    if "error" in result:
        raise SourceError("Wikipedia returned an API error.")
    pages = sorted(result.get("query", {}).get("pages", []), key=lambda p: p["index"])
    return [
        excerpt(f"S{i}", page["title"], page["extract"], page["fullurl"])
        for i, page in enumerate(pages, start=1)
        if page.get("extract", "").strip()
        and page.get("fullurl", "").startswith("https://en.wikipedia.org/wiki/")
    ]
