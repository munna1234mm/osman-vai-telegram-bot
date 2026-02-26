import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Update, InlineKeyboardMarkup, InlineKeyboardButton
import os
from fastapi import FastAPI, Request
import uvicorn
from pymongo import MongoClient
import certifi

# --- Configurations ---
TOKEN = os.getenv("BOT_TOKEN", "8243932163:AAFRMmbcIJqQgbQCrSpJIiHpKesHS5mH-LI")
bot = telebot.TeleBot(TOKEN)
app = FastAPI()

ADMIN_IDS = [] 

MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://testuser:testpass123@cluster0.exmple.mongodb.net/?retryWrites=true&w=majority")
try:
    client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())
    db = client['telegram_bot']
    users_collection = db['users']
    settings_collection = db['settings']
    tasks_collection = db['tasks']
    print("Connected to MongoDB successfully!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    users_collection = None
    settings_collection = None
    tasks_collection = None

# Fallback Memory
memory_banned = set()
memory_balances = {}
memory_channel = None
memory_tasks = []
memory_ref_bonus = 0

# --- Helper Functions for Database ---
def get_user(user_id, username=None):
    if users_collection is not None:
        user = users_collection.find_one({"_id": user_id})
        update_data = {}
        if username:
            update_data["username"] = username.lower()
            
        if not user:
            user = {"_id": user_id, "balance": 0, "banned": False}
            if username:
                user["username"] = username.lower()
            users_collection.insert_one(user)
        elif username and user.get("username") != username.lower():
            users_collection.update_one({"_id": user_id}, {"$set": {"username": username.lower()}})
            user["username"] = username.lower()
        return user
    return {"_id": user_id, "balance": memory_balances.get(user_id, 0), "banned": user_id in memory_banned, "username": username.lower() if username else None}

def get_user_by_input(input_str):
    """ Tries to find a user by ID or username """
    if users_collection is not None:
        try:
            # Try by ID first
            uid = int(input_str)
            return users_collection.find_one({"_id": uid})
        except ValueError:
            # If not a number, try by username
            clean_username = input_str.replace('@', '').lower().strip()
            return users_collection.find_one({"username": clean_username})
    return None

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

def get_ref_bonus():
    if settings_collection is not None:
        setting = settings_collection.find_one({"_id": "referral_bonus"})
        if setting:
            return setting.get("amount", 0)
    return memory_ref_bonus

def set_ref_bonus(amount):
    global memory_ref_bonus
    if settings_collection is not None:
        settings_collection.update_one({"_id": "referral_bonus"}, {"$set": {"amount": amount}}, upsert=True)
    else:
        memory_ref_bonus = amount

def add_task(title, url):
    if tasks_collection is not None:
        tasks_collection.insert_one({"title": title, "url": url})
    else:
        memory_tasks.append({"title": title, "url": url})

def get_all_users():
    if users_collection is not None:
        return list(users_collection.find())
    return [{"_id": k, "balance": v, "banned": k in memory_banned} for k, v in memory_balances.items()]

def get_all_tasks():
    if tasks_collection is not None:
        return list(tasks_collection.find())
    return memory_tasks

def is_admin(user_id):
    if not ADMIN_IDS:
        return True 
    return user_id in ADMIN_IDS

def check_join(user_id):
    channel = get_mandatory_channel()
    if not channel:
        return True 
    try:
        member = bot.get_chat_member(channel, user_id)
        if member.status in ['left', 'kicked']:
            return False
        return True
    except Exception as e:
        print(f"Error checking channel membership: {e}")
        return True 

# --- Keyboards ---
def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("One Task"),
        KeyboardButton("Daily Task"),
        KeyboardButton("Invite"),
        KeyboardButton("Balance"),
        KeyboardButton("FAQ"),
        KeyboardButton("✅ Submit Task")
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
        InlineKeyboardButton("🎁 Set Ref Bonus", callback_data="admin_ref_bonus")
    )
    markup.add(
        InlineKeyboardButton("➕ Add Task", callback_data="admin_add_task"),
        InlineKeyboardButton("👥 View All Users", callback_data="admin_view_users")
    )
    markup.add(
        InlineKeyboardButton("📢 Add/Change Channel", callback_data="admin_channel"),
        InlineKeyboardButton("🗑️ Remove Channel", callback_data="admin_rm_channel")
    )
    return markup

def get_join_keyboard():
    markup = InlineKeyboardMarkup()
    channel = get_mandatory_channel()
    link = f"https://t.me/{channel.replace('@', '')}" if channel and channel.startswith('@') else "https://t.me"
    markup.add(InlineKeyboardButton("📢 Join Channel", url=link))
    markup.add(InlineKeyboardButton("✅ Joined", callback_data="check_join"))
    return markup

def get_tasks_keyboard():
    markup = InlineKeyboardMarkup()
    tasks = get_all_tasks()
    for task in tasks:
        markup.add(InlineKeyboardButton(task['title'], url=task['url']))
    return markup

