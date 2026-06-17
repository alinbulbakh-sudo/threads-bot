# Threads Bot — @bullbashka

Бот шукає пости по ключових словах і пише коментарі від твого імені через офіційний Threads API.

---

## КРОК 1 — Meta App (вже зроблено частково)

В Meta App додай ці permissions (Threads API → Permissions and features):
- `threads_basic` ✅
- `threads_content_publish` → + Add
- `threads_keyword_search` → + Add  ⭐
- `threads_manage_replies` → + Add
- `threads_read_replies` → + Add

Також в App Settings → Basic:
- App Domains: `localhost`
- Redirect URI: `http://localhost:8000/callback`

---

## КРОК 2 — Отримай токен (локально, один раз)

```bash
# Встанови Python залежності
pip install requests python-dotenv

# Запусти скрипт авторизації
python get_token.py
```

Скрипт відкриє браузер → авторизуй свій Threads акаунт → скопіює токен.

Збережи два значення:
```
THREADS_ACCESS_TOKEN=...
THREADS_USER_ID=...
```

---

## КРОК 3 — Задеплой на Railway

1. Створи новий проект на railway.app
2. **New Project → Deploy from GitHub** (або **Deploy from local**)
3. Завантаж всі файли цієї папки
4. В Railway → **Variables** додай:

```
THREADS_ACCESS_TOKEN=твій_токен
THREADS_USER_ID=твій_user_id
DAILY_LIMIT=25
DELAY_MIN=180
DELAY_MAX=600
```

5. Railway сам запустить `python bot.py`

---

## КРОК 4 — Оновлення токена (кожні 60 днів)

Threads long-lived token живе 60 днів. Перед закінченням запусти:

```bash
python get_token.py
```

І оновіть `THREADS_ACCESS_TOKEN` в Railway Variables.

---

## Файли

| Файл | Призначення |
|------|-------------|
| `bot.py` | Головний бот |
| `get_token.py` | Отримати токен (запускати локально) |
| `.env.example` | Шаблон змінних середовища |
| `railway.toml` | Конфіг деплою |
| `requirements.txt` | Python залежності |

---

## Як працює

```
Кожні 2 години:
  → Пошук по 17 ключових запитах
  → Фільтрація (не свої пости, не коментовані раніше)
  → Вибір скрипту коментаря під тип посту
  → Публікація коментаря через API
  → Затримка 3-10 хвилин між коментарями
  → Ліміт 25 коментарів на день
```

---

## Скрипти коментарів

Редагуй в `bot.py` секцію `COMMENT_SCRIPTS`:

- `ads` — коли хтось скаржиться на рекламу або шукає таргетолога
- `tattoo` — тату-майстри
- `legal` — адвокати / юристи
- `selfpromo` — треди "хто чим займається"
- `general` — все інше
