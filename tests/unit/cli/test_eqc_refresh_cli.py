"""Unit tests for eqc_refresh CLI argument parsing (Story 6.2-P5)."""

import pytest

from work_data_hub.cli.eqc_refresh import build_parser


@pytest.mark.unit
class TestEqcRefreshCliParsing:
    def test_parses_initial_full_refresh_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--initial-full-refresh", "--yes"])
        assert args.initial_full_refresh is True
        assert args.yes is True

    def test_parses_resume_from_checkpoint_alias(self):
        parser = build_parser()
        args = parser.parse_args(["--resume-from-checkpoint", "--yes"])
        assert args.resume_from_checkpoint is True
        assert args.yes is True

    def test_parses_refresh_all_legacy_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--refresh-all"])
        assert args.refresh_all is True
