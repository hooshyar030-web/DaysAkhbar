import sqlite3
import time
import feedparser
import requests

# ۱. تنظیمات اولیه
DB_NAME = "sent_news.db"
BOT_TOKEN = "816136439:LxLDXaXtXGgfmfs5I6lvzNFdMD_6d0rbkvw"  # توکن ربات
MESSENGER = "bale"                # مقدار را "bale" یا "telegram" بگذارید

RSS_FEEDS = [
    "https://www.zoomit.ir/feed/",
    "https://www.khabaronline.ir/rss",
]

# ۲. مدیریت دیتابیس
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT UNIQUE,
                title TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def is_already_sent(link: str) -> bool:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sent_articles WHERE link = ?", (link,))
        return cursor.fetchone() is not None

def mark_as_sent(link: str, title: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO sent_articles (link, title) VALUES (?, ?)", (link, title))
        conn.commit()

# ۳. دریافت پیام‌های جدید از کاربر (getUpdates)
def get_updates(offset=None):
    base_url = "https://tapi.bale.ai" if MESSENGER == "bale" else "https://api.telegram.org"
    api_url = f"{base_url}/bot{BOT_TOKEN}/getUpdates"
    
    params = {"timeout": 10, "offset": offset}
    try:
        response = requests.get(api_url, params=params, timeout=15)
        if response.ok:
            return response.json().get("result", [])
    except Exception as e:
        print(f"خطا در دریافت پیام‌ها: {e}")
    return []

# ۴. ارسال پاسخ به چت مشخص
def send_to_messenger(chat_id: int, text: str) -> bool:
    base_url = "https://tapi.bale.ai" if MESSENGER == "bale" else "https://api.telegram.org"
    api_url = f"{base_url}/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(api_url, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        print(f"خطا در ارسال پیام: {e}")
        return False

# ۵. جستجوی خبر در RSS بر اساس کلمه درخواستی
def search_and_send(chat_id: int, keyword: str):
    send_to_messenger(chat_id, f"🔍 در حال جستجوی اخبار مرتبط با «<b>{keyword}</b>»...")
    
    matched_articles = []
    for feed_url in RSS_FEEDS:
        parsed_feed = feedparser.parse(feed_url)
        for entry in parsed_feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            
            # بررسی کلمه کلیدی
            if keyword.lower() in title.lower() or keyword.lower() in summary.lower():
                matched_articles.append({"title": title, "link": link})
    
    if not matched_articles:
        send_to_messenger(chat_id, f"❌ خبری با کلمه «<b>{keyword}</b>» در فیدها یافت نشد.")
        return

    sent_count = 0
    # ارسال حداکثر ۵ خبر اول مرتبط
    for news in matched_articles[:5]:
        # نشان‌گذاری اخبار قبلاً دیده شده
        already_seen = " (قبلاً دریافت شده)" if is_already_sent(news['link']) else ""
        
        formatted_message = (
            f"📰 <b>{news['title']}</b>{already_seen}\n\n"
            f"🔗 <a href='{news['link']}'>مشاهده خبر</a>"
        )
        if send_to_messenger(chat_id, formatted_message):
            mark_as_sent(news['link'], news['title'])
            sent_count += 1
            
    print(f"تعداد {sent_count} خبر درباره «{keyword}» برای چت {chat_id} ارسال شد.")

# ۶. حلقه اصلی گوش به زنگ ربات
def start_bot():
    init_db()
    last_update_id = None
    print("ربات فعال شد و منتظر دریافت کلمه از طرف شماست...")

    while True:
        updates = get_updates(offset=last_update_id)
        for update in updates:
            last_update_id = update["update_id"] + 1
            
            message = update.get("message", {})
            text = message.get("text", "").strip()
            chat_id = message.get("chat", {}).get("id")
            
            if text and chat_id:
                if text == "/start":
                    send_to_messenger(chat_id, "سلام! هر کلمه یا موضوعی که می‌خواهی درباره‌اش خبر ببینی را ارسال کن.")
                else:
                    # استفاده از متن فرستاده‌شده به عنوان کلمه کلیدی
                    search_and_send(chat_id, text)
                    
        time.sleep(1)

import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ساخت یک وب‌سرور بسیار ساده برای پاسخ به Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")

def run_dummy_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ۵. اجرای همزمان وب‌سرور و ربات
if __name__ == "__main__":
    # اجرای وب‌سرور در پس‌زمینه برای تایید سلامت سرویس در Render
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # اجرای ربات
    start_bot()
