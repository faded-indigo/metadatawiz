from __future__ import annotations

from datetime import datetime

from core.rules import (
    make_shib_token_from_folder,
    process_keywords,
    validate_date,
    validate_filename,
)


def test_process_keywords_preserves_rules_ordering_and_dedup():
    raw = "cbw, WHO, cbw, shib-2024, HSP, shib-1234, shib-3"
    result = process_keywords(raw)
    assert result == "cbw, HSP, WHO, shib-3, shib-2024, shib-1234"


def test_make_shib_token_from_folder_keeps_dotted_sequences():
    assert make_shib_token_from_folder(" A.4.3.12 ") == "shib-A.4.3.12"
    assert make_shib_token_from_folder("  ") == ""
    assert make_shib_token_from_folder("reports 2024") == "shib-reports-2024"


def test_validate_filename_accepts_expected_hsp_shape():
    assert validate_filename("2024-0315 {AGM}[HSP] Meeting notes.pdf") is None
    assert validate_filename("2023-0000 {Unknown} Valid unknown date.pdf") is None


def test_validate_filename_rejects_bad_date_or_shape():
    assert validate_filename("badformat.pdf") == "Expected YYYY-MMDD date."
    assert validate_filename("1949-0101 {Old} Too old.pdf") == "Year is unusually old—confirm."

    invalid = validate_filename("2025-0229 {Test} Invalid leap year.pdf")
    assert invalid is not None
    assert "invalid" in invalid.lower()

    missing_brackets = validate_filename("2024-0315    {AGM} Extra spaces before brackets.pdf")
    assert missing_brackets == "Expected {...} or [...] after date."


def test_validate_date_rules_for_future_and_partial_dates():
    future_year = datetime.now().year + 1
    future_error = validate_date(future_year, 1, 1)
    assert future_error == "Date is in the future—check."

    assert validate_date(2024, 0, 0) is None
    invalid_partial = validate_date(2024, 0, 1)
    assert invalid_partial is not None
    assert "invalid" in invalid_partial.lower()
