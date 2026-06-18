"""
Threads Bot для @bullbashka
Шукає пости по ключових словах → пише коментарі від імені акаунту
"""

import os
import time
import json
import random
import logging
import requests
import schedule
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────
ACCESS_TOKEN   = os.getenv("THREADS_ACCESS_TOKEN")
USER_ID        = os.getenv("THREADS_USER_ID")
DAILY_LIMIT    = int(os.getenv("DAILY_LIMIT", "25"))      # коментарів на день
DELAY_MIN      = int(os.getenv("DELAY_MIN", "180"))       # мін затримка між коментарями (сек)
DELAY_MAX      = int(os.getenv("DELAY_MAX", "600"))       # макс затримка (сек)
BASE_URL       = "https://graph.threads.net/v1.0"

# ─── ПОШУКОВІ ЗАПИТИ ──────────────────────────────────────
SEARCH_QUERIES = [
    # 🔴 HOT — люди з явним болем / потребою
    "потрібен таргетолог",
    "реклама не працює",
    "дорогі ліди",
    "запустити рекламу",
    "порадьте таргетолога",
    "Meta Ads",
    "таргет не приносить",


    # 🧵 Треди самореклами
    "розкажіть про себе",
    "хто чим займається",
    "порадьте спеціаліста",
]

# ─── СКРИПТИ КОМЕНТАРІВ ───────────────────────────────────
# Кожен варіант прив'язаний до типу посту
# {query} підставляється автоматично якщо треба

COMMENT_SCRIPTS = {

    # Коли шукають таргетолога / скаржаться на рекламу
    "ads": [
        "Привіт! Займаюсь Meta Ads для бізнесу з послуг — якщо хочеш розібратись що не так, можу подивитись без на безкоштовній консультації 🙌",
        "Таргетолог тут 👋 Спеціалізуюсь на послугах. Якщо хочеш — можу зробити міні-аудит кабінету, безкоштовно",
    ],


    # Треди самореклами / "хто чим займається"
    "selfpromo": [
        "Аліна, таргетолог 👋 Запускаю рекламу для бізнесу з різних послуг.Кому цікаво - пишіть!",
        "Таргетолог тут! Спеціалізуюсь на масштабуванні клієнтів на різні послуги. Пиши якщо потрібна реклама 🔥",
        "Привіт! Я Аліна — допомагаю бізнесу з послуг залучати клієнтів через Meta Ads. Якщо хочеш поговорити про рекламу — пиши в директ 🙌",
    ],

    # Загальний (fallback)
    "general": [
        "Займаюсь таргетом для послуг — якщо цікаво поговорити про рекламу, пишіть 🙌",
        "Таргетолог тут 👋 Пиши якщо потрібна реклама для бізнесу",
    ],
}

# Маппінг запитів до типів коментарів
QUERY_TO_TYPE = {
    "потрібен таргетолог": "ads",
    "реклама не працює": "ads",
    "дорогі ліди": "ads",
    "запустити рекламу": "ads",
    "порадьте таргетолога": "ads",
    "Meta Ads": "ads",
    "таргет не приносить": "ads",
    "потрібен адвокат": "legal",
    "порадьте юриста": "legal",
    "юридична допомога": "legal",
    "шукаю адвоката": "legal",
    "хочу тату": "tattoo",
    "порадьте майстра тату": "tattoo",
    "шукаю майстра тату": "tattoo",
    "розкажіть про себе": "selfpromo",
    "хто чим займається": "selfpromo",
    "порадьте спеціаліста": "general",
}


# ─── ЛІЧИЛЬНИК ЛІМІТІВ ────────────────────────────────────
class DailyCounter:
    def __init__(self):
        self.count = 0
        self.last_date = date.today()
        self.commented_posts = set()   # щоб не коментувати двічі

    def reset_if_new_day(self):
        today = date.today()
        if today != self.last_date:
            log.info(f"Новий день — скидаю лічильник. Вчора: {self.count} коментарів")
            self.count = 0
            self.last_date = today

    def can_comment(self):
        self.reset_if_new_day()
        return self.count < DAILY_LIMIT

    def register(self, post_id):
        self.count += 1
        self.commented_posts.add(post_id)
        log.info(f"Лічильник: {self.count}/{DAILY_LIMIT} сьогодні")

    def already_commented(self, post_id):
        return post_id in self.commented_posts


counter = DailyCounter()


