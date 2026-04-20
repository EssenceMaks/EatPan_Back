# Аналіз API Ендпоінтів проекту EatPan

Цей документ містить усі виявлені API ендпоінти, що використовуються в екосистемі EatPan, включаючи основний Django бекенд, Supabase сервіси та синхронізацію.

## 1. Основний бекенд (Django)
**Домен в продакшені:** `https://api.eatpan.com` (Проксі через Cloudflare Worker з Failover на Render)
**Локальний домен:** `http://localhost:6600`
**Базовий шлях:** `/api/v1`

### 🩺 Health Checks
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `GET` | `/api/health` | Перевірка працездатності ноди та БД | `HealthService.check()` |

### 🍳 Рецепти (Recipes)
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `GET` | `/api/v1/recipes/` | Отримання списку рецептів | `RecipeService.fetchAll()`, `fetchPage()` |
| `POST`| `/api/v1/recipes/` | Створення нового рецепту | `RecipeService.create()` |
| `GET` | `/api/v1/recipes/{id}/` | Деталі рецепту | `RecipeService.fetchDetail()` |
| `PUT` | `/api/v1/recipes/{id}/` | Оновлення рецепту | `RecipeService.update()` |
| `DELETE`| `/api/v1/recipes/{id}/` | Видалення рецепту | `RecipeService.delete()` |
| `POST`| `/api/v1/recipes/{id}/toggle_like/`| Додавання/видалення з улюблених | `RecipeService.toggleLike()` |
| `GET` | `/api/v1/recipes/ingredients/` | Список інгредієнтів для автодоповнення | `RecipeService.fetchIngredients()` |

### 📚 Книги рецептів та Категорії (Recipe Books & Categories)
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `GET` | `/api/v1/recipe-books/` | Список книг | `BookService.fetchAll()` |
| `POST`| `/api/v1/recipe-books/` | Створення книги | `BookService.create()` |
| `PATCH`|`/api/v1/recipe-books/{id}/`| Оновлення книги | `BookService.update()` |
| `GET` | `/api/v1/categories/` | Список категорій | `CategoryService.fetchAll()` |
| `POST`| `/api/v1/categories/` | Створення категорії | `CategoryService.create()` |
| `PUT` | `/api/v1/categories/{id}/` | Оновлення категорії | `CategoryService.update()` |
| `DELETE`|`/api/v1/categories/{id}/`| Видалення категорії | `CategoryService.delete()` |

### 👤 Профіль та Акаунт (Profile & Account) - Phase 3
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `GET` | `/api/v1/profile/me/` | Мій профіль | `ProfileService.getMe()` |
| `PATCH`| `/api/v1/profile/me/` | Оновлення профілю | `ProfileService.updateMe()` |
| `GET` | `/api/v1/profile/{uuid}/public/` | Публічний профіль | `ProfileService.getPublic()` |
| `PATCH`| `/api/v1/account/tier/` | Оновлення тарифу | `AccountService.updateTier()` |
| `POST`| `/api/v1/account/referral/create/`| Створення реферального коду | `AccountService.createReferral()` |
| `POST`| `/api/v1/account/referral/activate/`| Активація реферального коду | `AccountService.activateReferral()` |

### 📝 Завдання (Tasks) - Phase 4 & 14
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `GET` | `/api/v1/tasks/` | Список завдань | `TaskService.fetchAll()` |
| `POST`| `/api/v1/tasks/` | Створення завдання | `TaskService.create()` |
| `GET` | `/api/v1/tasks/{uuid}/` | Отримання завдання | `TaskService.get()` |
| `PATCH`|`/api/v1/tasks/{uuid}/` | Оновлення завдання | `TaskService.update()` |
| `DELETE`|`/api/v1/tasks/{uuid}/`| Видалення завдання | `TaskService.delete()` |
| `POST`| `/api/v1/tasks/{uuid}/comments/`| Додати коментар | `TaskService.addComment()` |
| `PATCH`|`/api/v1/tasks/{uuid}/comments/{cid}/`| Оновити коментар | `TaskService.editComment()` |
| `DELETE`|`/api/v1/tasks/{uuid}/comments/{cid}/`| Видалити коментар | `TaskService.deleteComment()` |
| `GET` | `/api/v1/task-groups/` | Групи завдань | `TaskService.fetchGroups()` |
| `POST`| `/api/v1/task-groups/` | Створити групу | `TaskService.createGroup()` |
| `PATCH`|`/api/v1/task-groups/{uuid}/`| Оновити групу | `TaskService.updateGroup()` |
| `DELETE`|`/api/v1/task-groups/{uuid}/`| Видалити групу | `TaskService.deleteGroup()` |
| `POST`| `/api/v1/task-groups/{uuid}/share/`| Поділитися групою | `TaskService.shareGroup()` |
| `GET` | `/api/v1/task-types/` | Типи завдань | `TaskTypeService.fetchAll()` |
| `POST`| `/api/v1/task-types/` | Створити тип | `TaskTypeService.create()` |
| `PATCH`|`/api/v1/task-types/{uuid}/`| Оновити тип | `TaskTypeService.update()` |
| `DELETE`|`/api/v1/task-types/{uuid}/`| Видалити тип | `TaskTypeService.delete()` |
| `POST`| `/api/v1/task-types/{uuid}/subtypes/`| Створити підтип | `TaskTypeService.createSubtype()` |
| `PATCH`|`/api/v1/task-subtypes/{uuid}/`| Оновити підтип | `TaskTypeService.updateSubtype()` |
| `DELETE`|`/api/v1/task-subtypes/{uuid}/`| Видалити підтип | `TaskTypeService.deleteSubtype()` |

