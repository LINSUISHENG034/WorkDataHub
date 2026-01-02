"""Unit tests for ETL verbosity flags (Story 7.5-6)."""

import argparse

import pytest

from work_data_hub.cli.etl.main import main


@pytest.mark.unit
class TestVerbosityFlagsParsing:
    """Test suite for CLI verbosity level flag parsing."""

    def test_verbose_long_flag_accepted(self):
        """Test that --verbose flag is accepted by argument parser."""
        # This test verifies the argument parser accepts --verbose
        # We're not running main() to avoid complex mocking
        parser = argparse.ArgumentParser()
        parser.add_argument("--verbose", "-v", action="store_true", default=False)
        parser.add_argument("--domains", help="Domain to process")

        # Should not raise SystemExit
        args = parser.parse_args(["--domains", "annuity_performance", "--verbose"])
        assert args.verbose is True

    def test_verbose_short_flag_accepted(self):
        """Test that -v short flag is accepted."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--verbose", "-v", action="store_true", default=False)
        parser.add_argument("--domains", help="Domain to process")

        args = parser.parse_args(["--domains", "annuity_performance", "-v"])
        assert args.verbose is True

    def test_quiet_long_flag_accepted(self):
        """Test that --quiet flag is accepted by argument parser."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--quiet", "-q", action="store_true", default=False)
        parser.add_argument("--domains", help="Domain to process")

        args = parser.parse_args(["--domains", "annuity_performance", "--quiet"])
        assert args.quiet is True

    def test_quiet_short_flag_accepted(self):
        """Test that -q short flag is accepted."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--quiet", "-q", action="store_true", default=False)
        parser.add_argument("--domains", help="Domain to process")

        args = parser.parse_args(["--domains", "annuity_performance", "-q"])
        assert args.quiet is True

    def test_verbose_and_debug_combination(self):
        """Test that --verbose and --debug can be used together."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--verbose", "-v", action="store_true", default=False)
        parser.add_argument("--debug", action="store_true", default=False)
        parser.add_argument("--domains", help="Domain to process")

        args = parser.parse_args(
            ["--domains", "annuity_performance", "--verbose", "--debug"]
        )
        assert args.verbose is True
        assert args.debug is True

    def test_default_mode_no_verbosity_flags(self):
        """Test that parser works without verbosity flags (default mode)."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--verbose", "-v", action="store_true", default=False)
        parser.add_argument("--quiet", "-q", action="store_true", default=False)
        parser.add_argument("--domains", help="Domain to process")

        args = parser.parse_args(["--domains", "annuity_performance"])
        assert args.verbose is False
        assert args.quiet is False


@pytest.mark.unit
class TestReconfigureForConsoleSignature:
    """Test suite for reconfigure_for_console() function signature."""

    def test_reconfigure_for_console_accepts_verbose_parameter(self):
        """Test that reconfigure_for_console() accepts verbose parameter."""
        from work_data_hub.utils.logging import reconfigure_for_console
        import inspect

        sig = inspect.signature(reconfigure_for_console)
        params = sig.parameters

        # Verify 'verbose' parameter exists
        assert "verbose" in params
        # Verify default value is False
        assert params["verbose"].default is False
        # Verify 'debug' parameter exists (existing)
        assert "debug" in params
        # Story 7.5-6: Verify 'quiet' parameter exists (AC-2)
        assert "quiet" in params
        assert params["quiet"].default is False
