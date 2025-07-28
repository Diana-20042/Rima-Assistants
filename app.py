import os
import sqlite3
from datetime import datetime
import gradio as gr
import random
import logging

# --- Настройка логов ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Rima")

# --- Конфигурация ---
class RimaConfig:
    def __init__(self):
        self.name = "Рима"
        self.age = 25
        self.avatar = "avatar.jpg"
        self.traits = ["дружелюбная", "эмпатичная"]
        self.behavior = {
            "sarcasm": 0.3,
            "empathy": 0.9
        }
        
    def update_behavior(self, sarcasm=None, empathy=None):
        if sarcasm is not None:
            self.behavior["sarcasm"] = max(0, min(1, sarcasm))
        if empathy is not None:
            self.behavior["empathy"] = max(0, min(1, empathy))

rima = RimaConfig()

# --- Упрощенная БД ---
class Database:
    def __init__(self, db_path="rima.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()
        
    def _init_db(self):
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY,
                    input_text TEXT,
                    response_text TEXT,
                    timestamp DATETIME
                )
            """)
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")

    def add_interaction(self, user_msg, bot_msg):
        try:
            self.conn.execute(
                "INSERT INTO memory (input_text, response_text, timestamp) VALUES (?, ?, ?)",
                (user_msg, bot_msg, datetime.now())
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка записи в БД: {e}")

db = Database()

# --- Генератор ответов ---
class ResponseGenerator:
    RESPONSE_TEMPLATES = {
        "anger": [
            "Похоже, ты расстроен. Давай обсудим это...",
            "Я чувствую, что тебя что-то задело. Хочешь поговорить?"
        ],
        "joy": [
            "Здорово, что ты в хорошем настроении! 😊",
            "Рада видеть твою улыбку!"
        ],
        "default": [
            "Интересно... Расскажи подробнее.",
            "Я тебя слушаю. Продолжай.",
            "Как я могу помочь?"
        ]
    }

    def generate_response(self, message):
        try:
            # Простейший анализ сообщения
            emotion = self._detect_emotion(message)
            
            # Выбор ответа по шаблону
            if emotion in self.RESPONSE_TEMPLATES:
                response = random.choice(self.RESPONSE_TEMPLATES[emotion])
            else:
                response = random.choice(self.RESPONSE_TEMPLATES["default"])
                
            # Добавляем персональный оттенок
            if rima.behavior["sarcasm"] > 0.5:
                response += " " + random.choice([
                    "(Шучу... или нет?)",
                    "*саркастично улыбается*"
                ])
                
            return response
            
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return "Ой, что-то пошло не так..."

    def _detect_emotion(self, text):
        text = text.lower()
        if any(word in text for word in ["злюсь", "бесит", "раздражает"]):
            return "anger"
        elif any(word in text for word in ["рад", "счастье", "ура"]):
            return "joy"
        return "default"

generator = ResponseGenerator()

# --- Интерфейс ---
def create_interface():
    with gr.Blocks(title="Рима", theme=gr.themes.Soft()) as app:
        # Шапка
        gr.Markdown(f"## 🤖 {rima.name} - виртуальный собеседник")
        
        # Чат
        chatbot = gr.Chatbot(height=350)
        msg = gr.Textbox(label="Ваше сообщение", placeholder="Напишите что-нибудь...")
        
        # Настройки
        with gr.Accordion("Настройки персонажа", open=False):
            sarcasm = gr.Slider(0, 1, value=rima.behavior["sarcasm"], label="Уровень сарказма")
            empathy = gr.Slider(0, 1, value=rima.behavior["empathy"], label="Уровень эмпатии")
            save_btn = gr.Button("Применить")
            
            def update_settings(s, e):
                rima.update_behavior(sarcasm=s, empathy=e)
                return "Настройки сохранены!"
            
            save_btn.click(update_settings, [sarcasm, empathy], gr.Markdown())
        
        # Логика чата
        def respond(message, chat_history):
            try:
                bot_message = generator.generate_response(message)
                db.add_interaction(message, bot_message)
                chat_history.append((message, bot_message))
                return chat_history
            except Exception as e:
                logger.error(f"Ошибка в respond: {e}")
                return chat_history + [(message, "Произошла ошибка 😔")]
        
        msg.submit(respond, [msg, chatbot], [chatbot])
    
    return app

# --- Запуск ---
if __name__ == "__main__":
    app = create_interface()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True
    )
