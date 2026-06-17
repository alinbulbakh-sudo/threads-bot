"""
Скрипт для отримання Threads Access Token
Запусти один раз локально: python get_token.py
"""

import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

# ── Заповни своїми даними з Meta App Dashboard ──
APP_ID     = input("Введи App ID з Meta App Dashboard: ").strip()
APP_SECRET = input("Введи App Secret з Meta App Dashboard: ").strip()
REDIRECT   = "http://localhost:8000/callback"

SCOPES = ",".join([
    "threads_basic",
    "threads_content_publish",
    "threads_keyword_search",
    "threads_manage_replies",
    "threads_read_replies",
])

auth_url = (
    f"https://threads.net/oauth/authorize"
    f"?client_id={APP_ID}"
    f"&redirect_uri={REDIRECT}"
    f"&scope={SCOPES}"
    f"&response_type=code"
)

print(f"\n🌐 Відкриваю браузер для авторизації...")
print(f"URL: {auth_url}\n")
webbrowser.open(auth_url)

# Локальний сервер щоб зловити code
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            code = params["code"][0]
            print(f"\n✅ Отримано code: {code[:20]}...")

            # Обміняти code на short-lived token
            r = requests.post("https://graph.threads.net/oauth/access_token", data={
                "client_id": APP_ID,
                "client_secret": APP_SECRET,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT,
                "code": code,
            })
            data = r.json()

            if "access_token" in data:
                short_token = data["access_token"]
                user_id = data.get("user_id")
                print(f"✅ Short-lived token отримано!")
                print(f"User ID: {user_id}")

                # Обміняти на long-lived token (60 днів)
                r2 = requests.get(
                    "https://graph.threads.net/access_token",
                    params={
                        "grant_type": "th_exchange_token",
                        "client_secret": APP_SECRET,
                        "access_token": short_token,
                    }
                )
                data2 = r2.json()

                if "access_token" in data2:
                    long_token = data2["access_token"]
                    expires = data2.get("expires_in", 0)
                    days = expires // 86400

                    print(f"\n{'='*50}")
                    print(f"🎉 LONG-LIVED TOKEN (дійсний {days} днів):")
                    print(f"\nTHREADS_ACCESS_TOKEN={long_token}")
                    print(f"THREADS_USER_ID={user_id}")
                    print(f"\n{'='*50}")
                    print("Скопіюй ці дані в .env файл або Railway Variables!")

                    # Зберегти в файл
                    with open("token_output.txt", "w") as f:
                        f.write(f"THREADS_ACCESS_TOKEN={long_token}\n")
                        f.write(f"THREADS_USER_ID={user_id}\n")
                    print("✅ Також збережено в token_output.txt")
                else:
                    print(f"❌ Помилка long-lived: {data2}")
            else:
                print(f"❌ Помилка: {data}")

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>Done! Check terminal.</h1>")
            raise SystemExit(0)
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # тихий режим

print("⏳ Чекаю на авторизацію на http://localhost:8000...")
HTTPServer(("localhost", 8000), Handler).handle_request()
