import os
import sys
import time

from clickhouse_connect import get_client as get_clickhouse_client
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import process_runs

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_DIRECT_URL")
CH_URL = os.getenv("CLICKHOUSE_URL", "url")
CH_USER = os.getenv("CLICKHOUSE_USER", "user")
CH_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "password")

CH_HOST = CH_URL.split("https://")[1].split(":")[0]
CH_PORT = CH_URL.split("https://")[1].split(":")[1]


def start():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    ch_client = get_clickhouse_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD,
    )
    return engine, session, ch_client


if __name__ == "__main__":
    try:
        engine, session, ch_client = start()
        while True:
            process_runs(session, ch_client)
            time.sleep(10)
    except Exception as err:
        print("Processing failed:", err)
    finally:
        session.close()
        engine.dispose()
        print("Restarting script...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
