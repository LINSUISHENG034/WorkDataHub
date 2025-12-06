"""Pattern-based file matching with include/exclude rules.

This module implements file pattern matching capabilities for Epic 3,
following Decision #1 (File-Pattern-Aware Version Detection) and
Decision #4 (Hybrid Error Context Standards) from architecture.
"""

import fnmatch
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from work_data_hub.io.connectors.exceptions import DiscoveryError
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FileMatchResult:
    """Result of file pattern matching.

    Provides comprehensive metadata about the matching process
    following Epic 3 structured logging requirements.
    """

    matched_file: Path  # Selected file path
    patterns_used: List[str]  # Include patterns tried
    exclude_patterns: List[str]  # Exclude patterns applied
    candidates_found: List[Path]  # All files before filtering
    excluded_files: List[Path]  # Files filtered out
    match_count: int  # Files remaining after filtering
    selected_at: datetime  # Timestamp of selection


class FilePatternMatcher:
    """Match files using glob patterns with include/exclude rules.

    Implements core file matching capability from Epic 3 Story 3.2,
    providing flexible pattern matching with Unicode support and
    structured error handling.
    """

    def match_files(
        self,
        search_path: Path,
        include_patterns: List[str],
        exclude_patterns: Optional[List[str]] = None,
    ) -> FileMatchResult:
        """
        Match files in search_path using include/exclude patterns.

        Args:
            search_path: Directory to search for files
            include_patterns: Glob patterns to include (OR logic)
            exclude_patterns: Glob patterns to exclude (AND NOT logic)

        Returns:
            FileMatchResult with selected file and metadata

        Raises:
            DiscoveryError: If no files match or multiple files remain after filtering
        """
        exclude_patterns = exclude_patterns or []

        logger.info(
            "file_matching.started",
            search_path=str(search_path),
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )

        # Step 1: Find all files matching include patterns
        candidates = self._find_candidates(search_path, include_patterns)

        # Step 2: Apply exclude patterns
        (matched, excluded) = self._apply_excludes(candidates, exclude_patterns)

        # Step 3: Validate exactly 1 file remains
        if len(matched) == 0:
            raise DiscoveryError(
                domain="unknown",
                failed_stage="file_matching",
                original_error=FileNotFoundError("No matching files"),
                message=(
                    f"No files found matching patterns {include_patterns} "
                    f"in path {search_path}. Candidates found: {len(candidates)}, "
                    f"Files excluded: {len(excluded)}"
                ),
            )

        if len(matched) > 1:
            raise DiscoveryError(
                domain="unknown",
                failed_stage="file_matching",
                original_error=ValueError("Ambiguous file match"),
                message=(
                    f"Ambiguous match: Found {len(matched)} files {matched}, "
                    f"refine patterns or use version detection. "
                    f"Searched in {search_path} with patterns {include_patterns}"
                ),
            )

        selected_file = matched[0]

        logger.info(
            "file_matching.completed",
            search_path=str(search_path),
            candidates_count=len(candidates),
            excluded_count=len(excluded),
            selected_file=str(selected_file),
            match_count=len(matched),
        )

        return FileMatchResult(
            matched_file=selected_file,
            patterns_used=include_patterns,
            exclude_patterns=exclude_patterns,
            candidates_found=candidates,
            excluded_files=excluded,
            match_count=len(matched),
            selected_at=datetime.now(),
        )

    def _find_candidates(self, search_path: Path, patterns: List[str]) -> List[Path]:
        """Find all files matching any include pattern."""
        candidates = []
        for pattern in patterns:
            try:
                matches = list(search_path.glob(pattern))
                candidates.extend(matches)
                logger.debug(
                    "file_matching.pattern_matched",
                    pattern=pattern,
                    matches_count=len(matches),
                    matches=[str(m) for m in matches],
                )
            except Exception as e:
                logger.warning(
                    "file_matching.pattern_failed", pattern=pattern, error=str(e)
                )

        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique_candidates.append(candidate)

        return unique_candidates

    def _apply_excludes(
        self, candidates: List[Path], exclude_patterns: List[str]
    ) -> Tuple[List[Path], List[Path]]:
        """Apply exclude patterns to candidates."""
        included = []
        excluded = []

        for candidate in candidates:
            # Check if candidate matches any exclude pattern
            is_excluded = False
            for pattern in exclude_patterns:
                if self._matches_pattern(candidate.name, pattern):
                    is_excluded = True
                    excluded.append(candidate)
                    logger.debug(
                        "file_matching.file_excluded",
                        file=str(candidate),
                        pattern=pattern,
                    )
                    break

            if not is_excluded:
                included.append(candidate)

        return included, excluded

    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches pattern, handling Unicode."""
        # Normalize both filename and pattern for Unicode consistency
        norm_filename = unicodedata.normalize("NFC", filename)
        norm_pattern = unicodedata.normalize("NFC", pattern)

        # Use fnmatch for glob pattern matching
        return fnmatch.fnmatch(norm_filename, norm_pattern)
