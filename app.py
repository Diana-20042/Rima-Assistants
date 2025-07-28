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
from textblob import TextBlob

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
        "important_events": {},
        "emotional_patterns": {}
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

# --- База данных ---
def init_db():
    conn = sqlite3.connect("rima_ai.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY,
            user_text TEXT,
            bot_text TEXT,
            timestamp DATETIME,
            sentiment REAL,
            emotion TEXT,
            is_important BOOLEAN
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_patterns (
            pattern TEXT PRIMARY KEY,
            response TEXT,
            usage_count INTEGER
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    return conn, cursor

conn, cursor = init_db()

# --- Анализ эмоций ---
def analyze_emotion(text):
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    
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

# --- Генерация ответов ---
def generate_response(message, history):
    emotion = analyze_emotion(message)
    
    prompt = f"""
    Ты — {rima['name']}, цифровая подруга Дианы ({rima['age']} лет). Твои задачи:
    1. Поддерживать как лучшая подруга
    2. Анализировать эмоции (сейчас Диана чувствует: {', '.join(emotion['emotions'])})
    3. Помнить важные детали о Диане
    
    Контекст:
    - Черты: {', '.join(rima['traits'])}
    - Последние диалоги: {" | ".join([h[0] for h in history[-3:]])}
    
    Диана: {message}
    Рима (ответь естественно):
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": message}
        ],
        temperature=0.9
    )
    
    bot_message = response.choices[0].message.content
    
    cursor.execute(
        "INSERT INTO memory VALUES (?, ?, ?, ?, ?, ?, ?)",
        (None, message, bot_message, datetime.now(), 
         emotion["polarity"], emotion["emotions"][0], False)
    )
    conn.commit()
    
    return bot_message

# --- Веб-интерфейс ---
def create_interface():
    with gr.Blocks(theme=gr.themes.Soft(primary_hue="pink")) as app:
        # Шапка
        with gr.Row():
            if os.path.exists(rima["avatar"]):
                gr.Image(rima["avatar"], label=rima["name"], width=150)
            with gr.Column():
                gr.Markdown(f"## {rima['name']}")
                gr.Markdown(f"*Твой виртуальный друг*  \n*Возраст: {rima['age']}*")
        
        # Чат
        chatbot = gr.Chatbot(height=400)
        msg = gr.Textbox(label="Напиши Риме...")
        voice_toggle = gr.Checkbox(label="Голос 🎙️", value=True)
        
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
    app = create_interface()
    app.launch(share=True)  # Добавлен share=True для временного публичного доступа
