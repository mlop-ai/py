import os


def get_smtp_config():
    return {
        "server": os.getenv("SMTP_SERVER", "localhost"),
        "port": os.getenv("SMTP_PORT", 25),
        "username": os.getenv("SMTP_USERNAME", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_address": os.getenv("SMTP_FROM_ADDRESS", ""),
        "app_host": os.getenv("APP_HOST", "localhost"),
    }

def get_database_url():
    return os.getenv("DATABASE_DIRECT_URL")
