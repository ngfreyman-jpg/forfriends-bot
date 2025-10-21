import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

# Получаем токен из переменной окружения (Railway)
TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

# URL твоего сайта
WEBAPP_URL = "https://ngfreyman-jpg.github.io/forfriends-catalog/"

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton(
        text="Открыть каталог 👕",
        web_app={"url": WEBAPP_URL}
    )
    markup.add(btn)
    bot.send_message(
        message.chat.id,
        "Привет! 👋\nНажми кнопку ниже, чтобы открыть каталог:",
        reply_markup=markup
    )

bot.polling(none_stop=True)
