from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as connection:
        print("✅ Успешное подключение к базе данных")
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
