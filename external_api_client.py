from datetime import datetime, timedelta
from typing import Any
import time
import requests
import requests
import urllib3

from config import (
    EXT_AUTH_URL,
    EXT_API_URL,
    EXT_API_BATCH_URL,
    EXT_CLIENT_ID,
    EXT_CLIENT_SECRET,
    EXT_PAGE_SIZE,
    EXT_SSL_VERIFY,
    EXT_CA_BUNDLE,
)

if not EXT_SSL_VERIFY and not EXT_CA_BUNDLE:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_token_cache = {
    "access_token": None,
    "expires_at": None,
}

def send_get_with_retry(url, headers, params, verify, timeout=60, max_attempts=10):
    last_response = None

    for attempt in range(1, max_attempts + 1):
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=timeout,
            verify=verify,
        )

        last_response = response

        if response.status_code != 429:
            return response

        sleep_seconds = min(2 ** attempt, 30)
        print(f"429 Too Many Requests -> próba {attempt}/{max_attempts}, czekam {sleep_seconds}s")
        time.sleep(sleep_seconds)

    return last_response
def get_verify_setting():
    if EXT_CA_BUNDLE:
        return EXT_CA_BUNDLE
    return EXT_SSL_VERIFY


def get_external_token() -> str:
    now = datetime.utcnow()

    if (
        _token_cache["access_token"] is not None
        and _token_cache["expires_at"] is not None
        and now < _token_cache["expires_at"]
    ):
        return _token_cache["access_token"]

    verify_value = get_verify_setting()

    response = requests.post(
        EXT_AUTH_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": EXT_CLIENT_ID,
            "client_secret": EXT_CLIENT_SECRET,
        },
        timeout=30,
        verify=verify_value,
    )
    response.raise_for_status()

    payload = response.json()
    access_token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 3600))

    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = now + timedelta(seconds=max(expires_in - 60, 60))

    return access_token


def clear_token_cache():
    _token_cache["access_token"] = None
    _token_cache["expires_at"] = None


def build_issue_date_range(hours_back: int = 24) -> str:
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(hours=hours_back)
    return (
        f"{start_dt.strftime('%Y-%m-%dT%H:%M:%S')},"
        f"{end_dt.strftime('%Y-%m-%dT%H:%M:%S')}"
    )


def fetch_transport_documents_page(
    page_number: int,
    page_size: int = EXT_PAGE_SIZE,
    hours_back: int = 24,
    document_type_codes: str = "KW",
    document_form_type_codes: str | None = None,
) -> list[dict[str, Any]]:
    token = get_external_token()
    verify_value = get_verify_setting()

    params = {
        "issueDateRange": build_issue_date_range(hours_back=hours_back),
        "pageNumber": page_number,
        "pageSize": page_size,
    }

    if document_type_codes:
        params["documentTypeCodes"] = document_type_codes

    if document_form_type_codes:
        params["documentFormTypeCodes"] = document_form_type_codes

    response = send_get_with_retry(
        EXT_API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        params=params,
        timeout=60,
        verify=verify_value,
    )

    if response.status_code == 401:
        clear_token_cache()
        token = get_external_token()

        response = requests.get(
            EXT_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            params=params,
            timeout=60,
            verify=verify_value,
        )

    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], list):
            return payload["data"]
        if "content" in payload and isinstance(payload["content"], list):
            return payload["content"]

    return []


def fetch_recent_document_summaries(
    max_pages: int = 3,
    page_size: int = EXT_PAGE_SIZE,
    hours_back: int = 24,
    document_type_codes: str = "KW",
    document_form_type_codes: str | None = None,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()

    for page_number in range(max_pages):
        page_docs = fetch_transport_documents_page(
            page_number=page_number,
            page_size=page_size,
            hours_back=hours_back,
            document_type_codes=document_type_codes,
            document_form_type_codes=document_form_type_codes,
        )

        print(f"Strona {page_number}: {len(page_docs)} rekordów")

        if not page_docs:
            break

        for doc in page_docs:
            doc_uuid = doc.get("uuid")
            if doc_uuid and doc_uuid not in seen:
                seen.add(doc_uuid)
                docs.append(doc)

    return docs


def chunk_list(items: list[str], chunk_size: int) -> list[list[str]]:
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def fetch_transport_documents_batch(uuids: list[str]) -> list[dict[str, Any]]:
    if not uuids:
        return []

    if len(uuids) > 100:
        raise ValueError("Batch endpoint accepts max 100 UUIDs")

    token = get_external_token()
    verify_value = get_verify_setting()

    params = [("uuids", uuid) for uuid in uuids]

    response = send_get_with_retry(
        EXT_API_BATCH_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        params=params,
        timeout=60,
        verify=verify_value,
    )

    if response.status_code == 401:
        clear_token_cache()
        token = get_external_token()

        response = requests.get(
            EXT_API_BATCH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            params=params,
            timeout=60,
            verify=verify_value,
        )

    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, list):
        return payload

    return []


def fetch_recent_external_documents(
    max_pages: int = 3,
    page_size: int = EXT_PAGE_SIZE,
    hours_back: int = 24,
    document_type_codes: str = "KW",
    document_form_type_codes: str | None = None,
) -> list[dict[str, Any]]:
    summaries = fetch_recent_document_summaries(
        max_pages=max_pages,
        page_size=page_size,
        hours_back=hours_back,
        document_type_codes=document_type_codes,
        document_form_type_codes=document_form_type_codes,
    )

    uuids = []
    seen = set()

    for doc in summaries:
        doc_uuid = doc.get("uuid")
        if doc_uuid and doc_uuid not in seen:
            seen.add(doc_uuid)
            uuids.append(doc_uuid)

    print(f"UUID do batch: {len(uuids)}")

    full_docs = []
    uuid_chunks = chunk_list(uuids, 100)

    for batch_no, uuid_chunk in enumerate(uuid_chunks, start=1):
        docs = fetch_transport_documents_batch(uuid_chunk)
        print(f"Batch {batch_no}: {len(docs)} pełnych dokumentów")
        full_docs.extend(docs)

        if batch_no < len(uuid_chunks):
            time.sleep(1.5)

    return full_docs