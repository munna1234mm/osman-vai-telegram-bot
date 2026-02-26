import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Update, InlineKeyboardMarkup, InlineKeyboardButton
import os
from fastapi import FastAPI, Request
import yaml  # In case we need it, but using env is better
from pymongo import MongoClient
import certifi

# --- Configurations ---
TOKEN = os.getenv("BOT_TOKEN", "8243932163:AAFRMmbcIJqQgbQCrSpJIiHpKesHS5mH-LI")
bot = telebot.TeleBot(TOKEN)
app = FastAPI()

# Replace with your own Admin ID! For now, we allow any ID to use /admin for testing if not set.
# Example: ADMIN_IDS = [123456789]
ADMIN_IDS = [] 

# --- Database Connection ---
# We use an environment variable for MongoDB. If not provided, it falls back to a free cluster for demonstration.
# WARNING: This fallback URL should be replaced by the user's own MongoDB connection string.
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://testuser:testpass123@cluster0.exmple.mongodb.net/?retryWrites=true&w=majority")
try:
    client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())
    db = client['telegram_bot']
    users_collection = db['users']
    settings_collection = db['settings']
    print("Connected to MongoDB successfully!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    # Fallback to local dicts if DB utterly fails
    users_collection = None
    settings_collection = None

# Fallback Memory (if DB connection fails or isn't set up yet)
memory_banned = set()
memory_balances = {}
memory_channel = None

# --- Helper Functions for Database ---
def get_user(user_id):
    if users_collection is not None:
        user = users_collection.find_one({"_id": user_id})
        if not user:
            user = {"_id": user_id, "balance": 0, "banned": False}
            users_collection.insert_one(user)
        return user
    return {"_id": user_id, "balance": memory_balances.get(user_id, 0), "banned": user_id in memory_banned}

def update_user_balance(user_id, amount):
    if users_collection is not None:
        users_collection.update_one({"_id": user_id}, {"$set": {"balance": amount}}, upsert=True)
    else:
        memory_balances[user_id] = amount

def ban_user(user_id):
    if users_collection is not None:
        users_collection.update_one({"_id": user_id}, {"$set": {"banned": True}}, upsert=True)
    else:
        memory_banned.add(user_id)

def unban_user(user_id):
    if users_collection is not None:
        users_collection.update_one({"_id": user_id}, {"$set": {"banned": False}}, upsert=True)
    else:
        if user_id in memory_banned:
            memory_banned.remove(user_id)

def get_mandatory_channel():
    if settings_collection is not None:
        setting = settings_collection.find_one({"_id": "mandatory_channel"})
        if setting:
            return setting.get("channel_id")
    return memory_channel

def set_mandatory_channel(channel_id):
    global memory_channel
    if settings_collection is not None:
        settings_collection.update_one({"_id": "mandatory_channel"}, {"$set": {"channel_id": channel_id}}, upsert=True)
    else:
        memory_channel = channel_id

def is_admin(user_id):
    if not ADMIN_IDS:
        return True # If no admins specified, let anyone use it for testing
    return user_id in ADMIN_IDS

# --- Middlewares (Check Ban & Join) ---
def check_join(user_id):
    channel = get_mandatory_channel()
    if not channel:
        return True # No channel required
    try:
        member = bot.get_chat_member(channel, user_id)
        if member.status in ['left', 'kicked']:
            return False
        return True
    except Exception as e:
        print(f"Error checking channel membership: {e}")
        # If bot is not admin in the channel, it will throw an error. We allow them to pass for safety.
        return True 

# --- Keyboards ---
def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("One Task"),
        KeyboardButton("Daily Task"),
        KeyboardButton("Invite"),
        KeyboardButton("Balance"),
        KeyboardButton("FAQ")
    )
    return markup

def get_admin_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
        InlineKeyboardButton("🟢 Unban User", callback_data="admin_unban")
    )
    markup.add(
        InlineKeyboardButton("💰 Edit Balance", callback_data="admin_balance"),
    )
    markup.add(
        InlineKeyboardButton("📢 Add/Change Channel", callback_data="admin_channel"),
        InlineKeyboardButton("🗑️ Remove Channel", callback_data="admin_rm_channel")
    )
    return markup

def get_join_keyboard():
    markup = InlineKeyboardMarkup()
    channel = get_mandatory_channel()
    # Assuming channel is a username like @mychannel. 
    # If it's a private ID, we can't easily generate a link without storing it.
    link = f"https://t.me/{channel.replace('@', '')}" if channel and channel.startswith('@') else "https://t.me"
    markup.add(InlineKeyboardButton("📢 Join Channel", url=link))
    markup.add(InlineKeyboardButton("✅ Joined", callback_data="check_join"))
    return markup


