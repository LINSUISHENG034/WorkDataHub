"""Unicode processing constants for cleansing rules (Story 7.1-16).

Constants for fullwidth CJK character range handling used in company name
normalization and string processing.
"""

# Fullwidth ASCII character range (U+FF01 to U+FF5E)
# Used for normalizing Chinese/Japanese text with fullwidth punctuation to halfwidth
FULLWIDTH_CHAR_START = 0xFF01  # Fullwidth exclamation mark ！
FULLWIDTH_CHAR_END = 0xFF5E  # Fullwidth tilde ～

# Offset to convert fullwidth ASCII to halfwidth
# fullwidth - halfwidth = 0xFEE0
FULLWIDTH_TO_HALFWIDTH_OFFSET = 0xFEE0
