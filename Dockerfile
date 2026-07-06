FROM python:3.11-slim

WORKDIR /app

COPY requirements.in .
RUN pip install --no-cache-dir -r requirements.in

COPY . .

ENTRYPOINT ["python", "main.py"]
