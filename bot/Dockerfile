FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем содержимое бота в /app/bot, чтобы python -m bot.main находил пакет
COPY . ./bot/

ENV PYTHONUNBUFFERED=1
ENV CORE_URL=http://core:8000

CMD ["python", "-m", "bot.main"]
