"""Conexión a PostgreSQL y sesión SQLAlchemy."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,        # conexiones persistentes en el pool
    max_overflow=5,     # conexiones extra permitidas en picos
    pool_timeout=20,    # segundos máximos esperando una conexión libre
    pool_recycle=1800,  # recicla conexiones cada 30 min para evitar timeouts
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency para obtener sesión de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crear todas las tablas en la base de datos."""
    Base.metadata.create_all(bind=engine)
