# promotions_worked Field Implementation

## Overview
Added `promotions_worked` field to the `matches` table to efficiently query which promotions wrestlers have worked for, without needing to parse all match JSON data.

## Changes Made

### 1. Database Schema ([joshirank/joshidb.py](joshirank/joshidb.py))
- Added `promotions_worked TEXT` column to matches table (line 92)
- Field stores JSON mapping of promotion_id → match count per year

### 2. Data Population ([joshirank/joshidb.py](joshirank/joshidb.py))
- Modified `update_matches_from_matches()` (lines 244-266)
- Added `promotions_worked` Counter alongside existing `countries_worked`
- Parses `match["promotion"]` field from cm_matches_json
- Filters out None values automatically

### 3. Data Retrieval ([joshirank/joshidb.py](joshirank/joshidb.py))
- Updated `get_match_info()` (lines 439-458)
- Returns `promotions_worked` as deserialized dict
- Returns empty dict `{}` if no data exists

### 4. Query Optimization ([joshirank/queries.py](joshirank/queries.py))
- Rewrote `all_tjpw_wrestlers()` to use promotions_worked field
- **Performance**: Reads pre-aggregated counts instead of parsing all matches
- **Efficiency**: For wrestler with 100 matches, reads 1 JSON field instead of 100 match records

### 5. Migration Script ([migrate_promotions.py](migrate_promotions.py))
- Populates promotions_worked for all 6,651 existing wrestlers with match data
- Adds column if it doesn't exist (for future DB instances)
- Runs in ~30 seconds

## Usage Examples

### Check what promotions a wrestler worked for:
```python
from joshirank.joshidb import wrestler_db

match_info = wrestler_db.get_match_info(16547, 2025)  # Yuka Sakazaki
print(match_info['promotions_worked'])
# Output: {'4': 7, '1467': 2, '2287': 2, ...}
# Promotion 1467 (TJPW): 2 matches in 2025
```

### Find all wrestlers who worked for a specific promotion:
```python
from joshirank.queries import all_tjpw_wrestlers
from joshirank.joshidb import wrestler_db

tjpw_wrestlers = all_tjpw_wrestlers(wrestler_db)
print(f"Found {len(tjpw_wrestlers)} TJPW wrestlers")
# Output: Found 62 TJPW wrestlers
```

### Aggregate across all years:
```python
from joshirank.joshidb import wrestler_db

def total_promotion_matches(wrestler_id, promotion_id):
    years = wrestler_db.match_years_available(wrestler_id)
    total = 0
    for year in years:
        match_info = wrestler_db.get_match_info(wrestler_id, year)
        promotions = match_info.get('promotions_worked', {})
        total += promotions.get(str(promotion_id), 0)
    return total

# Hikaru Shida's TJPW matches across all years
print(total_promotion_matches(9462, 1467))  # 4 matches (3 in 2022, 1 in 2024)
```

## Data Format

### Storage (SQLite):
```json
{"1467": 3, "326": 4, "2287": 27}
```
- Keys: promotion_id as string (JSON requires string keys)
- Values: match count for that promotion in that year

### Retrieval (Python):
```python
{
    "1467": 3,  # TJPW: 3 matches
    "326": 4,   # Stardom: 4 matches
    "2287": 27  # AEW: 27 matches
}
```

## Key Promotion IDs
- `1467`: Tokyo Joshi Pro-Wrestling (TJPW)
- `326`: World Wonder Ring Stardom
- `2287`: All Elite Wrestling (AEW)
- `154`: Ice Ribbon
- `327`: Pro Wrestling WAVE

## Testing
Run `python test_promotions_worked.py` to verify:
- ✓ Field is populated correctly
- ✓ all_tjpw_wrestlers() query works
- ✓ Both countries_worked and promotions_worked coexist

## Migration Instructions

For existing databases:
```bash
uv run python migrate_promotions.py
```

For new installations, the field is automatically created by `_create_matches_table()`.

## Performance Benefits

**Before**: Query all TJPW wrestlers
- Read cm_matches_json for all wrestlers, all years (~40,000+ records)
- Parse JSON for each record
- Check each match's promotion field
- **Est. time**: 10-30 seconds

**After**: Query all TJPW wrestlers
- Read promotions_worked for all wrestlers, all years (~40,000+ records)
- Simple dict lookup: `str(1467) in promotions`
- **Est. time**: 1-2 seconds (5-30x faster)

## Notes
- Promotion IDs are stored as strings in JSON (JSON spec requirement)
- Query functions should check both `str(promotion_id)` and `int(promotion_id)` for safety
- Field is automatically populated when `update_matches_from_matches()` is called
- Follows exact same pattern as `countries_worked` field for consistency
