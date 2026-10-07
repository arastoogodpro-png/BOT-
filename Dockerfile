FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV BOT_DATA_DIR=/app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
RUN mkdir -p /app/data

CMD ["python", "main.py"]
