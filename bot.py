import asyncio
import logging
import os
import base64
import re
import httpx
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

BOT_TOKEN = os.getenv("BOT_TOKEN")
NARA_API_KEY = os.getenv("NARA_API_KEY")
NARA_URL = "https://router.bynara.id/v1/chat/completions"
DB_PATH = "chat_history.db"

# Максимальное количество сообщений из истории, передаваемых в LLM (контекст)
MAX_HISTORY_LIMIT = 10 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

SECURITY_PROMPT = """Ты — эксперт по кибербезопасности. Проанализируй следующий код/файл на наличие вредоносного поведения, бэкдоров, уязвимостей или опасных системных вызовов (например, rm -rf, os.system, несанкционированные сетевые запросы, слив токенов).
Дай чёткий вердикт:
1. Безопасно / Подозрительно / Опасно.
2. Подробный разбор найденных угроз (если есть).
3. Рекомендации по исправлению."""

# --- РАБОТА С БАЗОЙ ДАННЫХ (SQLite) ---

async def init_db():
    """Инициализация БД: создание таблицы историй"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def save_message(chat_id: int, user_id: int, username: str, role: str, content: str):
    """Сохранение сообщения в историю"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (chat_id, user_id, username, role, content) VALUES (?, ?, ?, ?, ?)",
            (chat_id, user_id, username or "unknown", role, content)
        )
        await db.commit()

async def get_chat_history(chat_id: int, limit: int = MAX_HISTORY_LIMIT) -> list:
    """Получение последних N сообщений чата для формирования контекста"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            # Разворачиваем список, чтобы сообщения шли в хронологическом порядке
            history = [{"role": row[0], "content": row[1]} for row in reversed(rows)]
            return history

# --- ВНОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def call_nara_api(messages: list, model: str = "nemotron-3.5-lightning-free") -> str:
    headers = {"Authorization": f"Bearer {NARA_API_KEY}"}
    payload = {"model": model, "messages": messages}
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(NARA_URL, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            return f"⚠️ Ошибка API (Статус {res.status_code}): {res.text}"
    except Exception as e:
        return f"❌ Ошибка подключения к API: {e}"

# --- ХЭНДЛЕРЫ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Привет! Я Сара — твой AI-ассистент.**\n\n"
        "Чем я могу помочь:\n"
        "• **Общение с памятью контекста:** Помню ход нашего разговора.\n"
        "• **Анализ безопасности:** Отправь `.py`, `.sh`, `.cpp` или код — проверю на уязвимости.\n"
        "• **Зрение (Vision):** Пришли картинку или скриншот.\n"
        "• **Работа в группах:** Зови по имени **Сара** / **Sara** или отвечай на мои сообщения.\n"
        "• **Инлайн-режим:** Пиши `@username_bot ваш_запрос` в любых чатах!",
        parse_mode="Markdown"
    )

@dp.message(F.document)
async def handle_document(message: types.Message):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    doc = message.document
    file_info = await bot.get_file(doc.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    
    try:
        code_content = downloaded_file.read().decode('utf-8')
    except UnicodeDecodeError:
        await message.answer("❌ Не удалось прочитать файл как текст.")
        return

    # Логируем отправку файла
    await save_message(message.chat.id, message.from_user.id, message.from_user.username, "user", f"[Отправлен файл {doc.file_name}]")

    messages = [
        {"role": "system", "content": SECURITY_PROMPT},
        {"role": "user", "content": f"Имя файла: {doc.file_name}\nСодержимое:\n```\n{code_content[:4000]}\n```"}
    ]
    
    response = await call_nara_api(messages)
    await save_message(message.chat.id, bot.id, "SaraBot", "assistant", response)
    await message.answer(f"🔍 **Аудит безопасности файла {doc.file_name}:**\n\n{response}", parse_mode="Markdown")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    
    base64_image = base64.b64encode(downloaded_file.read()).decode('utf-8')
    caption = message.caption or "Что изображено на этой картинке?"

    await save_message(message.chat.id, message.from_user.id, message.from_user.username, "user", f"[Отправлено изображение с подписью: {caption}]")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": caption},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }
    ]
    
    response = await call_nara_api(messages, model="ling-3.0-flash-vl-free")
    await save_message(message.chat.id, bot.id, "SaraBot", "assistant", response)
    await message.answer(response, parse_mode="Markdown")

@dp.message(F.text)
async def handle_text(message: types.Message):
    bot_info = await message.bot.get_me()
    user_text = message.text.strip()
    
    # Проверка триггеров в группах
    if message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        is_reply_to_bot = (
            message.reply_to_message and 
            message.reply_to_message.from_user.id == bot_info.id
        )
        has_name_trigger = bool(re.search(r'\b(сара|sara)\b', user_text, re.IGNORECASE))
        is_mentioned = f"@{bot_info.username}" in user_text
        
        if not (is_reply_to_bot or has_name_trigger or is_mentioned):
            return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    # Очищаем реплику
    clean_text = re.sub(r'\b(сара|sara)\b', '', user_text, flags=re.IGNORECASE)
    clean_text = clean_text.replace(f"@{bot_info.username}", "").strip() or "Привет!"

    # 1. Сохраняем сообщение пользователя в БД
    await save_message(message.chat.id, message.from_user.id, message.from_user.username, "user", clean_text)

    # 2. Подтягиваем историю сообщений из БД для диалогового контекста
    chat_history = await get_chat_history(message.chat.id, limit=MAX_HISTORY_LIMIT)

    # Системная инструкция
    if any(k in clean_text for k in ("def ", "import ", "class ", "SELECT ", "function")):
        system_prompt = "Ты — Сара, эксперт по разработке и кибербезопасности. Подсказывай решения, ищи уязвимости и пиши чистый код."
    else:
        system_prompt = "Ты — Сара, умный, дружелюбный AI-ассистент. Отвечай с учетом контекста беседы, используя Markdown."

    # Собираем итоговый массив сообщений: [System Prompt] + [History]
    messages_payload = [{"role": "system", "content": system_prompt}] + chat_history
    
    # 3. Запрос к LLM
    response = await call_nara_api(messages_payload)
    
    # 4. Сохраняем ответ ассистента в БД
    await save_message(message.chat.id, bot.id, "SaraBot", "assistant", response)

    # Отправка пользователю
    for i in range(0, len(response), 4000):
        await message.reply(response[i:i+4000], parse_mode="Markdown")

@dp.inline_query()
async def inline_query_handler(query: types.InlineQuery):
    text = query.query.strip()
    if not text:
        return

    messages = [{"role": "user", "content": f"Дай краткий ответ: {text}"}]
    ai_response = await call_nara_api(messages)

    results = [
        InlineQueryResultArticle(
            id="1",
            title="Ответ Сары (AI)",
            description=ai_response[:100] + "...",
            input_message_content=InputTextMessageContent(
                message_text=f"❓ **Запрос:** {text}\n\n🤖 **Сара:**\n{ai_response}",
                parse_mode="Markdown"
            )
        )
    ]
    await query.answer(results, cache_time=1)

async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()  # Инициализируем БД при старте
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
