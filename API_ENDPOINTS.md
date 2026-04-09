# Аналіз API Ендпоінтів проекту EatPan

Цей документ містить усі виявлені API ендпоінти, що використовуються в екосистемі EatPan, включаючи основний Django бекенд, Supabase сервіси та заплановані маршрути з боку клієнта.

## 1. Основний бекенд (Django)
**Домен в продакшені:** `https://api.eatpan.com` (Проксі через Cloudflare Worker з Failover на Render)
**Локальний домен:** `http://localhost:6600`
**Базовий шлях:** `/api/v1`

### 🩺 Health Checks
| Метод | Ендпоінт | Опис |
|-------|----------|------|
| `GET` | `/api/health` | Перевірка працездатності ноди та БД (використовується Worker-ом для забезпечення Failover стратегії) |

### 🍳 Рецепти (Recipes)
| Метод | Ендпоінт | Опис | Клієнтська реалізація (Фронт) |
|-------|----------|------|-------------------------------|
| `GET` | `/api/v1/recipes/` | Отримання списку рецептів (з параметрами фільтрації: `book`, `group`, `category`) | `RecipeService.fetchAll()` |
| `POST`| `/api/v1/recipes/` | Створення нового рецепту (передається JSON `data`) | `RecipeService.create()` |
| `GET` | `/api/v1/recipes/{id}/` | Отримання повної інформації про конкретний рецепт | `RecipeService.fetchDetail()` |
| `PUT` | `/api/v1/recipes/{id}/` | Оновлення існуючого рецепту | `RecipeService.update()` |
| `DELETE`| `/api/v1/recipes/{id}/` | Видалення рецепту з бази | `RecipeService.delete()` |
| `POST`| `/api/v1/recipes/{id}/toggle_like/` | Додавання або видалення рецепту з улюблених | `RecipeService.toggleLike()` |

### 📚 Книги рецептів (Recipe Books / Таксономія)
| Метод | Ендпоінт | Опис | Клієнтська реалізація (Фронт) |
|-------|----------|------|-------------------------------|
| `GET` | `/api/v1/recipe-books/` | Отримання всієї ієрархії (книги, групи та категорії) | `BookService.fetchAll()` |
| `POST`| `/api/v1/recipe-books/` | Створення нової книги рецептів | `BookService.create()` |
| `PATCH`| `/api/v1/recipe-books/{id}/`| Оновлення книги (зміна назви або JSON структури `data`) | `BookService.update()` |
| `DELETE`|`/api/v1/recipe-books/{id}/`| Видалення книги рецептів (виконується в Django API) | *Не реалізовано в `ApiClient.js`* |

### 👤 Заплановані Ендпоінти (з `EatPan_Fr_2` ApiClient)
*Ці ендпоінти передбачені у фронтенді (v2), але наразі не обробляються або частково обробляються в Django `views.py`.*
- `GET` `/api/v1/profile/me/` – `ProfileService.getMe`
- `PUT` `/api/v1/profile/me/` – `ProfileService.updateMe`
- `GET` `/api/v1/profile/me/stats/` – `ProfileService.getStats`
- `GET / POST` `/api/v1/tasks/` – `TaskService.fetchAll`, `create`
- `PUT / DELETE` `/api/v1/tasks/{uuid}/` – `TaskService.update`, `delete`
- `GET / PUT` `/api/v1/preferences/` – `PreferencesService.get`, `save`

---

## 2. Supabase Сервіси (BaaS)
**Cloud домен:** `https://pkdnyonrejptotlpzclq.supabase.co`

### 🔑 Авторизація (GoTrue / `HeaderAuthModule`)
| Метод | Ендпоінт | Опис |
|-------|----------|------|
| `POST`| `/auth/v1/signup` | Реєстрація нового користувача (email, password та metadata, напр. ім'я) |
| `POST`| `/auth/v1/token?grant_type=password` | Логін (отримання Access та Refresh JWT токенів) |
| `GET` | `/auth/v1/authorize` | OAuth 2.0 Авторизація (використовується для Google Sign-in через `signInWithOAuth`) |

### ⚡ Edge Functions (через Deno)
Шлях маршрутизується через Kong API Gateway за префіксом `/functions/v1/`.
| Метод | Ендпоінт | Опис |
|-------|----------|------|
| `БУДЬ-ЯКИЙ` | `/functions/v1/hello` | Тестова функція Deno |
| `БУДЬ-ЯКИЙ` | `/functions/v1/main` | Головний proxy/обробник (містить кастомну перевірку підпису JWT: підтримує як legacy симетричні HS256 токени, так і нові ES256/RS256 ключі з JWKS) |

### ⚙ Інші системні Supabase API (доступні через Kong)
- `/rest/v1/*` – PostgREST для прямого REST-доступу до таблиць БД.
- `/graphql/v1` – GraphQL API до бази.
- `/realtime/v1/*` – Сервіс WebSockets Supabase Realtime (підписка на зміни в базі).
- `/storage/v1/*` – API управління медіафайлами (bucket'ами) EatPan.

---

## 3. Внутрішня комунікація / Sync Broker
За забезпечення Event-Driven синхронізації та відмовостійкості на бекенді відповідає брокер повідомлень (Outbox Pattern).
- **NATS JetStream**: `nats://nats:4222` (Використовується скриптами `sync_publisher.py` та `sync_consumer.py`)
  - **Stream:** `eatpan_sync`
  - **Subject:** `eatpan.sync`
- Формат подій в Outbox включає тип сутності (`recipe`, `recipe_book`), `uuid`, операцію (`upsert`, `patch`, `delete`) та сам `payload`.
