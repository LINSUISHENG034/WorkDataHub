# Validation Report

**Generated:** 2025-12-08 17:52:47
**Dry Run:** True
**Runtime (s):** 3.28
**Throughput (rows/s):** 9402.95

## Preflight
- **postgres_version_num**: 170006
- **table**: enterprise.enrichment_index
- **unique_index**: (lookup_key, lookup_type)
- **python_version**: 3.12.10

## Totals
- Total Read: 30798
- Inserted: 30798
- Updated: 0
- Skipped: 0
- Errors: 0

## Sources
### legacy.company_id_mapping
- Read: 19141
- Inserted: 19141
- Updated: 0
- Skipped: 0
- Errors: 0
- Sample:
- `宜昌市财源小额贷款有限责任公司` -> `610199601` (confidence=1.00)
- `广州汽车工业集团有限公司` -> `602827061` (confidence=1.00)
- `英格卡商贸（上海）有限公司` -> `616090167` (confidence=1.00)
- `龙岩市住房置业融资担保有限公司` -> `653441389` (confidence=1.00)
- `甘肃新瑞城市建设有限公司` -> `604494154` (confidence=1.00)

### legacy.eqc_search_result
- Read: 11657
- Inserted: 11657
- Updated: 0
- Skipped: 0
- Errors: 0
- Sample:
- `4403011011760` -> `622835248` (confidence=1.00)
- `深圳市土地房产交易中心` -> `696024146` (confidence=1.00)
- `11441900mb2c902079` -> `879132514` (confidence=1.00)
- `121000004000129672` -> `696150150` (confidence=1.00)
- `1210000071780089xh` -> `695545334` (confidence=1.00)
