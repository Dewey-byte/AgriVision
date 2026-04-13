from datetime import datetime

def log(message):
    time = datetime.now().strftime("%H:%M:%S")
    return f"{time} - {message}"