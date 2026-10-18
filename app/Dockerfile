# One image, two environments. The same container runs on your laptop in
# week 2 and on ECS Fargate from week 3 - nothing in here knows which.

FROM python:3.12-slim

# Do not run as root. The first thing a reviewer looks for.
RUN useradd --create-home --uid 10001 app

WORKDIR /app

# Dependencies first, so Docker can cache this layer and rebuilds are fast.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/
COPY static/ static/

# Where the SQLite file lives in week 2. Ignored once you move to Postgres.
RUN mkdir -p /data && chown app:app /data
VOLUME ["/data"]

USER app

ENV PORT=8080 \
    PYTHONUNBUFFERED=1
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status==200 else 1)"

# One process, eight threads. One process matters while the database is a
# SQLite file: several processes writing to one file fight over locks.
# In week 3, once you move to a real database, raising --workers is safe
# and is how you use more than one CPU core.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", \
     "--access-logfile", "-", "--error-logfile", "-", "app:app"]