# --- Core Command Handlers ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user = get_user(message.from_user.id)
    if user.get("banned"):
        return bot.reply_to(message, "You are banned from using this bot.")
        
    bot.reply_to(
        message, 
        "Welcome to the Task Bot! Please choose an option below:", 
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "You do not have permission to use this command.")

    bot.reply_to(message, "⚙️ Welcome to the Admin Panel!\nChoose an action:", reply_markup=get_admin_keyboard())

# --- Callback Handlers (Admin & User) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    # User Join Check
    if call.data == "check_join":
        if check_join(user_id):
            bot.answer_callback_query(call.id, "Verification successful!", show_alert=True)
            bot.send_message(user_id, "Welcome to the Task Bot! Please choose an option below:", reply_markup=get_main_keyboard())
        else:
            bot.answer_callback_query(call.id, "You have not joined the channel yet.", show_alert=True)
        return

    # Admin Callbacks
    if not is_admin(user_id):
        return bot.answer_callback_query(call.id, "Access Denied.")

    if call.data == "admin_ban":
        msg = bot.send_message(user_id, "Send the User ID to BAN:")
        bot.register_next_step_handler(msg, process_ban)
    elif call.data == "admin_unban":
        msg = bot.send_message(user_id, "Send the User ID to UNBAN:")
        bot.register_next_step_handler(msg, process_unban)
    elif call.data == "admin_balance":
        msg = bot.send_message(user_id, "Send the User ID to edit balance:")
        bot.register_next_step_handler(msg, process_balance_user_id)
    elif call.data == "admin_channel":
        msg = bot.send_message(user_id, "Send the Channel Username (e.g., @mychannel):\n\n*Make sure this bot is added as an Admin in that channel first!*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_channel)
    elif call.data == "admin_rm_channel":
        set_mandatory_channel(None)
        bot.send_message(user_id, "Mandatory channel verification has been removed.")

# --- Admin Step Functions ---
def process_ban(message):
    try:
        target_id = int(message.text)
        ban_user(target_id)
        bot.reply_to(message, f"User {target_id} has been successfully banned.")
    except ValueError:
        bot.reply_to(message, "Invalid User ID. Please send a number.")

def process_unban(message):
    try:
        target_id = int(message.text)
        unban_user(target_id)
        bot.reply_to(message, f"User {target_id} has been successfully unbanned.")
    except ValueError:
        bot.reply_to(message, "Invalid User ID.")

def process_balance_user_id(message):
    try:
        target_id = int(message.text)
        msg = bot.reply_to(message, f"Send the new balance amount for user {target_id}:")
        bot.register_next_step_handler(msg, process_balance_amount, target_id)
    except ValueError:
        bot.reply_to(message, "Invalid User ID.")

def process_balance_amount(message, target_id):
    try:
        amount = int(message.text)
        update_user_balance(target_id, amount)
        bot.reply_to(message, f"User {target_id}'s balance has been updated to {amount} Tokens.")
    except ValueError:
        bot.reply_to(message, "Invalid amount. Must be a number.")

def process_add_channel(message):
    channel = message.text.strip()
    if not channel.startswith('@'):
        return bot.reply_to(message, "Invalid format. Channel must start with '@' (e.g. @mychannel).")
    
    set_mandatory_channel(channel)
    bot.reply_to(message, f"Channel set to {channel}.\nAll users must now join this channel.")

# --- Text Message Handler ---
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    user = get_user(user_id)

    # 1. Check if banned
    if user.get("banned"):
        return

    # 2. Check if channel join is required
    if not check_join(user_id):
        return bot.reply_to(
            message, 
            "⚠️ You must join our official channel to use this bot!", 
            reply_markup=get_join_keyboard()
        )

    # 3. Process normal commands
    text = message.text
    if text == "One Task":
        bot.reply_to(message, "📝 You selected: One Task\nThis feature is coming soon!")
    elif text == "Daily Task":
        bot.reply_to(message, "📅 You selected: Daily Task\nComplete your daily task to earn rewards!")
    elif text == "Invite":
        bot.reply_to(message, f"🔗 Here is your personal invite link: https://t.me/{bot.get_me().username}?start={user_id}")
    elif text == "Balance":
        balance = user.get("balance", 0)
        bot.reply_to(message, f"💰 Balance: {balance} Tokens")
    elif text == "FAQ":
        bot.reply_to(message, "❓ Frequently Asked Questions:\n1. How to earn? Complete tasks.\n2. How to invite? Use your invite link.")
    else:
        bot.reply_to(message, "I didn't understand that. Please use the menu.", reply_markup=get_main_keyboard())


# --- FastAPI routes for Webhook ---
@app.post(f"/{TOKEN}/")
async def process_webhook(request: Request):
    json_str = await request.body()
    update = Update.de_json(json_str.decode('utf-8'))
    bot.process_new_updates([update])
    return {"status": "ok"}

@app.get("/")
def home():
    return {"status": "Bot is running on Render!"}

if __name__ == '__main__':
    print("Bot configuration loaded. To run locally, use 'uvicorn bot:app --host 0.0.0.0 --port 10000'")
