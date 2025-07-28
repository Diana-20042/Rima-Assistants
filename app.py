import os
from dotenv import load_dotenv
import openai
from elevenlabs import generate, play
import sqlite3
from datetime import datetime
import gradio as gr
from textblob import TextBlob
import random
from typing import List, Tuple

# --- Инициализация ---
load_dotenv()

# --- Конфигурация Римы ---
rima = {
    "name": "Рима",
    "voice": "Bella",
    "age": 25,
    "avatar": "avatar.jpg",
    "traits": ["эмпатичная", "аналитичная", "осторожная"],
    "memory": {
        "learned_phrases": {},
        "emotional_triggers": {}
    },
    "behavior": {
        "sarcasm_level": 0.3,
        "empathy_level": 0.9
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
            emotion TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_patterns (
            pattern TEXT PRIMARY KEY,
            response TEXT,
            usage_count INTEGER DEFAULT 1,
            usefulness REAL DEFAULT 1.0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Добавляем триггеры для эмоций
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emotional_triggers (
            emotion TEXT,
            trigger_text TEXT,
            response_template TEXT
        )
    """)
    
    # Стартовые триггеры
    cursor.execute("""
        INSERT OR IGNORE INTO emotional_triggers VALUES
        ('anger', 'бесит', 'Я вижу, что тебя это злит. Давай обсудим...'),
        ('sadness', 'грустно', 'Мне жаль, что тебе грустно. *обнимает*')
    """)
    
    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# --- Анализ эмоций ---
def analyze_emotion(text: str) -> dict:
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    
    emotions = {
        "anger": ["бесит", "злюсь", "ненавижу"],
        "joy": ["радость", "счастье", "люблю"],
        "sadness": ["грустно", "плакать", "тоска"]
    }
    
    detected = []
    for emotion, keywords in emotions.items():
        if any(word in text.lower() for word in keywords):
            detected.append(emotion)
    
    return {
        "polarity": round(polarity, 2),
        "emotions": detected or ["neutral"]
    }

# --- Поиск лучшего ответа из памяти ---
def get_cached_response(message: str) -> str:
    cursor.execute("""
        SELECT response FROM learned_patterns
        WHERE ? LIKE '%' || pattern || '%'
        ORDER BY usefulness DESC
        LIMIT 1
    """, (message,))
    return cursor.fetchone()[0] if cursor.fetchone() else None

# --- Генерация нового ответа ---
def generate_new_response(message: str, emotion: dict) -> str:
    try:
        # Ищем эмоциональный триггер
        cursor.execute("""
            SELECT response_template FROM emotional_triggers
            WHERE ? LIKE '%' || trigger_text || '%'
        """, (message,))
        template = cursor.fetchone()
        
        prompt = f"""
        Ты - {rima['name']} (возраст: {rima['age']}). Твои черты: {', '.join(rima['traits'])}.
        Эмоция собеседника: {emotion['emotions'][0]} (интенсивность: {emotion['polarity']}).
        {f"Используй шаблон: '{template[0]}'" if template else ""}
        
        Сообщение: {message}
        Твой ответ:"""
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7 + rima["behavior"]["sarcasm_level"] * 0.3,
            max_tokens=150
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        print(f"Ошибка генерации: {e}")
        return random.choice([
            "Я не совсем поняла...",
            "Давай поговорим о чём-то другом?",
            "*нервно молчит*"
        ])

# --- Оценка полезности ответа ---
def rate_response(user_msg: str, bot_msg: str) -> float:
    emotion = analyze_emotion(user_msg)
    bot_emotion = analyze_emotion(bot_msg)
    
    score = 0.5 + len(bot_msg) / 200  # Базовый счёт + длина
    
    # Эмоциональная согласованность
    if emotion["emotions"][0] == bot_emotion["emotions"][0]:
        score += 0.3
    
    # Избегаем негатива в ответ на радость
    if "joy" in emotion["emotions"] and bot_emotion["polarity"] < 0:
        score -= 0.4
        
    return max(0.1, min(score, 1.0))

# --- Обучение на взаимодействии ---
def learn_interaction(user_msg: str, bot_msg: str, score: float):
    try:
        # Запоминаем фразы
        keywords = [word for word in user_msg.split() if len(word) > 3][:2]
        if keywords:
            pattern = f"{'_'.join(keywords)}"
            cursor.execute("""
                INSERT INTO learned_patterns VALUES (?, ?, 1, ?)
                ON CONFLICT(pattern) DO UPDATE SET
                    usage_count = usage_count + 1,
                    usefulness = usefulness + ?
            """, (pattern, bot_msg, score, score))
        
        # Адаптируем поведение
        if score < 0.5:
            rima["behavior"]["sarcasm_level"] = max(0.1, rima["behavior"]["sarcasm_level"] - 0.1)
        elif score > 0.8:
            rima["behavior"]["empathy_level"] = min(1.0, rima["behavior"]["empathy_level"] + 0.1)
            
        conn.commit()
    except Exception as e:
        print(f"Ошибка обучения: {e}")

# --- Основная функция обработки ---
def respond(message: str, chat_history: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    try:
        # 1. Анализ эмоций
        emotion = analyze_emotion(message)
        
        # 2. Поиск в кэше
        bot_message = get_cached_response(message)
        
        # 3. Генерация нового ответа
        if not bot_message:
            bot_message = generate_new_response(message, emotion)
        
        # 4. Оценка и обучение
        score = rate_response(message, bot_message)
        learn_interaction(message, bot_message, score)
        
        # 5. Озвучка
        if ELEVENLABS_API:
            try:
                audio = generate(
                    text=bot_message,
                    voice=rima["voice"],
                    api_key=ELEVENLABS_API
                )
                play(audio)
            except Exception as e:
                print(f"Ошибка озвучки: {e}")
        
        chat_history.append((message, bot_message))
        return chat_history
    
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        chat_history.append((message, "Кажется, я сломалась..."))
        return chat_history

# --- Веб-интерфейс ---
def create_interface():
    with gr.Blocks(title="Рима AI", theme=gr.themes.Soft()) as app:
        gr.Markdown(f"## 🎭 {rima['name']} - твой цифровой друг")
        
        with gr.Row():
            chatbot = gr.Chatbot(height=400)
            with gr.Column():
                if os.path.exists(rima["avatar"]):
                    gr.Image(rima["avatar"], width=200)
                else:
                    gr.Markdown("*(Аватар не найден)*")
                
                gr.Markdown(f"""
                **Черты характера:**  
                {', '.join(rima['traits'])}  
                **Уровень сарказма:** {rima['behavior']['sarcasm_level']:.1f}/1.0
                """)
        
        msg = gr.Textbox(label="Напиши Риме...")
        msg.submit(respond, [msg, chatbot], [chatbot])
        
        with gr.Accordion("Настройки", open=False):
            gr.Markdown("### Параметры поведения")
            sarcasm = gr.Slider(0, 1, value=rima["behavior"]["sarcasm_level"], label="Сарказм")
            empathy = gr.Slider(0, 1, value=rima["behavior"]["empathy_level"], label="Эмпатия")
            
            def update_behavior(s, e):
                rima["behavior"]["sarcasm_level"] = s
                rima["behavior"]["empathy_level"] = e
                return "Настройки сохранены!"
            
            save = gr.Button("Сохранить")
            save.click(update_behavior, [sarcasm, empathy], gr.Markdown())
    
    return app

# --- Запуск ---
if __name__ == "__main__":
    app = create_interface()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_api=False
    )
