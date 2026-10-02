"""Guardrails (task 6.1), the diff report (6.2), `check`, and series resolution."""

import copy
import json
from datetime import UTC, datetime

import pytest
from helpers import FIXTURES

from series_data.cli import main
from series_data.fetch import OfflineSource, Redirect
from series_data.generate import GuardrailError, check, generate
from series_data.guardrails import check_guardrails
from series_data.overrides import load_overrides, parse_overrides
from series_data.series import SeriesResolver
from series_data.wiki import MiniseriesEntry, SeriesLink, WikiRow

GOLDEN = FIXTURES / "golden"
NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


@pytest.fixture
def published():
    return json.loads((GOLDEN / "series.json").read_text())


def _generate(offline_dir, previous, accept=False):
    return generate(
        OfflineSource(offline_dir),
        load_overrides(GOLDEN / "overrides.json"),
        previous,
        accept_guardrail_changes=accept,
        now=NOW,
    )


def _move_odyssey_to_stanton(previous):
    series = {s["id"]: s for s in previous["series"]}
    odyssey = "2026-07-19:the-odyssey"
    previous["episodes"][odyssey]["series"] = ["podd-c"]
    series["the-pod-knight-casts"]["episodes"].remove(odyssey)
    series["podd-c"]["episodes"].append(odyssey)


# --- guardrails -------------------------------------------------------------------


def test_unchanged_passes(offline_dir, published):
    assert _generate(offline_dir, published).accepted == []


def test_row_count_drop(published):
    new = copy.deepcopy(published)
    for episode_id in list(new["episodes"])[:6]:
        del new["episodes"][episode_id]
    names = [v.name for v in check_guardrails(new, published)]
    assert "row count dropped" in names
    assert "episode IDs disappeared" in names


def test_wiki_table_broken_drop_by_half(published):
    new = copy.deepcopy(published)
    for episode_id in list(new["episodes"])[::2]:
        del new["episodes"][episode_id]
    violations = check_guardrails(new, published)
    assert any(v.name == "row count dropped" and "fewer" in v.detail for v in violations)


def _synthetic(count):
    episodes = {
        f"2020-01-01:e{i}": {
            "title": f"E{i}",
            "airDate": "2020-01-01",
            "feed": "main",
            "series": [],
            "hints": {},
        }
        for i in range(count)
    }
    return {"series": [], "episodes": episodes}


@pytest.mark.parametrize(("dropped", "flagged"), [(5, False), (6, True)])
def test_row_drop_threshold_on_a_full_size_dataset(dropped, flagged):
    previous = _synthetic(1000)
    new = copy.deepcopy(previous)
    for episode_id in list(new["episodes"])[:dropped]:
        del new["episodes"][episode_id]
    names = [v.name for v in check_guardrails(new, previous)]
    assert ("row count dropped" in names) is flagged
    assert "episode IDs disappeared" in names


def test_series_loses_episodes_names_series_and_episodes(published):
    new = copy.deepcopy(published)
    (fellas,) = [s for s in new["series"] if s["id"] == "podcastfellas"]
    removed = fellas["episodes"][:3]
    fellas["episodes"] = fellas["episodes"][3:]
    violations = [v for v in check_guardrails(new, published) if v.name == "series lost episodes"]
    assert len(violations) == 1
    assert "Podcastfellas (podcastfellas) lost 3" in violations[0].detail
    assert all(e in violations[0].detail for e in removed)


def test_membership_change_over_five_percent(published):
    new = copy.deepcopy(published)
    for episode_id in list(new["episodes"])[:4]:
        new["episodes"][episode_id]["series"] = ["somewhere-else"]
    names = [v.name for v in check_guardrails(new, published)]
    assert "membership changed for more than 5% of episodes" in names


def test_membership_change_under_five_percent(published):
    new = copy.deepcopy(published)
    new["episodes"]["2026-09-27:after-hours"]["series"] = []
    names = [v.name for v in check_guardrails(new, published)]
    assert "membership changed for more than 5% of episodes" not in names


def test_generate_fails_without_acceptance(offline_dir, published):
    previous = copy.deepcopy(published)
    _move_odyssey_to_stanton(previous)
    with pytest.raises(GuardrailError, match="series lost episodes: PODD-C"):
        _generate(offline_dir, previous)


