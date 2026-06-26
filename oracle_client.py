try:
    import oracledb
except ImportError:  # optional in local demo mode without Oracle client
    oracledb = None
from config import (
    DB_X_USER,
    DB_X_PASSWORD,
    DB_X_DSN,
    DB_Y_USER,
    DB_Y_PASSWORD,
    DB_Y_DSN,
)


def _require_oracle_driver():
    if oracledb is None:
        raise RuntimeError("oracledb is not installed. Install demo dependencies and configure Oracle access to run live sync jobs.")

def get_connection_x():
    _require_oracle_driver()
    return oracledb.connect(
        user=DB_X_USER,
        password=DB_X_PASSWORD,
        dsn=DB_X_DSN,
    )


def get_connection_y():
    _require_oracle_driver()
    return oracledb.connect(
        user=DB_Y_USER,
        password=DB_Y_PASSWORD,
        dsn=DB_Y_DSN,
    )

SQL_INTERNAL_PRODUCTSALES_X = """
SELECT
    'X' AS SOURCE_DB,
    TRIM(ts.CDU_ID) AS CDU_ID,
    ts.TICKETNUMBER,
    ts.PRODUCTSALES_ID,
    ts.TICKETDATE AS SALE_DATE,
    ts.TRUCK_REGNUMBER,
    ts.TRAILER_REGNUMBER,
    ts.PRODUCT_ID,
    tp.CODE AS PRODUCT_CODE,
    ts.QUANTITY_RM,
    ts.TSC_PEFC_ID,
    ts.TSC_FSC_CW_ID
FROM demo_inventory.productsales ts
JOIN demo_sales.vkcustomer vc
    ON vc.VKCUSTOMER_ID = ts.VKCUSTOMER_ID
LEFT JOIN demo_inventory.product tp
    ON tp.PRODUCT_ID = ts.PRODUCT_ID
   AND tp.DBSTATE = 1
WHERE TRIM(ts.CDU_ID) = 'SRC_A'
  AND ts.TICKETDATE >= SYSDATE - 15
  AND TRIM(vc.MCODE) = 'DEMO_CUSTOMER'
"""

SQL_INTERNAL_PRODUCTSALES_Y = """
SELECT
    'Y' AS SOURCE_DB,
    TRIM(ts.CDU_ID) AS CDU_ID,
    ts.TICKETNUMBER,
    ts.PRODUCTSALES_ID,
    ts.TICKETDATE AS SALE_DATE,
    ts.TRUCK_REGNUMBER,
    ts.TRAILER_REGNUMBER,
    ts.PRODUCT_ID,
    tp.CODE AS PRODUCT_CODE,
    ts.QUANTITY_RM,
    ts.TSC_PEFC_ID,
    ts.TSC_FSC_CW_ID
FROM demo_inventory.productsales ts
JOIN demo_sales.vkcustomer vc
    ON vc.VKCUSTOMER_ID = ts.VKCUSTOMER_ID
LEFT JOIN demo_inventory.product tp
    ON tp.PRODUCT_ID = ts.PRODUCT_ID
   AND tp.DBSTATE = 1
WHERE TRIM(ts.CDU_ID) IN ('SRC_B', 'SRC_C')
  AND ts.TICKETDATE >= SYSDATE - 15
  AND TRIM(vc.MCODE) = 'DEMO_CUSTOMER'
"""

SQL_CANDIDATES = """
SELECT
    wb.TICKETNUMBER,
    wb.TIMESTAMP_IN,
    wb.PROCESSINGSTATUS,
    wb.TRUCK_REGNUMBER,
    wb.VEHICLETYPE,
    yl.LENGTH1,
    yl.WIDTH1,
    yl.HEIGHT1,
    yl.GAP1,
    yl.QUANTITY_RM1,
    yl.LENGTH2,
    yl.WIDTH2,
    yl.HEIGHT2,
    yl.GAP2,
    yl.QUANTITY_RM2
FROM demo_weighbridge.wbridgeproductentryhead wb
LEFT JOIN demo_weighbridge.wbridgelogyard yl
    ON yl.SRCRIDGEPRODUCTENTRYHEAD_ID = wb.SRCRIDGEPRODUCTENTRYHEAD_ID
WHERE wb.PROCESSINGSTATUS = 2
  AND wb.TIMESTAMP_IN >= SYSDATE - 14
  AND wb.CDU_ID = 'DEMO_SITE'
  AND wb.LOCATIONCODE = 0
  AND NOT EXISTS (
      SELECT 1
      FROM demo_inventory.productentryhead pz
      WHERE pz.TICKETNUMBER = wb.TICKETNUMBER
        AND pz.CDU_ID = 'DEMO_SITE'
  )
ORDER BY wb.TIMESTAMP_IN ASC
"""


