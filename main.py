import os
import re
import json
import time
import asyncio
from datetime import datetime
from rubka import Robot, Message
from rubka.keypad import ChatKeypadBuilder

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

# ================== مسیرهای ذخیره‌سازی ==================
# چند مسیر مختلف برای ذخیره‌سازی (اطلاعات در هر جا که موجود باشه بارگذاری می‌شه)
DATA_PATHS = [
    "/app/bot_data.json",
    "/app/data/bot_data.json",
    "/tmp/bot_data.json",
    "./bot_data.json",
]
CACHE_PATHS = [
    "/app/message_cache.json",
    "/app/data/message_cache.json",
    "/tmp/message_cache.json",
    "./message_cache.json",
]

BTN_CHANNEL_TEXT = "📢 کانال رسمی"
BTN_HELP_TEXT = "📚 آموزش فعال‌سازی"
BTN_USERS_TEXT = "👥 کاربران"
BTN_GROUPS_TEXT = "🏠 گروه‌های فعال"

MAX_FILTER_WORDS = 50


# ================== توابع کمکی ==================
def clean_message(text):
    if not text:
        return ""
    text = re.sub(r"@\S+", "", text)
    text = re.sub(r"/(\w+)", r"\1", text)
    return text.strip()


def normalize_text(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\u0600-\u06FF]', '', text)
    return text


def is_group_chat(chat_id):
    return bool(chat_id) and str(chat_id).lower().startswith("g")


def is_private_chat(chat_id):
    if not chat_id:
        return False
    cid = str(chat_id).lower()
    return cid.startswith("u") or cid.startswith("b")


def get_now_time():
    return datetime.now().strftime("%H:%M - %Y/%m/%d")


def extract_reply_id(message):
    for attr in ['reply_to_message_id', 'reply_to', 'reply_message_id']:
        if hasattr(message, attr):
            val = getattr(message, attr)
            if val:
                if hasattr(val, 'message_id'):
                    return str(val.message_id)
                return str(val)
    return None


async def get_user_info(chat_id, user_id):
    """دریافت اطلاعات کامل کاربر (نام، یوزرنیم، نقش)"""
    info = {"name": None, "username": None, "role": "عضو"}
    try:
        member_info = await bot.get_chat_member(chat_id, user_id)
        if member_info:
            data = member_info.get("data", member_info) if isinstance(member_info, dict) else member_info
            chat_member = data.get("chat_member", data) if isinstance(data, dict) else {}
            
            # نام
            info["name"] = (chat_member.get("first_name") or 
                           chat_member.get("name") or 
                           chat_member.get("title"))
            
            # یوزرنیم (بدون @)
            uname = chat_member.get("username") or chat_member.get("user_name")
            if uname:
                info["username"] = str(uname).lstrip("@")
            
            # نقش
            status = str(chat_member.get("status", "")).strip().lower()
            if status in ("creator", "owner"):
                info["role"] = "مالک"
            elif status in ("admin", "administrator"):
                info["role"] = "ادمین"
    except Exception as e:
        print(f"⚠️ USER INFO ERROR: {e}", flush=True)
    return info


def format_user_link(user_info, user_id):
    """نمایش کاربر به صورت کلیک‌پذیر"""
    if user_info.get("username"):
        return f"@{user_info['username']}"
    elif user_info.get("name"):
        return user_info["name"]
    else:
        # نمایش کوتاه‌شده آیدی
        return f"کاربر {str(user_id)[:8]}"


async def get_user_role(chat_id, user_id):
    info = await get_user_info(chat_id, user_id)
    return info["role"]


async def get_chat_name(chat_id):
    try:
        info = await bot.get_chat_info(chat_id)
        if isinstance(info, dict):
            data = info.get("data", info)
            if isinstance(data, dict):
                chat = data.get("chat", data)
                if isinstance(chat, dict):
                    return chat.get("title") or chat.get("name") or "گروه"
        return "گروه"
    except:
        return "گروه"


# ================== فایل‌ها (چند مسیره) ==================
def load_cache():
    for path in CACHE_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"✅ CACHE LOADED FROM: {path}", flush=True)
                    return data
        except Exception as e:
            print(f"⚠️ LOAD CACHE FROM {path} ERROR: {e}", flush=True)
    print("ℹ️ NO CACHE FILE FOUND - starting fresh", flush=True)
    return {}


