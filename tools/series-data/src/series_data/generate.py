"""`series-data generate` and `series-data check`: the stages wired together."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from series_data import wiki
from series_data.feed import parse_feed
from series_data.fetch import Source
from series_data.guardrails import Violation, check_guardrails
from series_data.overrides import Override, OverrideError
from series_data.pipeline import (
    GenerationError,
    apply_overrides,
    assign_ids,
    assign_series_ids,
    build_dataset,
    consistency_errors,
    drop_shared_post_ids,
    episodes_from_rows,
    match_public_feed,
)
from series_data.report import ReportInputs, render_report
from series_data.schema import schema_errors
from series_data.series import SeriesResolver, link_titles


class GuardrailError(GenerationError):
    def __init__(self, violations: list[Violation]):
        self.violations = violations
        lines = "\n  ".join(str(v) for v in violations)
        super().__init__(
            "guardrails failed (rerun with --accept-guardrail-changes if this is intended):\n  "
            + lines
        )


@dataclass
class Result:
    dataset: dict[str, Any]
    report: str
    accepted: list[Violation] = field(default_factory=list)


def serialize(dataset: Mapping[str, Any]) -> str:
    return json.dumps(dataset, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content(dataset: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in dataset.items() if k != "generatedAt"}


def stamp(dataset: dict[str, Any], previous: Mapping[str, Any] | None, now: datetime) -> None:
    """Set `generatedAt`, keeping the previous one when nothing else changed.

    An unchanged dataset is then byte-identical to the published file, so the
    weekly job sees no diff and opens no PR.
    """
    if previous is not None and _content(previous) == _content(dataset):
        dataset["generatedAt"] = previous["generatedAt"]
    else:
        dataset["generatedAt"] = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate(
    source: Source,
    overrides: list[Override],
    previous: Mapping[str, Any] | None,
    accept_guardrail_changes: bool = False,
    now: datetime | None = None,
) -> Result:
    rows = wiki.parse_episodes(source.wikitext("episodes"))
    rows += wiki.parse_special_features(source.wikitext("special-features"))
    miniseries = wiki.parse_miniseries(source.wikitext("miniseries"))
    redirects = source.redirects(sorted(link_titles(rows, miniseries)))
    items = parse_feed(source.public_feed())

    resolver = SeriesResolver(miniseries, redirects)
    keys = {id(row): resolver.keys_for(row) for row in rows}
    all_infos = [*resolver.known.values(), *resolver.unlisted.values()]
    series_ids = assign_series_ids(all_infos, previous["series"] if previous else [])

    previous_episodes = previous["episodes"] if previous else {}
    episodes = episodes_from_rows(rows, keys)
    acknowledged_feed = apply_overrides(
        episodes,
        overrides,
        previous_episodes,
        {item.guid for item in items},
        {series_id: key for key, series_id in series_ids.items()},
    )
    shared_posts = drop_shared_post_ids(episodes)
    matched = match_public_feed(episodes, items, acknowledged_feed)
    assign_ids(episodes, previous_episodes)

    dataset = build_dataset(episodes, resolver.info_by_key(), series_ids)
    stamp(dataset, previous, now or datetime.now(UTC))
    errors = schema_errors(dataset) or consistency_errors(dataset)
    if errors:
        raise GenerationError("generated dataset is invalid:\n  " + "\n  ".join(errors))

    accepted: list[Violation] = []
    if previous is not None:
        violations = check_guardrails(dataset, previous)
        if violations and not accept_guardrail_changes:
            raise GuardrailError(violations)
        accepted = violations

    used_series = {key for e in episodes if not e.excluded for key in e.series}
    report = render_report(
        ReportInputs(
            new=dataset,
            previous=previous,
            unmatched_episodes=[(e.id or "", e.describe()) for e in matched.unmatched_episodes],
            unmatched_items=matched.unmatched_items,
            shared_post_ids={
                post: [e.describe() for e in claimants] for post, claimants in shared_posts.items()
            },
            contested={
                guid: [e.describe() for e in claimants]
                for guid, claimants in matched.contested.items()
            },
            acks_no_longer_needed=[e.describe() for e in matched.acks_no_longer_needed],
            unlisted_series=[i for k, i in resolver.unlisted.items() if k in used_series],
            accepted=accepted,
        )
    )
    return Result(dataset=dataset, report=report, accepted=accepted)


@dataclass
class CheckResult:
    errors: list[str]
    pending: list[str]


def check(dataset: Mapping[str, Any] | None, overrides: list[Override]) -> CheckResult:
    """Offline validation of the committed dataset and overrides (design D7)."""
    errors: list[str] = []
    pending: list[str] = []
    if dataset is None:
        episodes: Mapping[str, Any] = {}
        series_ids: set[str] = set()
        pending.append("data/series.json doesn't exist yet; overrides are checked by generate")
    else:
        errors += [f"series.json: {e}" for e in schema_errors(dataset)]
        if not errors:
            errors += [f"series.json: {e}" for e in consistency_errors(dataset)]
        episodes = dataset.get("episodes", {}) if not errors else {}
        series_ids = {s.get("id") for s in dataset.get("series", [])} if not errors else set()
    numbers = {e.get("wikiNumber") for e in episodes.values()}

    for override in overrides:
        if dataset is None:
            continue
        if override.target is not None:
            if override.targets_wiki_number:
                # An excluded row is never in series.json, so only generate can check it.
                if override.target not in numbers and override.op != "exclude":
                    pending.append(
                        f"{override.describe()}: wiki number not in series.json yet (pending)"
                    )
            elif override.target not in episodes:
                errors.append(f"{override.describe()}: episode ID isn't in series.json (stale)")
        if override.series is not None and override.series not in series_ids:
            errors.append(
                f"{override.describe()}: series {override.series!r} isn't in series.json "
                "(a brand-new series can only be targeted once a dataset with it is merged)"
            )
    return CheckResult(errors=errors, pending=pending)


__all__ = ["CheckResult", "GenerationError", "GuardrailError", "OverrideError", "Result"]