SQL_CANDIDATE_POSITIONS = """
SELECT
    wb.TICKETNUMBER,
    pos.POSNUMBER,
    pos.PRODUCT_ID,
    pos.MATERIAL_SUPPLIER_ID,
    pos.MATERIAL_ADDRESS_ID,
    pos.QUANTITY_RM,
    pos.SUPPLIER_REFNO,
    pos.PRODUCT_DISPOSITION_ID,
    td.SOURCE_ORDER_NUMBER,
    tp.CODE AS PRODUCT_CODE,
    tp.TEXT AS PRODUCT_TEXT,
    tp.PRODUCT_TYPE_ID,
    s.MCODE AS SUPPLIER_CODE,
    td.PRODUCTPROVISIONPOSITION_ID,
    tpp.PRODUCTCONTRACTPOSITION_ID,
    tcp.PRODUCT_TYPE_ID AS SOURCE_ORDER_PRODUCT_TYPE_ID

FROM demo_weighbridge.wbridgeproductentryhead wb

JOIN demo_weighbridge.wbridgeproductentryposition pos
    ON pos.SRCRIDGEPRODUCTENTRYHEAD_ID = wb.SRCRIDGEPRODUCTENTRYHEAD_ID

LEFT JOIN demo_inventory.productdisposition td
    ON td.PRODUCT_DISPOSITION_ID = pos.PRODUCT_DISPOSITION_ID

LEFT JOIN demo_inventory.product tp
    ON tp.PRODUCT_ID = pos.PRODUCT_ID
    AND tp.DBSTATE = 1

LEFT JOIN demo_procurement.supplier s
    ON s.SUPPLIER_ID = pos.MATERIAL_SUPPLIER_ID
    AND s.DBSTATE = 1

LEFT JOIN demo_inventory.productprovisionposition tpp
    ON tpp.PRODUCTPROVISIONPOSITION_ID = td.PRODUCTPROVISIONPOSITION_ID

LEFT JOIN demo_inventory.productcontractposition tcp
    ON tcp.PRODUCTCONTRACTPOSITION_ID = tpp.PRODUCTCONTRACTPOSITION_ID

WHERE wb.PROCESSINGSTATUS = 2
  AND wb.TIMESTAMP_IN >= SYSDATE - 14
  AND wb.CDU_ID = 'DEMO_SITE'
  AND wb.LOCATIONCODE = 0
  AND NOT EXISTS (
      SELECT 1
      FROM demo_inventory.productentryhead pz
      WHERE pz.TICKETNUMBER = wb.TICKETNUMBER
        AND pz.CDU_ID = 'DEMO_SITE'
  )
ORDER BY wb.TIMESTAMP_IN ASC, pos.POSNUMBER ASC
"""


def fetch_oracle_candidates():
    conn = get_connection_x()
    cur = conn.cursor()
    try:
        cur.execute(SQL_CANDIDATES)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def fetch_oracle_candidate_positions():
    conn = get_connection_x()
    cur = conn.cursor()
    try:
        cur.execute(SQL_CANDIDATE_POSITIONS)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()
        
SQL_PRODUCTS = """
SELECT
    tp.PRODUCT_ID,
    tp.CODE,
    tp.CDU_ID,
    tp.TEXT,
    tp.PRODUCT_TYPE_ID,
    tp.FACTOR_FM_RM
FROM demo_inventory.product tp
WHERE tp.DBSTATE = 1
ORDER BY tp.PRODUCT_ID
"""

def fetch_products():
    conn = get_connection_x()
    cursor = conn.cursor()

    cursor.execute(SQL_PRODUCTS)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows
    
def fetch_partner_unit_mcodes():
    sql = """
    SELECT s.MCODE
    FROM demo_procurement.supplier s
    WHERE s.IS_PARTNER_UNIT = 1
      AND s.DBSTATE = 1
      AND s.CDU_ID = 'DEMO_SITE'
      AND s.MCODE IS NOT NULL
    """

    conn = get_connection_x()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()
        
        
def fetch_internal_product_sales_x():
    conn = get_connection_x()
    cur = conn.cursor()
    try:
        cur.execute(SQL_INTERNAL_PRODUCTSALES_X)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def fetch_internal_product_sales_y():
    conn = get_connection_y()
    cur = conn.cursor()
    try:
        cur.execute(SQL_INTERNAL_PRODUCTSALES_Y)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()
