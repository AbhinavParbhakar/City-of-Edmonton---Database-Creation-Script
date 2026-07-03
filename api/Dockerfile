FROM python:3.11-slim

WORKDIR /app

COPY requirements.in .
RUN pip install --no-cache-dir -r requirements.in

COPY main.py .

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
