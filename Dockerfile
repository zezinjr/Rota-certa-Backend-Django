# Imagem de produção do backend (ver deploy/README.md).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --create-home app && mkdir -p /app/staticfiles && chown -R app /app
USER app

EXPOSE 8000

# Migra, publica os estáticos para o Caddy e sobe o gunicorn.
# gthread porque os avisos do WhatsApp saem em threads depois do commit.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --worker-class gthread --workers 3 --threads 4 --timeout 60 --access-logfile -"]