def test_generate_passes_with_acceptance_and_lists_guardrails(offline_dir, published):
    previous = copy.deepcopy(published)
    _move_odyssey_to_stanton(previous)
    result = _generate(offline_dir, previous, accept=True)
    assert [v.name for v in result.accepted] == ["series lost episodes"]
    assert "### Guardrails overridden" in result.report
    assert "**series lost episodes**: PODD-C (podd-c) lost 1" in result.report


def test_first_run_skips_comparison(offline_dir):
    result = _generate(offline_dir, None)
    assert result.accepted == []
    assert "comparison guardrails were skipped" in result.report


# --- report for a diff (golden) ------------------------------------------------------


def test_diff_report_golden(offline_dir, published):
    import os

    previous = copy.deepcopy(published)
    _move_odyssey_to_stanton(previous)
    del previous["episodes"]["2026-09-27:after-hours"]
    for series in previous["series"]:
        if "2026-09-27:after-hours" in series["episodes"]:
            series["episodes"].remove("2026-09-27:after-hours")
    previous["episodes"]["2026-09-20:the-king-of-comedy"]["title"] = "The King Of Comedy"
    previous["episodes"]["2014-01-01:ghost-episode"] = {
        "title": "Ghost Episode",
        "airDate": "2014-01-01",
        "feed": "main",
        "series": [],
        "hints": {},
    }
    result = _generate(offline_dir, previous, accept=True)
    path = GOLDEN / "diff-report.md"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.write_text(result.report)
    assert result.report == path.read_text()
    report = result.report
    # Membership changes come before the other lists.
    assert report.index("### Series membership changes") < report.index("### Added episodes")


# --- check (design D7) ----------------------------------------------------------------


def test_check_committed_dataset_ok(published):
    overrides = load_overrides(GOLDEN / "overrides.json")
    result = check(published, overrides)
    assert result.errors == []


def test_check_stale_episode_id(published):
    overrides = parse_overrides(
        [{"op": "ackUnmatchedWiki", "target": "2001-01-01:not-here", "reason": "r"}]
    )
    result = check(published, overrides)
    (error,) = result.errors
    assert error.startswith("override #0 (ackUnmatchedWiki '2001-01-01:not-here')")
    assert error.endswith("episode ID isn't in series.json (stale)")


def test_check_pending_wiki_number(published):
    overrides = parse_overrides([{"op": "ackUnmatchedWiki", "target": "601", "reason": "r"}])
    result = check(published, overrides)
    assert result.errors == []
    assert "pending" in result.pending[0]


def test_check_schema_error(published):
    broken = copy.deepcopy(published)
    del broken["episodes"]["2026-09-27:after-hours"]["airDate"]
    assert any("airDate" in e for e in check(broken, []).errors)


def test_check_inconsistent_membership(published):
    broken = copy.deepcopy(published)
    broken["episodes"]["2026-09-27:after-hours"]["series"] = []
    assert any("doesn't list it" in e for e in check(broken, []).errors)


def test_cli_check_and_generate(tmp_path, offline_dir, capsys):
    out = tmp_path / "series.json"
    report = tmp_path / "report.md"
    args = ["--previous", str(tmp_path / "none.json"), "--output", str(out)]
    args += ["--overrides", str(GOLDEN / "overrides.json"), "--report", str(report)]
    assert main(["generate", "--offline", str(offline_dir), *args]) == 0
    assert json.loads(out.read_text())["schemaVersion"] == 1
    assert report.read_text().startswith("## Series data update")
    assert (
        main(["check", "--dataset", str(out), "--overrides", str(GOLDEN / "overrides.json")]) == 0
    )
    bad = tmp_path / "bad-overrides.json"
    bad.write_text(
        json.dumps([{"op": "ackUnmatchedWiki", "target": "2001-01-01:x", "reason": "r"}])
    )
    capsys.readouterr()
    assert main(["check", "--dataset", str(out), "--overrides", str(bad)]) == 1
    assert "override #0 (ackUnmatchedWiki '2001-01-01:x')" in capsys.readouterr().err


