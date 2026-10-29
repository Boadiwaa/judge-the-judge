# Judge the Judge: web app image. Serves precomputed results only; no model, no API key.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=8080 \
    HOST=0.0.0.0 \
    FLET_FORCE_WEB_SERVER=true \
    RATINGS_DB=/data/ratings.sqlite

WORKDIR /app
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

# Code, case files and precomputed results. Raw judge outputs and the LLM cache are not shipped.
COPY src/ src/
COPY data/cases/ data/cases/
COPY data/results/ data/results/

# The app runs as an unprivileged user. /data holds the ratings and usage databases; on fly.io it is a
# volume, mounted owned by root, so the container starts as root only to hand /data to the app user
# and then drops privileges before Python starts.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data src/jtj/app/assets \
    && chown -R app:app /data src/jtj/app/assets

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/', timeout=4).status == 200 else 1)"
CMD ["sh", "-c", "chown app:app /data && exec setpriv --reuid=app --regid=app --init-groups python -m jtj.app.main"]
