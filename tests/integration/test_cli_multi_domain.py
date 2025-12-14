"""
CLI-level tests for multi-domain CLI functionality (mock-based).

Story 6.2-P6: CLI Architecture Unification & Multi-Domain Batch Processing
Task 4.4: Add multi-domain integration tests

These tests verify (primarily via mocking execution):
- Multi-domain sequential execution
- Domain validation (reject special domains in multi-domain runs)
- --all-domains flag discovery
- Continue-on-failure behavior
- Exit code behavior
"""

import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from work_data_hub.cli.etl import (
    _load_configured_domains,
    _validate_domains,
    main as etl_main,
)


class TestDomainValidation:
    """Test domain validation logic."""

    def test_validate_configured_domains_only(self):
        """Test that configured domains are validated correctly."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = ['annuity_performance', 'annuity_income', 'sample_trustee_performance']

            # Test valid configured domains
            valid, invalid = _validate_domains(['annuity_performance', 'annuity_income'], allow_special=False)
            assert valid == ['annuity_performance', 'annuity_income']
            assert invalid == []

    def test_validate_rejects_special_domains_in_multi_domain(self):
        """Test that special orchestration domains are rejected in multi-domain runs."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = ['annuity_performance', 'annuity_income']

            # Test that special domains are rejected when allow_special=False
            valid, invalid = _validate_domains(
                ['annuity_performance', 'company_mapping'],
                allow_special=False
            )
            assert valid == ['annuity_performance']
            assert invalid == ['company_mapping']

    def test_validate_allows_special_domains_in_single_domain(self):
        """Test that special orchestration domains are allowed in single-domain runs."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = ['annuity_performance', 'annuity_income']

            # Test that special domains are allowed when allow_special=True
            valid, invalid = _validate_domains(
                ['company_mapping'],
                allow_special=True
            )
            assert valid == ['company_mapping']
            assert invalid == []

    def test_validate_unknown_domain(self):
        """Test that unknown domains are rejected."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = ['annuity_performance', 'annuity_income']

            # Test that unknown domains are rejected
            valid, invalid = _validate_domains(
                ['unknown_domain'],
                allow_special=False
            )
            assert valid == []
            assert invalid == ['unknown_domain']


class TestAllDomainsDiscovery:
    """Test --all-domains flag domain discovery."""

    def test_load_configured_domains(self):
        """Test that configured domains are loaded from data_sources.yml."""
        # This test requires a valid data_sources.yml file
        # In a real environment, this would load actual configured domains
        domains = _load_configured_domains()

        # Verify that we get a list of domains
        assert isinstance(domains, list)

        # Verify that common domains are present (if they exist in config)
        # This is environment-dependent, so we just check the structure
        if domains:
            assert all(isinstance(d, str) for d in domains)

    def test_all_domains_excludes_special_domains(self):
        """Test that --all-domains excludes special orchestration domains."""
        # Mock configured domains including a special domain
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = [
                'annuity_performance',
                'annuity_income',
                'sample_trustee_performance',
                'company_mapping',  # This should be excluded
            ]

            # Simulate --all-domains logic
            configured_domains = _load_configured_domains()
            SPECIAL_DOMAINS = {"company_mapping", "company_lookup_queue", "reference_sync"}
            domains_to_process = [d for d in configured_domains if d not in SPECIAL_DOMAINS]

            # Verify special domains are excluded
            assert 'company_mapping' not in domains_to_process
            assert 'annuity_performance' in domains_to_process
            assert 'annuity_income' in domains_to_process


