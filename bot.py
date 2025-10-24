import os
import json
import html
import logging
import telebot
from typing import Optional
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

logging.basicConfig(level=logging.INFO)

# ---- токен бота
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN/TOKEN не задана")

# ---- ссылки на каталог (можно переопределить в env)
WEBAPP_URL = os.getenv("CATALOG_WEBAPP_URL") or os.getenv("CATALOG_URL") or "https://ngfreyman-jpg.github.io/forfriends-catalog/"

# ---- маршрутизация заказов (разделённые конфиги)
def _parse_int(val: Optional[str]) -> Optional[int]:
    try:
        s = str(val).strip()
        return int(s) if s and s.lower() != "none" else None
    except Exception:
        return None

SELLER_CHAT_ID: Optional[int] = _parse_int(os.getenv("SELLER_CHAT_ID", "1048516560"))
ORDERS_LOG_CHAT_ID: Optional[int] = _parse_int(os.getenv("ORDERS_LOG_CHAT_ID"))  # опционально

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ===== UI: старт и кнопка каталога =====
@bot.message_handler(commands=['start'])
def start(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="Открыть каталог 👕", web_app=WebAppInfo(WEBAPP_URL)))
    bot.send_message(message.chat.id, "Привет! 👋 Нажми кнопку, чтобы открыть каталог:", reply_markup=kb)

# ===== Приём заказа из WebApp =====
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
    except Exception:
        bot.send_message(message.chat.id, "Не удалось обработать заказ 😕 Попробуйте ещё раз.")
        return

    items = data.get("items", [])
    comment = (data.get("comment") or "").strip()
    total = int(float(data.get("total") or 0))
    u = data.get("user") or {}

    safe = lambda s: html.escape(str(s or ""))
    lines, grand = [], 0
    for it in items:
        title = safe(it.get("title"))
        qty = int(it.get("qty") or 1)
        price = int(float(it.get("price") or 0))
        sub = price * qty
        grand += sub
        lines.append(f"• {title} — {qty} × {price} ₽ = {sub} ₽")

    if total <= 0:
        total = grand

    buyer = f"{safe(u.get('name'))}"
    if u.get("username"):
        buyer += f" @{safe(u.get('username'))}"
    if u.get("id"):
        buyer += f" (id {safe(u.get('id'))})"

    text = (
        "<b>🧾 Новый заказ</b>\n"
        f"Клиент: {buyer or safe(message.from_user.full_name)}\n\n"
        "<b>Товары:</b>\n" + ("\n".join(lines) if lines else "—") +
        f"\n\nИтого: <b>{total} ₽</b>\n"
        f"Комментарий: {safe(comment) if comment else '—'}"
    )

    # Куда отправлять: всегда продавцу; опционально — в лог-чат
    targets = []
    if SELLER_CHAT_ID:
        targets.append(SELLER_CHAT_ID)
    else:
        targets.append(message.chat.id)  # фолбэк на отправителя, чтобы не терять заказ
    if ORDERS_LOG_CHAT_ID:
        targets.append(ORDERS_LOG_CHAT_ID)

    errors = 0
    for chat_id in targets:
        try:
            bot.send_message(chat_id, text)
        except Exception as e:
            logging.exception("Failed to deliver order to %s: %s", chat_id, e)
            errors += 1

    if errors == 0:
        bot.send_message(message.chat.id, "✅ Заказ отправлен продавцу. Спасибо!")
    else:
        bot.send_message(message.chat.id, "⚠️ Заказ создан, но не все адресаты получили сообщение. Свяжитесь с продавцом на всякий случай.")

# ===== Поллинг =====
bot.infinity_polling(skip_pending=True)