# --- Core Command Handlers ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Check if this is a new user for referral
    is_new = False
    if users_collection is not None:
        existing = users_collection.find_one({"_id": user_id})
        if not existing:
            is_new = True

    user = get_user(user_id, username)
    if user.get("banned"):
        return bot.reply_to(message, "You are banned from using this bot.")
        
    # Handle Referral Logic
    if is_new and " " in message.text:
        referrer_id_str = message.text.split(" ")[1]
        try:
            referrer_id = int(referrer_id_str)
            if referrer_id != user_id:
                referrer = get_user(referrer_id)
                if referrer:
                    bonus = get_ref_bonus()
                    new_balance = referrer.get("balance", 0) + bonus
                    update_user_balance(referrer_id, new_balance)
                    bot.send_message(referrer_id, f"🎉 Someone joined using your invite link! You received {bonus} ৳.")
        except ValueError:
            pass

    bot.reply_to(
        message, 
        "Welcome to the Task Bot! Please choose an option below:", 
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "You do not have permission to use this command.")

    db_status = "✅ Connected" if users_collection is not None else "❌ Offline (Memory Mode)"
    msg_text = f"⚙️ Welcome to the Admin Panel!\n💾 DB Status: {db_status}\n\nChoose an action:"
    bot.reply_to(message, msg_text, reply_markup=get_admin_keyboard())