### 📅 Планувальник страв (Meal Plan) - Phase 5
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `GET` | `/api/v1/meal-plan/` | Список планів | `MealPlanService.fetchAll()` |
| `POST`| `/api/v1/meal-plan/` | Створити запис | `MealPlanService.create()` |
| `GET` | `/api/v1/meal-plan/{uuid}/` | Отримати запис | `MealPlanService.get()` |
| `PATCH`|`/api/v1/meal-plan/{uuid}/`| Оновити запис | `MealPlanService.update()` |
| `DELETE`|`/api/v1/meal-plan/{uuid}/`| Видалити запис | `MealPlanService.delete()` |
| `POST`| `/api/v1/meal-plan/{uuid}/bind-recipe/`| Прив'язати рецепт | `MealPlanService.bindRecipe()` |
| `DELETE`|`/api/v1/meal-plan/{uuid}/unbind-recipe/{r_uuid}/`| Відв'язати рецепт | `MealPlanService.unbindRecipe()` |
| `GET` | `/api/v1/meal-plan/labels/` | Мітки (чіпси) страв | `MealPlanService.fetchLabels()` |
| `POST`| `/api/v1/meal-plan/labels/` | Створити мітку | `MealPlanService.createLabel()` |
| `PATCH`|`/api/v1/meal-plan/labels/{uuid}/`| Оновити мітку | `MealPlanService.updateLabel()` |
| `DELETE`|`/api/v1/meal-plan/labels/{uuid}/`| Видалити мітку | `MealPlanService.deleteLabel()` |
| `GET` | `/api/v1/meal-plan/locations/` | Локації планів | `MealPlanService.locations.fetchAll()` |
| `POST`| `/api/v1/meal-plan/locations/` | Створити локацію | `MealPlanService.locations.create()` |
| `PATCH`|`/api/v1/meal-plan/locations/{uuid}/`| Оновити локацію | `MealPlanService.locations.update()` |
| `DELETE`|`/api/v1/meal-plan/locations/{uuid}/`| Видалити локацію | `MealPlanService.locations.delete()` |

### 📦 Кладова (Pantry) - Phase 6
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `GET` | `/api/v1/pantry/` | Усі інгредієнти кладової | `PantryService.fetchAll()` |
| `POST`| `/api/v1/pantry/items/` | Додати продукт | `PantryService.addItem()` |
| `PATCH`|`/api/v1/pantry/items/{uuid}/` | Оновити продукт | `PantryService.updateItem()` |
| `DELETE`|`/api/v1/pantry/items/{uuid}/`| Видалити продукт | `PantryService.deleteItem()` |
| `GET` | `/api/v1/pantry/locations/` | Локації кладової | `PantryService.fetchLocations()` |
| `POST`| `/api/v1/pantry/locations/` | Створити локацію | `PantryService.addLocation()` |
| `PATCH`|`/api/v1/pantry/locations/{uuid}/`| Оновити локацію | `PantryService.updateLocation()` |
| `DELETE`|`/api/v1/pantry/locations/{uuid}/`| Видалити локацію | `PantryService.deleteLocation()` |
| `GET` | `/api/v1/pantry/expiration-report/`| Звіт про терміни придатності | `PantryService.expirationReport()` |

### 🛒 Списки покупок (Shopping) - Phase 7
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `GET` | `/api/v1/shopping/` | Усі списки | `ShoppingService.fetchAll()` |
| `GET` | `/api/v1/shopping/lists/{uuid}/` | Деталі списку | `ShoppingService.fetchList()` |
| `POST`| `/api/v1/shopping/lists/` | Створити список | `ShoppingService.createList()` |
| `PATCH`|`/api/v1/shopping/lists/{uuid}/`| Оновити список | `ShoppingService.updateList()` |
| `DELETE`|`/api/v1/shopping/lists/{uuid}/`| Видалити список | `ShoppingService.deleteList()` |
| `POST`| `/api/v1/shopping/lists/{uuid}/share/`| Поділитися списком | `ShoppingService.shareList()` |
| `POST`| `/api/v1/shopping/lists/{uuid}/items/`| Додати товар | `ShoppingService.addItem()` |
| `PATCH`|`/api/v1/shopping/lists/{uuid}/items/{i_uuid}/`| Оновити товар | `ShoppingService.updateItem()` |
| `DELETE`|`/api/v1/shopping/lists/{uuid}/items/{i_uuid}/`| Видалити товар | `ShoppingService.deleteItem()` |

