FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py database.py migrate.py repository.py rules.py service.py ./chores_service/
COPY migrations/ ./chores_service/migrations/

RUN useradd --system --no-create-home appuser

USER appuser

EXPOSE 8000

CMD ["python", "-m", "chores_service.app"]