# --- Callback Handlers ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    if call.data == "check_join":
        if check_join(user_id):
            bot.answer_callback_query(call.id, "Verification successful!", show_alert=True)
            bot.send_message(user_id, "Welcome to the Task Bot! Please choose an option below:", reply_markup=get_main_keyboard())
        else:
            bot.answer_callback_query(call.id, "You have not joined the channel yet.", show_alert=True)
        return

    if not is_admin(user_id):
        return bot.answer_callback_query(call.id, "Access Denied.")

    if call.data == "admin_ban":
        msg = bot.send_message(user_id, "Send the User ID or @username to BAN:")
        bot.register_next_step_handler(msg, process_ban)
    elif call.data == "admin_unban":
        msg = bot.send_message(user_id, "Send the User ID or @username to UNBAN:")
        bot.register_next_step_handler(msg, process_unban)
    elif call.data == "admin_balance":
        msg = bot.send_message(user_id, "Send the User ID or @username to edit balance:")
        bot.register_next_step_handler(msg, process_balance_user_input)
    elif call.data == "admin_channel":
        msg = bot.send_message(user_id, "Send the Channel Username (e.g., @mychannel):\n\n*Make sure this bot is added as an Admin in that channel first!*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_channel)
    elif call.data == "admin_rm_channel":
        set_mandatory_channel(None)
        bot.send_message(user_id, "Mandatory channel verification has been removed.")
    elif call.data == "admin_add_task":
        msg = bot.send_message(user_id, "Send the **Title** of the new Task (e.g., 'Subscribe to YouTube'):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_task_title)
    elif call.data == "admin_ref_bonus":
        msg = bot.send_message(user_id, f"Current Referral Bonus: {get_ref_bonus()} ৳\n\nSend the **new amount** (in ৳):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_ref_bonus)
    elif call.data == "admin_view_users":
        send_all_users_report(user_id)
    elif call.data.startswith("approve_"):
        target_id = int(call.data.split("_")[1])
        msg = bot.send_message(user_id, f"How much ৳ to reward User {target_id} for this task?")
        bot.register_next_step_handler(msg, process_task_reward, target_id)
        bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=None)
    elif call.data.startswith("reject_"):
        target_id = int(call.data.split("_")[1])
        try:
            bot.send_message(target_id, "❌ Your recent task submission was **Rejected** by the Admin.", parse_mode="Markdown")
        except:
            pass
        bot.edit_message_text("Task Rejected. User notified.", user_id, call.message.message_id, reply_markup=None)

# --- Admin Step Functions ---
def process_ban(message):
    target_user = get_user_by_input(message.text)
    if target_user:
        ban_user(target_user['_id'])
        bot.reply_to(message, f"Successfully banned User: {target_user.get('username') or target_user['_id']}.")
    else:
        bot.reply_to(message, "User not found in database. Make sure they have started the bot before.")

def process_unban(message):
    target_user = get_user_by_input(message.text)
    if target_user:
        unban_user(target_user['_id'])
        bot.reply_to(message, f"Successfully unbanned User: {target_user.get('username') or target_user['_id']}.")
    else:
        bot.reply_to(message, "User not found in database.")

def process_balance_user_input(message):
    target_user = get_user_by_input(message.text)
    if target_user:
        msg = bot.reply_to(message, f"Current balance: {target_user.get('balance', 0)} ৳\nSend the new balance amount for {target_user.get('username') or target_user['_id']}:")
        bot.register_next_step_handler(msg, process_balance_amount, target_user['_id'])
    else:
        bot.reply_to(message, "User not found in database.")

def process_balance_amount(message, target_id):
    try:
        amount = int(message.text)
        update_user_balance(target_id, amount)
        bot.reply_to(message, f"Balance has been updated to {amount} ৳.")
    except ValueError:
        bot.reply_to(message, "Invalid amount. Must be a number.")

def process_add_channel(message):
    channel = message.text.strip()
    if not channel.startswith('@'):
        return bot.reply_to(message, "Invalid format. Channel must start with '@' (e.g. @mychannel).")
    
    set_mandatory_channel(channel)
    bot.reply_to(message, f"Channel set to {channel}.\nAll users must now join this channel.")

def process_task_title(message):
    title = message.text.strip()
    msg = bot.reply_to(message, f"Task Title set to: {title}\nNow, send the **URL Link** for this task:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_task_url, title)

def process_task_url(message, title):
    url = message.text.strip()
    if not url.startswith("http"):
        return bot.reply_to(message, "Invalid URL. Please start again from /admin and provide a valid link (e.g., https://youtube.com).")
    
    add_task(title, url)
    bot.reply_to(message, f"✅ Task added successfully!\nTitle: {title}\nURL: {url}")

def process_ref_bonus(message):
    try:
        bonus = int(message.text)
        set_ref_bonus(bonus)
        bot.reply_to(message, f"✅ Referral bonus updated to {bonus} ৳.")
    except ValueError:
        bot.reply_to(message, "Invalid amount. Must be a number.")

def process_task_submission(message):
    user_id = message.from_user.id
    if not ADMIN_IDS:
        return bot.reply_to(message, "❌ Cannot submit task. No Admin ID is configured in the bot.")
    
    bot.reply_to(message, "✅ Your task proof has been sent to the Admin for review! You will be notified soon.")
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
    )
    
    admin_id = ADMIN_IDS[0] # Send to the primary admin
    username_text = f" (@{message.from_user.username})" if message.from_user.username else ""
    caption = f"📩 **New Task Submission**\nFrom User ID: `{user_id}`{username_text}"
    
    try:
        if message.photo:
            bot.send_photo(admin_id, message.photo[-1].file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(admin_id, f"{caption}\n\n**Proof Text:**\n{message.text}", parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to send task to admin: {e}")

def process_task_reward(message, target_id):
    try:
        amount = int(message.text)
        user = get_user(target_id)
        new_balance = user.get("balance", 0) + amount
        update_user_balance(target_id, new_balance)
        bot.reply_to(message, f"✅ User {target_id} has been rewarded {amount} ৳.")
        try:
            bot.send_message(target_id, f"🎉 **Task Approved!**\nYou have been rewarded **{amount} ৳**.", parse_mode="Markdown")
        except:
            pass
    except ValueError:
        bot.reply_to(message, "Invalid amount. Must be a number. Start over from the admin panel if needed.")

def send_all_users_report(admin_id):
    try:
        users = get_all_users()
        if not users:
            return bot.send_message(admin_id, "No users found in database.")
        
        report = "👥 **All Users Report**\n\n"
        for u in users:
            uid = u.get('_id', 'Unknown')
            uname = f"@{u.get('username')}" if u.get('username') else "N/A"
            bal = u.get('balance', 0)
            ban = "Yes" if u.get('banned') else "No"
            report += f"ID: `{uid}` | User: {uname} | Bal: {bal}৳ | Banned: {ban}\n"
        
        if len(report) > 3500:
            file_path = f"users_report_{admin_id}.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report)
            with open(file_path, "rb") as f:
                bot.send_document(admin_id, f, caption="Users Report is too long for a single message.")
            os.remove(file_path)
        else:
            bot.send_message(admin_id, report, parse_mode="Markdown")
    except Exception as e:
        print(f"Error generating users report: {e}")
        bot.send_message(admin_id, f"❌ Error generating report: {e}")


# --- Text Message Handler ---
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username
    user = get_user(user_id, username)

    if user.get("banned"):
        return

    if not check_join(user_id):
        return bot.reply_to(
            message, 
            "⚠️ You must join our official channel to use this bot!", 
            reply_markup=get_join_keyboard()
        )

    text = message.text
    if text == "One Task":
        tasks = get_all_tasks()
        if not tasks:
            bot.reply_to(message, "📝 There are no tasks available right now.")
        else:
            bot.reply_to(message, "📝 Available Tasks:", reply_markup=get_tasks_keyboard())
    elif text == "Daily Task":
        bot.reply_to(message, "📅 You selected: Daily Task\nComplete your daily task to earn rewards!")
    elif text == "Invite":
        bot.reply_to(message, f"🔗 Here is your personal invite link: https://t.me/{bot.get_me().username}?start={user_id}\n\nInvite friends to earn {get_ref_bonus()} ৳ per referral!")
    elif text == "Balance":
        balance = user.get("balance", 0)
        bot.reply_to(message, f"💰 Balance: {balance} ৳")
    elif text == "FAQ":
        bot.reply_to(message, "❓ Frequently Asked Questions:\n1. How to earn? Complete tasks.\n2. How to invite? Use your invite link.")
    elif text == "✅ Submit Task":
        msg = bot.reply_to(message, "Please upload a screenshot or type your proof of completion to submit the task:")
        bot.register_next_step_handler(msg, process_task_submission)
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
    print("Bot configuration loaded.")
