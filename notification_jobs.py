"""Job functions split from the original monolithic jobs.py.

This module is intentionally domain-neutral for the portfolio demo.
"""

from jobs_common import (
    hashlib,
    smtplib,
    MIMEMultipart,
    MIMEText,
    fetch_oracle_candidates,
    is_valid_first_supplier_refno,
    SMTP_FROM,
    fetch_oracle_candidate_positions,
    fetch_recent_external_documents,
    parse_external_datetime,
    datetime,
    timedelta,
    json,
    Product,
    fetch_products,
    func,
    ExternalDocumentItem,
    csv,
    Path,
    RegionMapper,
    TransportHeaderMatch,
    TransportPositionMatch,
    extract_delivery_note_refno,
    normalize_supplier_refno,
    registration_match,
    build_external_inspectorate_code,
    supplier_refno_match,
    extract_delivery_note_refno_parts,
    normalize_supplier_refno_parts,
    SessionLocal,
    fetch_partner_unit_mcodes,
    defaultdict,
    ExternalDocument,
    ExternalDocumentItemAggregate,
    ArticleNoMapper,
    ERPWeightTicket,
    ERPWeightTicketPosition,
    ExternalDocumentItemTranslated,
    TransportPositionBestMatch,
    FinalPositionMatch,
    ToManualEntry,
    OUTQueue,
    OUTQueueItem,
    math,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SUBJECT_PREFIX,
    SMTP_TO_ADMIN,
    SMTP_TO_USER,
    SMTP_USE_SSL,
    SMTP_USE_TLS,
    SMTP_USERNAME,
    parse_internal_supplier_refno,
    fetch_internal_product_sales_x,
    fetch_internal_product_sales_y,
    InternalProductSalesCache,
    InternalSalesMatch,
    Decimal,
    ROUND_HALF_UP,
    MANUAL_REASONS_ONLY_AFTER_21,
    ADMIN_REASON_FINAL_RETRY_FAILED,
    is_type3_supplier_refno,
    mark_ticket_as_manual_by_id,
    round_2,
    classify_type2_tickets,
    build_manual_entry_fingerprint,
    get_manual_notification_type,
    upsert_manual_entry,
    resolve_missing_manual_entries,
    floor_2,
    classify_tickets_by_supplier_ref,
)

def send_program_started_email():
    print("START send_program_started_email")

    if not SMTP_HOST or not SMTP_FROM or not SMTP_TO_ADMIN:
        print("Brak konfiguracji SMTP admin - pomijam mail startowy")
        return

    recipients = [addr.strip() for addr in SMTP_TO_ADMIN.split(",") if addr.strip()]
    subject = f"{SMTP_SUBJECT_PREFIX} Program uruchomiony DEMO_SITE"
    text_body = "Program uruchomiony DEMO_SITE"
    html_body = "<p>Program uruchomiony DEMO_SITE</p>"

    _send_email_message(recipients, subject, text_body, html_body)

    print("KONIEC send_program_started_email")

def _format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""

def _build_manual_entry_email_html(rows):
    row_html = []
    for row in rows:
        row_html.append(
            f"<tr><td>{row.ticket_number or ''}</td><td>{_format_dt(row.timestamp_in)}</td><td>{row.truck_regnumber or ''}</td><td>{row.reason or ''}</td><td>{row.details or ''}</td></tr>"
        )

    return f"""
    <html>
      <body>
        <p>Poniżej lista OUT do wprowadzenia ręcznie:</p>
        <table border="1" cellspacing="0" cellpadding="6">
          <thead>
            <tr>
              <th>Ticket SRC</th>
              <th>Data SRC</th>
              <th>Rejestracja</th>
              <th>Powód</th>
              <th>Szczegóły</th>
            </tr>
          </thead>
          <tbody>
            {''.join(row_html)}
          </tbody>
        </table>
      </body>
    </html>
    """