def test_cli_generate_reports_stale_override(tmp_path, offline_dir, capsys):
    bad = tmp_path / "overrides.json"
    bad.write_text(
        json.dumps([{"op": "fix", "target": "2001-01-01:x", "title": "X", "reason": "r"}])
    )
    code = main(
        [
            "generate",
            "--offline",
            str(offline_dir),
            "--previous",
            str(tmp_path / "none.json"),
            "--output",
            str(tmp_path / "o.json"),
            "--overrides",
            str(bad),
        ]
    )
    assert code == 1
    assert "override #0 (fix '2001-01-01:x')" in capsys.readouterr().err
    assert not (tmp_path / "o.json").exists()


# --- series resolution ------------------------------------------------------------------


def _row(*links):
    from datetime import date

    return WikiRow("Episodes", "1", "T", date(2020, 1, 1), "main", list(links))


def test_series_redirects_merge_spellings():
    redirects = {
        "PodcastFellas": Redirect("Podcastfellas"),
        "Podcastfellas": Redirect("Podcastfellas"),
        "Family Choice": Redirect("Standalones", "Ben's Choice"),
        "Standalones": Redirect("Standalones"),
        "Standalone": Redirect("Standalones"),
    }
    resolver = SeriesResolver(
        [
            MiniseriesEntry(SeriesLink("PodcastFellas"), "Martin Scorsese", "director"),
            MiniseriesEntry(
                SeriesLink("Standalones", "Ben's Choice", "Ben's Choice/Guest's Choice"),
                "Picks",
                "other",
            ),
            MiniseriesEntry(SeriesLink("Standalones"), "One-offs", "other"),
        ],
        redirects,
    )
    assert resolver.keys_for(_row(SeriesLink("Podcastfellas"))) == ["podcastfellas"]
    assert resolver.info("podcastfellas").title == "Podcastfellas"
    assert resolver.info("podcastfellas").subject == "Martin Scorsese"
    assert resolver.keys_for(_row(SeriesLink("Family Choice"))) == ["bens-choice"]
    assert resolver.keys_for(_row(SeriesLink("Standalones", "Ben's Choice", "Guest's Choice"))) == [
        "bens-choice"
    ]
    assert resolver.keys_for(_row(SeriesLink("Standalones", "Other Standalone Episodes"))) == []
    assert resolver.keys_for(_row(SeriesLink("Standalone"))) == []
    assert "standalones" not in resolver.known


def test_series_missing_from_miniseries_is_other_and_reported(offline_dir):
    result = _generate(offline_dir, None)
    (announcements,) = [s for s in result.dataset["series"] if s["title"] == "Announcements"]
    assert announcements["category"] == "other"
    assert announcements["subject"] == ""
    section = result.report.split("### Series not on the Miniseries page")[1]
    assert "- Announcements (" in section


def test_check_unknown_series_is_an_error(published):
    overrides = parse_overrides(
        [{"op": "addToSeries", "target": "600", "series": "podcastfelas", "reason": "r"}]
    )
    (error,) = check(published, overrides).errors
    assert "series 'podcastfelas' isn't in series.json" in error


def test_guardrail_hint_changed_for_existing_episode(published):
    new = copy.deepcopy(published)
    new["episodes"]["2026-09-27:after-hours"]["hints"]["publicGuid"] = "some-other-guid"
    violations = check_guardrails(new, published)
    assert [v.name for v in violations] == ["publicGuid changed for existing episodes"]
    assert "2026-09-27:after-hours" in violations[0].detail


def test_guardrail_hint_gained_is_fine(published):
    new = copy.deepcopy(published)
    episode = new["episodes"]["2015-11-30:watch-with-us-live-union-hall"]
    episode["hints"]["publicGuid"] = "newly-matched"
    assert check_guardrails(new, published) == []


def test_shared_post_ids_reported(offline_dir):
    result = _generate(offline_dir, None)
    section = result.report.split("### Patreon post IDs linked from more than one wiki row")[1]
    assert "`140857396`" in section.split("###")[0]
    episodes = result.dataset["episodes"]
    assert (
        "patreonPostId"
        not in episodes["2025-10-11:spreadmasters-delight-3-decade-of-dreams-warriors"]["hints"]
    )
