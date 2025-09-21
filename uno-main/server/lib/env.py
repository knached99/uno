import os
from dotenv import load_dotenv

# Load variables from a .env file in this directory or parent when present
load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT") or 'development'
WEB_URL = os.getenv("WEB_URL") or 'http://localhost:3000'
# Optional: comma-separated list of allowed frontend origins
WEB_URLS = [u.strip() for u in os.getenv("WEB_URLS", "").split(",") if u.strip()]
