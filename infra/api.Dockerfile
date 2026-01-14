FROM python:3.13-slim
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

# requirements t.o.v. repo-root
COPY infra/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# app-code
COPY infra/loesoe /app/loesoe

ENV UPLOADS_DIR=/app/uploads
EXPOSE 8000
CMD ["uvicorn", "loesoe.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
