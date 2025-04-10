import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from python.send import send_email
from python.temp import process_run_email
from python.utils import get_run_url

load_dotenv()

SMTP_CONFIG = {
    "server": os.getenv("SMTP_SERVER"),
    "port": os.getenv("SMTP_PORT"),
    "username": os.getenv("SMTP_USERNAME"),
    "password": os.getenv("SMTP_PASSWORD"),
    "from_address": os.getenv("SMTP_FROM_ADDRESS"),
    "to_address": os.getenv("SMTP_TO_ADDRESS"),
    "app_host": os.getenv("APP_HOST"),
}

send_email(
    SMTP_CONFIG,
    SMTP_CONFIG["from_address"],
    SMTP_CONFIG["to_address"],
    "mlop: test email",
    process_run_email(
        run_name="test-run",
        project_name="examples",
        last_metric_time=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        time_diff_seconds=int(timedelta(seconds=16).total_seconds()),
        run_url=get_run_url(
            host=SMTP_CONFIG["app_host"],
            organization="mlop",
            project="examples",
            run_id=1
        ),
        reason="The run may have stalled and requires attention."
    ),
    html=True
)
