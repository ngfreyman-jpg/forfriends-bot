import asyncio, os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("BOT_TOKEN")  # возьмём из переменных окружения на Render

bot = Bot(TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_cmd(m: types.Message):
    await m.answer("Привет! Бот работает ✅")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
