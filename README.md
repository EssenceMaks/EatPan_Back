# EatPan Backend (EatPan_Back) ⚙️🥩

Добро пожаловать в репозиторий серверной части экосистемы **EatPan**. 
EatPan Backend — это надежное и производительное API на базе **Django** и **Django REST Framework (DRF)**. Он отвечает за бизнес-логику, хранение данных, синхронизацию и интеграцию с внешними сервисами (Supabase, Cloudflare, NATS).

---

## 🏗 Архитектура и Стек технологий

- **Фреймворк:** Django 5.x + Django REST Framework (DRF)
- **База данных:** PostgreSQL (через интеграцию с Supabase DB / PostgREST) / SQLite для локальной разработки.
- **Авторизация (Auth):** Supabase GoTrue (JWT-токены). Вся валидация JWT (в том числе кастомные HS256/RS256 токены) происходит на стороне API Gateway (Kong) или кастомного middleware.
- **Хранилище медиа (Storage):** Supabase Storage / Local Storage (для локальной разработки медиа загружается через `MediaUploadView` и маршрутизируется в `kong:8000`).
- **Брокер сообщений (Event Sync Broker):** NATS JetStream (паттерн Outbox для event-driven синхронизации данных). Скрипты `sync_publisher.py` и `sync_consumer.py`.
- **Окружение:** Python 3.10+, Docker.

---

## 🗺 Основные модули (Phases)

Бэкенд спроектирован по модульному принципу (разбит на Фазы):

1. **Рецепты и Категории (Phase 1-2):** `recipes/views.py`. Полный CRUD для управления рецептами, книгами и категориями.
2. **Профиль и Аккаунт (Phase 3):** `recipes/views_profile.py`. Управление подписками, Tier'ами, реферальной системой.
3. **Квесты и Задачи (Phase 4, 14):** `recipes/views_tasks.py`, `recipes/views_task_types.py`. Матрица задач, типы, комментарии к квестам.
4. **Планировщик (Phase 5):** `recipes/views_meal_plan.py`. Расписание еды, локации и привязка блюд.
5. **Кладовая (Phase 6):** `recipes/views_pantry.py`. Инвентарь продуктов со сроком годности.
6. **Списки покупок (Phase 7):** `recipes/views_shopping.py`. Шаринг списков, добавление товаров.
7. **Социальная сеть (Phase 8, 9):** `recipes/views_social.py`, `recipes/views_messages.py`. Друзья, подписки, личные сообщения и групповые чаты.
8. **Промокоды (Phase 10):** `recipes/views_promo.py`. Выпуск, погашение и дарение промокодов.

---

## 📂 Структура проекта

```text
EatPan_Back/
├── eatpan_core/        # Главный конфигурационный модуль Django (settings.py, urls.py)
├── recipes/            # Основное приложение (Models, Views, Serializers, URLs)
├── sync_publisher.py   # NATS Publisher (Outbox pattern)
├── sync_consumer.py    # NATS Consumer (Обработка фоновых событий)
├── manage.py           # CLI-утилита Django
├── requirements.txt    # Зависимости Python
├── API_ENDPOINTS.md    # Полная документация по всем доступным API-эндпоинтам
├── README.md           # Этот файл
└── .gitignore          # Игнор-лист Git
```

---

## 🚀 Как запустить проект (How to run)

### 1. Локальная разработка (Local Server)

Для локального тестирования необходимо активировать виртуальное окружение и запустить сервер разработки на порту `6600` (фронтенд ожидает API именно на этом порту).

```bash
# 1. Активация виртуального окружения (Windows)
.venv\Scripts\activate
# Для Mac/Linux: source .venv/bin/activate

# 2. Установка зависимостей (если еще не установлены)
pip install -r requirements.txt

# 3. Применение миграций БД
python manage.py migrate

# 4. Запуск сервера на нужном порту
python manage.py runserver 6600
```

После запуска локального сервера, DRF Browsable API (главная страница со всеми роутами) будет доступна по адресу:
👉 [http://localhost:6600/api/v1/](http://localhost:6600/api/v1/)

### 2. Запуск брокера сообщений (NATS Sync)

Если вы тестируете функционал синхронизации:
1. Убедитесь, что у вас запущен Docker (NATS-сервер должен быть поднят в контейнере из репозитория `EatPan_Supabase`).
2. Запустите Publisher и Consumer в отдельных окнах терминала:
   ```bash
   python sync_publisher.py
   python sync_consumer.py
   ```

---

## 🌐 Деплой и Failover Стратегия

Бэкенд имеет двойную линию отказоустойчивости (Failover), которая управляется со стороны фронтенда (`ApiClient.js`) и Cloudflare:

1. **Production Primary:** Cloudflare Worker Proxy -> API (Основной сервер)
2. **Production Fallback:** Render (`https://eatpan-back.onrender.com/api/v1/`)

Health Check эндпоинт (`/api/health`) постоянно пингуется воркерами для определения состояния ноды. Если сервер возвращает ошибку 500+ или не отвечает, трафик автоматически переключается на Fallback-сервер.

---

## 📚 Документация API

Дотошный и детальный список всех существующих эндпоинтов, их методов и предназначения находится в файле **[API_ENDPOINTS.md](./API_ENDPOINTS.md)**. 
Там же описана интеграция с Supabase Edge Functions.

---
*Stay organized, keep coding!* 🛠️🥩
