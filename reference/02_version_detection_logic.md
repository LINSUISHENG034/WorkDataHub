  ---
  The Real-World Complexity

  Your scenario:
  reference/monthly/202501/收集数据/业务收集/
  ├── V1/
  │   ├── 年金数据.xlsx        ← Annuity data (original)
  │   ├── 业务收集.xlsx        ← Business collection data
  │   └── 投资数据.xlsx        ← Investment data
  └── V2/
      └── 年金数据.xlsx        ← ONLY annuity was corrected

  Problem with folder-level version detection:
  - If we select V2 for the entire 业务收集 folder, we'd miss 业务收集.xlsx and 投资数据.xlsx (only     
  in V1)
  - If we select V1, we'd miss the corrected annuity data in V2
  - Data loss either way! ❌

  ---
  Revised Solution: File-Level Version Detection

  Key Insight: Version detection should be scoped to each domain's file pattern, not to the physical    
   folder.

  How It Works

  Given these domain configurations:
  domains:
    annuity_performance:
      base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
      file_patterns: ["*年金*.xlsx"]

    business_collection:
      base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"  # Same folder!
      file_patterns: ["*业务收集*.xlsx"]

  Version Detection Logic (per domain):

  1. For annuity_performance:
    - Scan: Does V3/*年金*.xlsx exist? → No
    - Scan: Does V2/*年金*.xlsx exist? → Yes → Use V2
    - Result: V2/年金数据.xlsx ✅
  2. For business_collection:
    - Scan: Does V3/*业务收集*.xlsx exist? → No
    - Scan: Does V2/*业务收集*.xlsx exist? → No
    - Scan: Does V1/*业务收集*.xlsx exist? → Yes → Use V1
    - Result: V1/业务收集.xlsx ✅

  Each domain independently finds its highest version where a matching file exists.

  ---
  Refined Decision Rules

  Version Detection Algorithm (File-Pattern-Aware):

  def detect_version(base_path: Path, file_patterns: List[str]) -> Path:
      """
      Returns the versioned path where files matching patterns exist.
      Scopes version detection to specific file patterns, not entire folder.
      """
      # 1. Discover all version folders
      version_folders = sorted([v for v in base_path.glob("V*") if v.is_dir()],
                              reverse=True)  # V3, V2, V1

      # 2. For each version (highest first), check if ANY file pattern matches
      for version_folder in version_folders:
          for pattern in file_patterns:
              matches = list(version_folder.glob(pattern))
              if matches:
                  return version_folder  # First version with matching file wins

      # 3. Fallback: no versioned folders have matching files → use base path
      return base_path

  Example Execution:

  | Domain              | File Pattern | Scan V2    | Scan V1 | Selected Path | File Found   |
  |---------------------|--------------|------------|---------|---------------|--------------|
  | annuity_performance | *年金*.xlsx    | ✅ Match    | (skip)  | V2/           | V2/年金数据.xlsx     
  |
  | business_collection | *业务*.xlsx    | ❌ No match | ✅ Match | V1/           | V1/业务收集.xlsx    
   |
  | investment_data     | *投资*.xlsx    | ❌ No match | ✅ Match | V1/           | V1/投资数据.xlsx    
   |

  ---
  Edge Case Handling

  Case 1: File exists in multiple versions
  - Behavior: Pick highest version (V2 > V1)
  - Example: If 年金数据.xlsx exists in both V1 and V2 → use V2

  Case 2: File doesn't exist in any version
  - Behavior: Fall back to base path (no version folder)
  - Example: If only base_path/年金数据.xlsx exists (no V folders) → use base path

  Case 3: Ambiguous file matching (multiple files match pattern in same version)
  - Behavior: ERROR - refine pattern or use exclude rules
  - Example: V2 has both 年金数据2025.xlsx and 年金数据final.xlsx → Fail with actionable error

  ---
  Logging & Observability

  Structured log output:
  {
    "domain": "annuity_performance",
    "base_path": "reference/monthly/202501/收集数据/业务收集",
    "file_patterns": ["*年金*.xlsx"],
    "versions_scanned": ["V2", "V1"],
    "selected_version": "V2",
    "selected_file": "V2/年金数据.xlsx",
    "strategy": "highest_version_with_matching_file"
  }

  ---
  Does This Solve Your Scenario?

  ✅ Annuity data: Uses V2 (corrected version)✅ Business collection: Uses V1 (only version with        
  this file)✅ Investment data: Uses V1 (only version with this file)✅ No data loss: Each domain       
  independently selects the right version✅ Deterministic: Always picks highest version where file      
  exists✅ Debuggable: Clear logs show why each version was selected