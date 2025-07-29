from transformers import AutoModelForCausalLM, AutoTokenizer
from pydantic import BaseModel
import sqlite3
import os
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
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
        self.model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")

    def generate_response(self, message):
        try:
            inputs = self.tokenizer.encode(message + self.tokenizer.eos_token, return_tensors="pt")
            outputs = self.model.generate(inputs, max_length=1000, pad_token_id=self.tokenizer.eos_token_id)
            reply = self.tokenizer.decode(outputs[:, inputs.shape[-1]:][0], skip_special_tokens=True)
            return reply
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return "Ой, что-то пошло не так..."

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
