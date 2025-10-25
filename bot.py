import os, json, html, logging, time
from typing import Optional
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# --- токен
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN/TOKEN не задан")

# --- адрес веб-аппа (кнопка /start)
WEBAPP_URL = (
    os.getenv("CATALOG_WEBAPP_URL")
    or os.getenv("CATALOG_URL")
    or "https://ngfreyman-jpg.github.io/forfriends-catalog/"
)

def _parse_int(v: Optional[str]) -> Optional[int]:
    try:
        s = str(v or "").strip()
        return int(s) if s and s.lower() != "none" else None
    except Exception:
        return None

SELLER_CHAT_ID: Optional[int]     = _parse_int(os.getenv("SELLER_CHAT_ID", "1048516560"))
ORDERS_LOG_CHAT_ID: Optional[int] = _parse_int(os.getenv("ORDERS_LOG_CHAT_ID"))

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ===== helpers
def safe(x): return html.escape(str(x or ""))

def format_order(data: dict, fallback_user) -> str:
    items   = data.get("items") or []
    comment = (data.get("comment") or "").strip()
    total   = int(float(data.get("total") or 0))
    u       = data.get("user") or {}

    lines, grand = [], 0
    for it in items:
        title = safe(it.get("title"))
        qty   = int(it.get("qty") or 1)
        price = int(float(it.get("price") or 0))
        sub   = qty * price
        grand += sub
        lines.append(f"• {title} — {qty} × {price} ₽ = {sub} ₽")

    if total <= 0:
        total = grand

    buyer = safe(u.get("name") or fallback_user.full_name)
    if u.get("username"): buyer += f" @{safe(u.get('username'))}"
    if u.get("id"):       buyer += f" (id {safe(u.get('id'))})"

    text = (
        "<b>🧾 Новый заказ</b>\n"
        f"Клиент: {buyer}\n\n"
        "<b>Товары:</b>\n" + ("\n".join(lines) if lines else "—") +
        f"\n\nИтого: <b>{total} ₽</b>\n"
        f"Комментарий: {safe(comment) if comment else '—'}"
    )
    return text

def send_log(msg: str):
    if ORDERS_LOG_CHAT_ID:
        try: bot.send_message(ORDERS_LOG_CHAT_ID, msg)
        except Exception as e: logging.warning("send_log failed: %s", e)

def deliver_order(message, payload: dict):
    """Отправка заказа продавцу + копия отправителю + (опц.) лог-чат."""
    text = format_order(payload, message.from_user)

    targets = []
    if SELLER_CHAT_ID: targets.append(SELLER_CHAT_ID)
    targets.append(message.chat.id)  # копия отправителю
    if ORDERS_LOG_CHAT_ID: targets.append(ORDERS_LOG_CHAT_ID)

    errs = 0
    for chat_id in targets:
        try:
            bot.send_message(chat_id, text)
        except Exception as e:
            errs += 1
            logging.exception("deliver fail to %s: %s", chat_id, e)

    if errs == 0 and message.chat.id != SELLER_CHAT_ID:
        bot.send_message(message.chat.id, "✅ Заказ отправлен продавцу. Копия у вас.")
    elif errs > 0:
        bot.send_message(message.chat.id, "⚠️ Заказ создан, но не все адресаты получили сообщение.")

# ===== UI
@bot.message_handler(commands=['start'])
def cmd_start(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="Открыть каталог 👕", web_app=WebAppInfo(WEBAPP_URL)))
    bot.send_message(message.chat.id, "Привет! Нажми кнопку, чтобы открыть каталог:", reply_markup=kb)

@bot.message_handler(commands=['id'])
def cmd_id(message):
    bot.send_message(message.chat.id, f"Ваш chat_id: <code>{message.chat.id}</code>")

# ===== Приём заказа из WebApp (основной хэндлер)
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        payload = json.loads(message.web_app_data.data)
        logging.info("GOT WEB_APP_DATA (native) from %s: %s", message.from_user.id, payload)
        send_log(f"🧩 got web_app_data from <code>{message.from_user.id}</code>")
    except Exception as e:
        logging.exception("bad web_app_data: %s", e)
        bot.send_message(message.chat.id, "Не удалось обработать заказ 😕 Попробуйте ещё раз.")
        return
    deliver_order(message, payload)

# ===== ФОЛБЭК: иногда web_app_data приходит вместе с text
@bot.message_handler(content_types=['text'])
def handle_text_possible_webapp(message):
    wad = getattr(message, 'web_app_data', None)
    if wad and getattr(wad, 'data', None):
        try:
            payload = json.loads(wad.data)
            logging.info("GOT WEB_APP_DATA (fallback/text) from %s: %s", message.from_user.id, payload)
            send_log(f"🧩 got web_app_data (fallback) from <code>{message.from_user.id}</code>")
            deliver_order(message, payload)
            return
        except Exception as e:
            logging.exception("bad web_app_data (fallback): %s", e)
            bot.send_message(message.chat.id, "Не удалось обработать заказ 😕 Попробуйте ещё раз.")
            return
    # прочие тексты игнорим/обрабатываем по желанию

# ===== запуск: снятие вебхука и polling
if __name__ == "__main__":
    try:
        info = bot.get_webhook_info()
        print("Webhook info:", info)
        bot.remove_webhook()     # без лишних аргументов — совместимо со старыми версиями
        time.sleep(0.5)
    except Exception as e:
        print("remove_webhook failed:", e)

    try:
        if SELLER_CHAT_ID:
            bot.send_message(SELLER_CHAT_ID, "🚀 Бот запущен, ожидаю заказы.")
    except Exception as e:
        logging.warning("Can't DM SELLER_CHAT_ID on startup: %s", e)

    bot.infinity_polling(
        skip_pending=True,
        timeout=60,
        long_polling_timeout=50
    )