# ─── THREADS API ──────────────────────────────────────────
def api_get(endpoint, params=None):
    """GET запит до Threads API"""
    url = f"{BASE_URL}/{endpoint}"
    p = {"access_token": ACCESS_TOKEN}
    if params:
        p.update(params)
    try:
        r = requests.get(url, params=p, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API GET помилка: {e}")
        return None


def api_post(endpoint, data=None):
    """POST запит до Threads API"""
    url = f"{BASE_URL}/{endpoint}"
    d = {"access_token": ACCESS_TOKEN}
    if data:
        d.update(data)
    try:
        r = requests.post(url, data=d, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        log.error(f"API POST помилка: {e}")
        return None


def search_posts(query, limit=10):
    """Шукає пости по ключовому слову"""
    log.info(f"Шукаю: '{query}'")
    result = api_get(
        f"{USER_ID}/threads_keyword_search",
        {"q": query, "limit": limit}
    )
    if not result or "data" not in result:
        return []
    posts = result["data"]
    log.info(f"Знайдено {len(posts)} постів по '{query}'")
    return posts


def get_my_user_id():
    """Отримує User ID поточного юзера"""
    result = api_get("me", {"fields": "id,username"})
    if result:
        log.info(f"Авторизовано як: @{result.get('username')} (ID: {result.get('id')})")
        return result.get("id")
    return None


def publish_comment(post_id, text):
    """Публікує коментар до поста"""
    # Крок 1: Створити media container
    container = api_post(
        f"{USER_ID}/threads",
        {
            "media_type": "TEXT",
            "text": text,
            "reply_to_id": post_id,
        }
    )
    if not container or "id" not in container:
        log.error(f"Не вдалось створити container для поста {post_id}")
        return False

    container_id = container["id"]
    time.sleep(3)  # чекаємо поки Meta обробить

    # Крок 2: Опублікувати
    result = api_post(
        f"{USER_ID}/threads_publish",
        {"creation_id": container_id}
    )

    if result and "id" in result:
        log.info(f"✅ Коментар опубліковано! Post: {post_id} | Comment ID: {result['id']}")
        return True
    else:
        log.error(f"❌ Не вдалось опублікувати коментар до {post_id}")
        return False


def publish_post(text):
    """Публікує новий пост від імені акаунту"""
    container = api_post(
        f"{USER_ID}/threads",
        {"media_type": "TEXT", "text": text}
    )
    if not container or "id" not in container:
        log.error("Не вдалось створити пост")
        return False

    time.sleep(3)

    result = api_post(
        f"{USER_ID}/threads_publish",
        {"creation_id": container["id"]}
    )

    if result and "id" in result:
        log.info(f"✅ Пост опубліковано! ID: {result['id']}")
        return True
    return False


def pick_comment(query, post_text=""):
    """Вибирає коментар під запит"""
    comment_type = QUERY_TO_TYPE.get(query, "general")
    scripts = COMMENT_SCRIPTS.get(comment_type, COMMENT_SCRIPTS["general"])
    return random.choice(scripts)


def filter_post(post, my_user_id):
    """Перевіряє чи варто коментувати цей пост"""
    post_id = post.get("id")

    # Не коментувати двічі
    if counter.already_commented(post_id):
        return False

    # Не коментувати свої пости
    owner = post.get("owner", {})
    if str(owner.get("id")) == str(my_user_id):
        return False

    # Не коментувати якщо текст порожній
    if not post.get("text"):
        return False

    return True


# ─── ОСНОВНИЙ ЦИКЛ ────────────────────────────────────────
def run_bot_cycle():
    """Один цикл бота: пошук → фільтр → коментар"""
    log.info("=" * 50)
    log.info(f"Старт циклу | {datetime.now().strftime('%H:%M:%S')} | Ліміт: {counter.count}/{DAILY_LIMIT}")

    if not counter.can_comment():
        log.info("Денний ліміт вичерпано. Чекаю до завтра.")
        return

    my_id = get_my_user_id()
    if not my_id:
        log.error("Не вдалось авторизуватись. Перевір THREADS_ACCESS_TOKEN")
        return

    # Перемішуємо запити щоб не бути передбачуваними
    queries = SEARCH_QUERIES.copy()
    random.shuffle(queries)

    commented_this_cycle = 0
    MAX_PER_CYCLE = 3  # не більше 3 коментарів за один запуск

    for query in queries:
        if not counter.can_comment():
            break
        if commented_this_cycle >= MAX_PER_CYCLE:
            break

        posts = search_posts(query, limit=5)

        for post in posts:
            if not counter.can_comment():
                break
            if commented_this_cycle >= MAX_PER_CYCLE:
                break

            post_id = post.get("id")
            post_text = post.get("text", "")

            if not filter_post(post, my_id):
                continue

            comment_text = pick_comment(query, post_text)

            log.info(f"Коментую пост: {post_id[:8]}...")
            log.info(f"Текст посту: {post_text[:80]}...")
            log.info(f"Коментар: {comment_text}")

            success = publish_comment(post_id, comment_text)

            if success:
                counter.register(post_id)
                commented_this_cycle += 1

                # Затримка між коментарями (як людина)
                delay = random.randint(DELAY_MIN, DELAY_MAX)
                log.info(f"Чекаю {delay} сек до наступного коментаря...")
                time.sleep(delay)

    log.info(f"Цикл завершено. Прокоментовано: {commented_this_cycle} постів")


# ─── ЗАПУСК ───────────────────────────────────────────────
if __name__ == "__main__":
    log.info("🤖 Threads Bot @bullbashka запущено")

    # Перевірка токена
    my_id = get_my_user_id()
    if not my_id:
        log.critical("❌ Токен не працює! Перевір .env файл")
        exit(1)

    # Розклад: запускати кожні 2 години з 9:00 до 22:00
    schedule.every(2).hours.do(run_bot_cycle)

    # Перший запуск одразу
    run_bot_cycle()

    while True:
        schedule.run_pending()
        time.sleep(60)
