
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x.strip().isdigit()]

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "bot.db")

WELCOME_TEXT = "Привет! Я помогу рассчитать твою норму калорий. Начни с /setprofile."
GOALS = {"loss": "Похудение", "maintain": "Поддержание", "gain": "Набор массы"}
ACTIVITY = {1:1.2,2:1.375,3:1.55,4:1.725,5:1.9}
