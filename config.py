import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database Configuration (PostgreSQL)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///default.db'
    SQLALCHEMY_TRACK_MODIFICATION = False

    # Redis Configuration
    REDIS_HOST = os.environ.get('REDIS_HOST', 'Localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

    # Rate Limiting Configuration
    LIMITER_STORAGE_URI = f"redis://{REDIS_HOST}:{REDIS_PORT}"
    LIMITER_DEFAULT = "5 per minute" # global limit
