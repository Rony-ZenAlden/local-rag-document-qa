FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc curl && rm -rf /var/lib/apt/lists/*

RUN pip config set global.timeout 1000
RUN pip config set global.retries 10
RUN pip config set install.extra-index-url "https://download.pytorch.org/whl/cpu"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir "torch>=2.0.0" --extra-index-url https://download.pytorch.org/whl/cpu

COPY . .
RUN mkdir -p /app/media /app/vector_db /app/staticfiles
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000
CMD ["waitress-serve", "--port=8000", "config.wsgi:application"]
