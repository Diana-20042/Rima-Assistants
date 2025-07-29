import os
from flask import Flask, render_template, request, jsonify
from transformers import pipeline
import pyttsx3
from dotenv import load_dotenv
from utils import save_to_file, load_from_file
import speech_recognition as sr

load_dotenv()

app = Flask(__name__)

# Инициализация моделей
chat_model = pipeline(
    "text-generation", 
    model="your-hugging-face-model",
    token=os.getenv('HUGGING_FACE_TOKEN')
)

# Настройка голоса
engine = pyttsx3.init()

# Загрузка важной информации
important_info = load_from_file('important_info.json')

# Функция генерации ответа
def generate_response(user_message):
    global important_info
    
    # Обработка важной информации
    if 'работаю' in user_message.lower():
        important_info['work'] = user_message
        save_to_file(important_info, 'important_info.json')
    elif 'встречаюсь' in user_message.lower():
        important_info['relationship'] = user_message
        save_to_file(important_info, 'important_info.json')
    
    # Формирование промпта
    prompt = f"""Ты — {important_info['about_me']['name']}, цифровая подруга и психолог. 
    Тебе {important_info['about_me']['age']} лет. Твоя внешность: {important_info['about_me']['appearance']['hair']}, 
    {important_info['about_me']['appearance']['eyes']}, одета в {important_info['about_me']['appearance']['clothes']}. 
    Ты любишь {important_info['about_me']['likes']}. Твоего друга зовут {important_info['user_name']}. 
    Помни важную информацию о {important_info['user_name']}: {important_info['user_info']}
    
    Предыдущая история диалога:
    {user_message}
    """
    
    response = chat_model(prompt)[0]['generated_text']
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.form['message']
    response = generate_response(user_message)
    return jsonify({'response': response})

@app.route('/voice', methods=['POST'])
def voice():
    # Обработка голосового сообщения
    return jsonify({'response': 'Обработка голоса...'})

if __name__ == '__main__':
    app.run(debug=True)
