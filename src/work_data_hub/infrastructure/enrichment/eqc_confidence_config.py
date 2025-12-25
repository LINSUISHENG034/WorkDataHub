"""
EQC Confidence Configuration Module (Story 7.1-8).

This module provides configuration management for EQC match type confidence scoring.
Confidence scores are assigned based on the quality of match returned by the EQC API:
- 全称精确匹配 (exact full name match) - highest reliability (1.00)
- 模糊匹配 (fuzzy match) - medium reliability (0.80)
- 拼音 (pinyin match) - lowest reliability (0.60)

Architecture Pattern: Follows DomainLearningConfig pattern in types.py
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import yaml

from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EQCConfidenceConfig:
    """
    Configuration for EQC match type confidence scoring.

    Attributes:
        eqc_match_confidence: Dictionary mapping EQC match type to confidence score.
        min_confidence_for_cache: Minimum confidence threshold for caching results.

    Example:
        >>> config = EQCConfidenceConfig.load_from_yaml()
        >>> confidence = config.get_confidence_for_match_type("全称精确匹配")
        >>> assert confidence == 1.00
    """

    eqc_match_confidence: Dict[str, float]
    min_confidence_for_cache: float

    @staticmethod
    def load_from_yaml(
        config_path: str = "config/eqc_confidence.yml",
    ) -> "EQCConfidenceConfig":
        """
        Load and validate configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file.

        Returns:
            EQCConfidenceConfig instance with validated values.

        Raises:
            ValueError: If confidence values are not in range [0.0, 1.0].
            yaml.YAMLError: If YAML file is malformed.
        """
        config_file = Path(config_path)

        if not config_file.exists():
            logger.warning(
                "eqc_confidence.config_not_found",
                msg=f"EQC confidence config not found: {config_path}, using defaults",
            )
            return EQCConfidenceConfig.get_default_config()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(
                "eqc_confidence.yaml_parse_error",
                msg=f"Invalid YAML in eqc_confidence.yml: {e}",
            )
            raise

        # Validate confidence range [0.0, 1.0]
        eqc_match_confidence = data.get("eqc_match_confidence", {})
        for match_type, confidence in eqc_match_confidence.items():
            if not isinstance(confidence, (int, float)):
                raise ValueError(
                    f"Confidence must be numeric, got {type(confidence)} for {match_type}"
                )
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(
                    f"Invalid confidence {confidence} for {match_type}: must be in [0.0, 1.0]"
                )

        # Validate min_confidence_for_cache
        min_confidence_for_cache = data.get("min_confidence_for_cache", 0.60)
        if not isinstance(min_confidence_for_cache, (int, float)):
            raise ValueError("min_confidence_for_cache must be numeric")
        if not 0.0 <= min_confidence_for_cache <= 1.0:
            raise ValueError(
                f"Invalid min_confidence_for_cache {min_confidence_for_cache}: "
                "must be in [0.0, 1.0]"
            )

        logger.info(
            "eqc_confidence.config_loaded",
            config_path=str(config_file),
            match_types_count=len(eqc_match_confidence),
            min_confidence=min_confidence_for_cache,
        )

        return EQCConfidenceConfig(
            eqc_match_confidence=eqc_match_confidence,
            min_confidence_for_cache=min_confidence_for_cache,
        )

    def get_confidence_for_match_type(self, match_type: str) -> float:
        """
        Get confidence score for a given match type.

        Args:
            match_type: EQC match type string (e.g., "全称精确匹配", "模糊匹配", "拼音").

        Returns:
            Confidence score in range [0.0, 1.0]. Returns default confidence if match type
            is not found in configuration.
        """
        return self.eqc_match_confidence.get(
            match_type, self.eqc_match_confidence.get("default", 0.70)
        )

    @staticmethod
    def get_default_config() -> "EQCConfidenceConfig":
        """
        Return default configuration if file is missing.

        Provides sensible defaults for common EQC match types.
        """
        return EQCConfidenceConfig(
            eqc_match_confidence={
                "全称精确匹配": 1.00,
                "模糊匹配": 0.80,
                "拼音": 0.60,
                "default": 0.70,
            },
            min_confidence_for_cache=0.60,
        )
