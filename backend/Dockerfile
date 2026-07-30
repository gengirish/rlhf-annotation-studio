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

# Migrations & task seeds are required; course content seed is optional (may not have content dir)
# --proxy-headers makes uvicorn trust X-Forwarded-* from Fly's edge proxy, so
# request.client.host and the scheme reflect the real caller. Fly's proxy is the
# only ingress, so allowing all forwarded hosts is safe here.
CMD ["sh", "-c", "alembic upgrade head && python seed_task_packs.py && (python seed_course_content.py || true) && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
