FROM python:3.13-slim

# Don't write .pyc files; print logs straight away instead of buffering them.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Australia/Brisbane

WORKDIR /app

# pg_dump for "Back up now" in Settings. It must be the same major version as the database
# (PostgreSQL 17), which Debian doesn't ship, so it comes from PostgreSQL's own apt repository.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
 && . /etc/os-release \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $VERSION_CODENAME-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update && apt-get install -y --no-install-recommends postgresql-client-17 \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Install dependencies first: Docker caches this layer, so code edits don't reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

EXPOSE 8000
# uvicorn is the web server that runs the FastAPI app. 0.0.0.0 = accept connections from
# other containers (nginx), not just from inside this one.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
