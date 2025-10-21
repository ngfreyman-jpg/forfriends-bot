import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
WEBAPP_URL = "https://ngfreyman-jpg.github.io/forfriends-catalog/"

if not TOKEN:
    raise RuntimeError("Переменная окружения TOKEN не задана")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    kb = InlineKeyboardMarkup()
    # ВАЖНО: web_app = WebAppInfo(url)
    kb.add(InlineKeyboardButton(text="Открыть каталог 👕",
                                web_app=WebAppInfo(WEBAPP_URL)))
    bot.send_message(message.chat.id,
                     "Привет! 👋 Нажми кнопку, чтобы открыть каталог:",
                     reply_markup=kb)

bot.infinity_polling(skip_pending=True)
