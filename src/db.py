from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

ENGINE = None
SessionLocal = None

def init_db(db_url: str = "sqlite:///./data/app.db"):
    global ENGINE, SessionLocal
    ENGINE = create_engine(db_url, echo=False, future=True)
    SessionLocal = scoped_session(sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True))
    return ENGINE, SessionLocal
