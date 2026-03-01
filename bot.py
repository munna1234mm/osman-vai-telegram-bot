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

def add_task(title, url, limit, reward, task_type, tutorial_url=None, image_file_id=None):
    import uuid
    task_id = str(uuid.uuid4())
    task_doc = {
        "_id": task_id, 
        "title": title, 
        "url": url, 
        "limit": limit, 
        "reward": reward,
        "type": task_type, # 'one_task' or 'daily_task'
        "completed_count": 0,
        "tutorial_url": tutorial_url,
        "image_file_id": image_file_id
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
        KeyboardButton("📝 কাজ করুন"),
        KeyboardButton("🎁 ডেইলি টাস্ক"),
        KeyboardButton("👥 রেফার করুন"),
        KeyboardButton("💳 উইথড্র"),
        KeyboardButton("🧑‍💻 আমার প্রোফাইল"),
        KeyboardButton("📊 স্ট্যাটাস"),
        KeyboardButton("❓ প্রশ্ন ও উত্তর")
    )
    return markup

def get_admin_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🚫 ইউজার ব্যান করুন", callback_data="admin_ban"),
        InlineKeyboardButton("🟢 ইউজার আনব্যান করুন", callback_data="admin_unban")
    )
    markup.add(
        InlineKeyboardButton("💰 ব্যালেন্স এডিট", callback_data="admin_balance"),
        InlineKeyboardButton("💼 হোল্ড ব্যালেন্স এডিট", callback_data="admin_hold_balance")
    )
    markup.add(
        InlineKeyboardButton("🎁 রেফার বোনাস সেট", callback_data="admin_ref_bonus"),
        InlineKeyboardButton("➕ কাজ যোগ করুন", callback_data="admin_add_task")
    )
    markup.add(
        InlineKeyboardButton("⚙️ মেথড ম্যানেজ", callback_data="admin_methods"),
        InlineKeyboardButton("👥 সব ইউজার দেখুন", callback_data="admin_view_users")
    )
    markup.add(
        InlineKeyboardButton("📢 চ্যানেল যোগ/পরিবর্তন", callback_data="admin_channel"),
        InlineKeyboardButton("🗑️ চ্যানেল রিমুভ", callback_data="admin_rm_channel")
    )
    markup.add(
        InlineKeyboardButton("🗑️ কাজ রিমুভ", callback_data="admin_remove_task"),
        InlineKeyboardButton("📢 ব্রডকাস্ট", callback_data="admin_broadcast")
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
    markup.add(InlineKeyboardButton("👉 কাজের লিংক 👈", url=url))
    if tutorial_url:
        markup.add(InlineKeyboardButton("👉 কাজের ভিডিও 👈", url=tutorial_url))
    markup.add(InlineKeyboardButton("👉 প্রুফ জমা করুন 👈", callback_data=f"submit_task_{task_id}"))
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
        return bot.reply_to(message, "আপনি এই বটটি ব্যবহার করতে পারছেন না কারণ আপনাকে ব্যান করা হয়েছে।")
        
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
                    bot.send_message(referrer_id, f"🎉 কেউ আপনার ইনভাইট লিংক ব্যবহার করে জয়েন করেছেন! তারা বর্তমানে **Inactive** মেম্বার হিসেবে আছেন। যখন তারা তাদের প্রথম কাজ শেষ করবেন, আপনি ১০ ৳ ব্যালেন্স পাবেন।", parse_mode="Markdown")
        except ValueError:
            pass

    welcome_text = (
        "<b>Earnx Box-এ স্বাগতম 🎁</b>\n\n"
        "<b>🎁 আমাদের বটে আপনাকে স্বাগতম ফ্রিতে ইনকাম করতে চাইলে আমাদের সাথে থাকুন 🤝</b>"
    )
    bot.reply_to(
        message, 
        welcome_text, 
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "আপনার এই কমান্ডটি ব্যবহার করার অনুমতি নেই।")

    msg_text = f"⚙️ অ্যাডমিন প্যানেলে স্বাগতম!\n💾 ডাটাবেস স্ট্যাটাস: JSON লোকাল (সক্রিয়)\n\nএকটি অ্যাকশন বেছে নিন:"
    bot.reply_to(message, msg_text, reply_markup=get_admin_keyboard())

# --- Callback Handlers ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    if call.data == "check_join":
        if check_join(user_id):
            bot.answer_callback_query(call.id, "ভেরিফিকেশন সফল হয়েছে!", show_alert=True)
            welcome_text = (
                "<b>Earnx Box-এ স্বাগতম 🎁</b>\n\n"
                "<b>🎁 আমাদের বটে আপনাকে স্বাগতম ফ্রিতে ইনকাম করতে চাইলে আমাদের সাথে থাকুন 🤝</b>"
            )
            bot.send_message(user_id, welcome_text, reply_markup=get_main_keyboard(), parse_mode="HTML")
        else:
            bot.answer_callback_query(call.id, "আপনি এখনো চ্যানেলটি জয়েন করেননি।", show_alert=True)
        return

    if not is_admin(user_id):
        return bot.answer_callback_query(call.id, "এক্সেস ডিনাইড।")

    if call.data == "admin_ban":
        msg = bot.send_message(user_id, "ব্যান করতে ইউজার আইডি অথবা @ইউজারনেম পাঠান:")
        bot.register_next_step_handler(msg, process_ban)
    elif call.data == "admin_unban":
        msg = bot.send_message(user_id, "আনব্যান করতে ইউজার আইডি অথবা @ইউজারনেম পাঠান:")
        bot.register_next_step_handler(msg, process_unban)
    elif call.data == "admin_balance":
        msg = bot.send_message(user_id, "ব্যালেন্স এডিট করতে ইউজার আইডি অথবা @ইউজারনেম পাঠান:")
        bot.register_next_step_handler(msg, process_balance_user_input)
    elif call.data == "admin_hold_balance":
        msg = bot.send_message(user_id, "**হোল্ড ব্যালেন্স** এডিট করতে ইউজার আইডি অথবা @ইউজারনেম পাঠান:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_hold_balance_user_input)
    elif call.data == "admin_methods":
        show_manage_methods(user_id)
    elif call.data.startswith("rm_method_"):
        method = call.data.replace("rm_method_", "")
        remove_payment_method(method)
        show_manage_methods(user_id)
    elif call.data == "admin_add_method":
        msg = bot.send_message(user_id, "নতুন পেমেন্ট মেথড এর নাম পাঠান (যেমন: রকেট):")
        bot.register_next_step_handler(msg, process_add_method)
    elif call.data == "user_withdraw":
        methods = get_payment_methods()
        if not methods:
            return bot.answer_callback_query(call.id, "কোনো পেমেন্ট মেথড পাওয়া যায়নি। এডমিনের সাথে যোগাযোগ করুন।")
        markup = InlineKeyboardMarkup()
        for m in methods:
            markup.add(InlineKeyboardButton(m, callback_data=f"wd_method_{m}"))
        bot.edit_message_text("💳 আপনার পছন্দের পেমেন্ট মেথড টি সিলেক্ট করুন:", user_id, call.message.message_id, reply_markup=markup)
    elif call.data.startswith("wd_method_"):
        method = call.data.replace("wd_method_", "")
        msg = bot.edit_message_text(f"সিলেক্ট করা হয়েছে: {method}\n\nআপনার উইথড্র নাম্বার পাঠান (যেমন: বিকাশ নাম্বার):", user_id, call.message.message_id)
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
            return bot.answer_callback_query(call.id, "ইউজারের পর্যাপ্ত ব্যালেন্স নেই!", show_alert=True)
        
        new_balance = user["balance"] - amount
        update_user_balance(target_id, new_balance)
        
        bot.edit_message_text(f"✅ উইথড্রাল সফল হয়েছে!\nইউজার: {target_id}\nপরিমাণ: {amount}৳\nমেথড: {method}\nনাম্বার: {number}", user_id, call.message.message_id, reply_markup=None)
        try:
            bot.send_message(target_id, f"✅ **উইথড্রাল সফল হয়েছে!**\n{amount} ৳ আপনার {method} একাউন্টে ({number}) পাঠিয়ে দেওয়া হয়েছে।", parse_mode="Markdown")
        except:
            pass
    elif call.data.startswith("wd_rej_"):
        parts = call.data.split("_")
        target_id = int(parts[2])
        bot.edit_message_text("❌ উইথড্রাল রিকোয়েস্ট বাতিল করা হয়েছে।", user_id, call.message.message_id, reply_markup=None)
        try:
            bot.send_message(target_id, "❌ আপনার উইথড্রাল রিকোয়েস্টটি অ্যাডমিন বাতিল করেছেন।", parse_mode="Markdown")
        except:
            pass
    elif call.data == "admin_remove_task":
        tasks = get_all_tasks()
        if not tasks:
            return bot.answer_callback_query(call.id, "মুছার মতো কোনো কাজ নেই।")
        markup = InlineKeyboardMarkup()
        for t in tasks:
            markup.add(InlineKeyboardButton(f"🗑️ {t['title']}", callback_data=f"del_task_{t['_id']}"))
        bot.send_message(user_id, "স্থায়ীভাবে মুছতে একটি কাজ বেছে নিন:", parse_mode="Markdown", reply_markup=markup)
    elif call.data.startswith("del_task_"):
        task_id = call.data.replace("del_task_", "")
        delete_task(task_id)
        bot.answer_callback_query(call.id, "কাজটি মুছে ফেলা হয়েছে!")
        bot.edit_message_text("✅ টাস্ক রিমুভ করা হয়েছে।", user_id, call.message.message_id)
    elif call.data == "admin_channel":
        msg = bot.send_message(user_id, "চ্যানেলের ইউজারনেম পাঠান (যেমন: @mychannel):\n\n*নিশ্চিত করুন যে এই বটটিকে চ্যানেলে অ্যাডমিন হিসেবে অ্যাড করা হয়েছে!*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_channel)
    elif call.data == "admin_rm_channel":
        set_mandatory_channel(None)
        bot.send_message(user_id, "চ্যানেল ভেরিফিকেশন রিমুভ করা হয়েছে।")
    elif call.data == "admin_add_task":
        msg = bot.send_message(user_id, "নতুন কাজের **টাইটেল** পাঠান (যেমন: 'ইউটিউব সাবস্ক্রাইব'):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_task_title)
    elif call.data == "admin_ref_bonus":
        msg = bot.send_message(user_id, f"বর্তমান রেফার বোনাস: {get_ref_bonus()} ৳\n\n**নতুন পরিমাণ** পাঠান (৳-এ):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_ref_bonus)
    elif call.data == "admin_broadcast":
        msg = bot.send_message(user_id, "📣 **ব্রডকাস্ট মেসেজ**\n\nআপনি সব ইউজারকে যে মেসেজটি পাঠাতে চান তা লিখুন।\nআপনি চাইলে ছবির সাথে ক্যাপশনও পাঠাতে পারেন।", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_broadcast)
    elif call.data == "admin_view_users":
        send_all_users_report(user_id)
    elif call.data.startswith("type_"):
        task_type = call.data.replace("type_", "")
        temp = db.get("temp_task", {})
        msg = bot.send_message(user_id, "টিউটোরিয়াল লিংক (ঐচ্ছিক):\n\nভিডিও লিংক পাঠান অথবা 'skip' লিখুন:")
        bot.register_next_step_handler(msg, process_task_tutorial_step, temp['title'], temp['url'], temp['reward'], temp['limit'], task_type)
    elif call.data.startswith("submit_task_"):
        task_id = call.data.split("submit_task_")[1]
        msg = bot.send_message(user_id, "🖼️ <b>Task Submit করতে (১-২) টি স্ক্রিনশট জমা করুন 👇</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_task_submission, task_id)
    elif call.data.startswith("app_"):
        # Format: app_USERID_TASKID
        parts = call.data.split("_")
        target_id = int(parts[1])
        task_id = parts[2]
        # Find the task to get its reward
        task_reward = 0
        for t in db["tasks"]:
            if t["_id"] == task_id:
                task_reward = t.get("reward", 0)
                break
        
        if task_reward > 0:
            # Auto-reward based on task definition
            process_task_reward_auto(call.message, target_id, task_id, task_reward)
        else:
            msg = bot.send_message(user_id, f"ইউজার {target_id}-কে কত টাকা রিওয়ার্ড দিতে চান?")
            bot.register_next_step_handler(msg, process_task_reward, target_id, task_id)
        bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=None)
    elif call.data.startswith("rej_"):
        parts = call.data.split("_")
        target_id = int(parts[1])
        user = get_user(target_id)
        user["rejected_tasks"] = user.get("rejected_tasks", 0) + 1
        save_db()
        try:
            bot.send_message(target_id, "❌ আপনার টাস্ক সাবমিশনটি অ্যাডমিন বাতিল করেছেন।", parse_mode="Markdown")
        except:
            pass
        bot.edit_message_text("কাজ বাতিল করা হয়েছে। ইউজারকে জানানো হয়েছে।", user_id, call.message.message_id, reply_markup=None)

# --- Admin Step Functions ---
def process_ban(message):
    target_user = get_user_by_input(message.text)
    if target_user:
        ban_user(target_user['_id'])
        bot.reply_to(message, f"ইউজারকে সফলভাবে ব্যান করা হয়েছে: {target_user.get('username') or target_user['_id']}।")
    else:
        bot.reply_to(message, "ডাটাবেজে ইউজারকে পাওয়া যায়নি। নিশ্চিত করুন যে তারা বটটি স্টার্ট করেছেন।")

def process_unban(message):
    target_user = get_user_by_input(message.text)
    if target_user:
        unban_user(target_user['_id'])
        bot.reply_to(message, f"ইউজারকে সফলভাবে আনব্যান করা হয়েছে: {target_user.get('username') or target_user['_id']}।")
    else:
        bot.reply_to(message, "ডাটাবেজে ইউজারকে পাওয়া যায়নি।")

def process_balance_user_input(message):
    target_user = get_user_by_input(message.text)
    if target_user:
        msg = bot.reply_to(message, f"বর্তমান ব্যালেন্স: {target_user.get('balance', 0)} ৳\nইউজার {target_user.get('username') or target_user['_id']} এর জন্য নতুন ব্যালেন্স পাঠান:")
        bot.register_next_step_handler(msg, process_balance_amount, target_user['_id'])
    else:
        bot.reply_to(message, "ডাটাবেজে ইউজারকে পাওয়া যায়নি।")

def process_balance_amount(message, target_id):
    try:
        amount = int(message.text)
        update_user_balance(target_id, amount)
        bot.reply_to(message, f"ব্যালেন্স আপডেট করে {amount} ৳ করা হয়েছে।")
    except ValueError:
        bot.reply_to(message, "অকার্যকর পরিমাণ। এটি অবশ্যই একটি সংখ্যা হতে হবে।")

def process_hold_balance_user_input(message):
    target_user = get_user_by_input(message.text)
    if target_user:
        msg = bot.reply_to(message, f"বর্তমান হোল্ড ব্যালেন্স: {target_user.get('hold_balance', 0)} ৳\nইউজার {target_user.get('username') or target_user['_id']} এর জন্য নতুন হোল্ড ব্যালেন্স পাঠান:")
        bot.register_next_step_handler(msg, process_hold_balance_amount, target_user['_id'])
    else:
        bot.reply_to(message, "ডাটাবেজে ইউজারকে পাওয়া যায়নি।")

def process_hold_balance_amount(message, target_id):
    try:
        amount = int(message.text)
        update_user_hold_balance(target_id, amount)
        bot.reply_to(message, f"হোল্ড ব্যালেন্স আপডেট করে {amount} ৳ করা হয়েছে।")
    except ValueError:
        bot.reply_to(message, "অকার্যকর পরিমাণ। এটি অবশ্যই একটি সংখ্যা হতে হবে।")

def process_add_channel(message):
    channel = message.text.strip()
    if not channel.startswith('@'):
        return bot.reply_to(message, "অকার্যকর ফরম্যাট। চ্যানেল অবশ্যই '@' দিয়ে শুরু হতে হবে (যেমন: @mychannel)।")
    
    set_mandatory_channel(channel)
    bot.reply_to(message, f"চ্যানেল সেট করা হয়েছে: {channel}।\nএখন সব ইউজারকে এই চ্যানেলটি জয়েন করতে হবে।")

def process_task_title(message):
    title = message.text.strip()
    msg = bot.reply_to(message, f"টাস্ক টাইটেল সেট করা হয়েছে: <b>{title}</b>\nএখন এই টাস্কের জন্য <b>URL লিংক</b> পাঠান:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_task_url, title)

def process_task_url(message, title):
    url = message.text.strip()
    if not url.startswith("http"):
        return bot.reply_to(message, "অকার্যকর URL। দয়া করে /admin থেকে আবার শুরু করুন এবং একটি সঠিক লিংক দিন (যেমন: https://youtube.com)।")
    
    msg = bot.reply_to(message, "ইউজার এই কাজের জন্য কত <b>রিওয়ার্ড (৳)</b> পাবেন?", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_task_reward_amount, title, url)

def process_task_reward_amount(message, title, url):
    try:
        reward = int(message.text.strip())
        msg = bot.reply_to(message, "কতজন ইউজার এই কাজটি করতে পারবেন? (লিমিট সংখ্যাটি লিখুন):")
        bot.register_next_step_handler(msg, process_task_limit, title, url, reward)
    except ValueError:
        bot.reply_to(message, "অকার্যকর পরিমাণ। দয়া করে আবার কাজটি যোগ করার চেষ্টা করুন।")

def process_task_limit(message, title, url, reward):
    try:
        limit = int(message.text.strip())
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📝 কাজ করুন", callback_data="type_one_task"),
            InlineKeyboardButton("🎁 ডেইলি টাস্ক", callback_data="type_daily_task")
        )
        msg = bot.send_message(message.chat.id, "<b>টাস্ক টাইপ</b> সিলেক্ট করুন:", parse_mode="HTML", reply_markup=markup)
        # Store temporary data in a global or state-based way if needed, but for simplicity here:
        # We'll use a hack by registering the next step but passing arguments
        # Wait, for callbacks we need to handle it in handle_callbacks. Let's adjust.
        # Temporary storage for task being created
        db["temp_task"] = {"title": title, "url": url, "reward": reward, "limit": limit}
    except ValueError:
        bot.reply_to(message, "অকার্যকর সংখ্যা। দয়া করে আবার কাজটি যোগ করার চেষ্টা করুন।")

def process_task_tutorial_step(message, title, url, reward, limit, task_type):
    tutorial_url = message.text.strip()
    if tutorial_url.lower() == 'skip':
        tutorial_url = None
    elif not tutorial_url.startswith("http"):
        return bot.reply_to(message, "অকার্যকর URL। দয়া করে একটি সঠিক লিংক দিন অথবা 'skip' লিখুন।")
    
    msg = bot.reply_to(message, "এই কাজের জন্য একটি <b>ছবি/ফটো</b> পাঠান, অথবা <b>'skip'</b> লিখুন:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_task_image, title, url, reward, limit, task_type, tutorial_url)

def process_task_image(message, title, url, reward, limit, task_type, tutorial_url):
    image_file_id = None
    if message.photo:
        image_file_id = message.photo[-1].file_id
    elif message.text and message.text.lower() != 'skip':
        # If user sent text instead of photo and it's not skip
        pass 
    
    add_task(title, url, limit, reward, task_type, tutorial_url, image_file_id)
    tut_text = f"\nটিউটোরিয়াল: {tutorial_url}" if tutorial_url else ""
    bot.reply_to(message, f"✅ <b>কাজটি সফলভাবে যোগ করা হয়েছে!</b>\nটাইটেল: {title}\nটাইপ: {task_type}\nরিওয়ার্ড: {reward}৳\nলিমিট: {limit} জন{tut_text}", parse_mode="HTML")

def process_broadcast(message):
    admin_id = message.from_user.id
    users = get_all_users()
    if not users:
        return bot.reply_to(message, "ডাটাবেজে কোনো ইউজার পাওয়া যায়নি।")

    bot.send_message(admin_id, f"🚀 {len(users)} জন ইউজারের কাছে ব্রডকাস্ট পাঠানো শুরু হচ্ছে... দয়া করে অপেক্ষা করুন।")
    
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
            
    bot.send_message(admin_id, f"✅ **ব্রডকাস্ট শেষ হয়েছে!**\n\n🟢 সফল: {success}\n🔴 ব্যর্থ: {fail}", parse_mode="Markdown")

def process_ref_bonus(message):
    try:
        bonus = int(message.text)
        set_ref_bonus(bonus)
        bot.reply_to(message, f"✅ রেফার বোনাস আপডেট করে {bonus} ৳ করা হয়েছে।")
    except ValueError:
        bot.reply_to(message, "অকার্যকর পরিমাণ। এটি অবশ্যই একটি সংখ্যা হতে হবে।")

def process_task_submission(message, task_id):
    user_id = message.from_user.id
    if not ADMIN_IDS:
        return bot.reply_to(message, "❌ কাজ সাবমিট করা যাচ্ছে না। বটে কোনো এডমিন আইডি কনফিগার করা নেই।")
    
    bot.reply_to(message, "✅ আপনার কাজের প্রমাণ এডমিনের কাছে পাঠানো হয়েছে! আপনাকে শীঘ্রই জানানো হবে।")
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ অ্যাপ্রুভ", callback_data=f"app_{user_id}_{task_id}"),
        InlineKeyboardButton("❌ রিজেক্ট", callback_data=f"rej_{user_id}_{task_id}")
    )
    
    admin_id = ADMIN_IDS[0] # Send to the primary admin
    username_text = f" (@{message.from_user.username})" if message.from_user.username else ""
    caption = f"📩 **নতুন টাস্ক সাবমিশন**\nইউজার আইডি: `{user_id}`{username_text}\nটাস্ক আইডি: `{task_id}`"
    
    try:
        if message.photo:
            bot.send_photo(admin_id, message.photo[-1].file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(admin_id, f"{caption}\n\n**প্রমাণ টেক্সট:**\n{message.text}", parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to send task to admin: {e}")

def process_task_reward_auto(message, target_id, task_id, amount):
    user = get_user(target_id)
    new_balance = user.get("balance", 0) + amount
    update_user_balance(target_id, new_balance)
    
    # Referral Bonus Logic (Only on first task)
    if user.get("completed_tasks", 0) == 0:
        referrer_id = user.get("referred_by")
        if referrer_id:
            referrer = get_user(referrer_id)
            if referrer:
                new_ref_balance = referrer.get("balance", 0) + 10
                update_user_balance(referrer_id, new_ref_balance)
                referrer["active_referrals"] = referrer.get("active_referrals", 0) + 1
                referrer["inactive_referrals"] = max(0, referrer.get("inactive_referrals", 0) - 1)
                save_db()
                try:
                    bot.send_message(referrer_id, "🎊 Your referral just completed their first task! You received **10 ৳** referral bonus.", parse_mode="Markdown")
                except: pass

    user["completed_tasks"] = user.get("completed_tasks", 0) + 1
    save_db()
    
    for i, task in enumerate(db["tasks"]):
        if task["_id"] == task_id:
            task["completed_count"] += 1
            if task["completed_count"] >= task.get("limit", 0):
                del db["tasks"][i]
            save_db()
            break
            
    try:
        bot.send_message(target_id, f"✅ <b>Task Approved!</b>\n\nReward: <b>{amount}৳</b> has been added to your balance.", parse_mode="HTML")
    except: pass

def process_task_reward(message, target_id, task_id):
    try:
        amount = int(message.text)
        process_task_reward_auto(message, target_id, task_id, amount)
    except ValueError:
        bot.reply_to(message, "Invalid amount. Must be a number.")

def send_all_users_report(admin_id):
    try:
        users = get_all_users()
        if not users:
            return bot.send_message(admin_id, "No users found in database.")
        
        report = "👥 **সব ইউজারের রিপোর্ট**\n\n"
        for u in users:
            uid = u.get('_id', 'অজ্ঞাত')
            uname = f"@{u.get('username')}" if u.get('username') else "নেই"
            bal = u.get('balance', 0)
            h_bal = u.get('hold_balance', 0)
            ban = "হ্যাঁ" if u.get('banned') else "না"
            report += f"আইডি: `{uid}`|ইউজার: {uname}|ব্যালেন্স: {bal}৳|হোল্ড: {h_bal}৳|ব্যান: {ban}\n"
        
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
        markup.add(InlineKeyboardButton(f"❌ রিমুভ {m}", callback_data=f"rm_method_{m}"))
    markup.add(InlineKeyboardButton("➕ মেথড যোগ করুন", callback_data="admin_add_method"))
    markup.add(InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_to_admin"))
    
    text = "⚙️ **পেমেন্ট মেথড ম্যানেজ**\n\nবর্তমান মেথডগুলো:"
    if not methods:
        text += "\nনেই"
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
    msg = bot.send_message(user_id, f"মেথড: {method}\nনাম্বার: {number}\n\nআপনি কত টাকা (৳) উইথড্র করতে চান?")
    bot.register_next_step_handler(msg, process_withdraw_amount, method, number)

def process_withdraw_amount(message, method, number):
    user_id = message.from_user.id
    try:
        amount = int(message.text.strip())
        user = get_user(user_id)
        if amount < 20:
            return bot.reply_to(message, "❌ মিনিমাম উইথড্র ২০ টাকা।")
        if user["balance"] < amount:
            return bot.reply_to(message, "❌ আপনার পর্যাপ্ত ব্যালেন্স নেই!")

        bot.reply_to(message, "✅ আপনার উইথড্রাল রিকোয়েস্টটি এডমিনের কাছে পাঠানো হয়েছে!")
        
        # Notify Admin
        admin_id = ADMIN_IDS[0] if ADMIN_IDS else user_id
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ অ্যাপ্রুভ", callback_data=f"wd_app_{user_id}_{amount}_{method}_{number}"),
            InlineKeyboardButton("❌ রিজেক্ট", callback_data=f"wd_rej_{user_id}")
        )
        caption = f"💰 **নতুন উইথড্রাল রিকোয়েস্ট**\nইউজার আইডি: `{user_id}`\nপরিমাণ: {amount}৳\nমেথড: {method}\nনাম্বার: `{number}`"
        bot.send_message(admin_id, caption, parse_mode="Markdown", reply_markup=markup)
        
    except ValueError:
        bot.reply_to(message, "অকার্যকর পরিমাণ। দয়া করে আবার চেষ্টা করুন।")


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
            "⚠️ এই বটটি ব্যবহার করতে আপনাকে অবশ্যই আমাদের অফিসিয়াল চ্যানেলে জয়েন করতে হবে!", 
            reply_markup=get_join_keyboard()
        )

    text = message.text
    if text == "📝 কাজ করুন":
        tasks = [t for t in get_all_tasks() if t.get('type') == 'one_task']
        if not tasks:
            bot.reply_to(message, "<b>📝 বর্তমান কোনো কাজ নেই</b>", parse_mode="HTML")
        else:
            bot.reply_to(message, "<b>📝 উপলব্ধ কাজগুলো:</b>", parse_mode="HTML")
            for task in tasks:
                task_id = str(task.get('_id', ''))
                title = task.get('title', 'Task')
                url = task.get('url', '')
                reward = task.get('reward', 0)
                tut_url = task.get('tutorial_url')
                limit = task.get('limit', 0)
                completed = task.get('completed_count', 0)
                image_id = task.get('image_file_id')
                
                msg_text = (
                    f"🔴 <b>টাইটেল: {title}</b>\n"
                    f"👥 <b>কাজ : {completed}/{limit} টি সম্পন্ন হয়েছে ✅</b>\n"
                    f"💸 <b>প্রতি কাজ {reward} টাকা</b>"
                )
                
                if image_id:
                    bot.send_photo(message.chat.id, image_id, caption=msg_text, reply_markup=get_single_task_keyboard(task_id, url, tut_url), parse_mode="HTML")
                else:
                    bot.send_message(message.chat.id, msg_text, reply_markup=get_single_task_keyboard(task_id, url, tut_url), parse_mode="HTML", disable_web_page_preview=True)
                    
    elif text == "🎁 ডেইলি টাস্ক":
        tasks = [t for t in get_all_tasks() if t.get('type') == 'daily_task']
        if not tasks:
            bot.reply_to(message, "<b>📝 বর্তমান কোনো কাজ নেই</b>", parse_mode="HTML")
        else:
            bot.reply_to(message, "<b>🎁 ডেইলি টাস্কসমূহ:</b>", parse_mode="HTML")
            for task in tasks:
                task_id = str(task.get('_id', ''))
                title = task.get('title', 'Task')
                url = task.get('url', '')
                reward = task.get('reward', 0)
                tut_url = task.get('tutorial_url')
                limit = task.get('limit', 0)
                completed = task.get('completed_count', 0)
                image_id = task.get('image_file_id')
                
                msg_text = (
                    f"🔴 <b>টাইটেল: {title}</b>\n"
                    f"👥 <b>কাজ : {completed}/{limit} টি সম্পন্ন হয়েছে ✅</b>\n"
                    f"💸 <b>প্রতি কাজ {reward} টাকা</b>"
                )
                
                if image_id:
                    bot.send_photo(message.chat.id, image_id, caption=msg_text, reply_markup=get_single_task_keyboard(task_id, url, tut_url), parse_mode="HTML")
                else:
                    bot.send_message(message.chat.id, msg_text, reply_markup=get_single_task_keyboard(task_id, url, tut_url), parse_mode="HTML", disable_web_page_preview=True)
    elif text == "👥 রেফার করুন":
        active = user.get("active_referrals", 0)
        inactive = user.get("inactive_referrals", 0)
        invite_msg = (
            f"✅ <b>সক্রিয় {active}.0 রেফার</b>\n"
            f"❌ <b>নিষ্ক্রিয় {inactive}.0 রেফার</b>\n"
            f"👥 <b>প্রতি রেফার ১০ টাকা</b>\n\n"
            f"👥 <b>রেফার লিংক 👇</b>\n"
            f"https://t.me/{bot.get_me().username}?start={user_id}"
        )
        bot.reply_to(message, invite_msg, parse_mode="HTML")
    elif text == "💳 উইথড্র":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 উইথড্র করুন", callback_data="user_withdraw"))
        withdraw_text = (
            "<b>🧑💻 মিনিমাম উইথড্র ২০ টাকা 💸</b>\n\n"
            "<b>🧑💻 পেমেন্ট মেথড</b>\n"
            "<b>🏧 বিকাশ / নগদ</b>\n"
            "<b>💵 উইথড্র চার্জ ১০%</b>"
        )
        bot.reply_to(message, withdraw_text, parse_mode="HTML", reply_markup=markup)
    elif text == "🧑‍💻 আমার প্রোফাইল":
        balance = user.get("balance", 0)
        hold = user.get("hold_balance", 0)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 উইথড্র করুন", callback_data="user_withdraw"))
        profile_text = (
            f"🧑‍💻 <b>আমার প্রোফাইল আইডি: <code>{user_id}</code></b>\n\n"
            f"💰 <b>বর্তমান ব্যালেন্স: {balance} ৳</b>\n"
            f"💼 <b>হোল্ড ব্যালেন্স: {hold} ৳</b>\n\n"
            f"💸 <b>মিনিমাম উইথড্র মাত্র ২০ টাকা</b> 💸\n"
            f"🧑‍💻 <b>পেমেন্ট বিকাশ/নগদ</b> 🏧"
        )
        bot.reply_to(message, profile_text, parse_mode="HTML", reply_markup=markup)
    elif text == "📊 স্ট্যাটাস":
        comp = user.get("completed_tasks", 0)
        rej = user.get("rejected_tasks", 0)
        status_text = (
            f"📊 <b>আপনার কাজের হিস্টোরি 👇</b>\n\n"
            f"✅ <b>কমপিল্ট : {comp} টা কাজ</b>\n"
            f"❌ <b>রিজেক্ট : {rej} টা কাজ</b>"
        )
        bot.reply_to(message, status_text, parse_mode="HTML")
    elif text == "❓ প্রশ্ন ও উত্তর":
        faq_text = (
            "<b>যে কোনো সমস্যা টেলিগ্ৰাম চ্যানেল জয়েন করুন এবং সকল আপডেট ও পেমেন্ট প্রুফ দেখুন 🧑💻</b>\n\n"
            "<b>🔴 টেলিগ্ৰাম চ্যানেল 👇</b>\n"
            "<b>👉 ( t.me/Earnx_Box )</b>"
        )
        bot.reply_to(message, faq_text, parse_mode="HTML")

    else:
        bot.reply_to(message, "আমি আপনার কথাটি বুঝতে পারিনি। দয়া করে মেনু ব্যবহার করুন।", reply_markup=get_main_keyboard())


# --- FastAPI routes for Webhook ---
@app.post(f"/{TOKEN}/")
async def process_webhook(request: Request):
    try:
        json_str = await request.body()
        update = Update.de_json(json_str.decode('utf-8'))
        bot.process_new_updates([update])
        return {"status": "ok"}
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/ping")
def ping():
    return {"status": "alive", "message": "Bot is awake!"}

@app.get("/")
def home():
    return {"status": "Bot is running on Render!", "ping_endpoint": "/ping"}

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
