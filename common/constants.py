import os
import pathlib
from dotenv import load_dotenv

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
if (BASE_DIR / ".env").is_file():
    load_dotenv()
else:
    print("No .env file found")

IK_API_URL = os.getenv("IK_API_URL")
IK_PRODUCT_ID = os.getenv("IK_PRODUCT_ID")
IK_ACCESS_TOKEN = os.getenv("IK_ACCESS_TOKEN")
EMAIL_SORT_LIMIT = 20