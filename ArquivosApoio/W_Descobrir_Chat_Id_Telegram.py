import asyncio
from telegram import Bot


async def get_chat_id(token):
    bot = Bot(token=token)
    updates = await bot.get_updates()

    for update in updates:
        if update.message:
            chat = update.message.chat
            print(f"Chat ID: {chat.id}")
            print(f"Tipo: {chat.type}")
            print(f"Nome: {chat.title if chat.title else chat.first_name}")
            print("---")


# Use seu token aqui
asyncio.run(get_chat_id("8306189935:AAFOys5WC7UqfrO0A_p1xooYAmVV8bDt-HY"))