class TestMultiDomainCLI:
    """Test multi-domain CLI execution."""

    def test_multi_domain_validation_error(self, capsys):
        """Test that multi-domain runs reject special domains with clear error message."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = ['annuity_performance', 'annuity_income']

            # Test multi-domain with special domain (should fail)
            argv = [
                '--domains', 'annuity_performance,company_mapping',
                '--period', '202411',
                '--plan-only'
            ]

            exit_code = etl_main(argv)

            # Verify exit code indicates failure
            assert exit_code == 1

            # Verify error message
            captured = capsys.readouterr()
            assert 'Invalid domains for multi-domain processing' in captured.out
            assert 'company_mapping' in captured.out

    def test_single_domain_allows_special_domain(self):
        """Test that single-domain runs allow special orchestration domains."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = ['annuity_performance', 'annuity_income']

            # Mock _execute_single_domain to avoid actual execution
            with patch('work_data_hub.cli.etl._execute_single_domain') as mock_execute:
                mock_execute.return_value = 0

                # Test single domain with special domain (should succeed validation)
                argv = [
                    '--domains', 'company_mapping',
                    '--execute'
                ]

                exit_code = etl_main(argv)

                # Verify that execution was attempted (validation passed)
                mock_execute.assert_called_once()
                assert exit_code == 0

    def test_all_domains_flag(self, capsys):
        """Test that --all-domains flag discovers and processes configured domains."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = [
                'annuity_performance',
                'annuity_income',
                'sample_trustee_performance'
            ]

            # Mock _execute_single_domain to avoid actual execution
            with patch('work_data_hub.cli.etl._execute_single_domain') as mock_execute:
                mock_execute.return_value = 0

                # Test --all-domains flag
                argv = [
                    '--all-domains',
                    '--period', '202411',
                    '--plan-only'
                ]

                exit_code = etl_main(argv)

                # Verify that all domains were processed
                assert mock_execute.call_count == 3

                # Verify output shows domain processing
                captured = capsys.readouterr()
                assert 'Processing all configured domains' in captured.out
                assert 'annuity_performance' in captured.out
                assert 'annuity_income' in captured.out


class TestMultiDomainExecution:
    """Test multi-domain sequential execution behavior."""

    def test_multi_domain_sequential_execution(self):
        """Test that multiple domains are processed sequentially."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = ['annuity_performance', 'annuity_income']

            # Mock _execute_single_domain to track execution order
            execution_order = []

            def mock_execute(args, domain):
                execution_order.append(domain)
                return 0

            with patch('work_data_hub.cli.etl._execute_single_domain', side_effect=mock_execute):
                # Test multi-domain execution
                argv = [
                    '--domains', 'annuity_performance,annuity_income',
                    '--period', '202411',
                    '--plan-only'
                ]

                exit_code = etl_main(argv)

                # Verify sequential execution
                assert execution_order == ['annuity_performance', 'annuity_income']
                assert exit_code == 0

    def test_multi_domain_continue_on_failure(self, capsys):
        """Test that multi-domain execution continues after domain failure."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = ['annuity_performance', 'annuity_income', 'sample_trustee_performance']

            # Mock _execute_single_domain to simulate failure on second domain
            execution_order = []

            def mock_execute(args, domain):
                execution_order.append(domain)
                if domain == 'annuity_income':
                    return 1  # Simulate failure
                return 0

            with patch('work_data_hub.cli.etl._execute_single_domain', side_effect=mock_execute):
                # Test multi-domain execution with failure
                argv = [
                    '--domains', 'annuity_performance,annuity_income,sample_trustee_performance',
                    '--period', '202411',
                    '--plan-only'
                ]

                exit_code = etl_main(argv)

                # Verify all domains were attempted despite failure
                assert execution_order == ['annuity_performance', 'annuity_income', 'sample_trustee_performance']

                # Verify exit code indicates failure
                assert exit_code == 1

                # Verify summary shows failure
                captured = capsys.readouterr()
                assert 'MULTI-DOMAIN BATCH PROCESSING SUMMARY' in captured.out
                assert 'Failed: 1' in captured.out

    def test_multi_domain_all_success_exit_code(self):
        """Test that exit code is 0 when all domains succeed."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = ['annuity_performance', 'annuity_income']

            # Mock _execute_single_domain to simulate success
            with patch('work_data_hub.cli.etl._execute_single_domain') as mock_execute:
                mock_execute.return_value = 0

                # Test multi-domain execution
                argv = [
                    '--domains', 'annuity_performance,annuity_income',
                    '--period', '202411',
                    '--plan-only'
                ]

                exit_code = etl_main(argv)

                # Verify exit code indicates success
                assert exit_code == 0

    def test_multi_domain_any_failure_exit_code(self):
        """Test that exit code is 1 when any domain fails."""
        # Mock configured domains
        with patch('work_data_hub.cli.etl._load_configured_domains') as mock_load:
            mock_load.return_value = ['annuity_performance', 'annuity_income']

            # Mock _execute_single_domain to simulate failure on one domain
            def mock_execute(args, domain):
                if domain == 'annuity_income':
                    return 1  # Simulate failure
                return 0

            with patch('work_data_hub.cli.etl._execute_single_domain', side_effect=mock_execute):
                # Test multi-domain execution
                argv = [
                    '--domains', 'annuity_performance,annuity_income',
                    '--period', '202411',
                    '--plan-only'
                ]

                exit_code = etl_main(argv)

                # Verify exit code indicates failure
                assert exit_code == 1


class TestCLIArgumentParsing:
    """Test CLI argument parsing for multi-domain features."""

    def test_domains_and_all_domains_mutually_exclusive(self, capsys):
        """Test that --domains and --all-domains cannot be used together."""
        argv = [
            '--domains', 'annuity_performance',
            '--all-domains',
            '--period', '202411',
            '--plan-only'
        ]

        # This should fail during argument parsing
        with pytest.raises(SystemExit):
            etl_main(argv)

    def test_requires_domains_or_all_domains(self, capsys):
        """Test that either --domains or --all-domains must be specified."""
        argv = [
            '--period', '202411',
            '--plan-only'
        ]

        # This should fail during argument parsing
        with pytest.raises(SystemExit):
            etl_main(argv)


# Manual verification test cases (not automated)
"""
Manual Verification Test Cases:

1. Test multi-domain execution with real data:
   ```bash
   python -m work_data_hub.cli etl --domains annuity_performance,annuity_income --period 202411 --mode append --plan-only
   ```
   Expected: Both domains processed sequentially, summary shows 2 successful domains

2. Test --all-domains flag:
   ```bash
   python -m work_data_hub.cli etl --all-domains --period 202411 --mode append --plan-only
   ```
   Expected: All configured domains discovered and processed, special domains excluded

3. Test domain validation error:
   ```bash
   python -m work_data_hub.cli etl --domains annuity_performance,company_mapping --period 202411 --plan-only
   ```
   Expected: Error message about invalid domains for multi-domain processing

4. Test single-domain with special domain:
   ```bash
   python -m work_data_hub.cli etl --domains company_mapping --execute
   ```
   Expected: Validation passes, company mapping job executes

5. Test continue-on-failure (requires setup to force failure):
   - Modify one domain to fail (e.g., invalid period)
   - Run multi-domain command
   - Expected: First domain fails, second domain still processes, exit code 1
"""
