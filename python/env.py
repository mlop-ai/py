import os


def get_smtp_config():
    return {
        "server": os.getenv("SMTP_SERVER"),
        "port": os.getenv("SMTP_PORT"),
        "username": os.getenv("SMTP_USERNAME"),
        "password": os.getenv("SMTP_PASSWORD"),
        "from_address": os.getenv("SMTP_FROM_ADDRESS"),
        "app_host": os.getenv("APP_HOST"),
    }

def get_database_url():
    return os.getenv("DATABASE_DIRECT_URL")
