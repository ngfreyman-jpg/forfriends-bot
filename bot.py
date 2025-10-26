import os
import json
import time
import logging
from urllib.request import urlopen, Request
from urllib.parse import urlencode

import telebot
from telebot import types

# ---------- конфиг ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CATALOG_WEBAPP_URL = os.getenv("CATALOG_WEBAPP_URL", "").strip()
SELLER_CHAT_ID = os.getenv("SELLER_CHAT_ID", "").strip()  # строкой ок

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is empty")
if not CATALOG_WEBAPP_URL:
    raise RuntimeError("CATALOG_WEBAPP_URL is empty")
if not SELLER_CHAT_ID:
    raise RuntimeError("SELLER_CHAT_ID is empty")

# ---------- логирование ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("bot")

# ---------- инициализация ----------
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)

# ---------- утилиты ----------
def tg_api_call(method: str, params: dict = None):
    """
    Прямая работа с Telegram API без сторонних либ (чтобы гарантированно
    удалить вебхук с drop_pending_updates и не ловить несовпадения сигнатур).
    """
    params = params or {}
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "bot"})
    with urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
    try:
        return json.loads(raw)
    except Exception:
        return {"ok": False, "raw": raw}

def safe_delete_webhook():
    # 1) жёстко удаляем вебхук с drop_pending_updates=true
    try:
        r = tg_api_call("deleteWebhook", {"drop_pending_updates": "true"})
        log.info(f"deleteWebhook -> {r}")
    except Exception as e:
        log.warning(f"deleteWebhook failed: {e}")
    # 2) проверим состояние
    try:
        info = tg_api_call("getWebhookInfo")
        log.info(f"getWebhookInfo -> {info}")
    except Exception as e:
        log.warning(f"getWebhookInfo failed: {e}")

# ---------- команды ----------
@bot.message_handler(commands=["start"])
def cmd_start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Открыть каталог", web_app=types.WebAppInfo(CATALOG_WEBAPP_URL)))
    bot.reply_to(
        message,
        "🚀 Бот запущен, ожидаю заказы.\n\nНажми кнопку ниже, чтобы открыть каталог.",
        reply_markup=kb,
    )

@bot.message_handler(commands=["ping"])
def cmd_ping(message: types.Message):
    bot.reply_to(message, "pong")

@bot.message_handler(commands=["test_seller"])
def cmd_test_seller(message: types.Message):
    # пробросим простую тестовую заметку продавцу
    text = f"Test message from user <b>{message.from_user.id}</b>"
    try:
        bot.send_message(int(SELLER_CHAT_ID), text)
        bot.reply_to(message, "Отправил продавцу ✔️")
    except Exception as e:
        log.exception("send test to seller failed")
        bot.reply_to(message, f"Не удалось отправить продавцу: {e}")

# ---------- приём данных из WebApp (кнопка «Отправить продавцу»/submit) ----------
@bot.message_handler(content_types=["web_app_data"])
def handle_webapp_data(message: types.Message):
    # message.web_app_data.data — это строка; попытаемся распарсить JSON
    raw = message.web_app_data.data
    try:
        data = json.loads(raw)
    except Exception:
        data = {"raw": raw}

    # соберём человекочитаемое сообщение продавцу
    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    user = message.from_user
    header = (
        f"🧾 <b>Новая заявка</b>\n"
        f"from: <a href=\"tg://user?id={user.id}\">{user.first_name or ''}</a> (id: <code>{user.id}</code>)\n"
        f"username: @{user.username if user.username else '—'}\n"
    )
    body = f"<pre>{pretty}</pre>"

    try:
        bot.send_message(int(SELLER_CHAT_ID), header + body, disable_web_page_preview=True)
        bot.reply_to(message, "✅ Вы успешно передали данные боту кнопкой «Открыть каталог».")
    except Exception as e:
        log.exception("send order to seller failed")
        bot.reply_to(message, f"❌ Не удалось передать данные продавцу: {e}")

# ---------- запуск ----------
if __name__ == "__main__":
    log.info("starting…")
    safe_delete_webhook()  # гарантированно убираем вебхук и висящие апдейты
    # даём чуть-чуть времени, чтобы у телеги «отпустило»
    time.sleep(1)

    # важное: пропускаем накопленные апдейты и явно задаём таймауты
    bot.infinity_polling(
        timeout=10,
        long_polling_timeout=20,
        skip_pending=True,          # 💡 чтобы не выедались старые апдейты
        allowed_updates=["message", "web_app_data"],
    )
