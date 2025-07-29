import os
import json
from datetime import datetime

def save_to_file(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def load_from_file(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def clean_old_messages(messages, max_count=100):
    if len(messages) > max_count:
        return messages[-max_count:]
    return messages
