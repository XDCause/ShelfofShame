FROM python:3.13-slim

# Don't write .pyc files; print logs straight away instead of buffering them.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Australia/Brisbane

WORKDIR /app

# Install dependencies first: Docker caches this layer, so code edits don't reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

EXPOSE 8000
# uvicorn is the web server that runs the FastAPI app. 0.0.0.0 = accept connections from
# other containers (nginx), not just from inside this one.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
