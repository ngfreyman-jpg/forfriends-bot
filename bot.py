# bot.py
import os, logging, time
import telebot
from telebot.apihelper import ApiTelegramException

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
try:
    telebot.logger.setLevel(logging.CRITICAL)
except Exception:
    pass

TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
SELLER_CHAT_ID = os.getenv("SELLER_CHAT_ID")

if not TOKEN:
    raise SystemExit("ENV BOT_TOKEN не задан")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

@bot.message_handler(commands=["start"])
def on_start(m):
    bot.reply_to(m, "Бот жив. Команда /ping тоже должна работать.")

@bot.message_handler(commands=["ping"])
def on_ping(m):
    bot.reply_to(m, "pong")

@bot.message_handler(commands=["test_seller"])
def on_test_seller(m):
    if not SELLER_CHAT_ID:
        bot.reply_to(m, "SELLER_CHAT_ID не задан в ENV")
        return
    try:
        bot.send_message(int(SELLER_CHAT_ID), f"Test message from user {m.from_user.id}")
        bot.reply_to(m, "Отправил продавцу.")
    except Exception as e:
        bot.reply_to(m, f"Не смог отправить продавцу: {e}")

def run():
    # 1) Сносим вебхук и чистим “хвосты”
    try:
        info_before = bot.get_webhook_info()
        logging.info("Webhook info BEFORE: %s", info_before)
        bot.remove_webhook(drop_pending_updates=True)
        info_after = bot.get_webhook_info()
        logging.info("Webhook info AFTER: %s", info_after)
    except Exception as e:
        logging.warning("Не смог получить/удалить вебхук: %s", e)

    # 2) Проверим токен
    try:
        me = bot.get_me()
        logging.info("getMe: id=%s username=@%s name=%s", me.id, getattr(me, "username", None), me.first_name)
    except Exception as e:
        logging.error("getMe провалился: %s", e)
        time.sleep(5)

    # 3) Стартуем один цикл polling с бэкоффом
    delay = 1
    while True:
        try:
            logging.info("START polling")
            bot.infinity_polling(
                timeout=30,      # таймаут long poll
                long_polling_timeout=30,
                allowed_updates=["message", "callback_query"]
            )
            delay = 1  # если polling завершился сам — сбросим задержку и попробуем снова
        except ApiTelegramException as e:
            # 409 = параллельный getUpdates => где-то второй инстанс
            logging.error("API error: %s", e)
            if getattr(e, "result", None) and getattr(e.result, "status_code", None) == 409:
                logging.error("Параллельный getUpdates (409). Значит запущен второй процесс/деплой.")
            time.sleep(delay)
            delay = min(delay * 2, 60)
        except Exception as e:
            logging.exception("Poll crashed: %s", e)
            time.sleep(delay)
            delay = min(delay * 2, 60)

if __name__ == "__main__":
    run()
