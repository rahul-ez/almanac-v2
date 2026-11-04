from sqlalchemy import create_engine

def make_engine(settings):
    return create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True,
                         connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"})
