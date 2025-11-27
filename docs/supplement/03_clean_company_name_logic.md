  ---
  Analysis of Legacy clean_company_name (lines 309-355)

  The legacy function is significantly more sophisticated than my initial recommendation:

  Key Operations

  1. Complete whitespace removal (line 324)
  name = re.sub(r'\s+', '', name)  # Removes ALL spaces, not just trim
  2. Business-specific pattern removal (lines 327-328)
    - Removes: "及下属子企业" (and subsidiaries)
    - Removes trailing: (团托), -A, -123, -养老, -福利
  3. Status marker cleansing (lines 330-343)
    - Extensive set of invalid markers: 已转出, 待转出, 终止, 转出, 保留, etc. (29 patterns!)
    - Removes from both start and end of name
    - Handles markers with/without parentheses
  4. Character width normalization (lines 345-350)
    - Default behavior (to_fullwidth=False): Full-width → Half-width
    - Example: "公司Ａ" → "公司A" (opposite of NFKC!)
  5. Bracket normalization (line 353)
  name = name.replace('(', '（').replace(')', '）')  # English → Chinese brackets

  Notable: No lowercasing (preserves case)

  ---
  Updated Decision: Legacy-Compatible Normalization

  For temporary ID generation, I recommend a two-step approach:

  Step 1: Reuse Legacy Normalization Core

  def normalize_for_temp_id(company_name: str) -> str:
      """
      Normalize company name for temporary ID generation.
      Uses legacy-compatible normalization to ensure consistency with existing data.

      Based on: legacy/annuity_hub/common_utils/common_utils.py::clean_company_name
      """
      if not company_name:
          return ''

      name = company_name

      # 1. Remove all whitespace (legacy behavior)
      name = re.sub(r'\s+', '', name)

      # 2. Remove business-specific patterns
      name = re.sub(r'及下属子企业', '', name)
      name = re.sub(r'(?:\(团托\)|-[A-Za-z]+|-\d+|-养老|-福利)$', '', name)

      # 3. Remove status markers (from CORE_REPLACE_STRING)
      # Import from legacy or duplicate the pattern list
      for core_str in CORE_REPLACE_STRING_SORTED:  # See legacy lines 14-30
          pattern_start = rf'^([\(\（]?){re.escape(core_str)}([\)\）]?)(?=[^\u4e00-\u9fff]|$)'
          name = re.sub(pattern_start, '', name)

          pattern_end =
  rf'(?<![\u4e00-\u9fff])([\-\(\（]?){re.escape(core_str)}([\)\）]?)[\-\(\（\)\）]*$'
          name = re.sub(pattern_end, '', name)

      # 4. Remove trailing punctuation
      name = re.sub(r'[\-\(\（\)\）]+$', '', name)

      # 5. Full-width → Half-width conversion (legacy default)
      name = ''.join([
          chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char
          for char in name
      ])

      # 6. Normalize brackets to Chinese (legacy behavior)
      name = name.replace('(', '（').replace(')', '）')

      # 7. Additional: Lowercase for hash stability (NEW - not in legacy)
      #    This ensures "公司A" and "公司a" get same temp ID
      name = name.lower()

      return name

  Step 2: Generate Temporary ID

  def generate_temp_company_id(company_name: str, salt: str) -> str:
      """
      Generate stable temporary company ID with legacy-compatible normalization.

      Format: IN_<16-char-Base32>
      Algorithm: HMAC-SHA1 (more secure than legacy MD5)

      Note: Legacy uses MD5 with GM/GC prefixes for different purpose.
            This is NEW temporary ID system with IN_ prefix.
      """
      normalized = normalize_for_temp_id(company_name)

      # HMAC-SHA1 with secret salt (more secure than legacy MD5)
      digest = hmac.new(
          salt.encode('utf-8'),
          normalized.encode('utf-8'),
          hashlib.sha1
      ).digest()

      # Take first 80 bits (10 bytes), Base32 encode → 16 chars
      encoded = base64.b32encode(digest[:10]).decode('ascii')

      return f"IN_{encoded}"

  ---
  Key Architectural Decisions

  Decision #2 Finalized:

  | Aspect          | Decision                                                | Rationale
                             |
  |-----------------|---------------------------------------------------------|---------------------    
  ---------------------------|
  | Business Key    | Normalized company name only                            | Enable cross-domain     
  joins                      |
  | Normalization   | Legacy-compatible (reuse clean_company_name core logic) | Maintain parity with    
   existing data cleansing   |
  | Additional Step | Add .lower() for hash input                             | Ensure
  case-insensitive matching               |
  | Hash Algorithm  | HMAC-SHA1 (not MD5)                                     | More secure,
  cryptographically sound           |
  | ID Format       | IN_<16-char-Base32>                                     | Distinguishable from    
   legacy GM/GC codes        |
  | Salt Management | WDH_ALIAS_SALT environment variable                     | Must be secret,
  consistent across environments |

  ---
  Implementation Notes for AI Agents

  Epic 5 Story 5.2 Implementation:

  1. Extract legacy normalization patterns into shared module:
    - CORE_REPLACE_STRING set → src/work_data_hub/cleansing/config/status_markers.py
    - Core normalization logic → src/work_data_hub/utils/company_normalizer.py
  2. Reuse legacy patterns but document differences:
  # src/work_data_hub/utils/company_normalizer.py

  def normalize_company_name_legacy_compat(name: str) -> str:
      """
      Legacy-compatible normalization for company names.

      Based on: legacy/annuity_hub/common_utils/common_utils.py::clean_company_name

      Differences from legacy:
      - Adds .lower() at end for temp ID stability (legacy preserves case)
      - Uses imported CORE_REPLACE_STRING (same content as legacy)
      """
      # ... implementation following legacy pattern ...
  3. Test parity with legacy using golden datasets:
  def test_normalization_parity():
      """Ensure new normalization matches legacy for known companies."""
      legacy_results = load_legacy_normalized_names()
      for company in test_companies:
          new_result = normalize_company_name_legacy_compat(company).lower()
          legacy_result = legacy_clean_company_name(company).lower()
          assert new_result == legacy_result

  ---
  Does this legacy-compatible approach address your normalization concerns?

  This ensures:
  - ✅ Parity with existing data cleansing logic
  - ✅ Handles business-specific patterns (status markers, subsidiaries)
  - ✅ Stable temporary IDs across runs
  - ✅ Documented differences for future maintenance