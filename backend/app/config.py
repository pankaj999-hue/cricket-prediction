# backend/app/config.py
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cricket_predictor")

# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30