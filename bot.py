import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Update
import os
from fastapi import FastAPI, Request
import uvicorn

TOKEN = os.getenv("BOT_TOKEN", "8243932163:AAFRMmbcIJqQgbQCrSpJIiHpKesHS5mH-LI")
bot = telebot.TeleBot(TOKEN)
app = FastAPI()

ADMIN_ID = -1

def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_one_task = KeyboardButton("One Task")
    btn_daily_task = KeyboardButton("Daily Task")
    btn_invite = KeyboardButton("Invite")
    btn_balance = KeyboardButton("Balance")
    btn_faq = KeyboardButton("FAQ")
    markup.add(btn_one_task, btn_daily_task, btn_invite, btn_balance, btn_faq)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Welcome to the Task Bot! Please choose an option below:", 
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    bot.reply_to(message, "⚙️ Welcome to the Admin Panel!\n(Here you can add admin specific configuration)")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    text = message.text
    if text == "One Task":
        bot.reply_to(message, "📝 You selected: One Task\nThis feature is coming soon!")
    elif text == "Daily Task":
        bot.reply_to(message, "📅 You selected: Daily Task\nComplete your daily task to earn rewards!")
    elif text == "Invite":
        bot.reply_to(message, f"🔗 Here is your personal invite link: https://t.me/{bot.get_me().username}?start={message.from_user.id}")
    elif text == "Balance":
        bot.reply_to(message, "💰 Balance: 0 Tokens\n(This will be updated as you complete tasks)")
    elif text == "FAQ":
        bot.reply_to(message, "❓ Frequently Asked Questions:\n1. How to earn? Complete tasks.\n2. How to invite? Use your invite link.")
    else:
        bot.reply_to(message, "I didn't understand that. Please use the menu.", reply_markup=get_main_keyboard())


# FastAPI routes for Webhook
@app.post(f"/{TOKEN}/")
async def process_webhook(request: Request):
    json_str = await request.body()
    update = Update.de_json(json_str.decode('utf-8'))
    bot.process_new_updates([update])
    return {"status": "ok"}

@app.get("/")
def home():
    return {"status": "Bot is running on Render!"}

# Required to run on Render
if __name__ == '__main__':
    # When testing locally, you can use polling or set up ngrok for webhook.
    # For now we'll assume Render handles the execution via uvicorn.
    print("Bot configuration loaded. To run locally, use 'uvicorn bot:app --host 0.0.0.0 --port 10000'")
