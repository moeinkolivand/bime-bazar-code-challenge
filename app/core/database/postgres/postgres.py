from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.conf.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=settings.db_echo,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_postgres():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
