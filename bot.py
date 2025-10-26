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
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

# ---------- инициализация ----------
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)

# ---------- утилиты ----------
def tg_api_call(method: str, params: dict = None):
    """Прямой вызов Telegram API (для deleteWebhook/getWebhookInfo)."""
    params = params or {}
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "forfriends-bot"})
    with urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
    try:
        return json.loads(raw)
    except Exception:
        return {"ok": False, "raw": raw}

def safe_delete_webhook():
    # снять вебхук и выкинуть старые апдейты
    try:
        r = tg_api_call("deleteWebhook", {"drop_pending_updates": "true"})
        log.info("deleteWebhook -> %s", r)
    except Exception as e:
        log.warning("deleteWebhook failed: %s", e)
    try:
        info = tg_api_call("getWebhookInfo")
        log.info("getWebhookInfo -> %s", info)
    except Exception as e:
        log.warning("getWebhookInfo failed: %s", e)

# ---------- команды ----------
@bot.message_handler(commands=["start"])
def cmd_start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Открыть каталог", web_app=types.WebAppInfo(CATALOG_WEBAPP_URL)))
    bot.reply_to(
        message,
        "Привет! Нажми кнопку ниже, чтобы открыть каталог.",
        reply_markup=kb,
    )

@bot.message_handler(commands=["id"])
def cmd_id(message: types.Message):
    bot.reply_to(message, f"Ваш chat_id: <code>{message.chat.id}</code>")

@bot.message_handler(commands=["ping"])
def cmd_ping(message: types.Message):
    bot.reply_to(message, "pong")

# ---------- приём данных из WebApp (кнопка «Отправить продавцу») ----------
@bot.message_handler(content_types=["web_app_data"])
def handle_webapp_data(message: types.Message):
    raw = message.web_app_data.data
    try:
        data = json.loads(raw)
    except Exception:
        data = {"raw": raw}

    # Сообщение продавцу: аккуратный JSON
    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    user = message.from_user
    header = (
        "🧾 <b>Новая заявка</b>\n"
        f"Клиент: <a href=\"tg://user?id={user.id}\">{user.first_name or ''}</a> "
        f"(id: <code>{user.id}</code>)\n"
        f"username: @{user.username if user.username else '—'}\n\n"
    )
    body = f"<pre>{pretty}</pre>"

    try:
        bot.send_message(int(SELLER_CHAT_ID), header + body, disable_web_page_preview=True)
        # Покупателю — короткое подтверждение
        bot.reply_to(message, "✅ Заказ принят. Спасибо!")
    except Exception as e:
        log.exception("send order to seller failed")
        bot.reply_to(message, f"❌ Не удалось передать данные продавцу: {e}")

# (необязательный компактный лог всех входящих — не мешает логике)
@bot.message_handler(func=lambda m: True, content_types=[
    'text','web_app_data','photo','document','contact','location','venue',
    'sticker','audio','video','voice','dice','poll'
])
def _dbg_everything(message: types.Message):
    try:
        has_wad = bool(getattr(message, 'web_app_data', None) and getattr(message.web_app_data, 'data', None))
        logging.info("DBG: type=%s has_web_app_data=%s text=%r",
                     message.content_type, has_wad, (message.text or '')[:60])
    except Exception as e:
        logging.warning("DBG logger err: %s", e)

# ---------- запуск ----------
if __name__ == "__main__":
    log.info("starting…")
    safe_delete_webhook()           # гарантированно убираем вебхук и хвосты
    time.sleep(0.5)

    # стабильный polling без спорных параметров
    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=10,
                long_polling_timeout=20,
            )
            time.sleep(1)  # если внезапно вышли — перезапустим цикл
        except telebot.apihelper.ApiTelegramException as e:
            # типичный конфликт 409 — подождём и повторим
            if "409" in str(e) or "terminated by other getUpdates" in str(e):
                logging.error("409 conflict: waiting 5s and retry…")
                try: bot.stop_polling()
                except Exception: pass
                time.sleep(5)
                continue
            logging.exception("Telegram API error, retry in 5s")
            time.sleep(5)
        except Exception:
            logging.exception("Bot crashed, restart in 5s")
            try: bot.stop_polling()
            except Exception: pass
            time.sleep(5)
