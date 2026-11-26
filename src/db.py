from sqlmodel import create_engine

from config import DATABASE_URL, DB_CONNECT_TIMEOUT_SECONDS


def normalize_database_url(url: str) -> str:
    
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def make_engine(url: str | None = None):

    database_url = DATABASE_URL if url is None else url
    database_url = normalize_database_url(database_url)

    if database_url.startswith("postgresql"):
        return create_engine(
            database_url,
            connect_args={"connect_timeout": DB_CONNECT_TIMEOUT_SECONDS},
        )
    return create_engine(database_url)
