FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# default command is overridden per-service in docker-compose.yml
CMD ["uvicorn", "app.retrieval_api:app", "--host", "0.0.0.0", "--port", "8000"]
