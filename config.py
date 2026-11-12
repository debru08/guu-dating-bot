import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "9226518533:AAHG6yjCmvbwaWBuCzVhNRjKQRkfT5922Q8")
ADMIN_IDS = [1960993749]  # твой ID

# Настройки
MIN_AGE = 16
MAX_AGE = 30
MAX_DESCRIPTION_LENGTH = 300
