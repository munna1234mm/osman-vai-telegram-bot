import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Update, InlineKeyboardMarkup, InlineKeyboardButton
import os
from fastapi import FastAPI, Request
import uvicorn
import json

# --- Configurations ---
TOKEN = os.getenv("BOT_TOKEN", "8243932163:AAFRMmbcIJqQgbQCrSpJIiHpKesHS5mH-LI")
bot = telebot.TeleBot(TOKEN)
app = FastAPI()

ADMIN_IDS = []

DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading DB: {e}")
    return {"users": {}, "settings": {}, "tasks": []}

def save_db():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print(f"Error saving DB: {e}")

db = load_db()



# --- Helper Functions for Database ---
def get_user(user_id, username=None):
    uid_str = str(user_id)
    if uid_str not in db["users"]:
        db["users"][uid_str] = {
            "_id": user_id, 
            "balance": 0, 
            "hold_balance": 0, 
            "completed_tasks": 0,
            "rejected_tasks": 0,
            "active_referrals": 0,
            "inactive_referrals": 0,
            "referred_by": None,
            "banned": False, 
            "username": username.lower() if username else None
        }
        save_db()
    
    user = db["users"][uid_str]
    # Retroactive fix for users without these fields
    needs_save = False
    if "hold_balance" not in user:
        user["hold_balance"] = 0
        needs_save = True
    if "completed_tasks" not in user:
        user["completed_tasks"] = 0
        needs_save = True
    if "rejected_tasks" not in user:
        user["rejected_tasks"] = 0
        needs_save = True
    if "active_referrals" not in user:
        user["active_referrals"] = 0
        needs_save = True
    if "inactive_referrals" not in user:
        user["inactive_referrals"] = 0
        needs_save = True
    if "referred_by" not in user:
        user["referred_by"] = None
        needs_save = True
    
    if needs_save:
        save_db()
        
    if username and user.get("username") != username.lower():
        user["username"] = username.lower()
        save_db()
        
    return user

def get_user_by_input(input_str):
    """ Tries to find a user by ID or username """
    try:
        uid_str = str(int(input_str))
        if uid_str in db["users"]:
            return db["users"][uid_str]
    except ValueError:
        clean_username = input_str.replace('@', '').lower().strip()
        for user in db["users"].values():
            if user.get("username") == clean_username:
                return user
    return None

def update_user_balance(user_id, amount):
    uid_str = str(user_id)
    if uid_str in db["users"]:
        db["users"][uid_str]["balance"] = amount
    else:
        db["users"][uid_str] = {"_id": user_id, "balance": amount, "hold_balance": 0, "banned": False, "username": None}
    save_db()

def update_user_hold_balance(user_id, amount):
    uid_str = str(user_id)
    if uid_str in db["users"]:
        db["users"][uid_str]["hold_balance"] = amount
    else:
        db["users"][uid_str] = {"_id": user_id, "balance": 0, "hold_balance": amount, "banned": False, "username": None}
    save_db()

def ban_user(user_id):
    uid_str = str(user_id)
    if uid_str in db["users"]:
        db["users"][uid_str]["banned"] = True
        save_db()

def unban_user(user_id):
    uid_str = str(user_id)
    if uid_str in db["users"]:
        db["users"][uid_str]["banned"] = False
        save_db()

def get_mandatory_channel():
    return db["settings"].get("mandatory_channel")

def set_mandatory_channel(channel_id):
    db["settings"]["mandatory_channel"] = channel_id
    save_db()

def get_ref_bonus():
    return db["settings"].get("referral_bonus", 0)

def set_ref_bonus(amount):
    db["settings"]["referral_bonus"] = amount
    save_db()

def get_payment_methods():
    if "payment_methods" not in db["settings"]:
        db["settings"]["payment_methods"] = ["Bkash", "Nagad"]
        save_db()
    return db["settings"]["payment_methods"]

def add_payment_method(name):
    methods = get_payment_methods()
    if name not in methods:
        methods.append(name)
        db["settings"]["payment_methods"] = methods
        save_db()

def remove_payment_method(name):
    methods = get_payment_methods()
    if name in methods:
        methods.remove(name)
        db["settings"]["payment_methods"] = methods
        save_db()

def add_task(title, url, limit, tutorial_url=None):
    import uuid
    task_id = str(uuid.uuid4())
    task_doc = {
        "_id": task_id, 
        "title": title, 
        "url": url, 
        "limit": limit, 
        "completed_count": 0,
        "tutorial_url": tutorial_url
    }
    db["tasks"].append(task_doc)
    save_db()

