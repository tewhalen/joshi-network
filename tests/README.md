# Test Suite

## Overview
This test suite covers the core functionality of the Joshi Network scraping and ranking system.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── fixtures/
│   └── html/               # Real HTML from CageMatch.net
│       ├── wrestler_4629_profile.html
│       └── wrestler_4629_matches_2025.html
├── unit/                   # Fast, isolated tests
│   ├── test_profile.py
│   └── test_match_parsing.py
└── integration/            # Database integration tests
    └── test_database.py
```

## Fixtures

### Database Fixtures
- `temp_db` - Fresh temporary database for each test
- `seeded_db` - Pre-populated database with test wrestlers

### HTML Fixtures
- `sample_profile_html` - Emi Sakura's profile page
- `sample_matches_html` - Emi Sakura's 2025 matches
- `html_fixtures` - Path to HTML fixtures directory

## Running Tests

```bash
# Run all tests
make test
# or
uv run pytest

# Run with coverage
uv run pytest --cov=joshirank

# Run specific test file
uv run pytest tests/unit/test_profile.py

# Run with verbose output
uv run pytest -v
```

## Coverage
Current coverage: **67%** of core joshirank package

Strong coverage in:
- HTML parsing (88%)
- Database operations (60%)
- Match parsing (79%)

Areas to improve:
- `all_matches.py` (0% - needs singles match filtering tests)
- `identifier.py` (0% - needs promotion ID mapping tests)

## Adding New Tests

1. **Unit tests** - For parsing logic, pure functions:
   ```python
   def test_my_feature(sample_profile_html):
       result = parse_something(sample_profile_html)
       assert result == expected
   ```

2. **Integration tests** - For database operations:
   ```python
   def test_database_operation(temp_db):
       temp_db.save_something(...)
       result = temp_db.get_something(...)
       assert result == expected
   ```

3. **HTML fixtures** - Fetch new HTML samples:
   ```python
   import requests
   from pathlib import Path
   
   html = requests.get('https://www.cagematch.net/?id=2&nr=WRESTLER_ID').text
   Path('tests/fixtures/html/wrestler_XXX.html').write_text(html)
   ```

## Known Issues

1. **DeprecationWarning**: `findAll()` should be replaced with `find_all()` in profile.py line 28
2. Rate limiting: Be careful when fetching new HTML fixtures from CageMatch

## Future Improvements

- [ ] Add VCR.py cassettes for network recording/replay
- [ ] Add tests for `all_matches.py` singles match extraction
- [ ] Add tests for Glicko2 ranking logic
- [ ] Add property-based tests with hypothesis
- [ ] Mock CageMatchScraper for scraping session tests
