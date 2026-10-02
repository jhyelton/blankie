"""Command-line entry point: `series-data generate | check | check-patreon`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from series_data import paths
from series_data.feed import FeedParseError
from series_data.fetch import FetchError, LiveSource, OfflineSource
from series_data.generate import check, generate, serialize
from series_data.overrides import OverrideError, load_overrides
from series_data.pipeline import GenerationError
from series_data.wiki import WikiParseError


def _load_json(path: Path) -> Any | None:
    return json.loads(path.read_text()) if path.exists() else None


def _cmd_generate(args: argparse.Namespace) -> int:
    source = OfflineSource(args.offline) if args.offline else LiveSource()
    try:
        try:
            result = generate(
                source,
                load_overrides(args.overrides),
                _load_json(args.previous),
                accept_guardrail_changes=args.accept_guardrail_changes,
            )
        finally:
            if args.save_raw and isinstance(source, LiveSource):
                source.save(args.save_raw)
    except (FetchError, FeedParseError, WikiParseError, OverrideError, GenerationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    args.output.write_text(serialize(result.dataset))
    if args.report:
        args.report.write_text(result.report)
    else:
        print(result.report)
    if result.accepted:
        print(
            f"warning: {len(result.accepted)} guardrail(s) overridden; listed in the report",
            file=sys.stderr,
        )
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        overrides = load_overrides(args.overrides)
        dataset = _load_json(args.dataset)
    except (OverrideError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    result = check(dataset, overrides)
    for line in result.pending:
        print(f"pending: {line}")
    for line in result.errors:
        print(f"error: {line}", file=sys.stderr)
    if result.errors:
        return 1
    print(f"ok: series.json and {len(overrides)} override(s) are valid")
    return 0


def _cmd_check_patreon(args: argparse.Namespace) -> int:
    from series_data.patreon import run

    return run(args.dataset)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="series-data", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="fetch the wiki and feed, then write data/series.json")
    gen.add_argument(
        "--offline", type=Path, metavar="DIR", help="read responses saved with --save-raw"
    )
    gen.add_argument("--save-raw", type=Path, metavar="DIR", help="save every raw response here")
    gen.add_argument(
        "--accept-guardrail-changes",
        action="store_true",
        help="propose the dataset even if guardrails fail; the report lists them",
    )
    gen.add_argument("--report", type=Path, metavar="FILE", help="write the report here")
    gen.add_argument("--output", type=Path, default=paths.SERIES_JSON)
    gen.add_argument("--previous", type=Path, default=paths.SERIES_JSON)
    gen.add_argument("--overrides", type=Path, default=paths.OVERRIDES_JSON)
    gen.set_defaults(func=_cmd_generate)

    chk = sub.add_parser("check", help="validate committed data without network access")
    chk.add_argument("--dataset", type=Path, default=paths.SERIES_JSON)
    chk.add_argument("--overrides", type=Path, default=paths.OVERRIDES_JSON)
    chk.set_defaults(func=_cmd_check)

    pat = sub.add_parser(
        "check-patreon", help="local only: check Special Features matching against your feed"
    )
    pat.add_argument("--dataset", type=Path, default=paths.SERIES_JSON)
    pat.set_defaults(func=_cmd_check_patreon)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
