from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os

MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_HOST = "localhost"
MYSQL_PORT = "3306"
MYSQL_DB = "ai_blog"

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://ai_blogdb_user:BizqgHMOr7EYb3Xk57wvtmJ1JdFYI8Eb@dpg-d4favlnpm1nc73eqv5tg-a.oregon-postgres.render.com/ai_blogdb")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()