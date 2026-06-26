import os
from pathlib import Path

try:
    import oracledb
except ImportError:  # optional in local demo mode without Oracle client
    oracledb = None
from dotenv import load_dotenv

ORACLE_CLIENT_LIB_DIR = os.getenv("ORACLE_CLIENT_LIB_DIR")

if oracledb and ORACLE_CLIENT_LIB_DIR:
    try:
        oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_LIB_DIR)
        print("Oracle Instant Client initialized.")
    except Exception as e:
        print("Oracle Client initialization skipped:", e)

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

DB_X_USER = os.getenv("DB_X_USER")
DB_X_PASSWORD = os.getenv("DB_X_PASSWORD")
DB_X_DSN = os.getenv("DB_X_DSN")

DB_Y_USER = os.getenv("DB_Y_USER")
DB_Y_PASSWORD = os.getenv("DB_Y_PASSWORD")
DB_Y_DSN = os.getenv("DB_Y_DSN")

EXT_AUTH_URL = os.getenv("EXT_AUTH_URL")
EXT_API_URL = os.getenv("EXT_API_URL")
EXT_CLIENT_ID = os.getenv("EXT_CLIENT_ID")
EXT_CLIENT_SECRET = os.getenv("EXT_CLIENT_SECRET")
EXT_PAGE_SIZE = int(os.getenv("EXT_PAGE_SIZE", "100"))
EXT_SSL_VERIFY = os.getenv("EXT_SSL_VERIFY", "true").lower() == "true"
EXT_CA_BUNDLE = os.getenv("EXT_CA_BUNDLE")

EXT_API_BATCH_URL = os.getenv(
    "EXT_API_BATCH_URL",
    "https://api.example.com/external-api/v1/documents/batch"
)

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "false").lower() == "true"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

SMTP_FROM = os.getenv("SMTP_FROM")

SMTP_TO = os.getenv("SMTP_TO")
SMTP_TO_USER = os.getenv("SMTP_TO_USER", SMTP_TO)
SMTP_TO_ADMIN = os.getenv("SMTP_TO_ADMIN")

SMTP_SUBJECT_PREFIX = os.getenv("SMTP_SUBJECT_PREFIX", "[ERP-EXT]")