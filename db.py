import oracledb
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

def get_connection():
    connection = oracledb.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        dsn=os.getenv("DB_DSN")
    )

    return connection