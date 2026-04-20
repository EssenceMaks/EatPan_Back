# EatPan Backend (EatPan_Back) ⚙️🥩

Ласкаво просимо до репозиторію серверної частини екосистеми **EatPan**. 
EatPan Backend — це надійне та продуктивне API на базі **Django** та **Django REST Framework (DRF)**. Воно відповідає за бізнес-логіку, зберігання даних, синхронізацію та інтеграцію із зовнішніми сервісами (Supabase, Cloudflare, NATS).

---

## 🏗 Архітектура та Стек технологій

- **Фреймворк:** Django 5.x + Django REST Framework (DRF)
- **База даних:** PostgreSQL (через інтеграцію з Supabase DB / PostgREST) / SQLite для локальної розробки.
- **Авторизація (Auth):** Supabase GoTrue (JWT-токени). Уся валідація JWT (зокрема кастомні HS256/RS256 токени) відбувається на боці API Gateway (Kong) або кастомного middleware.
- **Сховище медіа (Storage):** Supabase Storage / Local Storage (для локальної розробки медіа завантажується через `MediaUploadView` і маршрутизується в `kong:8000`).
- **Брокер повідомлень (Event Sync Broker):** NATS JetStream (патерн Outbox для event-driven синхронізації даних). Скрипти `sync_publisher.py` та `sync_consumer.py`.
- **Оточення:** Python 3.10+, Docker.

---

## 🗺 Основні модули (Phases)

Бекенд спроєктований за модульним принципом (розбитий на Фази):

1. **Рецепти та Категорії (Phase 1-2):** `recipes/views.py`. Повний CRUD для керування рецептами, книгами та категоріями.
2. **Профіль та Акаунт (Phase 3):** `recipes/views_profile.py`. Керування підписками, Tier'ами, реферальною системою.
3. **Квести та Завдання (Phase 4, 14):** `recipes/views_tasks.py`, `recipes/views_task_types.py`. Матриця завдань, типи, коментарі до квестів.
4. **Планувальник (Phase 5):** `recipes/views_meal_plan.py`. Розклад їжі, локації та прив'язка страв.
5. **Кладова (Phase 6):** `recipes/views_pantry.py`. Інвентар продуктів із терміном придатності.
6. **Списки покупок (Phase 7):** `recipes/views_shopping.py`. Шеринг списків, додавання товарів.
7. **Соціальна мережа (Phase 8, 9):** `recipes/views_social.py`, `recipes/views_messages.py`. Друзі, підписки, особисті повідомлення та групові чати.
8. **Промокоды (Phase 10):** `recipes/views_promo.py`. Випуск, використання та дарування промокодів.

---

## 📂 Структура проєкту

```text
EatPan_Back/
├── eatpan_core/        # Головний конфігураційний модуль Django (settings.py, urls.py)
├── recipes/            # Основний додаток (Models, Views, Serializers, URLs)
├── sync_publisher.py   # NATS Publisher (Outbox pattern)
├── sync_consumer.py    # NATS Consumer (Обробка фонових подій)
├── manage.py           # CLI-утиліта Django
├── requirements.txt    # Залежності Python
├── API_ENDPOINTS.md    # Повна документація щодо всіх доступних API-ендпоінтів
├── README.md           # Цей файл
└── .gitignore          # Ігнор-лист Git
```

---

## 🚀 Як запустити проєкт (How to run)

### 1. Локальна розробка (Local Server)

Для локального тестування необхідно активувати віртуальне оточення та запустити сервер розробки на порту `6600` (фронтенд очікує API саме на цьому порту).

```bash
# 1. Активація віртуального оточення (Windows)
.venv\Scripts\activate
# Для Mac/Linux: source .venv/bin/activate

# 2. Встановлення залежностей (якщо ще не встановлені)
pip install -r requirements.txt

# 3. Застосування міграцій БД
python manage.py migrate

# 4. Запуск сервера на потрібному порту
python manage.py runserver 6600
```

Після запуску локального сервера, DRF Browsable API (головна сторінка з усіма роутами) буде доступна за адресою:
👉 [http://localhost:6600/api/v1/](http://localhost:6600/api/v1/)

### 2. Запуск брокера повідомлень (NATS Sync)

Якщо ви тестуєте функціонал синхронізації:
1. Переконайтеся, що у вас запущений Docker (NATS-сервер має бути піднятий у контейнері з репозиторію `EatPan_Supabase`).
2. Запустіть Publisher і Consumer в окремих вікнах термінала:
   ```bash
   python sync_publisher.py
   python sync_consumer.py
   ```

---

## 🌐 Деплой та Failover Стратегия

Бекенд має подвійну лінію відмовостійкості (Failover), яка керується з боку фронтенду (`ApiClient.js`) та Cloudflare:

1. **Production Primary:** Cloudflare Worker Proxy -> API (Основний сервер)
2. **Production Fallback:** Render (`https://eatpan-back.onrender.com/api/v1/`)

Health Check ендпоінт (`/api/health`) постійно пінгується воркерами для визначення стану ноди. Якщо сервер повертає помилку 500+ або не відповідає, трафік автоматично перемикається на Fallback-сервер.

---

## 📚 Документація API

Дотошний і детальний список усіх існуючих ендпоінтів, їх методів та призначення знаходиться у файлі **[API_ENDPOINTS.md](./API_ENDPOINTS.md)**. 
Там же описана інтеграція з Supabase Edge Functions.

---
*Stay organized, keep coding!* 🛠️🥩
