from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, BigInteger
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class InternalSalesMatch(Base):
    __tablename__ = "internal_sales_matches"

    id = Column(Integer, primary_key=True)

    erp_weight_ticket_id = Column(Integer, ForeignKey("erp_weight_tickets.id"), nullable=False, index=True)
    erp_weight_ticket_position_id = Column(Integer, ForeignKey("erp_weight_ticket_positions.id"), nullable=False, index=True)
    internal_product_sales_cache_id = Column(Integer, ForeignKey("internal_product_sales_cache.id"), nullable=False, index=True)

    source_type = Column(Integer, nullable=False, default=2, index=True)

    # ERP - nagłówek
    erp_ticket_number = Column(String(50), nullable=True, index=True)
    erp_timestamp_in = Column(DateTime, nullable=True, index=True)
    erp_truck_regnumber = Column(String(30), nullable=True, index=True)
    erp_position_count = Column(Integer, nullable=True)
    erp_first_pos_supplier_refno = Column(String(50), nullable=True)
    erp_first_pos_mcode = Column(String(30), nullable=True)

    # ERP - pozycja
    erp_pos_number = Column(Integer, nullable=True)
    erp_supplier_refno = Column(String(50), nullable=True, index=True)
    erp_supplier_code = Column(String(30), nullable=True, index=True)
    erp_product_id = Column(BigInteger, nullable=True, index=True)
    erp_product_code = Column(String(50), nullable=True, index=True)
    erp_product_text = Column(Text, nullable=True)
    erp_product_type_id = Column(Integer, nullable=True)
    erp_quantity_rm = Column(Float, nullable=True)
    erp_source_order_number = Column(String(50), nullable=True, index=True)

    # ERP - sparsowane z supplier_refno
    parsed_cdu_id = Column(String(10), nullable=True, index=True)
    parsed_ticket_number = Column(String(50), nullable=True, index=True)

    # Internal product sales cache
    cache_source_db = Column(String(10), nullable=True, index=True)
    cache_cdu_id = Column(String(10), nullable=True, index=True)
    cache_ticket_number = Column(String(50), nullable=True, index=True)
    productsales_id = Column(BigInteger, nullable=True, index=True)
    sale_date = Column(DateTime, nullable=True, index=True)

    truck_regnumber = Column(String(30), nullable=True, index=True)
    trailer_regnumber = Column(String(30), nullable=True, index=True)

    cache_product_id = Column(BigInteger, nullable=True, index=True)
    cache_product_code = Column(String(50), nullable=True, index=True)
    cache_quantity_rm = Column(Float, nullable=True)

    tsc_pefc_id = Column(BigInteger, nullable=True, index=True)
    tsc_fsc_cw_id = Column(BigInteger, nullable=True, index=True)

    match_status = Column(String(30), nullable=False, default="MATCHED", index=True)
    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    first_detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class InternalProductSalesCache(Base):
    __tablename__ = "internal_product_sales_cache"

    id = Column(Integer, primary_key=True)

    source_db = Column(String(10), nullable=False, index=True)   # X / Y
    cdu_id = Column(String(10), nullable=False, index=True)
    ticket_number = Column(String(50), nullable=False, index=True)

    productsales_id = Column(BigInteger, nullable=False, index=True)
    sale_date = Column(DateTime, nullable=True, index=True)

    truck_regnumber = Column(String(30), nullable=True, index=True)
    trailer_regnumber = Column(String(30), nullable=True, index=True)

    product_id = Column(BigInteger, nullable=True, index=True)
    product_code = Column(String(50), nullable=True, index=True)

    quantity_rm = Column(Float, nullable=True)

    tsc_pefc_id = Column(BigInteger, nullable=True, index=True)
    tsc_fsc_cw_id = Column(BigInteger, nullable=True, index=True)

    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    first_detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FinalPositionMatch(Base):
    __tablename__ = "final_position_matches"

    id = Column(Integer, primary_key=True)

    erp_weight_ticket_id = Column(Integer, ForeignKey("erp_weight_tickets.id"), nullable=False, index=True)
    erp_weight_ticket_position_id = Column(Integer, ForeignKey("erp_weight_ticket_positions.id"), nullable=False, index=True)
    external_document_id = Column(Integer, ForeignKey("external_documents.id"), nullable=False, index=True)
    external_document_item_translated_id = Column(Integer, ForeignKey("external_document_item_translated.id"), nullable=False, index=True)

    erp_ticket_number = Column(String(50), nullable=True, index=True)
    erp_pos_number = Column(Integer, nullable=True)
    erp_supplier_refno = Column(String(30), nullable=True)
    erp_product_code = Column(String(50), nullable=True)

    external_uuid = Column(String(50), nullable=True, index=True)
    external_product_code = Column(String(50), nullable=True)
    external_volume_sum = Column(Float, nullable=True)

    match_status = Column(String(30), nullable=False, default="MATCHED", index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    first_detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

class ERPToExternalPositionMatch(Base):
    __tablename__ = "erp_to_external_position_match"

    id = Column(Integer, primary_key=True)

    erp_weight_ticket_id = Column(Integer, ForeignKey("erp_weight_tickets.id"), nullable=False, index=True)
    erp_weight_ticket_position_id = Column(Integer, ForeignKey("erp_weight_ticket_positions.id"), nullable=False, index=True)
    external_document_id = Column(Integer, ForeignKey("external_documents.id"), nullable=False, index=True)
    external_document_item_translated_id = Column(Integer, ForeignKey("external_document_item_translated.id"), nullable=False, index=True)

    supplier_refno = Column(String(50), nullable=True)
    erp_product_code = Column(String(50), nullable=True)
    external_product_code = Column(String(50), nullable=True)

    erp_ticket_number = Column(String(50), nullable=True)
    external_uuid = Column(String(50), nullable=True)

    erp_quantity_rm = Column(Float, nullable=True)
    external_volume_sum = Column(Float, nullable=True)

    match_status = Column(String(50), nullable=False, default="MATCHED", index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExternalDocumentItemTranslated(Base):
    __tablename__ = "external_document_item_translated"

    id = Column(Integer, primary_key=True)

    external_document_id = Column(Integer, ForeignKey("external_documents.id"), nullable=False, index=True)

    external_uuid = Column(String(50), nullable=True, index=True)

    product_code = Column(String(50), nullable=True, index=True)
    volume_sum = Column(Float, nullable=True)

    source_count = Column(Integer, nullable=True)
    article_no_list = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    first_detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

class ArticleNoMapper(Base):
    __tablename__ = "article_no_mapper"

    id = Column(Integer, primary_key=True)

    article_no = Column(String(100), nullable=False, index=True)
    product_code = Column(String(50), nullable=False, index=True)

    example_uuid = Column(String(50), nullable=True)
    species_code = Column(String(20), nullable=True)
    assortment_code = Column(String(20), nullable=True)
    dimensional_class = Column(String(20), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ToManualEntry(Base):
    __tablename__ = "to_manual_entry"

    id = Column(Integer, primary_key=True)

    erp_weight_ticket_id = Column(Integer, nullable=True, index=True)

    ticket_number = Column(String(50), nullable=True, index=True)
    timestamp_in = Column(DateTime, nullable=True)
    truck_regnumber = Column(String(30), nullable=True)

    first_pos_supplier_refno = Column(String(30), nullable=True)
    position_count = Column(Integer, nullable=True)

    reason = Column(String(100), nullable=True, index=True)
    details = Column(Text, nullable=True)

    notification_type = Column(String(20), nullable=False, default="USER", index=True)
    notification_status = Column(String(20), nullable=False, default="NEW", index=True)
    notification_sent_at = Column(DateTime, nullable=True)

    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    fingerprint = Column(String(64), nullable=True, index=True)
    first_detected_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TransportPositionBestMatch(Base):
    __tablename__ = "transport_position_best_matches"

    id = Column(Integer, primary_key=True)

    transport_position_match_id = Column(Integer, ForeignKey("transport_position_matches.id"), nullable=False, index=True)
    transport_header_match_id = Column(Integer, ForeignKey("transport_header_matches.id"), nullable=False, index=True)
    erp_weight_ticket_position_id = Column(Integer, ForeignKey("erp_weight_ticket_positions.id"), nullable=False, index=True)
    external_document_id = Column(Integer, ForeignKey("external_documents.id"), nullable=False, index=True)

    erp_ticket_number = Column(String(50), nullable=True, index=True)
    erp_pos_number = Column(Integer, nullable=True)

    external_uuid = Column(String(50), nullable=True, index=True)
    external_delivery_note_no = Column(String(50), nullable=True)

    time_diff_seconds = Column(Integer, nullable=True)

    match_status = Column(String(30), nullable=False, default="BEST_MATCH", index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    first_detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

class TransportHeaderMatch(Base):
    __tablename__ = "transport_header_matches"

    id = Column(Integer, primary_key=True)

    erp_weight_ticket_id = Column(Integer, ForeignKey("erp_weight_tickets.id"), nullable=False, index=True)
    external_document_id = Column(Integer, ForeignKey("external_documents.id"), nullable=False, index=True)

    erp_ticket_number = Column(String(50), nullable=True, index=True)
    erp_timestamp_in = Column(DateTime, nullable=True, index=True)
    erp_truck_regnumber = Column(String(30), nullable=True)
    erp_first_pos_mcode = Column(String(30), nullable=True)

    external_uuid = Column(String(50), nullable=True, index=True)
    external_issue_date = Column(DateTime, nullable=True, index=True)
    external_delivery_note_no = Column(String(50), nullable=True)
    external_car_registration_no = Column(String(100), nullable=True)
    external_region_code = Column(String(10), nullable=True)
    external_inspectorate_code = Column(String(10), nullable=True)

    external_erp_unit_code = Column(String(30), nullable=True)
    registration_match_value = Column(String(150), nullable=True)

    match_key_truck_reg = Column(String(30), nullable=True)
    match_key_erp_unit_code = Column(String(30), nullable=True)
    time_diff_seconds = Column(Integer, nullable=True)

    match_status = Column(String(30), nullable=False, default="MATCHED", index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    first_detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

class TransportPositionMatch(Base):
    __tablename__ = "transport_position_matches"

    id = Column(Integer, primary_key=True)

    transport_header_match_id = Column(Integer, ForeignKey("transport_header_matches.id"), nullable=False, index=True)
    erp_weight_ticket_position_id = Column(Integer, ForeignKey("erp_weight_ticket_positions.id"), nullable=False, index=True)
    external_document_id = Column(Integer, ForeignKey("external_documents.id"), nullable=False, index=True)

    erp_ticket_number = Column(String(50), nullable=True, index=True)
    erp_pos_number = Column(Integer, nullable=True)

    erp_supplier_refno = Column(String(30), nullable=True)
    normalized_supplier_refno = Column(String(30), nullable=True)

    erp_source_order_number = Column(String(50), nullable=True)
    erp_product_code = Column(String(50), nullable=True)
    erp_supplier_code = Column(String(30), nullable=True)

    external_uuid = Column(String(50), nullable=True, index=True)
    external_delivery_note_no = Column(String(50), nullable=True)
    external_issue_date = Column(DateTime, nullable=True)

    match_key_supplier_refno = Column(String(30), nullable=True)
    match_status = Column(String(30), nullable=False, default="MATCHED", index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    first_detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    
class RegionMapper(Base):
    __tablename__ = "region_mapper"

    id = Column(Integer, primary_key=True)

    region_code = Column(String(10), nullable=True, index=True)
    inspectorate_code = Column(String(10), nullable=True, index=True)
    region_name = Column(String(100), nullable=True)
    inspectorate_name = Column(String(150), nullable=True)
    postal_code = Column(String(20), nullable=True)
    voivodeship = Column(String(50), nullable=True)
    erp_unit_code = Column(String(30), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExternalDocumentItemAggregate(Base):
    __tablename__ = "external_document_item_aggregates"

    id = Column(Integer, primary_key=True)

    external_document_id = Column(Integer, ForeignKey("external_documents.id"), nullable=False, index=True)

    position_no = Column(Integer, nullable=True)
    article_no = Column(String(100), nullable=True, index=True)
    volume_sum = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    first_detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

class Product(Base):
    __tablename__ = "products"

    product_id = Column(BigInteger, primary_key=True)

    code = Column(String(50), index=True)
    cdu_id = Column(String(20), index=True)
    text = Column(Text)
    product_type_id = Column(Integer)
    factor_fm_rm = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ERPWeightTicketPosition(Base):
    __tablename__ = "erp_weight_ticket_positions"

    id = Column(Integer, primary_key=True)

    erp_weight_ticket_id = Column(
        Integer,
        ForeignKey("erp_weight_tickets.id"),
        nullable=False,
        index=True,
    )

    pos_number = Column(Integer, nullable=True)
    product_id = Column(BigInteger, nullable=True)
    material_supplier_id = Column(BigInteger, nullable=True)
    material_address_id = Column(BigInteger, nullable=True)
    quantity_rm = Column(Float, nullable=True)

    supplier_refno = Column(String(30), nullable=True)
    productdisposition_id = Column(BigInteger, nullable=True, index=True)
    source_order_number = Column(String(50), nullable=True, index=True)

    product_code = Column(String(50), nullable=True, index=True)
    product_text = Column(Text, nullable=True)
    product_type_id = Column(Integer, nullable=True)
    productprovisionposition_id = Column(BigInteger, nullable=True, index=True)
    productcontractposition_id = Column(BigInteger, nullable=True, index=True)
    source_order_product_type_id = Column(BigInteger, nullable=True, index=True)

    supplier_code = Column(String(30), nullable=True, index=True)

    type = Column(Integer, nullable=False, default=1, index=True)

    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    first_detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
 
class ERPWeightTicket(Base):
    __tablename__ = "erp_weight_tickets"

    id = Column(Integer, primary_key=True)

    ticket_number = Column(String(50), unique=True, nullable=False, index=True)
    timestamp_in = Column(DateTime, nullable=True)
    processing_status = Column(Integer, nullable=False)

    truck_regnumber = Column(String(30), nullable=True, index=True)
    vehicletype = Column(String(30), nullable=True)

    cdu_id = Column(String(20), nullable=True)
    location_code = Column(Integer, nullable=True)

    length1 = Column(Float, nullable=True)
    width1 = Column(Float, nullable=True)
    height1 = Column(Float, nullable=True)
    gap1 = Column(Float, nullable=True)
    quantity_rm1 = Column(Float, nullable=True)

    length2 = Column(Float, nullable=True)
    width2 = Column(Float, nullable=True)
    height2 = Column(Float, nullable=True)
    gap2 = Column(Float, nullable=True)
    quantity_rm2 = Column(Float, nullable=True)

    position_count = Column(Integer, nullable=True, default=0)

    first_pos_product_code = Column(String(50), nullable=True)
    first_pos_mcode = Column(String(30), nullable=True)
    first_pos_supplier_refno = Column(String(30), nullable=True)

    type = Column(Integer, nullable=False, default=1, index=True)

    status = Column(String(30), nullable=False, default="ACTIVE", index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class ExternalDocument(Base):
    __tablename__ = "external_documents"

    id = Column(Integer, primary_key=True)

    uuid = Column(String(50), unique=True, nullable=False, index=True)
    delivery_note_no = Column(String(50), nullable=True, index=True)

    region_code = Column(String(10), nullable=True, index=True)
    inspectorate_code = Column(String(10), nullable=True, index=True)
    source_location_name = Column(String(150), nullable=True)

    issue_date = Column(DateTime, nullable=True, index=True)
    issuer_name = Column(String(150), nullable=True)

    contract_major_identifier = Column(String(50), nullable=True)
    contract_minor_identifier = Column(String(50), nullable=True)

    transport_driver_name = Column(String(150), nullable=True)
    carrier_name = Column(String(200), nullable=True)
    car_registration_no = Column(String(100), nullable=True, index=True)

    certificate_text = Column(Text, nullable=True)

    eudr_ref_no = Column(String(50), nullable=True)
    eudr_ver_code = Column(String(50), nullable=True)

    volume = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)

    raw_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExternalDocumentItem(Base):
    __tablename__ = "external_document_items"

    id = Column(Integer, primary_key=True)

    external_document_id = Column(Integer, ForeignKey("external_documents.id"), nullable=False, index=True)

    position_no = Column(Integer, nullable=True)
    species_code = Column(String(20), nullable=True)
    assortment_code = Column(String(20), nullable=True)
    dimensional_class = Column(String(20), nullable=True)

    article_no = Column(String(100), nullable=True, index=True)

    forest_area = Column(String(50), nullable=True)
    wod_name = Column(String(50), nullable=True)
    stock_no = Column(Integer, nullable=True)
    section_no = Column(Integer, nullable=True)

    length = Column(Float, nullable=True)
    diameter = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
  
class OUTQueueItem(Base):
    __tablename__ = "output_queue_items"

    id = Column(Integer, primary_key=True)
    
    output_queue_id = Column(Integer, ForeignKey("output_queue.id"), nullable=False, index=True)
    erp_weight_ticket_position_id = Column(Integer, ForeignKey("erp_weight_ticket_positions.id"), nullable=False, index=True)
    final_position_match_id = Column(Integer, ForeignKey("final_position_matches.id"), nullable=True, index=True)
    ticket_number = Column(String(50), nullable=True, index=True)
    timestamp_in = Column(DateTime, nullable=True, index=True)
    source_order_number = Column(String(50), nullable=True, index=True)
    supplier_refno = Column(String(30), nullable=True, index=True)
    product_code = Column(String(50), nullable=True, index=True)
    mp_amount = Column(Float, nullable=True)
    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    resolved_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(30), nullable=False, default="NEW", index=True)
    source_type = Column(Integer, nullable=False, default=1, index=True)
    
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 
    

class OUTQueue(Base):
    __tablename__ = "output_queue"

    id = Column(Integer, primary_key=True)

    erp_weight_ticket_id = Column(Integer, ForeignKey("erp_weight_tickets.id"), nullable=False, index=True)
    external_document_id = Column(Integer, ForeignKey("external_documents.id"), nullable=True, index=True)
    

    ticket_number = Column(String(50), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="NEW", index=True)
    supplier_refno = Column(String(30), nullable=True, index=True)
    external_uuid = Column(String(50), nullable=True, index=True)
    truck_regnumber = Column(String(30), nullable=True)
    timestamp_in = Column(DateTime, nullable=True, index=True)
    vehicletype = Column(String(30), nullable=True)
    cont1 = Column(Integer, nullable=False, default=0)
    cont2 = Column(Integer, nullable=False, default=0)
    clerk = Column(String(20), nullable=False, default="99998")

    total_mp = Column(Float, nullable=True)
    position_count = Column(Integer, nullable=True)

    is_fsc = Column(Integer, nullable=False, default=0)
    is_pefc = Column(Integer, nullable=False, default=0)

    
    source_type = Column(Integer, nullable=False, default=1, index=True)
    entry_status = Column(String(20), nullable=False, default="OPEN", index=True)
    resolved_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)