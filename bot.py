import os
import json
import html
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
WEBAPP_URL = "https://ngfreyman-jpg.github.io/forfriends-catalog/"

# ЛС получателя заказов (пока твой ID)
SELLER_CHAT_ID = int(os.getenv("SELLER_CHAT_ID", "1048516560"))

if not TOKEN:
    raise RuntimeError("Переменная окружения TOKEN/BOT_TOKEN не задана")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


@bot.message_handler(commands=['start'])
def start(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="Открыть каталог 👕",
                                web_app=WebAppInfo(WEBAPP_URL)))
    bot.send_message(message.chat.id,
                     "Привет! 👋 Нажми кнопку, чтобы открыть каталог:",
                     reply_markup=kb)


@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    # Данные приходят от WebApp через Telegram
    try:
        raw = message.web_app_data.data
        data = json.loads(raw)
    except Exception:
        bot.send_message(message.chat.id, "Не удалось обработать заказ 😕 Попробуйте ещё раз.")
        return

    items = data.get("items", [])
    comment = (data.get("comment") or "").strip()
    total = int(float(data.get("total") or 0))
    u = data.get("user") or {}

    # Форматируем позиции
    lines = []
    safe = lambda s: html.escape(str(s or ""))
    grand = 0
    for it in items:
        title = safe(it.get("title"))
        qty = int(it.get("qty") or 1)
        price = int(float(it.get("price") or 0))
        sub = price * qty
        grand += sub
        lines.append(f"• {title} — {qty} × {price} ₽ = {sub} ₽")

    # На всякий случай сверим total
    if total <= 0:
        total = grand

    user_line = f"{safe(u.get('name'))} @{safe(u.get('username'))} (id {safe(u.get('id'))})"

    text = (
        "<b>🧾 Новый заказ</b>\n"
        f"Клиент: {user_line}\n\n"
        "<b>Товары:</b>\n" + ("\n".join(lines) if lines else "—") +
        f"\n\nИтого: <b>{total} ₽</b>\n"
        f"Комментарий: {safe(comment) if comment else '—'}"
    )

    # Отправляем продавцу в личку
    try:
        bot.send_message(SELLER_CHAT_ID, text)
    except Exception:
        # Если не удалось отправить продавцу — сообщим покупателю
        bot.send_message(message.chat.id, "Что-то не так на стороне продавца. Сообщение не доставлено.")
        return

    # Подтверждение покупателю
    bot.send_message(message.chat.id, "Спасибо! Заказ отправлен продавцу. Мы свяжемся с вами 😊")


bot.infinity_polling(skip_pending=True)
