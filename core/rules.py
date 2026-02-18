"""
core/rules.py - Pure functions for keyword processing, natural sort, and filename validation.

This module contains all the business logic for:
1. Processing and sorting keywords according to HSP rules
2. Validating filenames against the expected pattern
3. Natural sorting implementation (no external dependencies)
"""

import os
import re
from datetime import datetime
from typing import List, Tuple, Optional, Iterable  
import unicodedata



def make_shib_token_from_folder(foldername: str) -> str:
    """Preserve dotted sequences like 'A.4.3.12'; allow letters, digits, '-' and '.'."""
    if foldername is None:
        return ""
    s = unicodedata.normalize("NFKC", str(foldername)).strip()
    if not s:
        return ""
    s = re.sub(r"\s+", "-", s)                # spaces -> hyphen
    s = re.sub(r"[^A-Za-z0-9.\-]+", "", s)    # keep letters/digits/dot/hyphen
    s = re.sub(r"-{2,}", "-", s)              # collapse hyphens
    s = s.strip("-.")
    return f"shib-{s}" if s else ""

def _is_ascii_digit(ch: str) -> bool:
    """Return True if ch is in '0'..'9' (avoid non-ASCII numerals)."""
    return '0' <= ch <= '9'


def tokenize_for_natural_sort(text: str) -> List[Tuple[bool, str]]:
    """
    Tokenize a string into alternating ASCII digit and non-digit runs.
    Returns list of (is_digit, token) tuples.

    Example: "abc123def45" -> [(False, "abc"), (True, "123"), (False, "def"), (True, "45")]
    """
    if not text:
        return []
    
    tokens: List[Tuple[bool, str]] = []
    current: List[str] = []
    is_digit = _is_ascii_digit(text[0])
    
    for char in text:
        if _is_ascii_digit(char) == is_digit:
            current.append(char)
        else:
            tokens.append((is_digit, ''.join(current)))
            current = [char]
            is_digit = not is_digit
    
    if current:
        tokens.append((is_digit, ''.join(current)))
    
    return tokens


def natural_sort_key(text: str) -> List:
    """
    Generate a sort key for natural sorting.
    ASCII digit runs are compared as integers; non-digit runs case-insensitively.
    """
    tokens = tokenize_for_natural_sort(text)
    key = []
    
    for is_digit, token in tokens:
        if is_digit:
            # Safe: token only contains ASCII digits
            key.append((0, int(token)))  # digits sort before text within the tuple
        else:
            key.append((1, token.lower()))
    
    return key


def natural_sort(items: List[str]) -> List[str]:
    """
    Sort a list of strings using natural sort order.
    Stable sort - preserves original order for equal items.
    """
    return sorted(items, key=natural_sort_key)


def process_keywords(keywords_input: str | List[str]) -> str:
    """
    Canonicalize keywords:
      - Input: CSV string or list
      - NFKC normalize, trim, drop empties
      - Case-insensitive de-dup (preserve first-seen casing)
      - Natural sort within tiers
      - Comma+space delimiter (", ")
      - No implicit shib additions here. Those are explicit UI actions.
      - Tiers: non-shib (0) < shib-* except shib-1234 (1) < shib-1234 (2, always last)
    """
    if isinstance(keywords_input, str):
        raw = [unicodedata.normalize("NFKC", s).strip() for s in keywords_input.split(",")]
    else:
        raw = [unicodedata.normalize("NFKC", str(s)).strip() for s in keywords_input]

    tokens = [t for t in raw if t]

    # de-dup, case-insensitive; preserve first casing
    seen: set[str] = set()
    uniq: List[str] = []
    for t in tokens:
        k = t.casefold()
        if k not in seen:
            seen.add(k)
            uniq.append(t)

    def _tier_key(s: str):
        sc = s.casefold()
        if sc.startswith("shib-"):
            # shib-1234 always last
            return (2,) if sc == "shib-1234" else (1,) + tuple(natural_sort_key(s))
        return (0,) + tuple(natural_sort_key(s))

    uniq_sorted = sorted(uniq, key=_tier_key)
    return ", ".join(uniq_sorted)


