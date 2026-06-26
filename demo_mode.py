"""Small local demo seed used by `python app.py --demo`.

The demo does not call Oracle or external APIs. It creates the schema and inserts
synthetic reference data so reviewers can inspect the database structure quickly.
"""

from database import SessionLocal, init_db
from models import ArticleNoMapper, Product, RegionMapper


def run_demo_seed() -> None:
    init_db()
    with SessionLocal() as session:
        if not session.query(Product).filter_by(product_id=1001).first():
            session.add_all([
                Product(product_id=1001, code="PROD-A", cdu_id="DEMO_UNIT", text="Demo product A", product_type_id=1, factor_fm_rm=1.25),
                Product(product_id=1002, code="PROD-B", cdu_id="DEMO_UNIT", text="Demo product B", product_type_id=2, factor_fm_rm=1.10),
            ])

        if not session.query(ArticleNoMapper).filter_by(article_no="ART-001").first():
            session.add_all([
                ArticleNoMapper(article_no="ART-001", product_code="PROD-A", example_uuid="demo-uuid-001"),
                ArticleNoMapper(article_no="ART-002", product_code="PROD-B", example_uuid="demo-uuid-002"),
            ])

        if not session.query(RegionMapper).filter_by(inspectorate_code="0101").first():
            session.add(
                RegionMapper(
                    region_code="01",
                    inspectorate_code="0101",
                    region_name="Demo Region",
                    inspectorate_name="Demo Unit",
                    postal_code="00-000",
                    voivodeship="demo",
                    erp_unit_code="DEMO_UNIT",
                )
            )

        session.commit()
    print("Demo database initialized with synthetic reference data.")
