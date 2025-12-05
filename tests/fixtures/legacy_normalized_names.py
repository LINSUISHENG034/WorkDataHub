"""
Legacy normalized names for testing parity.
"""

LEGACY_TEST_CASES = [
    # Basic cases
    ("中国平安", "中国平安"),
    ("中国平安 ", "中国平安"),
    (" 中国平安", "中国平安"),
    # Status markers
    ("中国平安-已转出", "中国平安"),
    ("中国平安（已转出）", "中国平安"),
    # Business patterns
    ("中国平安及下属子企业", "中国平安"),
    ("中国平安-养老", "中国平安"),
    # Brackets
    ("中国平安(集团)", "中国平安（集团）"),
    # Full-width
    ("中国平安Ａ", "中国平安a"),
    # Combined
    ("中国平安(集团) -已转出", "中国平安（集团）"),
]