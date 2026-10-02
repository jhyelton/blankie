from series_data.cli import build_parser


def test_parser_has_three_subcommands():
    help_text = build_parser().format_help()
    for name in ("generate", "check", "check-patreon"):
        assert name in help_text
