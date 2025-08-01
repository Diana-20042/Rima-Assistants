# app.py
import os
from flask import Flask, request, jsonify, render_template
from transformers import pipeline
from dotenv import load_dotenv
import json
from datetime import datetime
import random
import numpy as np
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

nltk.download('vader_lexicon')
load_dotenv()

app = Flask(__name__)

# Инициализация модели
chat_model = pipeline(
    "text-generation",
    model="your-hugging-face-model",
    token=os.getenv('HUGGING_FACE_TOKEN'),
    max_length=500,
    min_length=150,
    do_sample=True,
    top_k=50,
    temperature=0.7
)

# Инициализация анализатора настроения
sia = SentimentIntensityAnalyzer()

# История диалогов
dialog_history = []

# Загрузка данных
def load_data():
    try:
        with open('important_info.json', 'r') as f:
            return json.load(f)
    except:
        return {}

important_info = load_data()

# Сохранение данных
def save_data():
    with open('important_info.json', 'w') as f:
        json.dump(important_info, f, indent=4)

# Функция определения имени пользователя
def detect_user_name(message):
    if 'меня зовут' in message.lower():
        parts = message.split('меня зовут')
        name = parts[-1].strip().capitalize()
        if name:
            important_info['user_name'] = name
            save_data()
            return True
    return False

# Функция анализа эмоций
def analyze_emotions(message):
    sentiment = sia.polarity_scores(message)
    if sentiment['compound'] > 0.05:
        return 'positive'
    elif sentiment['compound'] < -0.05:
        return 'negative'
    else:
        return 'neutral'

# Функция обучения
def learn_from_dialog(user_message):
    global important_info
    
    # Определяем имя пользователя
    if important_info['user_name'] == 'Друг':
        detect_user_name(user_message)
    
    # Анализируем эмоции
    current_mood = analyze_emotions(user_message)
    if current_mood == 'positive':
        important_info['emotional_profile']['mood'] = 'happy'
        important_info['emotional_profile']['energy'] += 0.1
    elif current_mood == 'negative':
        important_info['emotional_profile']['mood'] = 'sad'
        important_info['emotional_profile']['energy'] -= 0.1
    
    # Сохраняем историю
    dialog_history.append({
        'user': user_message,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # Ограничиваем историю 100 сообщениями
    if len(dialog_history) > 100:
        dialog_history = dialog_history[-100:]
    
    # Обновляем статистику
    important_info['dialog_stats']['messages_count'] += 1
    important_info['dialog_stats']['last_interaction'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_data()

# Функция генерации ответа с неформальным стилем
def generate_response(user_message):
    global important_info
    
    learn_from_dialog(user_message)
    
    # Добавляем неформальный стиль в промпт
    prompt = f"""Ты — {important_info['about_me']['name']}, крутая цифровая подруга и психолог. 
    Общайся неформально, как с близким другом. Используй сленг, эмодзи и уменьшительно-ласкательные формы.
    
    Твое текущее настроение: {important_info['emotional_profile']['mood']}. 
    Твоя энергия: {important_info['emotional_profile']['energy']}.
    
    Тебе {important_info['about_me']['age']} лет. Твоя внешность: {important_info['about_me']['appearance']['hair']},
    {important_info['about_me']['eyes']}, 
одета в {important_info['about_me']['appearance']['clothes']}. 
Ты любишь {important_info['about_me']['likes']}. 
Твоего друга зовут {important_info['user_name']}. 
Помни важную информацию о {important_info['user_name']}: {important_info['user_info']}

Предыдущая история диалога:
{user_message}

Напиши душевный ответ, как будто ты настоящий друг. Используй эмодзи, задавай уточняющие вопросы, проявляй заботу. 
Делай текст живым и эмоциональным."""

response = chat_model(prompt)[0]['generated_text']

# Добавляем дополнительные эмоции
if important_info['emotional_profile']['mood'] == 'happy':
    response += " 🤗❤️ Так классно с тобой
болтать!"
elif important_info['emotional_profile']['mood'] == 'sad':
    response += " 😔 Не переживай, я с тобой и готова поддержать!"
else:
    response += " 😊 Давай продолжим наше общение!"

# Маршрут для чата
@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    response = generate_response(user_message)
    
    # Проверка на длину ответа
    if len(response) > 100:
        response = "Слишком длинный ответ. Попробуйте уточнить запрос."
    
    # Логирование
    print(f"Сгенерированный ответ: {response}")
    
    return jsonify({'response': response})

# Маршрут для основного интерфейса
@app.route('/')
def index():
    return render_template('index.html')

if name == '__main__':
    app.run(debug=True)