def delete_task(task_id):
    db["tasks"] = [t for t in db["tasks"] if t["_id"] != task_id]
    save_db()

def get_all_users():
    return list(db["users"].values())

def get_all_tasks():
    return db["tasks"]

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
        KeyboardButton("My Profile"),
        KeyboardButton("📊 Status"),
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
        InlineKeyboardButton("💼 Edit Hold Balance", callback_data="admin_hold_balance")
    )
    markup.add(
        InlineKeyboardButton("🎁 Set Ref Bonus", callback_data="admin_ref_bonus"),
        InlineKeyboardButton("➕ Add Task", callback_data="admin_add_task")
    )
    markup.add(
        InlineKeyboardButton("⚙️ Manage Methods", callback_data="admin_methods"),
        InlineKeyboardButton("👥 View All Users", callback_data="admin_view_users")
    )
    markup.add(
        InlineKeyboardButton("📢 Add/Change Channel", callback_data="admin_channel"),
        InlineKeyboardButton("🗑️ Remove Channel", callback_data="admin_rm_channel")
    )
    markup.add(
        InlineKeyboardButton("🗑️ Remove Task", callback_data="admin_remove_task"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
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

def get_single_task_keyboard(task_id, url, tutorial_url=None):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 Go to Task", url=url))
    if tutorial_url:
        markup.add(InlineKeyboardButton("📺 Tutorial", url=tutorial_url))
    markup.add(InlineKeyboardButton("✅ Submit This Task", callback_data=f"submit_task_{task_id}"))
    return markup

# --- Core Command Handlers ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Check if this is a new user for referral
    is_new = False
    uid_str = str(user_id)
    if uid_str not in db["users"]:
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
                    user["referred_by"] = referrer_id
                    referrer["inactive_referrals"] = referrer.get("inactive_referrals", 0) + 1
                    save_db()
                    bot.send_message(referrer_id, f"🎉 Someone joined using your invite link! They are currently an **Inactive** referral. Once they complete their first task, you will receive 10 ৳ balance.", parse_mode="Markdown")
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

    msg_text = f"⚙️ Welcome to the Admin Panel!\n💾 DB Status: JSON Local (Active)\n\nChoose an action:"
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
    elif call.data == "admin_hold_balance":
        msg = bot.send_message(user_id, "Send the User ID or @username to edit **Hold Balance**:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_hold_balance_user_input)
    elif call.data == "admin_methods":
        show_manage_methods(user_id)
    elif call.data.startswith("rm_method_"):
        method = call.data.replace("rm_method_", "")
        remove_payment_method(method)
        show_manage_methods(user_id)
    elif call.data == "admin_add_method":
        msg = bot.send_message(user_id, "Send the name of the new Payment Method (e.g., Rocket):")
        bot.register_next_step_handler(msg, process_add_method)
    elif call.data == "user_withdraw":
        methods = get_payment_methods()
        if not methods:
            return bot.answer_callback_query(call.id, "No payment methods available. Contact Admin.")
        markup = InlineKeyboardMarkup()
        for m in methods:
            markup.add(InlineKeyboardButton(m, callback_data=f"wd_method_{m}"))
        bot.edit_message_text("💳 Select your preferred payment method:", user_id, call.message.message_id, reply_markup=markup)
    elif call.data.startswith("wd_method_"):
        method = call.data.replace("wd_method_", "")
        msg = bot.edit_message_text(f"Selected: {method}\n\nSend your withdrawal Number (e.g., your Bkash Number):", user_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_withdraw_number, method)
    elif call.data.startswith("wd_app_"):
        # Format: wd_app_USERID_AMOUNT_METHOD_NUMBER
        parts = call.data.split("_")
        target_id = int(parts[2])
        amount = int(parts[3])
        method = parts[4]
        number = parts[5]
        
        user = get_user(target_id)
        if user.get("balance", 0) < amount:
            return bot.answer_callback_query(call.id, "User does not have enough balance anymore!", show_alert=True)
        
        new_balance = user["balance"] - amount
        update_user_balance(target_id, new_balance)
        
        bot.edit_message_text(f"✅ Withdrawal Approved!\nUser: {target_id}\nAmount: {amount}৳\nMethod: {method}\nNumber: {number}", user_id, call.message.message_id, reply_markup=None)
        try:
            bot.send_message(target_id, f"✅ **Withdrawal Approved!**\n{amount} ৳ has been sent to your {method} account ({number}).", parse_mode="Markdown")
        except:
            pass
    elif call.data.startswith("wd_rej_"):
        parts = call.data.split("_")
        target_id = int(parts[2])
        bot.edit_message_text("❌ Withdrawal Request Rejected.", user_id, call.message.message_id, reply_markup=None)
        try:
            bot.send_message(target_id, "❌ Your recent withdrawal request was **Rejected** by the Admin.", parse_mode="Markdown")
        except:
            pass
    elif call.data == "admin_remove_task":
        tasks = get_all_tasks()
        if not tasks:
            return bot.answer_callback_query(call.id, "No tasks to remove.")
        markup = InlineKeyboardMarkup()
        for t in tasks:
            markup.add(InlineKeyboardButton(f"🗑️ {t['title']}", callback_data=f"del_task_{t['_id']}"))
        bot.send_message(user_id, "Select a task to **Permanently Delete**:", parse_mode="Markdown", reply_markup=markup)
    elif call.data.startswith("del_task_"):
        task_id = call.data.replace("del_task_", "")
        delete_task(task_id)
        bot.answer_callback_query(call.id, "Task Deleted!")
        bot.edit_message_text("✅ Task has been removed.", user_id, call.message.message_id)
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
    elif call.data == "admin_broadcast":
        msg = bot.send_message(user_id, "📣 **Broadcast Message**\n\nSend the message you want to broadcast to **ALL users**.\nYou can send text or a photo with a caption.", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_broadcast)
    elif call.data == "admin_view_users":
        send_all_users_report(user_id)
    elif call.data.startswith("submit_task_"):
        task_id = call.data.split("submit_task_")[1]
        msg = bot.send_message(user_id, "Please upload a screenshot or type your proof of completion for this task:")
        bot.register_next_step_handler(msg, process_task_submission, task_id)
    elif call.data.startswith("app_"):
        # Format: app_USERID_TASKID
        parts = call.data.split("_")
        target_id = int(parts[1])
        task_id = parts[2]
        msg = bot.send_message(user_id, f"How much ৳ to reward User {target_id} for this task?")
        bot.register_next_step_handler(msg, process_task_reward, target_id, task_id)
        bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=None)
    elif call.data.startswith("rej_"):
        parts = call.data.split("_")
        target_id = int(parts[1])
        user = get_user(target_id)
        user["rejected_tasks"] = user.get("rejected_tasks", 0) + 1
        save_db()
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

def process_hold_balance_user_input(message):
    target_user = get_user_by_input(message.text)
    if target_user:
        msg = bot.reply_to(message, f"Current Hold Balance: {target_user.get('hold_balance', 0)} ৳\nSend the new Hold Balance amount for {target_user.get('username') or target_user['_id']}:")
        bot.register_next_step_handler(msg, process_hold_balance_amount, target_user['_id'])
    else:
        bot.reply_to(message, "User not found in database.")

def process_hold_balance_amount(message, target_id):
    try:
        amount = int(message.text)
        update_user_hold_balance(target_id, amount)
        bot.reply_to(message, f"Hold Balance has been updated to {amount} ৳.")
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
    
    msg = bot.reply_to(message, "How many users can complete this task? (Enter a number for the limit):")
    bot.register_next_step_handler(msg, process_task_limit, title, url)

def process_task_limit(message, title, url):
    try:
        limit = int(message.text.strip())
        msg = bot.reply_to(message, "Tutorial Link (Optional):\n\nSend the URL (e.g. YouTube video) or type 'skip':")
        bot.register_next_step_handler(msg, process_task_tutorial, title, url, limit)
    except ValueError:
        bot.reply_to(message, "Invalid number. Please try adding the task again from /admin.")

def process_task_tutorial(message, title, url, limit):
    tutorial_url = message.text.strip()
    if tutorial_url.lower() == 'skip':
        tutorial_url = None
    elif not tutorial_url.startswith("http"):
        return bot.reply_to(message, "Invalid URL. Please send a valid link starting with http:// or https://, or type 'skip'.")
    
    add_task(title, url, limit, tutorial_url)
    tut_text = f"\nTutorial: {tutorial_url}" if tutorial_url else ""
    bot.reply_to(message, f"✅ Task added successfully!\nTitle: {title}\nURL: {url}\nLimit: {limit} users{tut_text}")

def process_broadcast(message):
    admin_id = message.from_user.id
    users = get_all_users()
    if not users:
        return bot.reply_to(message, "No users found in database.")

    bot.send_message(admin_id, f"🚀 Starting broadcast to {len(users)} users... Please wait.")
    
    success = 0
    fail = 0
    
    for u in users:
        target_id = u.get('_id')
        try:
            if message.photo:
                bot.send_photo(target_id, message.photo[-1].file_id, caption=message.caption, caption_entities=message.caption_entities)
            else:
                bot.send_message(target_id, message.text, entities=message.entities)
            success += 1
        except Exception as e:
            fail += 1
            print(f"Broadcast failed for user {target_id}: {e}")
            
    bot.send_message(admin_id, f"✅ **Broadcast Finished!**\n\n🟢 Success: {success}\n🔴 Failed: {fail}", parse_mode="Markdown")

def process_ref_bonus(message):
    try:
        bonus = int(message.text)
        set_ref_bonus(bonus)
        bot.reply_to(message, f"✅ Referral bonus updated to {bonus} ৳.")
    except ValueError:
        bot.reply_to(message, "Invalid amount. Must be a number.")

def process_task_submission(message, task_id):
    user_id = message.from_user.id
    if not ADMIN_IDS:
        return bot.reply_to(message, "❌ Cannot submit task. No Admin ID is configured in the bot.")
    
    bot.reply_to(message, "✅ Your task proof has been sent to the Admin for review! You will be notified soon.")
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"app_{user_id}_{task_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user_id}_{task_id}")
    )
    
    admin_id = ADMIN_IDS[0] # Send to the primary admin
    username_text = f" (@{message.from_user.username})" if message.from_user.username else ""
    caption = f"📩 **New Task Submission**\nFrom User ID: `{user_id}`{username_text}\nTask ID: `{task_id}`"
    
    try:
        if message.photo:
            bot.send_photo(admin_id, message.photo[-1].file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(admin_id, f"{caption}\n\n**Proof Text:**\n{message.text}", parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to send task to admin: {e}")

def process_task_reward(message, target_id, task_id):
    try:
        amount = int(message.text)
        user = get_user(target_id)
        new_balance = user.get("balance", 0) + amount
        update_user_balance(target_id, new_balance)
        # Referral Bonus Logic (Only on first task)
        if user.get("completed_tasks", 0) == 0:
            referrer_id = user.get("referred_by")
            if referrer_id:
                referrer = get_user(referrer_id)
                if referrer:
                    # Award 10 TK bonus to referrer
                    new_ref_balance = referrer.get("balance", 0) + 10
                    update_user_balance(referrer_id, new_ref_balance)
                    
                    # Update counts
                    referrer["active_referrals"] = referrer.get("active_referrals", 0) + 1
                    referrer["inactive_referrals"] = max(0, referrer.get("inactive_referrals", 0) - 1)
                    save_db()
                    
                    try:
                        bot.send_message(referrer_id, "🎊 Your referral just completed their first task! You received **10 ৳** referral bonus.", parse_mode="Markdown")
                    except:
                        pass

        user["completed_tasks"] = user.get("completed_tasks", 0) + 1
        save_db()
        for i, task in enumerate(db["tasks"]):
            if task["_id"] == task_id:
                task["completed_count"] += 1
                if task["completed_count"] >= task.get("limit", 0):
                    del db["tasks"][i]
                save_db()
                break
                
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
            h_bal = u.get('hold_balance', 0)
            ban = "Yes" if u.get('banned') else "No"
            report += f"ID: `{uid}`|User: {uname}|Bal: {bal}৳|Hold: {h_bal}৳|Ban: {ban}\n"
        
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

def show_manage_methods(admin_id):
    methods = get_payment_methods()
    markup = InlineKeyboardMarkup()
    for m in methods:
        markup.add(InlineKeyboardButton(f"❌ Remove {m}", callback_data=f"rm_method_{m}"))
    markup.add(InlineKeyboardButton("➕ Add Method", callback_data="admin_add_method"))
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_admin"))
    
    text = "⚙️ **Manage Payment Methods**\n\nCurrent methods:"
    if not methods:
        text += "\nNone"
    else:
        for m in methods:
            text += f"\n- {m}"
    
    bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=markup)

def process_add_method(message):
    name = message.text.strip()
    add_payment_method(name)
    bot.reply_to(message, f"✅ Added '{name}' to payment methods.")
    show_manage_methods(message.from_user.id)

def process_withdraw_number(message, method):
    user_id = message.from_user.id
    number = message.text.strip()
    msg = bot.send_message(user_id, f"Method: {method}\nNumber: {number}\n\nHow much ৳ do you want to withdraw?")
    bot.register_next_step_handler(msg, process_withdraw_amount, method, number)

def process_withdraw_amount(message, method, number):
    user_id = message.from_user.id
    try:
        amount = int(message.text.strip())
        user = get_user(user_id)
        if amount < 20:
            return bot.reply_to(message, "❌ Minimum withdrawal is 20 ৳.")
        if user["balance"] < amount:
            return bot.reply_to(message, "❌ Insufficient balance!")

        bot.reply_to(message, "✅ Your withdrawal request has been sent to the Admin!")
        
        # Notify Admin
        admin_id = ADMIN_IDS[0] if ADMIN_IDS else user_id
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"wd_app_{user_id}_{amount}_{method}_{number}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"wd_rej_{user_id}")
        )
        caption = f"💰 **New Withdrawal Request**\nUser: `{user_id}`\nAmount: {amount}৳\nMethod: {method}\nNumber: `{number}`"
        bot.send_message(admin_id, caption, parse_mode="Markdown", reply_markup=markup)
        
    except ValueError:
        bot.reply_to(message, "Invalid amount. Please try again.")


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
            bot.reply_to(message, "**📝 বর্তমান কোনো কাজ নেই**", parse_mode="Markdown")
        else:
            bot.reply_to(message, "**📝 Available Tasks:**", parse_mode="Markdown")
            for task in tasks:
                task_id = str(task.get('_id', ''))
                title = task.get('title', 'Task')
                url = task.get('url', '')
                tut_url = task.get('tutorial_url')
                limit = task.get('limit', 0)
                completed = task.get('completed_count', 0)
                
                text = f"📌 **{title}**\n👥 Slots: {completed}/{limit} completed"
                bot.send_message(message.chat.id, text, reply_markup=get_single_task_keyboard(task_id, url, tut_url), parse_mode="Markdown")
    elif text == "Daily Task":
        bot.reply_to(message, "**📝 বর্তমান কোনো কাজ নেই**", parse_mode="Markdown")
    elif text == "Invite":
        active = user.get("active_referrals", 0)
        inactive = user.get("inactive_referrals", 0)
        invite_msg = (
            f"✅ Active {active}.0 রেফার\n"
            f"❌ Inactive {inactive}.0 রেফার\n"
            f"👥 প্রতি রেফার ১০ টাকা\n\n"
            f"👥 Invite লিংক 👇\n"
            f"https://t.me/{bot.get_me().username}?start={user_id}"
        )
        bot.reply_to(message, invite_msg)
    elif text == "Balance":
        balance = user.get("balance", 0)
        hold = user.get("hold_balance", 0)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 Withdraw", callback_data="user_withdraw"))
        bot.reply_to(message, f"💰 **Available Balance: {balance} ৳**\n💼 **Hold Balance: {hold} ৳**", parse_mode="Markdown", reply_markup=markup)
    elif text == "My Profile":
        balance = user.get("balance", 0)
        hold = user.get("hold_balance", 0)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 Withdraw", callback_data="user_withdraw"))
        profile_text = (
            f"🧑‍💻 **My Profile ID: `{user_id}`**\n\n"
            f"💰 **Available Balance: {balance} ৳**\n"
            f"💼 **Hold Balance: {hold} ৳**\n\n"
            f"💸 **মিনিমাম উইথড্র মাএ ২০ টাকা** 💸\n"
            f"🧑‍💻 **পেমেন্ট বিকাশ/নগদ** 🏧"
        )
        bot.reply_to(message, profile_text, parse_mode="Markdown", reply_markup=markup)
    elif text == "📊 Status":
        comp = user.get("completed_tasks", 0)
        rej = user.get("rejected_tasks", 0)
        status_text = (
            f"📊 **আপনার কাজের হিস্টোরি 👇**\n\n"
            f"✅ **কমপিল্ট : {comp} টা কাজ**\n"
            f"❌ **রিজেক্ট : {rej} টা কাজ**"
        )
        bot.reply_to(message, status_text, parse_mode="Markdown")
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

@app.get("/ping")
def ping():
    return {"status": "alive", "message": "Bot is awake!"}

@app.get("/")
def home():
    return {"status": "Bot is running on Render!", "ping_endpoint": "/ping"}

if __name__ == '__main__':
    print("Bot configuration loaded.")
