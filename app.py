import os
import subprocess
import shutil
import telebot
from flask import Flask, request, jsonify

app = Flask(__name__)

# Telegram Bot Token (replace with your own or use environment variable)
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')

# Initialize the bot
bot = telebot.TeleBot(BOT_TOKEN)

# Simple health check endpoint
@app.route('/')
def home():
    return "Telegram PyArmor Bot is running!", 200

# Webhook setup for Render (optional)
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Bad request', 400

# Handle /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Send me a .py file and I'll obfuscate it using PyArmor.")

# Handle .py file uploads
@bot.message_handler(content_types=['document'])
def handle_file(message):
    if not message.document.file_name.endswith('.py'):
        bot.reply_to(message, "Please send a .py file only.")
        return

    user_id = str(message.from_user.id)
    user_dir = f"temp/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    file_path = f"{user_dir}/{message.document.file_name}"
    output_dir = f"{user_dir}/dist"

    try:
        # Download the file
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        bot.reply_to(message, "File received. Obfuscating...")

        # Run PyArmor 8.0+ to obfuscate the file
        subprocess.run([
            "pyarmor", "gen", 
            "-O", output_dir,  # Output directory
            file_path         # Input file
        ], check=True)

        # Find the obfuscated file (PyArmor 8+ changes output structure)
        obf_file_path = None
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith('.py'):
                    obf_file_path = os.path.join(root, file)
                    break
            if obf_file_path:
                break

        if obf_file_path and os.path.exists(obf_file_path):
            with open(obf_file_path, 'rb') as obf_file:
                bot.send_document(message.chat.id, obf_file, caption=f"Obfuscated: {message.document.file_name}")
        else:
            bot.reply_to(message, "Obfuscation failed - couldn't find output file.")

    except subprocess.CalledProcessError as e:
        bot.reply_to(message, f"PyArmor error: {str(e)}")
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")
    finally:
        # Cleanup user's temp folder
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir)

def run_bot():
    # For Render, we need to use webhooks or polling in a separate thread
    if os.getenv('RENDER'):
        # Webhook setup for production
        bot.remove_webhook()
        bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook")
        print("Webhook set up")
    else:
        # Local development with polling
        print("Starting polling...")
        bot.polling()

if __name__ == '__main__':
    from threading import Thread
    # Start Flask app in main thread
    # Start Telegram bot in a separate thread
    Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=3000)