def _build_manual_entry_email_text(rows):
    lines = [
        "Poniżej lista OUT do wprowadzenia ręcznie:",
        "",
    ]

    for idx, row in enumerate(rows, start=1):
        lines.extend([
            f"{idx}. Ticket/OUT: {row.ticket_number or ''}",
            f"   Timestamp in: {_format_dt(row.timestamp_in)}",
            f"   Rejestracja: {row.truck_regnumber or ''}",
            f"   Powód: {row.reason or ''}",
            f"   Szczegóły: {row.details or ''}",
            "",
        ])

    lines.append("Pozdrawiam,")
    lines.append("ERP-EXT Integration")
    return "\n".join(lines)

def _send_email_message(recipients, subject, text_body, html_body):
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    if SMTP_USE_SSL:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            if SMTP_USERNAME:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD or "")
            smtp.sendmail(SMTP_FROM, recipients, message.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            if SMTP_USE_TLS:
                smtp.starttls()
                smtp.ehlo()
            if SMTP_USERNAME:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD or "")
            smtp.sendmail(SMTP_FROM, recipients, message.as_string())

def send_manual_entry_email():
    print("START send_manual_entry_email")

    if not SMTP_HOST:
        print("Brak SMTP_HOST - pomijam wysyłkę maila")
        return

    if not SMTP_FROM:
        print("Brak SMTP_FROM - pomijam wysyłkę maila")
        return

    now_local = datetime.now()
    is_after_21 = 21 <= now_local.hour < 24

    with SessionLocal() as session:
        base_user_query = (
            session.query(ToManualEntry)
            .filter(
                ToManualEntry.entry_status == "OPEN",
                ToManualEntry.notification_status == "NEW",
                ToManualEntry.notification_type == "USER",
            )
        )

        regular_user_rows = (
            base_user_query
            .filter(~ToManualEntry.reason.in_(MANUAL_REASONS_ONLY_AFTER_21))
            .order_by(ToManualEntry.reason.asc(), ToManualEntry.ticket_number.asc())
            .all()
        )

        delayed_reason_rows = []
        if is_after_21:
            delayed_reason_rows = (
                base_user_query
                .filter(ToManualEntry.reason.in_(MANUAL_REASONS_ONLY_AFTER_21))
                .order_by(ToManualEntry.reason.asc(), ToManualEntry.ticket_number.asc())
                .all()
            )

        user_rows = regular_user_rows + delayed_reason_rows

        admin_rows = (
            session.query(ToManualEntry)
            .filter(
                ToManualEntry.entry_status == "OPEN",
                ToManualEntry.notification_status == "NEW",
                ToManualEntry.notification_type == "ADMIN",
            )
            .order_by(ToManualEntry.reason.asc(), ToManualEntry.created_at.asc())
            .all()
        )

        sent_any = False

        if SMTP_TO_USER and user_rows:
            recipients = [addr.strip() for addr in SMTP_TO_USER.split(",") if addr.strip()]
            now_str = now_local.strftime("%Y-%m-%d %H:%M")
            subject = f"{SMTP_SUBJECT_PREFIX} OUT do ręcznego wprowadzenia {now_str}"
            text_body = _build_manual_entry_email_text(user_rows)
            html_body = _build_manual_entry_email_html(user_rows)
            _send_email_message(recipients, subject, text_body, html_body)
            sent_any = True
            now_utc = datetime.utcnow()
            for row in user_rows:
                row.notification_status = "SENT"
                row.notification_sent_at = now_utc

        if SMTP_TO_ADMIN and admin_rows:
            recipients = [addr.strip() for addr in SMTP_TO_ADMIN.split(",") if addr.strip()]
            now_str = now_local.strftime("%Y-%m-%d %H:%M")
            subject = f"{SMTP_SUBJECT_PREFIX} Powiadomienia techniczne {now_str}"
            text_body = _build_manual_entry_email_text(admin_rows)
            html_body = _build_manual_entry_email_html(admin_rows)
            _send_email_message(recipients, subject, text_body, html_body)
            sent_any = True
            now_utc = datetime.utcnow()
            for row in admin_rows:
                row.notification_status = "SENT"
                row.notification_sent_at = now_utc

        session.commit()

    if not sent_any:
        print("Brak nowych rekordów do wysłania albo brak skonfigurowanych odbiorców")
    print("KONIEC send_manual_entry_email")

