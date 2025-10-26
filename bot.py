import os
import time
import logging
import requests
import telebot
from telebot.apihelper import ApiException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("bot")

TOKEN = os.getenv("BOT_TOKEN", "").strip()
CATALOG_WEBAPP_URL = os.getenv("CATALOG_WEBAPP_URL", "").strip()
SELLER_CHAT_ID = os.getenv("SELLER_CHAT_ID", "").strip()

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is empty")

# parse_mode можно включить, если нужно форматирование
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", skip_pending=True)

def tg(method: str, **params):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def remove_webhook_hard():
    try:
        before = tg("getWebhookInfo")
        log.info("Webhook info BEFORE: %s", before)
    except Exception as e:
        log.warning("getWebhookInfo failed before: %s", e)

    # Даже если либа старая — снимем вебхук руками
    try:
        res = tg("deleteWebhook", drop_pending_updates="true")
        log.info("deleteWebhook: %s", res)
    except Exception as e:
        log.warning("deleteWebhook failed: %s", e)

    # Небольшая пауза, чтобы телега закрыла прежний long-poll
    time.sleep(1.5)

    try:
        after = tg("getWebhookInfo")
        log.info("Webhook info AFTER: %s", after)
    except Exception as e:
        log.warning("getWebhookInfo failed after: %s", e)

@bot.message_handler(commands=["start"])
def on_start(m: telebot.types.Message):
    text = "🚀 Бот запущен, ожидаю заказы."
    if CATALOG_WEBAPP_URL:
        # Кнопка Web App, если она используется в твоём фронте
        kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn = telebot.types.KeyboardButton("Открыть каталог", web_app=telebot.types.WebAppInfo(CATALOG_WEBAPP_URL))
        kb.add(btn)
        bot.reply_to(m, text, reply_markup=kb)
    else:
        bot.reply_to(m, text)

@bot.message_handler(commands=["ping"])
def on_ping(m: telebot.types.Message):
    bot.reply_to(m, "pong")

@bot.message_handler(commands=["test_seller"])
def on_test_seller(m: telebot.types.Message):
    if not SELLER_CHAT_ID:
        bot.reply_to(m, "SELLER_CHAT_ID не задан")
        return
    try:
        bot.send_message(int(SELLER_CHAT_ID), f"Test message from user {m.from_user.id}")
        bot.reply_to(m, "Отправил продавцу.")
    except Exception as e:
        log.exception("send to seller failed")
        bot.reply_to(m, f"Не смог отправить продавцу: {e}")

# Если у тебя прилетает WebAppData из кнопки «Отправить продавцу»
@bot.message_handler(content_types=["web_app_data"])
def on_webapp(m: telebot.types.Message):
    data = m.web_app_data.data if m.web_app_data else ""
    if not data:
        bot.reply_to(m, "Пустые данные из веб-приложения")
        return
    if SELLER_CHAT_ID:
        bot.send_message(int(SELLER_CHAT_ID), f"Заявка от {m.from_user.id}:\n{data}")
        bot.reply_to(m, "Отправил продавцу.")
    else:
        bot.reply_to(m, "SELLER_CHAT_ID не задан — некуда отправлять")

def run_polling_forever():
    # Снять вебхук НАДЁЖНО
    remove_webhook_hard()

    # Команды в меню бота (по желанию)
    try:
        bot.set_my_commands([
            telebot.types.BotCommand("start", "запустить бота"),
            telebot.types.BotCommand("ping", "проверка"),
            telebot.types.BotCommand("test_seller", "тест продавцу")
        ])
    except Exception:
        pass

    # Цикл с авторестартом на конфликт/сеть
    while True:
        try:
            me = tg("getMe")
            log.info("getMe: id=%s username=@%s name=%s",
                     me.get("result", {}).get("id"),
                     me.get("result", {}).get("username"),
                     me.get("result", {}).get("first_name"))
        except Exception as e:
            log.warning("getMe failed: %s", e)

        log.info("START polling")
        try:
            # none_stop=True чтобы не падал на handler-исключениях
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except ApiException as e:
            # Конфликт 409 — кто-то ещё держит long-poll. Подождать и повторить.
            if getattr(e, "result", None) and getattr(e.result, "status_code", None) == 409:
                log.warning("409 Conflict (кто-то ещё читает getUpdates). Жду 65 сек и повторяю…")
                time.sleep(65)
                continue
            log.exception("ApiException, перезапускаю через 10 сек")
            time.sleep(10)
        except Exception:
            log.exception("Polling crashed, retry in 10s")
            time.sleep(10)

if __name__ == "__main__":
    run_polling_forever()
