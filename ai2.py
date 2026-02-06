import os
import logging
import random
import asyncio
from collections import defaultdict, deque
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import AsyncOpenAI

# --- Настройки ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# СЮДА ВСТАВЬ СВОИ КЛЮЧИ
BOT_TOKEN = '7351866361:AAEzpBbfJhgb0_f1i8KdsIDstbqiMO5hF48'
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Настройки поведения
MAX_HISTORY_PER_CHAT = 15  # Сколько последних сообщений помнить для контекста
USER_STYLE_SAMPLES = 10  # Сколько сообщений конкретного юзера брать для примера стиля
REPLY_CHANCE = 0.15  # Вероятность (15%), что бот ответит сам, без упоминания

# Память бота
chat_histories = defaultdict(lambda: deque(maxlen=MAX_HISTORY_PER_CHAT))
user_messages = defaultdict(lambda: deque(maxlen=20))  # Память стилей пользователей


async def get_chat_response(messages, system_prompt):
    """Запрос к OpenAI"""
    try:
        response = await client.chat.completions.create(
            model="mistralai/mistral-7b-instruct",  # или gpt-3.5-turbo
            messages=[{"role": "system", "content": system_prompt}] + list(messages),
            temperature=0.8,  # Чуть выше для креативности
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI Error: {e}")
        return None


def build_style_prompt(user_id, user_name, chat_id):
    """Создает системную инструкцию на основе стиля участника"""
    samples = list(user_messages[user_id])
    style_examples = "\n".join([f"- {s}" for s in samples[-USER_STYLE_SAMPLES:]])

    prompt = (
        f"Ты — живой участник чата. Ты общаешься непринужденно, как человек.\n"
        f"Сейчас ты имитируешь стиль пользователя {user_name}.\n"
        f"Вот примеры его сообщений для подражания (используй те же манеры, сленг, пунктуацию):\n"
        f"{style_examples}\n\n"
        f"ПРАВИЛА:\n"
        f"1. Не пиши как ИИ. Не используй фразы 'Как я могу помочь?' или 'Я ассистент'.\n"
        f"2. Если в чате матерятся — можешь слегка поддерживать тон, но не груби сам без причины.\n"
        f"3. Пиши коротко, как в мессенджерах. Редко используй заглавные буквы, если пользователь их не использует.\n"
        f"4. Твоя задача — вклиниться в диалог естественно или ответить на вопрос."
    )
    return prompt


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    msg = update.message
    chat_id = msg.chat.id
    user = msg.from_user
    text = msg.text

    # 1. Запоминаем сообщение для стиля пользователя
    user_messages[user.id].append(text)

    # 2. Формируем контекст чата (кто что сказал)
    formatted_msg = {"role": "user", "content": f"{user.first_name}: {text}"}
    chat_histories[chat_id].append(formatted_msg)

    # 3. Логика: отвечать или нет?
    is_reply_to_bot = msg.reply_to_message and msg.reply_to_message.from_user.id == context.bot.id
    is_mention = context.bot.username and f"@{context.bot.username}" in text
    random_interjection = random.random() < REPLY_CHANCE

    if is_reply_to_bot or is_mention or random_interjection:
        # Показываем, что бот "печатает"
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        # Строим промпт
        system_prompt = build_style_prompt(user.id, user.first_name, chat_id)

        # Получаем ответ
        response_text = await get_chat_response(chat_histories[chat_id], system_prompt)

        if response_text:
            # Убираем имя из начала, если нейросеть его случайно добавила
            clean_response = response_text.split(':')[-1].strip()

            await msg.reply_text(clean_response)
            # Добавляем свой ответ в историю
            chat_histories[chat_id].append({"role": "assistant", "content": clean_response})


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я в деле. Буду общаться в вашем стиле.")


def main():
    # Проверка ключей
    if "7351866361" in BOT_TOKEN:  # Заглушка, если ты забыл поменять
        print("Не забудь обновить токены в коде!")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()



