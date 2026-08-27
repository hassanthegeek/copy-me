from sqlmodel import SQLModel, create_engine
from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
