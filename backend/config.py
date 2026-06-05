import os
from pathlib import Path
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Data and database settings
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_EXCEL_PATH = DATA_DIR / "database.xlsx"

# Ola Maps API Configuration
OLA_MAPS_API_KEY = os.getenv("OLA_MAPS_API_KEY", "MOCK")
OLA_MAPS_BASE_URL = os.getenv("OLA_MAPS_BASE_URL", "https://api.olamaps.io")

# API Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Default matching parameters
DEFAULT_MAX_STUDENTS_PER_VOLUNTEER = 4
DEFAULT_PREVENT_DUPLICATES = True
