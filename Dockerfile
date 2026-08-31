# Amnesia runs on Python 3.11: the ADK and google-genai stacks assume 3.10+,
# and slim keeps the image small enough that Cloud Run cold starts stay fast.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so a code change does not reinstall the world.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY amnesia ./amnesia

# Cloud Run injects PORT and it is not always 8080. Honouring it is what makes
# the difference between a healthy revision and one that never passes checks.
ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn amnesia.web.app:app --host 0.0.0.0 --port ${PORT}