def is_leap_year(year: int) -> bool:
    """Check if a year is a leap year."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def validate_date(year: int, month: int, day: int) -> Optional[str]:
    """
    Validate a date according to HSP rules.
    
    Returns None if valid, or an error message if invalid.
    Special cases:
    - Month can be 00 (unknown month)
    - Day can be 00 (unknown day)
    - If month is 00, day must also be 00
    """
    current_year = datetime.now().year
    
    # Year validation
    if year < 1950:
        return "Year is unusually old—confirm."
    if year > current_year:
        return "Date is in the future—check."
    
    # Special case: YYYY-0000 for unknown date
    if month == 0:
        if day != 0:
            return f"Date '{year:04d}-{month:02d}{day:02d}' is invalid."
        return None  # YYYY-0000 is valid
    
    # Normal date validation
    if month < 1 or month > 12:
        return f"Date '{year:04d}-{month:02d}{day:02d}' is invalid."
    
    if day == 0:
        return None  # YYYY-MM00 is valid
    
    # Check day validity for the month
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    # Adjust for leap year
    if month == 2 and is_leap_year(year):
        max_day = 29
    else:
        max_day = days_in_month[month - 1]
    
    if day < 1 or day > max_day:
        return f"Date '{year:04d}-{month:02d}{day:02d}' is invalid."
    
    # Check if date is in the future (for current year)
    if year == current_year:
        try:
            date_obj = datetime(year, month if month > 0 else 1, day if day > 0 else 1)
            if date_obj > datetime.now():
                return "Date is in the future—check."
        except ValueError:
            return f"Date '{year:04d}-{month:02d}{day:02d}' is invalid."
    
    return None


def validate_filename(filename: str) -> Optional[str]:
    """
    Validate a filename according to HSP conventions:
      - YYYY-MMDD prefix with logic checks (year>=1950; month 00 or 01..12; day 00 or valid)
      - One or more {...} or [...] blocks immediately after the date
      - Space after the bracket block(s), then free-text
      - We do NOT enforce .pdf here (loader already filters PDFs)
    """
    # For validation only: if it ends with .pdf, strip extension
    name_part = filename[:-4] if filename.lower().endswith(".pdf") else filename

    m = re.match(r'^(\d{4})-(\d{2})(\d{2})', name_part)
    if not m:
        return "Expected YYYY-MMDD date."

    year = int(m.group(1)); month = int(m.group(2)); day = int(m.group(3))
    date_error = validate_date(year, month, day)
    if date_error:
        return date_error

    # Brackets must immediately follow the 10-char date prefix
    after_date = name_part[10:]
    if not re.match(r'^([\{\[].*?[\}\]])+\s+', after_date):
        return "Expected {...} or [...] after date."

    return None


def extract_folder_name(full_path: str) -> str:
    """
    Extract the folder name from a full path.
    """
    import os
    return os.path.basename(os.path.normpath(full_path))


# Example usage and testing
if __name__ == "__main__":
    # Test keyword processing
    test_keywords = "CBW, cbw, WHO, HSP, shib-2024"
    result = process_keywords(test_keywords)
    print(f"Processed keywords: {result}")
    
    # Test filename validation
    test_files = [
        "2024-0315 {AGM}[HSP] Meeting notes.pdf",
        "2025-0229 {Test} Invalid leap year.pdf",
        "2023-0000 {Unknown} Valid unknown date.pdf",
        "1949-0101 {Old} Too old.pdf",
        "badformat.pdf",
        "2024-0315    {AGM} Extra spaces before brackets.pdf",  # should warn
    ]
    
    for filename in test_files:
        error = validate_filename(filename)
        if error:
            print(f"[INVALID] {filename}: {error}")
        else:
            print(f"[VALID] {filename}: Valid")