### 👥 Соціальні функції (Social) - Phase 8
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `POST`| `/api/v1/social/follow/{uuid}/` | Підписатися | `SocialService.follow()` |
| `DELETE`|`/api/v1/social/follow/{uuid}/`| Відписатися | `SocialService.unfollow()` |
| `POST`| `/api/v1/social/friends/{uuid}/`| Додати друга | `SocialService.addFriend()` |
| `PATCH`|`/api/v1/social/friends/{uuid}/`| Оновити дані друга | `SocialService.updateFriend()` |
| `DELETE`|`/api/v1/social/friends/{uuid}/`| Видалити друга | `SocialService.removeFriend()` |
| `GET` | `/api/v1/social/friend-groups/` | Групи друзів | `SocialService.fetchGroups()` |
| `POST`| `/api/v1/social/friend-groups/` | Створити групу | `SocialService.createGroup()` |
| `PATCH`|`/api/v1/social/friend-groups/{uuid}/`| Оновити групу | `SocialService.updateGroup()` |
| `DELETE`|`/api/v1/social/friend-groups/{uuid}/`| Видалити групу | `SocialService.deleteGroup()` |
| `GET` | `/api/v1/social/followers/` | Підписники | `SocialService.fetchFollowers()` |
| `GET` | `/api/v1/social/following/` | Підписки | `SocialService.fetchFollowing()` |
| `GET` | `/api/v1/social/all-users/` | Усі користувачі | `SocialService.fetchAllUsers()` |

### 💬 Повідомлення (Messages) - Phase 9
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `GET` | `/api/v1/messages/` | Список діалогів | `MessageService.fetchConversations()` |
| `GET` | `/api/v1/messages/{id}/` | Чат | `MessageService.getConversation()` |
| `POST`| `/api/v1/messages/{uuid}/send/` | Надіслати особисте повідомлення | `MessageService.sendDM()` |
| `PATCH`|`/api/v1/messages/{cid}/{mid}/` | Редагувати повідомлення | `MessageService.editMessage()` |
| `DELETE`|`/api/v1/messages/{cid}/{mid}/`| Видалити повідомлення | `MessageService.deleteMessage()` |
| `POST`| `/api/v1/messages/groups/` | Створити груповий чат | `MessageService.createGroup()` |
| `PATCH`|`/api/v1/messages/groups/{id}/` | Редагувати груповий чат | `MessageService.editGroup()` |
| `POST`| `/api/v1/messages/groups/{id}/send/`| Надіслати в групу | `MessageService.sendToGroup()` |

### 🎟️ Промокоди (Promo Codes) - Phase 10
| Метод | Ендпоінт | Опис | Клієнтська реалізація |
|-------|----------|------|-----------------------|
| `GET` | `/api/v1/promo-codes/` | Усі промокоди | `PromoService.fetchAll()` |
| `GET` | `/api/v1/promo-codes/{code}/`| Деталі промокоду | `PromoService.get()` |
| `POST`| `/api/v1/promo-codes/` | Створити промокод | `PromoService.create()` |
| `PATCH`|`/api/v1/promo-codes/{code}/`| Оновити промокод | `PromoService.update()` |
| `DELETE`|`/api/v1/promo-codes/{code}/`| Деактивувати | `PromoService.deactivate()` |
| `POST`| `/api/v1/promo-codes/{code}/use/`| Використати | `PromoService.use()` |
| `POST`| `/api/v1/promo-codes/{code}/gift/{uuid}/`| Подарувати | `PromoService.gift()` |

---

## 2. Supabase Сервіси (BaaS)
**Cloud домен:** `https://pkdnyonrejptotlpzclq.supabase.co`

### 🔑 Авторизація (GoTrue / `HeaderAuthModule`)
| Метод | Ендпоінт | Опис |
|-------|----------|------|
| `POST`| `/auth/v1/signup` | Реєстрація нового користувача |
| `POST`| `/auth/v1/token?grant_type=password` | Логін (отримання Access та Refresh JWT токенів) |
| `GET` | `/auth/v1/authorize` | OAuth 2.0 Авторизація (використовується для Google Sign-in) |

### ⚡ Edge Functions (через Deno)
Шлях маршрутизується через Kong API Gateway за префіксом `/functions/v1/`.
| Метод | Ендпоінт | Опис |
|-------|----------|------|
| `БУДЬ-ЯКИЙ` | `/functions/v1/hello` | Тестова функція Deno |
| `БУДЬ-ЯКИЙ` | `/functions/v1/main` | Головний proxy/обробник (містить кастомну перевірку підпису JWT) |

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
- Формат подій в Outbox включає тип сутності (`recipe`, `recipe_book`, тощо), `uuid`, операцію (`upsert`, `patch`, `delete`) та сам `payload`.