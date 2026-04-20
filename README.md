# EatPan Backend (EatPan_Back) ⚙️🥩

Серверна частина екосистеми **EatPan** — надійне та продуктивне REST API на базі **Django** та **Django REST Framework (DRF)**.
Відповідає за бізнес-логіку, зберігання даних, синхронізацію та інтеграцію із зовнішніми сервісами (Supabase, Cloudflare, NATS).

---

## 🏗 Архітектура та стек технологій

| Компонент | Технологія |
|---|---|
| **Фреймворк** | Django 5.x + Django REST Framework (DRF) |
| **База даних** | PostgreSQL (Supabase DB / PostgREST) — production; SQLite — локальна розробка |
| **Авторизація** | Supabase GoTrue (JWT). Валідація токенів через кастомний middleware (`authentication.py`) |
| **Сховище медіа** | Supabase Storage. Локально — через `MediaUploadView` → `kong:8000` |
| **Брокер подій** | NATS JetStream (патерн Outbox для event-driven синхронізації) |
| **Оточення** | Python 3.10+, Docker |

---

## 🗺 Основні модулі

Бекенд побудований за модульним принципом, розділеним на фази розробки:

| Фаза | Модуль | Файл | Опис |
|---|---|---|---|
| 1–2 | Рецепти та категорії | `views.py` | Повний CRUD для рецептів, книг та категорій |
| 3 | Профіль та акаунт | `views_profile.py` | Підписки, Tier-система, реферали |
| 4, 14 | Квести та завдання | `views_tasks.py`, `views_task_types.py` | Матриця Ейзенхауера, типи завдань, коментарі |
| 5 | Планувальник їжі | `views_meal_plan.py` | Розклад їжі, локації, прив'язка страв |
| 6 | Кладова | `views_pantry.py` | Інвентар продуктів із терміном придатності |
| 7 | Списки покупок | `views_shopping.py` | Шеринг списків, додавання товарів |
| 8–9 | Соціальна мережа | `views_social.py`, `views_messages.py` | Друзі, підписки, повідомлення, групові чати |
| 10 | Промокоди | `views_promo.py` | Випуск, використання та дарування промокодів |

---

## 📂 Структура проєкту

```text
EatPan_Back/
├── eatpan_core/            # Головний конфігураційний модуль Django
│   ├── settings.py         # Налаштування проєкту (DB, CORS, Auth)
│   ├── urls.py             # Кореневий маршрутизатор
│   ├── authentication.py   # Кастомний JWT middleware (Supabase GoTrue)
│   └── health.py           # Health-check ендпоінт (/api/health)
├── recipes/                # Основний додаток
│   ├── models.py           # ORM-моделі (Recipe, UserProfile, MediaAsset тощо)
│   ├── serializers.py      # DRF серіалізатори
│   ├── urls.py             # Маршрути API v1
│   ├── views*.py           # ViewSets та APIViews (розбиті по модулях)
│   ├── sync_outbox.py      # NATS Outbox — фіксація подій для синхронізації
│   ├── migrations/         # Міграції бази даних
│   ├── management/         # Django management commands (sync_publisher, sync_consumer)
│   └── tests/              # Unit-тести (models, views, serializers, sync)
├── Dockerfile              # Docker-образ для production
├── docker-compose.yml      # Локальний стек (Django + DB)
├── requirements.txt        # Залежності Python (production)
├── requirements-dev.txt    # Залежності для розробки (pytest, coverage)
├── pytest.ini              # Конфігурація тестів
├── .coveragerc             # Конфігурація покриття коду
├── .env                    # Змінні оточення (НЕ комітити!)
├── API_ENDPOINTS.md        # Повна документація API ендпоінтів
└── README.md               # Цей файл
```

---

## 🚀 Як запустити проєкт

### 1. Локальна розробка

```bash
# 1. Клонувати репозиторій та перейти до директорії
git clone <repo-url> && cd EatPan_Back

# 2. Створити та активувати віртуальне оточення
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Встановити залежності
pip install -r requirements.txt

# 4. Створити файл .env (скопіювати з прикладу та заповнити)
# Обов'язкові змінні: SECRET_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, JWT_SECRET

# 5. Застосувати міграції
python manage.py migrate

# 6. Запустити сервер на порту 6600
python manage.py runserver 6600
```

Після запуску DRF Browsable API доступний за адресою:
👉 [http://localhost:6600/api/v1/](http://localhost:6600/api/v1/)

### 2. Брокер повідомлень (NATS Sync)

Для тестування синхронізації між нодами:

```bash
# Переконайтесь, що NATS-сервер запущений у Docker (з EatPan_Supabase)
python manage.py sync_publisher   # Відправка подій
python manage.py sync_consumer    # Обробка подій
```

---

## 🧪 Тестування

```bash
# Активувати venv та встановити dev-залежності
pip install -r requirements-dev.txt

# Запустити всі тести
pytest

# Запустити з покриттям
pytest --cov=recipes --cov=eatpan_core --cov-report=html
# Результат: htmlcov/index.html
```

---

## 🔑 Змінні оточення (.env)

| Змінна | Опис |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` / `False` |
| `SUPABASE_URL` | URL до Supabase (Cloud або Self-Hosted) |
| `SUPABASE_SERVICE_KEY` | Service Role Key для серверного доступу |
| `JWT_SECRET` | Секрет для валідації JWT-токенів |
| `DATABASE_URL` | URL до PostgreSQL (production) |
| `NATS_URL` | URL до NATS JetStream (за замовчуванням `nats://localhost:4222`) |

---

## 🌐 Деплой та Failover-стратегія

Бекенд працює за принципом подвійної відмовостійкості, яка керується з боку фронтенду (`ApiClient.js`) та Cloudflare:

1. **Production Primary:** Cloudflare Worker Proxy → API (домашній сервер через тунель)
2. **Production Fallback:** Render (`https://eatpan-back.onrender.com/api/v1/`)

Health-check ендпоінт (`/api/health`) постійно перевіряється для визначення стану ноди. Якщо сервер повертає 500+ або не відповідає — трафік автоматично перемикається на Fallback.

---

## 📚 Документація API

Детальний перелік усіх ендпоінтів, їхніх методів та призначення → **[API_ENDPOINTS.md](./API_ENDPOINTS.md)**

---

*Гарного кодингу та смачних квестів!* 🛠️🥩
