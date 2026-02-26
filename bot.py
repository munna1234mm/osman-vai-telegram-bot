import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import os

# To ensure the token isn't hardcoded entirely in standard practice, 
# but for fast access, we'll use the provided token explicitly if not in enviroment.
TOKEN = os.getenv("BOT_TOKEN", "8243932163:AAFRMmbcIJqQgbQCrSpJIiHpKesHS5mH-LI")
bot = telebot.TeleBot(TOKEN)

# Basic Admin IDs - replace with real user ID
ADMIN_ID = -1 

def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # Buttons as requested
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
    # In a real scenario, you'd check: if message.from_user.id == ADMIN_ID:
    # Here we just respond with the admin panel text for demonstration.
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

if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
