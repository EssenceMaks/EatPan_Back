FROM python:3.12-slim

# Встановлюємо змінні середовища
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Копіюємо та встановлюємо залежності
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо проєкт
COPY . /app/

# Збираємо статику для Render (щоб адмінка працювала в хмарі без Nginx)
RUN python manage.py collectstatic --noinput

# За замовчуванням (для продакшену) команди запуску
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "eatpan_core.wsgi:application"]
