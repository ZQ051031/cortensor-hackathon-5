import json
import socket

import httpx
import pytest

from research_brief.agent import Research
from research_brief.sources import (
    MAX_EXCERPT,
    SourceError,
    discover,
    fetch_source,
    public_url,
    read_note,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "https://user:pass@example.org",
        "https://example.org:8443",
        "https://127.0.0.1",
        "https://[::1]",
        "file:///etc/hosts",
    ],
)
def test_source_url_rejects_nonpublic_targets(url):
    with pytest.raises(SourceError):
        public_url(url)


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )


def test_fetch_extracts_article_and_caps_excerpt(public_dns):
    html = "<title>Field guide</title><nav>Menu</nav><article><p>" + "x" * 5000
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, text=html, headers={"Content-Type": "text/html"})
    )
    with httpx.Client(transport=transport) as client:
        source = fetch_source(client, "S1", "https://example.org/article#part")
    assert source.id == "S1"
    assert source.label == "Field guide"
    assert source.url == "https://example.org/article"
    assert source.excerpt == "x" * MAX_EXCERPT
    assert source.truncated


def test_fetch_blocks_redirects(public_dns):
    requested = []

    def transport(request):
        requested.append(request.url)
        return httpx.Response(302, headers={"location": "https://127.0.0.1"})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(SourceError, match="Redirects are disabled"):
            fetch_source(client, "S1", "https://example.org")
    assert len(requested) == 1


def test_fetch_rejects_unsupported_media_type(public_dns):
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, headers={"Content-Type": "application/pdf"})
    )
    with httpx.Client(transport=transport) as client:
        with pytest.raises(SourceError, match="Unsupported source content type"):
            fetch_source(client, "S1", "https://example.org/download")


def test_read_note_parses_utf8_and_rejects_binary(tmp_path):
    note = tmp_path / "field.md"
    note.write_text("\ufeffFirst paragraph.\n\nCafé.", encoding="utf-8")
    source = read_note("S1", note)
    assert source.label == "field.md"
    assert source.excerpt == "First paragraph. Café."
    assert not source.truncated

    note.write_bytes(b"binary\x00data")
    with pytest.raises(SourceError, match="binary"):
        read_note("S1", note)


def test_discovery_uses_ranked_wikipedia_extracts():
    def transport(request):
        assert request.url.host == "en.wikipedia.org"
        assert request.url.params["gsrsearch"] == "Apollo 11"
        assert request.url.params["gsrlimit"] == "2"
        pages = [
            {
                "index": 2,
                "title": "Second",
                "extract": "Text two",
                "fullurl": "https://en.wikipedia.org/wiki/Second",
            },
            {
                "index": 1,
                "title": "First",
                "extract": "Text one",
                "fullurl": "https://en.wikipedia.org/wiki/First",
            },
        ]
        return httpx.Response(200, json={"query": {"pages": pages}})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        sources = discover(client, "Apollo 11")
    assert [(source.id, source.label) for source in sources] == [
        ("S1", "First"),
        ("S2", "Second"),
    ]


def test_gather_keeps_successful_notes_when_another_source_fails(tmp_path):
    note = tmp_path / "scope.md"
    note.write_text("Project scope", encoding="utf-8")
    research = Research("What is the scope?", ["http://example.org"], [note])
    first = research.gather("Read the supplied notes.", "Project scope")
    assert json.loads(first)["sources"][0]["id"] == "S2"
    assert json.loads(first)["failures"][0].startswith("S1:")
    assert research.gather("Second attempt", "Other topic") == first
    assert [event["event"] for event in research.events] == [
        "tool_started",
        "tool_finished",
        "tool_reused",
    ]
