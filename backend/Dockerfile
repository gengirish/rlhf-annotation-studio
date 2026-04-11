FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY seed_task_packs.py ./
COPY seed_course_content.py ./
COPY tasks ./tasks

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

EXPOSE 8000

# Run migrations, seed task packs, seed course content, then start the API
CMD ["sh", "-c", "alembic upgrade head && python seed_task_packs.py && python seed_course_content.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
