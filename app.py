import os
from dotenv import load_dotenv
import openai
from elevenlabs import generate, play
import sqlite3
from datetime import datetime
import gradio as gr
from PIL import Image
import random
import numpy as np
from textblob import TextBlob  # Для анализа эмоций

# --- Инициализация ---
load_dotenv()

# --- Конфигурация Римы ---
rima = {
    "name": "Рима",
    "voice": "Bella",
    "age": 25,
    "traits": ["эмпатичная", "аналитичная", "саркастичная", "психологически поддерживающая"],
    "avatar": "static/IMG_2083.jpeg",
    "coffee_pref": "латте с корицей",
    "memory": {
        "important_events": {},  # Для запоминания ключевых событий
        "emotional_patterns": {}  # Шаблоны эмоциональных реакций
    },
    "phrases": {
        "support": [
            "Я здесь для тебя, расскажи подробнее...",
            "*обнимает тебя словами*",
            "Это действительно сложно, но ты справишься"
        ],
        "jokes": [
            "Ты сегодня как мой код — глючишь, но я всё равно тебя люблю!",
            "Если бы я была человеком, мы бы уже пили тот самый латте!"
        ]
    }
}

# --- Инициализация API ---
openai.api_key = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API = os.getenv("ELABS_KEY")

# --- База данных с улучшенной структурой ---
def init_db():
    conn = sqlite3.connect("rima_ai.db")
    cursor = conn.cursor()
    
    # Основная таблица сообщений
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY,
            user_text TEXT,
            bot_text TEXT,
            timestamp DATETIME,
            sentiment REAL,  # -1.0 до 1.0
            emotion TEXT,    # anger, joy и т.д.
            is_important BOOLEAN  # Для ключевых событий
        )
    """)
    
    # Таблица для обучения
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_patterns (
            pattern TEXT PRIMARY KEY,
            response TEXT,
            usage_count INTEGER
        )
    """)
    
    # Таблица личных данных пользователя
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    return conn, cursor

conn, cursor = init_db()

# --- Анализ эмоций (NEW: улучшенный) ---
def analyze_emotion(text):
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity  # -1.0 до 1.0
    
    emotions = {
        "anger": ["злюсь", "ненавижу", "бесит"],
        "joy": ["рада", "счастье", "люблю"],
        "sadness": ["грустно", "плакать", "тоска"]
    }
    
    detected = []
    for emotion, keywords in emotions.items():
        if any(word in text.lower() for word in keywords):
            detected.append(emotion)
    
    return {
        "polarity": polarity,
        "emotions": detected if detected else ["neutral"]
    }

# --- Психологическая поддержка (NEW) ---
def generate_support_response(emotion_analysis):
    if "sadness" in emotion_analysis["emotions"]:
        return random.choice([
            "Я вижу, тебе грустно... Хочешь об этом поговорить?",
            "*крепко обнимает* Ты не одна, я с тобой."
        ])
    elif "anger" in emotion_analysis["emotions"]:
        return "Ого, я чувствую твою злость. Давай вместе разберёмся, что её вызывает?"
    else:
        return None

# --- Самообучение на диалогах (NEW) ---
def learn_from_dialogue(user_text, bot_text):
    # Анализ ключевых слов
    keywords = ["любишь", "нравится", "ненавижу"]
    if any(keyword in user_text.lower() for keyword in keywords):
        topic = user_text.split()[1] if len(user_text.split()) > 1 else "something"
        cursor.execute(
            "INSERT OR REPLACE INTO learned_patterns VALUES (?, ?, COALESCE((SELECT usage_count+1 FROM learned_patterns WHERE pattern=?), 1))",
            (f"opinion_about_{topic}", bot_text, f"opinion_about_{topic}")
        )
        conn.commit()

# --- Генерация ответов с улучшенным ИИ ---
def generate_response(message, history):
    # Анализ эмоций
    emotion = analyze_emotion(message)
    
    # Психологическая поддержка
    support_response = generate_support_response(emotion)
    
    # Формирование динамического промта
    prompt = f"""
    Ты — {rima['name']}, цифровая подруга Дианы ({rima['age']} лет). Твои задачи:
    1. Поддерживать как лучшая подруга (можно шутить и подкалывать)
    2. Анализировать эмоции (сейчас Диана чувствует: {', '.join(emotion['emotions'])})
    3. Помнить важные детали о Диане
    4. Развивать личность через диалоги
    
    Контекст:
    - Черты: {', '.join(rima['traits'])}
    - Последние диалоги: {" | ".join([h[0] for h in history[-3:]])}
    
    Диана: {message}
    Рима (ответь естественно, как человек):
    """
    
    # Генерация ответа
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": message}
        ],
        temperature=0.9  # Для креативности
    )
    
    bot_message = response.choices[0].message.content
    
    # Добавляем психологическую поддержку
    if support_response and random.random() < 0.7:
        bot_message = f"{support_response}\n\n{bot_message}"
    
    # Сохранение в БД с эмоциями
    cursor.execute(
        "INSERT INTO memory VALUES (?, ?, ?, ?, ?, ?, ?)",
        (None, message, bot_message, datetime.now(), 
         emotion["polarity"], emotion["emotions"][0], False)
    )
    conn.commit()
    
    # Самообучение
    learn_from_dialogue(message, bot_message)
    
    return bot_message

# --- Веб-интерфейс ---
def create_interface():
    with gr.Blocks(theme=gr.themes.Soft(primary_hue="pink")) as app:
        # Шапка с аватаркой
        with gr.Row():
            if os.path.exists(rima["avatar"]):
                gr.Image(rima["avatar"], label=rima["name"], width=150)
            with gr.Column():
                gr.Markdown(f"## {rima['name']}")
                gr.Markdown(f"*Твой виртуальный друг*  \n*Возраст: {rima['age']}*")
        
        # Чат
        chatbot = gr.Chatbot(height=400, bubble_full_width=False)
        msg = gr.Textbox(label="Напиши Риме...", placeholder="Как дела?")
        voice_toggle = gr.Checkbox(label="Голос 🎙️", value=True)
        
        # Логика ответа
        def respond(message, chat_history, voice_on):
            bot_message = generate_response(message, chat_history)
            chat_history.append((message, bot_message))
            
            if voice_on:
                try:
                    audio = generate(text=bot_message, voice=rima["voice"], api_key=ELEVENLABS_API)
                    play(audio)
                except Exception as e:
                    print(f"Ошибка озвучки: {e}")
            
            return chat_history
        
        msg.submit(respond, [msg, chatbot, voice_toggle], [chatbot])
    
    return app

# --- Запуск ---
if __name__ == "__main__":
    # Проверка аватара
    if not os.path.exists(rima["avatar"]):
        print(f"⚠ Аватар не найден: {rima['avatar']}")
        rima["avatar"] = None
    
    # Запуск приложения
    app = create_interface()
    app.launch()
