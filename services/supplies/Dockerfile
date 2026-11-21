FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py database.py migrate.py repository.py rules.py service.py ./supplies_service/
COPY migrations/ ./supplies_service/migrations/

RUN useradd --system --no-create-home appuser

USER appuser

EXPOSE 8000

CMD ["python", "-m", "supplies_service.app"]
