FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
EXPOSE 8000

# Belangrijk: main:app (niet loesoe.main:app), want main.py staat op /app/main.py
CMD ["python","-m","uvicorn","main:app","--host","0.0.0.0","--port","8000","--proxy-headers","--forwarded-allow-ips","*"]
