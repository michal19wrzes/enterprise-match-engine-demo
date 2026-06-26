from utils import (
    extract_delivery_note_refno,
    normalize_internal_supplier_refno,
    normalize_registration,
    normalize_supplier_refno,
    parse_internal_supplier_refno,
    registration_match,
    supplier_refno_match,
)


def test_normalize_internal_supplier_refno_removes_whitespace():
    assert normalize_internal_supplier_refno(" SRC_A   12345 ") == "SRC_A12345"


def test_parse_internal_supplier_refno_accepts_known_source_code():
    assert parse_internal_supplier_refno("SRC_A 12345") == ("SRC_A", "12345")


def test_parse_internal_supplier_refno_rejects_unknown_source_code():
    assert parse_internal_supplier_refno("UNKNOWN 12345") == (None, None)


def test_normalize_supplier_refno_zero_pads_prefix_and_strips_suffix():
    assert normalize_supplier_refno("8/AB-6019") == "08/6019"


def test_extract_delivery_note_refno_builds_supplier_refno_shape():
    assert extract_delivery_note_refno("08X123456019") == "08/6019"


def test_supplier_refno_match_compares_prefix_and_suffix():
    assert supplier_refno_match("8/116019", "08X123456019") is True


def test_normalize_registration_removes_spaces_and_punctuation():
    assert normalize_registration(" ab-123 cd ") == "AB123CD"


def test_registration_match_supports_partial_external_value():
    assert registration_match("AB 123 CD / ZZ999", "AB123CD") is True
