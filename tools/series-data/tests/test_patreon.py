"""`check-patreon` never prints the feed URL or token and writes nothing (task 8.1).

A local HTTP server stands in for Patreon. Its items are synthetic.
"""

import http.server
import json
import subprocess
import threading
from pathlib import Path

import pytest

from series_data.patreon import SETUP, keychain_url, run

FAKE_TOKEN = "FAKETOKENfaketoken0123456789"
FEED = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>synthetic</title>
<item><title>Mortal Kombat II</title><guid>900000001</guid>
<pubDate>Thu, 21 May 2026 12:00:00 -0000</pubDate></item>
<item><title>Ocean's Eleven Commentary (synthetic)</title><guid>900000002</guid>
<pubDate>Fri, 21 Jul 2023 12:00:00 -0000</pubDate></item>
<item><title>After Hours with Alison Sivitz (Ad-Free)</title><guid>900000003</guid>
<pubDate>Sun, 27 Sep 2026 04:00:00 -0000</pubDate></item>
</channel></rss>"""
DATASET = {
    "episodes": {
        "2026-05-21:mortal-kombat-ii": {
            "title": "Mortal Kombat II",
            "airDate": "2026-05-21",
            "feed": "special-features",
            "series": [],
            "hints": {"patreonPostId": "900000001"},
        },
        "2023-07-21:oceans-eleven": {
            "title": "Ocean's Eleven",
            "airDate": "2023-07-21",
            "feed": "special-features",
            "series": [],
            "hints": {},
        },
        "2024-01-01:not-in-feed": {
            "title": "Not In Feed",
            "airDate": "2024-01-01",
            "feed": "special-features",
            "series": [],
            "hints": {},
        },
        "2026-09-27:after-hours": {
            "title": "After Hours",
            "airDate": "2026-09-27",
            "feed": "main",
            "series": [],
            "hints": {},
        },
    }
}


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200
    hits: list[str] = []

    def do_GET(self):  # noqa: N802
        type(self).hits.append(self.path)
        self.send_response(self.status)
        self.send_header("Content-Type", "application/rss+xml")
        self.end_headers()
        if self.status == 200:
            self.wfile.write(FEED)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    _Handler.hits = []
    _Handler.status = 200
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    dataset = tmp_path / "series.json"
    dataset.write_text(json.dumps(DATASET))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _url(server):
    return f"http://127.0.0.1:{server.server_address[1]}/rss/12345?auth={FAKE_TOKEN}"


def _assert_clean(captured):
    for stream in (captured.out, captured.err):
        assert "http" not in stream
        assert FAKE_TOKEN not in stream
        assert "auth=" not in stream


def _files(directory: Path):
    return sorted(p.name for p in directory.rglob("*"))


def test_report_lists_titles_dates_ids_only(server, workdir, capsys):
    before = _files(workdir)
    code = run(workdir / "series.json", lambda: _url(server))
    captured = capsys.readouterr()
    _assert_clean(captured)
    assert _Handler.hits == [f"/rss/12345?auth={FAKE_TOKEN}"]
    assert "Matched by Patreon post ID: 1" in captured.out
    assert "2026-05-21  Mortal Kombat II  [2026-05-21:mortal-kombat-ii]" in captured.out
    assert "Matched by title and date (no post ID hint): 1" in captured.out
    assert "Unmatched: 1" in captured.out
    assert "Not In Feed  [2024-01-01:not-in-feed]" in captured.out
    assert "After Hours" not in captured.out  # main-feed episodes aren't checked
    assert code == 1  # one unmatched episode
    assert _files(workdir) == before


def test_http_403_shows_status_only(server, workdir, capsys):
    _Handler.status = 403
    code = run(workdir / "series.json", lambda: _url(server))
    captured = capsys.readouterr()
    _assert_clean(captured)
    assert code == 1
    assert captured.err.strip() == "error: fetching the Patreon feed failed (HTTP 403)"


def test_connection_failure_shows_no_url(workdir, capsys):
    url = f"http://127.0.0.1:9/rss/12345?auth={FAKE_TOKEN}"  # port 9: nothing listens
    code = run(workdir / "series.json", lambda: url)
    captured = capsys.readouterr()
    _assert_clean(captured)
    assert code == 1
    assert captured.err.startswith("error: fetching the Patreon feed failed (")


def test_missing_keychain_entry_makes_no_request(server, workdir, capsys):
    code = run(workdir / "series.json", lambda: None)
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.strip() == SETUP
    assert "security add-generic-password -s blankie-patreon-feed" in captured.err
    assert _Handler.hits == []


def test_keychain_reader_uses_security_tool():
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="the-url\n", stderr="")

    assert keychain_url(fake_run) == "the-url"
    assert calls == [["security", "find-generic-password", "-s", "blankie-patreon-feed", "-w"]]


def test_keychain_reader_missing_entry():
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 44, stdout="", stderr="could not be found")

    assert keychain_url(fake_run) is None


def test_two_episodes_on_one_feed_item_are_flagged():
    from datetime import date

    from series_data.matching import FeedItem
    from series_data.patreon import build_report

    dataset = {
        "episodes": {
            "2025-10-11:a": {
                "title": "A",
                "airDate": "2025-10-11",
                "feed": "special-features",
                "series": [],
                "hints": {"patreonPostId": "900000010"},
            },
            "2025-10-11:b": {
                "title": "B",
                "airDate": "2025-10-11",
                "feed": "special-features",
                "series": [],
                "hints": {"patreonPostId": "900000010"},
            },
        }
    }
    report, problems = build_report(dataset, [FeedItem("900000010", "A", date(2025, 10, 11))])
    assert "Matched to the same feed item as another episode: 2" in report
    assert problems == 2
