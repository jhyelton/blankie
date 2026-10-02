import json

import httpx
import pytest

from series_data.fetch import (
    USER_AGENT,
    FetchError,
    LiveSource,
    OfflineSource,
    Redirect,
)


def _parse_payload(text):
    return {"parse": {"title": "Episodes", "wikitext": text}}


def _source(handler, sleeps=None):
    client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"User-Agent": USER_AGENT}
    )
    return LiveSource(client, sleep=(sleeps.append if sleeps is not None else lambda s: None))


def test_fetch_success_sends_user_agent_and_params():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_parse_payload("{| |}"))

    assert _source(handler).wikitext("episodes") == "{| |}"
    (request,) = seen
    assert request.headers["User-Agent"].startswith("blankie-series-data/")
    assert "+https://github.com/jhyelton/blankie" in request.headers["User-Agent"]
    assert request.url.params["action"] == "parse"
    assert request.url.params["page"] == "Episodes"
    assert request.url.params["prop"] == "wikitext"


def test_fetch_retries_a_503():
    calls = []
    sleeps = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=_parse_payload("ok"))

    assert _source(handler, sleeps).wikitext("episodes") == "ok"
    assert len(calls) == 2
    assert sleeps == [2]


def test_fetch_honours_retry_after_on_429():
    responses = [
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(200, json=_parse_payload("ok")),
    ]
    sleeps = []
    assert _source(lambda r: responses.pop(0), sleeps).wikitext("episodes") == "ok"
    assert sleeps == [7]


def test_fetch_gives_up_after_final_failure():
    calls = []
    sleeps = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503)

    with pytest.raises(FetchError, match=r"gave up after 4 attempts \(HTTP 503\)"):
        _source(handler, sleeps).wikitext("episodes")
    assert len(calls) == 4
    assert sleeps == [2, 4, 8]


def test_fetch_does_not_retry_a_404():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404)

    with pytest.raises(FetchError, match="HTTP 404"):
        _source(handler).public_feed()
    assert len(calls) == 1


def test_fetch_reports_api_error_payload():
    def handler(request):
        return httpx.Response(
            200, json={"error": {"code": "missingtitle", "info": "The page doesn't exist."}}
        )

    with pytest.raises(FetchError, match="doesn't exist"):
        _source(handler).wikitext("miniseries")


def test_redirects_batched_and_resolved():
    batches = []

    def handler(request):
        titles = request.url.params["titles"].split("|")
        batches.append(titles)
        query = {
            "normalized": [
                {"from": t, "to": t[0].upper() + t[1:]} for t in titles if t[0].islower()
            ],
            "redirects": [
                {"from": "PodcastFellas", "to": "Podcastfellas"},
                {"from": "Ben's Choice", "to": "Standalones", "tofragment": "Ben's Choice"},
            ],
        }
        return httpx.Response(200, json={"query": query})

    titles = ["PodcastFellas", "Ben's Choice", "standalones"] + [f"T{i}" for i in range(60)]
    result = _source(handler).redirects(titles)
    assert [len(b) for b in batches] == [50, 13]
    assert result["PodcastFellas"] == Redirect("Podcastfellas")
    assert result["Ben's Choice"] == Redirect("Standalones", "Ben's Choice")
    assert result["standalones"] == Redirect("Standalones")
    assert result["T5"] == Redirect("T5")


def test_save_then_offline_round_trip(tmp_path):
    def handler(request):
        if request.url.host == "feeds.megaphone.fm":
            return httpx.Response(200, content=b"<rss/>")
        if request.url.params["action"] == "parse":
            return httpx.Response(200, json=_parse_payload(request.url.params["page"]))
        return httpx.Response(200, json={"query": {"redirects": [{"from": "A", "to": "B"}]}})

    live = _source(handler)
    texts = {k: live.wikitext(k) for k in ("episodes", "special-features", "miniseries")}
    live.redirects(["A", "C"])
    live.public_feed()
    live.save(tmp_path)

    offline = OfflineSource(tmp_path)
    assert {k: offline.wikitext(k) for k in texts} == texts
    assert offline.redirects(["A", "C"]) == {"A": Redirect("B"), "C": Redirect("C")}
    assert offline.public_feed() == b"<rss/>"
    with pytest.raises(FetchError, match="no saved redirect lookup"):
        offline.redirects(["D"])


def test_offline_reads_fixture_directory(tmp_path):
    (tmp_path / "episodes.json").write_text(json.dumps(_parse_payload("saved text")))
    assert OfflineSource(tmp_path).wikitext("episodes") == "saved text"
    with pytest.raises(FetchError, match="public-feed.xml is missing"):
        OfflineSource(tmp_path).public_feed()


def test_redirect_chains_followed_to_the_end():
    def handler(request):
        query = {
            "redirects": [
                {"from": "Oldest Name", "to": "Old Name"},
                {"from": "Old Name", "to": "Current Name", "tofragment": "Section"},
                {"from": "Loop A", "to": "Loop B"},
                {"from": "Loop B", "to": "Loop A"},
            ]
        }
        return httpx.Response(200, json={"query": query})

    result = _source(handler).redirects(["Oldest Name", "Old Name", "Loop A"])
    assert result["Oldest Name"] == Redirect("Current Name", "Section")
    assert result["Old Name"] == Redirect("Current Name", "Section")
    assert result["Loop A"].page in ("Loop A", "Loop B")