def save_cache(cache):
    """ذخیره در تمام مسیرهای ممکن"""
    saved = False
    for path in CACHE_PATHS:
        try:
            dir_name = os.path.dirname(path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
            saved = True
        except Exception as e:
            print(f"⚠️ SAVE CACHE TO {path} ERROR: {e}", flush=True)
    return saved


def load_data():
    default_data = {
        "welcomed_users": {}, "user_titles": {}, "taken_asl": {},
        "taken_laghab": {}, "message_counts": {}, "join_dates": {},
        "special_users": {}, "warnings": {}, "warn_limit": {},
        "started_users": [], "known_groups": [],
        "group_message_count": {}, "promo_sent": {},
        "filtered_words": {}, "banned_users": {},
    }
    for path in DATA_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for k, v in default_data.items():
                        if k not in loaded:
                            loaded[k] = v
                    print(f"✅ DATA LOADED FROM: {path}", flush=True)
                    return loaded
        except Exception as e:
            print(f"⚠️ LOAD DATA FROM {path} ERROR: {e}", flush=True)
    print("ℹ️ NO DATA FILE FOUND - starting fresh", flush=True)
    return default_data


def save_data(data):
    """ذخیره در تمام مسیرهای ممکن"""
    saved = False
    for path in DATA_PATHS:
        try:
            dir_name = os.path.dirname(path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            saved = True
        except Exception as e:
            print(f"⚠️ SAVE DATA TO {path} ERROR: {e}", flush=True)
    return saved


# ================== وضعیت‌ها ==================
bot_is_active = True
mute_list = {}
settings = {
    "link": False, "id": False, "spam": False, "hyperlink": False,
    "welcome": True, "warning": False,
    "filter": True, "auto_ban": True,
}
spam_tracker = {}
message_cache = load_cache()
bot_data = load_data()


# ================== توابع تشخیص ==================
def contains_link(text):
    if not text:
        return False
    patterns = [r'https?://\S+', r'www\.\S+', r't\.me/\S+', r'rubika\.ir/\S+',
                r'telegram\.me/\S+', r'\.ir/\S+', r'\.com/\S+', r'\.org/\S+', r'\.net/\S+', r'\.me/\S+']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def contains_hyperlink(text):
    if not text:
        return False
    return bool(re.search(r'\[.+?\]\(.+?\)', text) or re.search(r'<a\s+href=', text, re.IGNORECASE))


def contains_id(text):
    if not text:
        return False
    return bool(re.search(r'@\w+', text))


def is_command(text, *commands):
    if not text:
        return False
    t = text.strip()
    return any(t == c for c in commands)


def contains_filtered_word(text, filtered_list):
    if not text or not filtered_list:
        return None
    normalized = normalize_text(text)
    if not normalized:
        return None
    for word in filtered_list:
        nw = normalize_text(word)
        if nw and nw in normalized:
            return word
    return None


# ================== اخطار ==================
async def add_warning(chat_id, user_id, reason=""):
    try:
        if chat_id not in bot_data["warnings"]:
            bot_data["warnings"][chat_id] = {}
        if user_id not in bot_data["warnings"][chat_id]:
            bot_data["warnings"][chat_id][user_id] = 0

        bot_data["warnings"][chat_id][user_id] += 1
        count = bot_data["warnings"][chat_id][user_id]
        limit = bot_data["warn_limit"].get(chat_id, 3)
        save_data(bot_data)

        user_info = await get_user_info(chat_id, user_id)
        display = format_user_link(user_info, user_id)

        warn_text = (
            f"⚠️ **اخطار!** ⚠️\n\n"
            f"👤 **کاربر:** {display}\n"
            f"📌 **دلیل:** {reason if reason else 'تخلف از قوانین'}\n"
            f"📊 **اخطار فعلی:** [{count}/{limit}]\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ **FLUXBOT** | جریان قدرت"
        )
        try:
            await bot.send_message(chat_id=chat_id, text=warn_text)
        except Exception as e:
            print(f"⚠️ WARN SEND ERROR: {e}", flush=True)

        if count >= limit and settings.get("auto_ban", True):
            try:
                await bot.ban_member_chat(chat_id, user_id)
                if chat_id not in bot_data["banned_users"]:
                    bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][user_id] = time.time()
                save_data(bot_data)

                await bot.send_message(
                    chat_id=chat_id,
                    text=f"🚫 **کاربر اخراج شد!**\n\n"
                         f"👤 {display}\n"
                         f"📊 تعداد اخطار: [{count}/{limit}]"
                )
                bot_data["warnings"][chat_id][user_id] = 0
                save_data(bot_data)
                return True
            except Exception as e:
                print(f"❌ BAN ERROR: {e}", flush=True)
        return False
    except Exception as e:
        print(f"❌ ADD WARNING ERROR: {e}", flush=True)
        return False


def register_user(user_id):
    if user_id and user_id not in bot_data["started_users"]:
        bot_data["started_users"].append(user_id)
        save_data(bot_data)


def register_group(chat_id):
    if chat_id and chat_id not in bot_data["known_groups"]:
        bot_data["known_groups"].append(chat_id)
        save_data(bot_data)


# ================== کیبورد ==================
def build_chat_keypad():
    try:
        b = ChatKeypadBuilder()
        btn1 = b.button_simple(id="btn_channel", text=BTN_CHANNEL_TEXT)
        btn2 = b.button_simple(id="btn_help", text=BTN_HELP_TEXT)
        btn3 = b.button_simple(id="btn_users", text=BTN_USERS_TEXT)
        btn4 = b.button_simple(id="btn_groups", text=BTN_GROUPS_TEXT)
        b.row(btn1, btn2)
        b.row(btn3, btn4)
        return b.build()
    except Exception as e:
        print(f"❌ BUILD KEYPAD ERROR: {e}", flush=True)
        return None


# ================== متن‌ها ==================
def get_channel_text():
    return (
        "📢 **کانال رسمی ربات FluxBot**\n\n"
        "➣ **@Fluxbot1**\n\n"
        "🌟 برای حمایت از ما، دریافت آخرین اخبار،\n"
        "به‌روزرسانی‌ها و آموزش‌های ویژه،\n"
        "لطفاً در کانال رسمی ما عضو شوید. 🙏\n\n"
        "💎 **عضویت شما، انگیزه ما برای بهتر شدن است.**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ **FLUXBOT** | جریان قدرت"
    )


def get_help_text():
    return (
        "📚 **آموزش فعال‌سازی ربات FluxBot**\n\n"
        "🌟 **مراحل فعال‌سازی:**\n\n"
        "1️⃣ **ربات را به گروه خود اضافه کنید**\n\n"
        "2️⃣ **دسترسی کامل بدهید:**\n"
        "   └ ربات را **ادمین** کنید\n"
        "   └ دسترسی «حذف پیام» و «مشاهده پیام‌ها» را فعال کنید\n\n"
        "3️⃣ **منتظر بمانید:**\n"
        "   └ بین ۱ تا ۲ دقیقه صبر کنید\n\n"
        "4️⃣ **فعال‌سازی:**\n"
        "   └ در گروه بنویسید: `فعال`\n\n"
        "💡 **نکته:** گزینه «دریافت همه پیام‌های گروه» را فعال کنید.\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ **FLUXBOT** | جریان قدرت"
    )


def get_users_text():
    user_count = len(bot_data.get("started_users", []))
    return (
        "👥 **آمار کاربران FluxBot**\n\n"
        f"📊 **تعداد کاربران استارت‌زده:**\n"
        f"└ **{user_count}** کاربر\n\n"
        "🌟 از اعتماد شما سپاسگزاریم.\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ **FLUXBOT** | جریان قدرت"
    )


def get_groups_text():
    group_count = len(bot_data.get("known_groups", []))
    return (
        "🏠 **آمار گروه‌های فعال FluxBot**\n\n"
        f"📊 **تعداد گروه‌های فعال:**\n"
        f"└ **{group_count}** گروه\n\n"
        "🌟 از اعتماد شما سپاسگزاریم.\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ **FLUXBOT** | جریان قدرت"
    )


# ================== هندلر پیام‌ها ==================
@bot.on_message()
async def handle_message(bot, message):
    global bot_is_active, message_cache, bot_data

    try:
        msg_id = str(message.message_id)
        chat_id = str(message.chat_id) if message.chat_id else ""
        sender_id = str(message.sender_id) if message.sender_id else ""
        raw_text = (message.text or "").strip()
        clean_text = clean_message(raw_text)

        aux_data = getattr(message, 'aux_data', None) or getattr(message, 'auxData', None)
        button_id = None
        if aux_data and isinstance(aux_data, dict):
            button_id = aux_data.get('button_id') or aux_data.get('id')

        if sender_id:
            register_user(sender_id)
        if is_group_chat(chat_id):
            register_group(chat_id)

        if chat_id and msg_id and sender_id:
            if chat_id not in message_cache:
                message_cache[chat_id] = {}
            message_cache[chat_id][msg_id] = sender_id
            if len(message_cache[chat_id]) > 500:
                keys = list(message_cache[chat_id].keys())
                for k in keys[:-500]:
                    del message_cache[chat_id][k]
            save_cache(message_cache)

        if not hasattr(handle_message, 'processed'):
            handle_message.processed = {}
            handle_message.last_cleanup = time.time()

        current_time = time.time()
        if current_time - handle_message.last_cleanup > 30:
            handle_message.processed = {k: v for k, v in handle_message.processed.items() if current_time - v < 30}
            handle_message.last_cleanup = current_time

        if msg_id in handle_message.processed:
            return
        handle_message.processed[msg_id] = current_time

        print(f"📩 MESSAGE | chat={chat_id} | sender={sender_id} | raw={raw_text!r}", flush=True)

        # ============================================================
        # پیوی
        # ============================================================
        if is_private_chat(chat_id):
            if button_id == "btn_channel" or raw_text == BTN_CHANNEL_TEXT:
                await bot.send_message(chat_id=chat_id, text=get_channel_text())
                return
            if button_id == "btn_help" or raw_text == BTN_HELP_TEXT:
                await bot.send_message(chat_id=chat_id, text=get_help_text())
                return
            if button_id == "btn_users" or raw_text == BTN_USERS_TEXT:
                await bot.send_message(chat_id=chat_id, text=get_users_text())
                return
            if button_id == "btn_groups" or raw_text == BTN_GROUPS_TEXT:
                await bot.send_message(chat_id=chat_id, text=get_groups_text())
                return

            if is_command(clean_text, "start", "شروع", "منو"):
                welcome_text = (
                    "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                    "   ⚡ **FLUXBOT** ⚡\n"
                    "   🌊 جریان قدرت 🌊\n"
                    "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                    "🌟 **به ربات مدیریتی FluxBot خوش آمدید!**\n\n"
                    "🤖 من یک ربات مدیریتی حرفه‌ای برای گروه‌های روبیکا هستم.\n"
                    "با من می‌تونید گروهتون رو به بهترین شکل مدیریت کنید.\n\n"
                    "👇 **از منوی پایین، یکی از گزینه‌ها رو انتخاب کنید:**"
                )
                keypad = build_chat_keypad()
                if keypad:
                    try:
                        await bot.send_message(
                            chat_id=chat_id, text=welcome_text,
                            chat_keypad=keypad, chat_keypad_type="New"
                        )
                    except Exception as e:
                        print(f"❌ KEYPAD SEND: {e}", flush=True)
                        await bot.send_message(chat_id=chat_id, text=welcome_text)
                else:
                    await bot.send_message(chat_id=chat_id, text=welcome_text)
                return
            return

        # ============================================================
        # گروه
        # ============================================================
        if not is_group_chat(chat_id):
            return

        if chat_id not in bot_data["group_message_count"]:
            bot_data["group_message_count"][chat_id] = 0
        bot_data["group_message_count"][chat_id] += 1

        if bot_data["group_message_count"][chat_id] >= 200:
            bot_data["group_message_count"][chat_id] = 0
            bot_data["promo_sent"][chat_id] = bot_data["promo_sent"].get(chat_id, 0) + 1
            save_data(bot_data)
            promo_text = (
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                "   ⚡ **FLUXBOT** ⚡\n"
                "   🌊 جریان قدرت 🌊\n"
                "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                "💎 **از مدیریت حرفه‌ای لذت می‌برید؟**\n\n"
                "برای حمایت از ما لطفاً در کانال رسمی عضو شوید:\n"
                "📢 **@Fluxbot1**\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            try:
                await bot.send_message(chat_id=chat_id, text=promo_text)
            except:
                pass
        else:
            save_data(bot_data)

        now = time.time()
        chat_mutes = mute_list.get(chat_id, {})
        if sender_id in chat_mutes:
            end_time = chat_mutes[sender_id]
            if now < end_time:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                except:
                    pass
                return
            else:
                del chat_mutes[sender_id]

        user_info = await get_user_info(chat_id, sender_id)
        role = user_info["role"]
        display_name = format_user_link(user_info, sender_id)
        is_owner = (role == "مالک")
        is_special = bot_data.get("special_users", {}).get(chat_id, {}).get(sender_id, False)
        can_manage = is_owner or is_special

        print(f"👤 ROLE: {role} | is_owner={is_owner} | special={is_special}", flush=True)

        # خوش‌آمدگویی
        if settings["welcome"] and bot_is_active:
            welcomed = bot_data.get("welcomed_users", {}).get(chat_id, {})
            if sender_id not in welcomed:
                chat_name = await get_chat_name(chat_id)
                now_str = get_now_time()
                welcome_text = (
                    f"╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                    f"   ⚡ **FLUXBOT** ⚡\n"
                    f"   🌊 جریان قدرت 🌊\n"
                    f"╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                    f"🌟 **به گروه {chat_name} خوش آمدید!** 🌟\n\n"
                    f"👤 **کاربر گرامی {display_name}:**\n"
                    f"از اینکه به جمع ما پیوستید بی‌نهایت خوشحالیم. 🌹\n\n"
                    f"⏰ **زمان ورود:** {now_str}\n\n"
                    f"💎 **امکانات FluxBot:**\n"
                    f"├ 📊 `پروفایل`\n"
                    f"├ 🐺 `تنظیم اصل [نام]`\n"
                    f"├ 🎭 `تنظیم لقب [نام]`\n"
                    f"├ 👑 `مقام`\n"
                    f"└ 📚 `راهنما`\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ **FLUXBOT** | جریان قدرت"
                )
                try:
                    await bot.send_message(chat_id=chat_id, text=welcome_text, reply_to_message_id=message.message_id)
                except:
                    pass
                if chat_id not in bot_data["welcomed_users"]:
                    bot_data["welcomed_users"][chat_id] = {}
                bot_data["welcomed_users"][chat_id][sender_id] = True
                save_data(bot_data)

        today = datetime.now().strftime("%Y-%m-%d")
        if chat_id not in bot_data["message_counts"]:
            bot_data["message_counts"][chat_id] = {}
        if sender_id not in bot_data["message_counts"][chat_id]:
            bot_data["message_counts"][chat_id][sender_id] = {"today": 0, "date": today}
        else:
            if bot_data["message_counts"][chat_id][sender_id]["date"] != today:
                bot_data["message_counts"][chat_id][sender_id] = {"today": 0, "date": today}
        bot_data["message_counts"][chat_id][sender_id]["today"] += 1
        save_data(bot_data)

        # ============================================================
        # دستورات
        # ============================================================

        if is_command(clean_text, "فعال", "فاعل"):
            if not can_manage:
                return
            reply_text = "✅ ربات از قبل فعال است." if bot_is_active else "✅ ربات فعال شد."
            bot_is_active = True
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "غیرفعال", "غيرفعال"):
            if not is_owner:
                return
            reply_text = "⛔ ربات از قبل غیرفعال است." if not bot_is_active else "🛑 ربات غیرفعال شد."
            bot_is_active = False
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # --- بن ---
        if is_command(clean_text, "بن", "سیک", "اخراج", "ban"):
            if not can_manage:
                return
            reply_id = extract_reply_id(message)
            target_user_id = None
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]

            if not target_user_id:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ لطفاً روی پیام کاربر مورد نظر ریپلای کنید.", reply_to_message_id=message.message_id)
                return

            try:
                t_info = await get_user_info(chat_id, target_user_id)
                t_display = format_user_link(t_info, target_user_id)
                await bot.ban_member_chat(chat_id, target_user_id)
                
                if chat_id not in bot_data["banned_users"]:
                    bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][target_user_id] = time.time()
                save_data(bot_data)

                ban_text = (
                    f"🚫 **کاربر اخراج شد!** 🚫\n\n"
                    f"👤 **کاربر:** {t_display}\n"
                    f"📌 **دلیل:** تخلف از قوانین\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ **FLUXBOT** | جریان قدرت"
                )
                await bot.send_message(chat_id=message.chat_id, text=ban_text, reply_to_message_id=message.message_id)
            except Exception as e:
                print(f"❌ BAN ERROR: {e}", flush=True)
                await bot.send_message(chat_id=message.chat_id, text=f"❌ خطا در اخراج: {e}", reply_to_message_id=message.message_id)
            return

        # --- انبن ---
        if is_command(clean_text, "انبن", "آنبن", "ان بن", "unban"):
            if not can_manage:
                return
            reply_id = extract_reply_id(message)
            target_user_id = None
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]

            if not target_user_id:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ لطفاً روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return

            try:
                t_info = await get_user_info(chat_id, target_user_id)
                t_display = format_user_link(t_info, target_user_id)
                await bot.unban_member_chat(chat_id, target_user_id)
                
                if chat_id in bot_data["banned_users"] and target_user_id in bot_data["banned_users"][chat_id]:
                    del bot_data["banned_users"][chat_id][target_user_id]
                    save_data(bot_data)

                unban_text = (
                    f"✅ **کاربر آنبن شد!** ✅\n\n"
                    f"👤 **کاربر:** {t_display}\n"
                    f"🌟 از لیست سیاه حذف شد.\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ **FLUXBOT** | جریان قدرت"
                )
                await bot.send_message(chat_id=message.chat_id, text=unban_text, reply_to_message_id=message.message_id)
            except Exception as e:
                print(f"❌ UNBAN ERROR: {e}", flush=True)
                await bot.send_message(chat_id=message.chat_id, text=f"❌ خطا در آنبن: {e}", reply_to_message_id=message.message_id)
            return

        # --- فیلتر ---
        filter_match = re.match(r"^فیلتر\s+(.+)$", clean_text)
        if filter_match:
            if not is_owner:
                return
            word = filter_match.group(1).strip()
            if not word:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ یک کلمه وارد کنید.", reply_to_message_id=message.message_id)
                return

            if chat_id not in bot_data["filtered_words"]:
                bot_data["filtered_words"][chat_id] = []

            if word in bot_data["filtered_words"][chat_id]:
                await bot.send_message(chat_id=message.chat_id, text=f"⚠️ کلمه «{word}» از قبل فیلتر شده.", reply_to_message_id=message.message_id)
                return

            if len(bot_data["filtered_words"][chat_id]) >= MAX_FILTER_WORDS:
                await bot.send_message(chat_id=message.chat_id, text=f"⚠️ حداکثر {MAX_FILTER_WORDS} کلمه می‌توانید فیلتر کنید.", reply_to_message_id=message.message_id)
                return

            bot_data["filtered_words"][chat_id].append(word)
            save_data(bot_data)
            count = len(bot_data["filtered_words"][chat_id])
            
            await bot.send_message(
                chat_id=message.chat_id,
                text=f"✅ **کلمه فیلتر شد!**\n\n"
                     f"🚫 کلمه: `{word}`\n"
                     f"📊 تعداد فیلترها: {count}/{MAX_FILTER_WORDS}",
                reply_to_message_id=message.message_id
            )
            return

        unfilter_match = re.match(r"^حذف\s+فیلتر\s+(.+)$", clean_text)
        if unfilter_match:
            if not is_owner:
                return
            word = unfilter_match.group(1).strip()
            if chat_id in bot_data["filtered_words"] and word in bot_data["filtered_words"][chat_id]:
                bot_data["filtered_words"][chat_id].remove(word)
                save_data(bot_data)
                await bot.send_message(chat_id=message.chat_id, text=f"✅ کلمه «{word}» حذف شد.", reply_to_message_id=message.message_id)
            else:
                await bot.send_message(chat_id=message.chat_id, text=f"⚠️ کلمه «{word}» در لیست نبود.", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "لیست فیلتر", "فیلترها"):
            if not can_manage:
                return
            words = bot_data["filtered_words"].get(chat_id, [])
            if not words:
                text = "📋 **لیست فیلتر خالی است.**"
            else:
                word_list = "\n".join([f"├ 🚫 {w}" for w in words])
                text = f"📋 **لیست کلمات فیلترشده ({len(words)}/{MAX_FILTER_WORDS}):**\n\n{word_list}"
            await bot.send_message(chat_id=message.chat_id, text=text, reply_to_message_id=message.message_id)
            return

        # --- آمار گروه (Top 10) ---
        if is_command(clean_text, "آمار گروه", "برترین‌ها", "تاپ", "تاپ۱۰"):
            print("📊 GROUP STATS", flush=True)
            today = datetime.now().strftime("%Y-%m-%d")
            counts = bot_data["message_counts"].get(chat_id, {})
            
            today_counts = []
            for uid, data in counts.items():
                if data.get("date") == today and data.get("today", 0) > 0:
                    today_counts.append((uid, data["today"]))
            
            today_counts.sort(key=lambda x: x[1], reverse=True)
            top10 = today_counts[:10]

            if not top10:
                await bot.send_message(chat_id=message.chat_id, text="📊 **امروز هنوز پیامی ارسال نشده است.**", reply_to_message_id=message.message_id)
                return

            medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
            lines = []
            for i, (uid, count) in enumerate(top10):
                u_info = await get_user_info(chat_id, uid)
                name = format_user_link(u_info, uid)
                lines.append(f"{medals[i]} {name} — `{count}` پیام")

            stats_text = (
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                "   ⚡ **FLUXBOT** ⚡\n"
                "   🏆 برترین‌های امروز 🏆\n"
                "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                + "\n".join(lines) +
                f"\n\n━━━━━━━━━━━━━━━━━━━\n"
                f"📅 {today}\n"
                f"⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=message.chat_id, text=stats_text, reply_to_message_id=message.message_id)
            return

        # --- سکوت ---
        mute_match = re.match(r"^سکوت\s+(\d+)$", clean_text)
        if mute_match:
            if not can_manage:
                return
            minutes = int(mute_match.group(1))
            if minutes <= 0:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد باید بیشتر از صفر باشد.", reply_to_message_id=message.message_id)
                return
            target_user_id = None
            reply_id = extract_reply_id(message)
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]
            if not target_user_id:
                target_user_id = sender_id
            end_time = time.time() + (minutes * 60)
            if chat_id not in mute_list:
                mute_list[chat_id] = {}
            mute_list[chat_id][target_user_id] = end_time
            await bot.send_message(chat_id=message.chat_id, text=f"🔇 کاربر سکوت شد ({minutes} دقیقه).", reply_to_message_id=message.message_id)
            return

        # --- تنظیم اخطار ---
        warn_set_match = re.match(r"^تنظیم\s+اخطار\s+(\d+)$", clean_text)
        if warn_set_match:
            if not is_owner:
                return
            limit = int(warn_set_match.group(1))
            if limit <= 0 or limit > 500:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد باید بین 1 تا 500 باشد.", reply_to_message_id=message.message_id)
                return
            bot_data["warn_limit"][chat_id] = limit
            settings["warning"] = True
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, text=f"✅ سیستم اخطار فعال شد (حداکثر: {limit})", reply_to_message_id=message.message_id)
            return

        # --- اخطار دستی ---
        if is_command(clean_text, "اخطار"):
            if not is_owner:
                return
            target_user_id = None
            reply_id = extract_reply_id(message)
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]
            if not target_user_id:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            await add_warning(chat_id, target_user_id, "اخطار دستی از طرف مالک")
            return

        # --- ویژه ---
        if is_command(clean_text, "ویژه", "ادمین", "ویژه کردن", "ادمین کردن"):
            if not is_owner:
                return
            target_user_id = None
            reply_id = extract_reply_id(message)
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]
            if not target_user_id:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            if chat_id not in bot_data["special_users"]:
                bot_data["special_users"][chat_id] = {}
            bot_data["special_users"][chat_id][target_user_id] = True
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, text="⭐ کاربر با موفقیت ویژه شد!", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "حذف ویژه", "لغو ویژه", "حذف ادمین"):
            if not is_owner:
                return
            target_user_id = None
            reply_id = extract_reply_id(message)
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]
            if target_user_id and chat_id in bot_data["special_users"]:
                if target_user_id in bot_data["special_users"][chat_id]:
                    del bot_data["special_users"][chat_id][target_user_id]
                    save_data(bot_data)
                    await bot.send_message(chat_id=message.chat_id, text="❌ کاربر از لیست ویژه حذف شد.", reply_to_message_id=message.message_id)
                    return
            await bot.send_message(chat_id=message.chat_id, text="⚠️ کاربر در لیست ویژه نبود.", reply_to_message_id=message.message_id)
            return

        # --- قفل‌ها ---
        feature_match = re.match(r"^(لینک|آیدی|اسپم|هایپرلینک|خوش‌آمدگویی|خوش‌امدگویی)\s+(باز|بسته)$", clean_text)
        if feature_match:
            if not can_manage:
                return
            feature = feature_match.group(1)
            state = feature_match.group(2)
            feature_key_map = {
                "لینک": "link", "آیدی": "id", "اسپم": "spam",
                "هایپرلینک": "hyperlink", "خوش‌آمدگویی": "welcome", "خوش‌امدگویی": "welcome"
            }
            key = feature_key_map.get(feature)
            if key:
                settings[key] = (state == "بسته")
                status_text = "بسته" if settings[key] else "باز"
                await bot.send_message(chat_id=message.chat_id, text=f"✅ {feature} {status_text} شد.", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "لیست قفل"):
            if not can_manage:
                return
            def st(v): return "🔴 بسته" if v else "🟢 باز"
            warn_limit = bot_data["warn_limit"].get(chat_id, 3)
            warn_status = "🔴 فعال" if settings["warning"] else "🟢 غیرفعال"
            filter_count = len(bot_data["filtered_words"].get(chat_id, []))
            reply_text = (
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                "   ⚡ **FLUXBOT** ⚡\n"
                "   📋 وضعیت قفل‌ها 📋\n"
                "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                f"🔗 **لینک:** {st(settings['link'])}\n"
                f"🆔 **آیدی:** {st(settings['id'])}\n"
                f"📢 **اسپم:** {st(settings['spam'])}\n"
                f"🔗 **هایپرلینک:** {st(settings['hyperlink'])}\n"
                f"👋 **خوش‌آمدگویی:** {st(settings['welcome'])}\n"
                f"⚠️ **اخطار:** {warn_status} (حداکثر: {warn_limit})\n"
                f"🚫 **کلمات فیلتر:** {filter_count}/{MAX_FILTER_WORDS}\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # --- راهنما ---
        if is_command(clean_text, "راهنما", "help", "دستور", "دستورات"):
            help_text = (
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                "   ⚡ **FLUXBOT** ⚡\n"
                "   📚 راهنمای ربات 📚\n"
                "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                "👤 **دستورات کاربران:**\n"
                "├ 👑 `مقام`\n"
                "├ 📊 `پروفایل`\n"
                "├ 🏆 `آمار گروه` - برترین‌ها\n"
                "├ 🐺 `تنظیم اصل [نام]`\n"
                "├ 🎭 `تنظیم لقب [نام]`\n"
                "└ 📚 `راهنما`\n\n"
                "👑 **دستورات مالک / ویژه:**\n"
                "├ ✅ `فعال` / 🛑 `غیرفعال`\n"
                "├ 🚫 `بن` / `سیک` / `اخراج` (ریپلای)\n"
                "├ ✅ `انبن` (ریپلای)\n"
                "├ 🔇 `سکوت [عدد]`\n"
                "├ ⚠️ `اخطار` (ریپلای)\n"
                "├ ⚙️ `تنظیم اخطار [عدد]`\n"
                "├ ⭐ `ویژه` / ❌ `حذف ویژه`\n"
                "├ 🚫 `فیلتر [کلمه]`\n"
                "├ ❌ `حذف فیلتر [کلمه]`\n"
                "├ 📋 `لیست فیلتر`\n"
                "├ 🔗 `لینک باز/بسته`\n"
                "├ 🆔 `آیدی باز/بسته`\n"
                "├ 📢 `اسپم باز/بسته`\n"
                "├ 🔗 `هایپرلینک باز/بسته`\n"
                "├ 👋 `خوش‌آمدگویی باز/بسته`\n"
                "└ 📋 `لیست قفل`\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=message.chat_id, text=help_text, reply_to_message_id=message.message_id)
            return

        # --- تنظیم اصل ---
        asl_match = re.match(r"^تنظیم\s+اصل\s+(.+)$", clean_text)
        if asl_match:
            asl_value = asl_match.group(1).strip()
            if not asl_value:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ مقدار اصل را وارد کنید.", reply_to_message_id=message.message_id)
                return
            if chat_id not in bot_data["taken_asl"]:
                bot_data["taken_asl"][chat_id] = []
            current_asl = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("asl")
            if asl_value in bot_data["taken_asl"][chat_id] and asl_value != current_asl:
                await bot.send_message(chat_id=message.chat_id, text=f"❌ اصل «{asl_value}» تکراری است.", reply_to_message_id=message.message_id)
                return
            if chat_id not in bot_data["user_titles"]:
                bot_data["user_titles"][chat_id] = {}
            if sender_id not in bot_data["user_titles"][chat_id]:
                bot_data["user_titles"][chat_id][sender_id] = {}
            old_asl = bot_data["user_titles"][chat_id][sender_id].get("asl")
            if old_asl and old_asl in bot_data["taken_asl"][chat_id]:
                bot_data["taken_asl"][chat_id].remove(old_asl)
            bot_data["user_titles"][chat_id][sender_id]["asl"] = asl_value
            if asl_value not in bot_data["taken_asl"][chat_id]:
                bot_data["taken_asl"][chat_id].append(asl_value)
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, text=f"✅ اصل ثبت شد:\n🐺 `{asl_value}`", reply_to_message_id=message.message_id)
            return

        # --- تنظیم لقب ---
        laghab_match = re.match(r"^تنظیم\s+لقب\s+(.+)$", clean_text)
        if laghab_match:
            laghab_value = laghab_match.group(1).strip()
            if not laghab_value:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ مقدار لقب را وارد کنید.", reply_to_message_id=message.message_id)
                return
            if chat_id not in bot_data["taken_laghab"]:
                bot_data["taken_laghab"][chat_id] = []
            current_laghab = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("laghab")
            if laghab_value in bot_data["taken_laghab"][chat_id] and laghab_value != current_laghab:
                await bot.send_message(chat_id=message.chat_id, text=f"❌ لقب «{laghab_value}» تکراری است.", reply_to_message_id=message.message_id)
                return
            if chat_id not in bot_data["user_titles"]:
                bot_data["user_titles"][chat_id] = {}
            if sender_id not in bot_data["user_titles"][chat_id]:
                bot_data["user_titles"][chat_id][sender_id] = {}
            old_laghab = bot_data["user_titles"][chat_id][sender_id].get("laghab")
            if old_laghab and old_laghab in bot_data["taken_laghab"][chat_id]:
                bot_data["taken_laghab"][chat_id].remove(old_laghab)
            bot_data["user_titles"][chat_id][sender_id]["laghab"] = laghab_value
            if laghab_value not in bot_data["taken_laghab"][chat_id]:
                bot_data["taken_laghab"][chat_id].append(laghab_value)
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, text=f"✅ لقب ثبت شد:\n🎭 `{laghab_value}`", reply_to_message_id=message.message_id)
            return

        # --- پروفایل ---
        if is_command(clean_text, "پروفایل", "آمارم", "امارم", "profile"):
            user_titles = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {})
            asl = user_titles.get("asl", "ثبت نشده")
            laghab = user_titles.get("laghab", "ثبت نشده")
            today = datetime.now().strftime("%Y-%m-%d")
            counts = bot_data["message_counts"].get(chat_id, {}).get(sender_id, {})
            today_count = counts.get("today", 0) if counts.get("date") == today else 0
            if chat_id not in bot_data["join_dates"]:
                bot_data["join_dates"][chat_id] = {}
            if sender_id not in bot_data["join_dates"][chat_id]:
                bot_data["join_dates"][chat_id][sender_id] = get_now_time()
                save_data(bot_data)
            join_date = bot_data["join_dates"][chat_id][sender_id]
            special_status = "⭐ ویژه" if is_special else "عادی"
            warn_count = bot_data["warnings"].get(chat_id, {}).get(sender_id, 0)
            warn_limit = bot_data["warn_limit"].get(chat_id, 3)
            
            reply_text = (
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                "   ⚡ **FLUXBOT** ⚡\n"
                "   📊 پروفایل کاربر 📊\n"
                "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                f"👤 **کاربر:** {display_name}\n\n"
                "┌──── مشخصات ────┐\n"
                f"│ 🐺 اصل: `{asl}`\n"
                f"│ 🎭 لقب: `{laghab}`\n"
                f"│ 👑 مقام: {role}\n"
                f"│ ⭐ وضعیت: {special_status}\n"
                f"│ ⚠️ اخطار: [{warn_count}/{warn_limit}]\n"
                f"│ 📅 پیوست: {join_date}\n"
                f"│ 💬 پیام امروز: {today_count}\n"
                "└────────────────────┘\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # --- مقام ---
        if is_command(clean_text, "مقام"):
            await bot.send_message(chat_id=message.chat_id, text=f"👤 **مقام شما:** {role}", reply_to_message_id=message.message_id)
            return

        # ============================================================
        # بررسی خودکار
        # ============================================================
        if not bot_is_active:
            return
        if can_manage:
            return

        if settings["filter"]:
            filtered_list = bot_data["filtered_words"].get(chat_id, [])
            matched = contains_filtered_word(raw_text, filtered_list)
            if matched:
                print(f"🚫 FILTERED WORD: {matched}", flush=True)
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]:
                        await add_warning(chat_id, sender_id, f"استفاده از کلمه فیلترشده: {matched}")
                except Exception as e:
                    print(f"❌ DELETE FAILED: {e}", flush=True)
                return

        if settings["spam"]:
            now = time.time()
            if chat_id not in spam_tracker:
                spam_tracker[chat_id] = {}
            if sender_id not in spam_tracker[chat_id]:
                spam_tracker[chat_id][sender_id] = []
            spam_tracker[chat_id][sender_id] = [t for t in spam_tracker[chat_id][sender_id] if now - t < 5]
            spam_tracker[chat_id][sender_id].append(now)
            if len(spam_tracker[chat_id][sender_id]) >= 5:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]:
                        await add_warning(chat_id, sender_id, "ارسال اسپم")
                except Exception as e:
                    print(f"❌ DELETE FAILED: {e}", flush=True)
                return

        if settings["link"] and contains_link(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال لینک")
            except Exception as e:
                print(f"❌ DELETE FAILED: {e}", flush=True)
            return

        if settings["hyperlink"] and contains_hyperlink(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال هایپرلینک")
            except Exception as e:
                print(f"❌ DELETE FAILED: {e}", flush=True)
            return

        if settings["id"] and contains_id(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال آیدی")
            except Exception as e:
                print(f"❌ DELETE FAILED: {e}", flush=True)
            return

    except Exception as e:
        print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)


async def main():
    print("🤖 FLUXBOT STARTING...", flush=True)
    print(f"📁 DATA PATHS: {DATA_PATHS}", flush=True)
    print(f"📁 CACHE PATHS: {CACHE_PATHS}", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN ERROR: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
