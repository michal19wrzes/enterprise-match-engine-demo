from datetime import datetime
from models import ToManualEntry
import re

def snapshot_manual_entries(session, run_label=None):
    rows = session.query(ToManualEntry).order_by(ToManualEntry.ticket_number).all()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"manual_snapshot_{ts}_{run_label or 'snapshot'}.csv"

    with open(filename, "w", encoding="utf-8") as f:
        f.write("snapshot_at,run_label,ticket_number,reason,reason_source,entry_status,created_at,updated_at,last_seen_at,resolved_at,details\n")

        for r in rows:
            f.write(
                f"{ts},"
                f"{run_label or ''},"
                f"{r.ticket_number},"
                f"{r.reason},"
                f"{getattr(r, 'reason_source', '')},"
                f"{r.entry_status},"
                f"{r.created_at},"
                f"{r.updated_at},"
                f"{r.last_seen_at},"
                f"{r.resolved_at},"
                f"{(r.details or '').replace(',', ';')}\n"
            )

def normalize_internal_supplier_refno(value: str | None) -> str | None:
    """
    Usuwa wszystkie białe znaki, np.:
    'SRC_C 73264637' -> 'SRC_C73264637'
    'SRC_C   73264637' -> 'SRC_C73264637'
    ' SRC_A  3242345 ' -> 'SRC_A3242345'
    """
    if not value:
        return None

    value = str(value).upper().strip()
    value = re.sub(r"\s+", "", value)

    return value or None


def parse_internal_supplier_refno(value: str | None) -> tuple[str | None, str | None]:
    """
    Type=2:
    oczekiwany format to:
      <CDU_ID> <ticket_number>

    Przykłady poprawne:
      'SRC_A 3242345' -> ('SRC_A', '3242345')
      'SRC_C 73264637' -> ('SRC_C', '73264637')
      'SRC_B   932828' -> ('SRC_B', '932828')

    Przykłady błędne:
      'MA1 23432435' -> (None, None)
      'SV7 123456' -> (None, None)
      '3242345' -> (None, None)
    """
    if not value:
        return None, None

    raw = str(value).upper().strip()
    raw = re.sub(r"\s+", " ", raw)

    parts = raw.split(" ")

    if len(parts) < 2:
        return None, None

    cdu_id = parts[0].strip()
    ticket_number = "".join(part.strip() for part in parts[1:])

    allowed_cdu_ids = {"SRC_A", "SRC_B", "SRC_C"}

    if cdu_id not in allowed_cdu_ids:
        return None, None

    if not ticket_number or not ticket_number.isdigit():
        return None, None

    return cdu_id, ticket_number

def is_valid_first_supplier_refno(value):
    if value is None:
        return False

    s = str(value).strip()
    return s.count("/") == 1 and len(s) >= 6
def normalize_supplier_refno_parts(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None

    value = str(value).strip()
    if "/" not in value:
        return None, None

    left, right = value.split("/", 1)
    left = re.sub(r"\D", "", left).zfill(2)
    right = re.sub(r"\D", "", right)

    if not left or not right:
        return None, None

    return left, right


def extract_delivery_note_refno_parts(delivery_note_no: str | None) -> tuple[str | None, str | None]:
    """
    Z 08P289116019 zwraca ('08', '6019')
    """
    if not delivery_note_no:
        return None, None

    value = str(delivery_note_no).strip()
    if len(value) < 6:
        return None, None

    prefix = value[:2]
    suffix = value[-4:]

    if not prefix.isdigit() or not suffix.isdigit():
        return None, None

    return prefix, suffix


def supplier_refno_match(erp_supplier_refno: str | None, external_delivery_note_no: str | None) -> bool:
    erp_prefix, erp_suffix = normalize_supplier_refno_parts(erp_supplier_refno)
    external_prefix, external_suffix = extract_delivery_note_refno_parts(external_delivery_note_no)

    if not erp_prefix or not erp_suffix or not external_prefix or not external_suffix:
        return False

    return erp_prefix == external_prefix and erp_suffix.endswith(external_suffix)
    
def build_external_inspectorate_code(region_code: str | None, inspectorate_code: str | None) -> str | None:
    if region_code is None or inspectorate_code is None:
        return None

    region = str(region_code).strip().zfill(2)
    inspectorate = str(inspectorate_code).strip().zfill(2)

    if not region.isdigit() or not inspectorate.isdigit():
        return None

    return f"{region}{inspectorate}"
def parse_external_datetime(value: str | None):
    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None

import re



def normalize_supplier_refno(value: str | None) -> str | None:
    if not value:
        return None

    value = str(value).strip()
    if "/" not in value:
        return value

    left, right = value.split("/", 1)
    left = left.strip().zfill(2)
    right = re.sub(r"\D", "", right.strip())

    return f"{left}/{right}" if right else f"{left}/"


def extract_delivery_note_refno(delivery_note_no: str | None) -> str | None:
    """
    Z delivery_note_no typu 08P289116019 zwraca 08/6019
    """
    if not delivery_note_no:
        return None

    value = str(delivery_note_no).strip()
    if len(value) < 6:
        return None

    prefix = value[:2]
    suffix = value[-4:]

    if not prefix.isdigit() or not suffix.isdigit():
        return None

    return f"{prefix}/{suffix}"

def normalize_registration(value: str | None) -> str | None:
    if not value:
        return None

    value = str(value).upper()
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[^A-Z0-9]", "", value)

    return value or None


def registration_match(external_reg: str | None, erp_reg: str | None) -> bool:
    erp = normalize_registration(erp_reg)

    if not external_reg or not erp:
        return False

    external_raw = str(external_reg).upper().strip()

    parts = re.split(r"[\/,;|]+|\s{2,}", external_raw)

    candidates = [normalize_registration(part) for part in parts]
    candidates = [c for c in candidates if c]

    external_full = normalize_registration(external_reg)

    if external_full and (external_full.startswith(erp) or erp.startswith(external_full)):
        return True

    for candidate in candidates:
        if candidate == erp:
            return True

        if candidate.startswith(erp) or erp.startswith(candidate):
            return True

    return False






def normalize_truck_reg_lp(value: str | None) -> str | None:
    """
    EXT: usuwamy białe znaki i bierzemy max 8 znaków
    """
    if not value:
        return None

    value = re.sub(r"\s+", "", str(value).upper())
    return value[:8] if value else None


def normalize_truck_reg_erp(value: str | None) -> str | None:
    """
    ERP: usuwamy białe znaki
    """
    if not value:
        return None

    return re.sub(r"\s+", "", str(value).upper()) or None


def build_external_inspectorate_code(region_code: str | None, inspectorate_code: str | None) -> str | None:
    """
    region_code + inspectorate_code => 4 cyfry, np. 11 + 16 => 1116
    """
    if region_code is None or inspectorate_code is None:
        return None

    region = str(region_code).strip().zfill(2)
    inspectorate = str(inspectorate_code).strip().zfill(2)

    if not region.isdigit() or not inspectorate.isdigit():
        return None

    return f"{region}{inspectorate}"