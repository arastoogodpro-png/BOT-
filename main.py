import os
import re
import json
import time
import asyncio
from datetime import datetime
from rubka import Robot, Message

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

# فایل‌های ذخیره‌سازی داده‌ها
CACHE_FILE = "/app/message_cache.json"
DATA_FILE = "/app/bot_data.json"


# ================== توابع کمکی ==================
def clean_message(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"@\S+", "", text)
    text = re.sub(r"/(\w+)", r"\1", text)
    return text.strip()


def is_group_chat(chat_id: str) -> bool:
    if not chat_id:
        return False
    return str(chat_id).strip().lower().startswith("g")


def get_now_time() -> str:
    """دریافت ساعت فعلی به فرمت خوانا"""
    return datetime.now().strftime("%H:%M - %Y/%m/%d")


async def get_user_role(chat_id: str, user_id: str) -> str:
    try:
        member_info = await bot.get_chat_member(chat_id, user_id)
        if not member_info:
            return "عضو"
        data = member_info
        if isinstance(member_info, dict) and "data" in member_info:
            data = member_info["data"]
        chat_member = data.get("chat_member", {}) if isinstance(data, dict) else {}
        status = str(chat_member.get("status", "")).strip().lower()
        if status in ("creator", "owner"):
            return "مالک"
        if status in ("admin", "administrator"):
            return "ادمین"
        return "عضو"
    except Exception as e:
        print(f"⚠️ ROLE ERROR: {e}", flush=True)
        return "عضو"


async def get_chat_name(chat_id: str) -> str:
    """دریافت نام گروه"""
    try:
        info = await bot.get_chat_info(chat_id)
        if isinstance(info, dict):
            data = info.get("data", info)
            if isinstance(data, dict):
                chat = data.get("chat", data)
                if isinstance(chat, dict):
                    return chat.get("title") or chat.get("name") or "گروه"
        return "گروه"
    except Exception:
        return "گروه"


# ================== مدیریت فایل کش پیام‌ها ==================
def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ LOAD CACHE ERROR: {e}", flush=True)
    return {}


def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ SAVE CACHE ERROR: {e}", flush=True)


# ================== مدیریت فایل داده‌های ربات ==================
def load_data():
    """بارگذاری داده‌های ربات (اصل، لقب، خوش‌آمدگویی، آمار)"""
    default_data = {
        "welcomed_users": {},   # {chat_id: {user_id: True}}
        "user_titles": {},      # {chat_id: {user_id: {"asl": "...", "laghab": "..."}}}
        "taken_asl": {},        # {chat_id: [list of taken asl]}
        "taken_laghab": {},     # {chat_id: [list of taken laghab]}
        "message_counts": {},   # {chat_id: {user_id: {"today": 0, "date": "..."}}}
        "join_dates": {},       # {chat_id: {user_id: "تاریخ"}}
    }
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # اطمینان از وجود همه کلیدها
                for k, v in default_data.items():
                    if k not in loaded:
                        loaded[k] = v
                return loaded
    except Exception as e:
        print(f"⚠️ LOAD DATA ERROR: {e}", flush=True)
    return default_data


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ SAVE DATA ERROR: {e}", flush=True)


# ================== وضعیت‌های کلی ==================
bot_is_active = True
mute_list = {}
settings = {
    "link": False,
    "id": False,
    "spam": False,
    "hyperlink": False,
    "welcome": True,  # خوش‌آمدگویی پیش‌فرض فعال
}

spam_tracker = {}
message_cache = load_cache()
bot_data = load_data()


# ================== توابع بررسی ==================
def contains_link(text: str) -> bool:
    if not text:
        return False
    patterns = [r'https?://\S+', r'www\.\S+', r't\.me/\S+', r'rubika\.ir/\S+']
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def contains_hyperlink(text: str) -> bool:
    if not text:
        return False
    if re.search(r'\[.+?\]\(.+?\)', text):
        return True
    if re.search(r'<a\s+href=', text, re.IGNORECASE):
        return True
    return False


def contains_id(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r'@\w+', text))


def is_command(text: str, *commands) -> bool:
    """بررسی دستور با نادیده گرفتن فاصله‌های اضافی"""
    if not text:
        return False
    t = text.strip()
    for c in commands:
        if t == c:
            return True
    return False


# ================== هندلر پیام‌ها ==================
@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    global bot_is_active, message_cache, bot_data

    try:
        msg_id = str(message.message_id)
        chat_id = str(message.chat_id) if message.chat_id else ""
        sender_id = str(message.sender_id) if message.sender_id else ""
        raw_text = (message.text or "").strip()
        clean_text = clean_message(raw_text)

        # ================== ذخیره پیام در کش ==================
        if chat_id and msg_id and sender_id:
            if chat_id not in message_cache:
                message_cache[chat_id] = {}
            message_cache[chat_id][msg_id] = sender_id
            if len(message_cache[chat_id]) > 200:
                keys = list(message_cache[chat_id].keys())
                for k in keys[:-200]:
                    del message_cache[chat_id][k]
            save_cache(message_cache)

        # ================== فیلتر پیام تکراری ==================
        if not hasattr(handle_message, 'processed'):
            handle_message.processed = {}
            handle_message.last_cleanup = time.time()

        current_time = time.time()
        if current_time - handle_message.last_cleanup > 30:
            handle_message.processed = {
                k: v for k, v in handle_message.processed.items()
                if current_time - v < 30
            }
            handle_message.last_cleanup = current_time

        if msg_id in handle_message.processed:
            print(f"⏭️ DUPLICATE IGNORED: {msg_id}", flush=True)
            return
        handle_message.processed[msg_id] = current_time

        print(f"📩 MESSAGE | chat={chat_id} | sender={sender_id} | raw={raw_text!r}", flush=True)

        if not is_group_chat(chat_id):
            return

        # ================== بررسی سکوت ==================
        now = time.time()
        chat_mutes = mute_list.get(chat_id, {})
        if sender_id in chat_mutes:
            end_time = chat_mutes[sender_id]
            if now < end_time:
                print(f"🔇 MUTED USER - DELETING", flush=True)
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    print(f"🗑️ DELETED (muted)", flush=True)
                except Exception as e:
                    print(f"❌ DELETE FAILED: {e}", flush=True)
                return
            else:
                del chat_mutes[sender_id]
                print(f"🔊 MUTE EXPIRED for {sender_id}", flush=True)

        # ================== تشخیص نقش ==================
        role = await get_user_role(chat_id, sender_id)
        is_owner = (role == "مالک")
        print(f"👤 ROLE: {role} | is_owner={is_owner}", flush=True)

        # ============================================================
        # خوش‌آمدگویی خودکار (برای هر کاربری که اولین پیامش رو می‌ده)
        # ============================================================
        if settings["welcome"] and bot_is_active:
            welcomed = bot_data.get("welcomed_users", {}).get(chat_id, {})
            if sender_id not in welcomed:
                # این کاربر تازه‌وارد هست - خوش‌آمد بگو
                print(f"👋 WELCOME USER: {sender_id}", flush=True)
                
                chat_name = await get_chat_name(chat_id)
                now_str = get_now_time()
                
                welcome_text = (
                    f"🌟 **به گروه {chat_name} خوش آمدید!** 🌟\n\n"
                    f"👤 **کاربر گرامی:**\n"
                    f"از اینکه به جمع ما پیوستید بسیار خوشحالیم. 🌹\n\n"
                    f"⏰ **زمان ورود:** {now_str}\n\n"
                    f"💎 **امکانات گروه:**\n"
                    f"• برای دیدن مقام خود بنویسید: `مقام`\n"
                    f"• برای مشاهده پروفایل: `پروفایل`\n"
                    f"• برای تنظیم اصل و لقب: `تنظیم اصل [نام]` یا `تنظیم لقب [نام]`\n\n"
                    f"🎯 **امیدواریم اوقات خوشی در کنار ما داشته باشید.**"
                )
                
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=welcome_text,
                        reply_to_message_id=message.message_id,
                        disable_notification=False
                    )
                    print(f"📤 WELCOME SENT", flush=True)
                except Exception as e:
                    print(f"❌ WELCOME SEND ERROR: {e}", flush=True)
                
                # ذخیره در لیست خوش‌آمد گفته شده
                if chat_id not in bot_data["welcomed_users"]:
                    bot_data["welcomed_users"][chat_id] = {}
                bot_data["welcomed_users"][chat_id][sender_id] = True
                save_data(bot_data)

        # ============================================================
        # آمار پیام‌ها (شمارش پیام‌های امروز)
        # ============================================================
        today = datetime.now().strftime("%Y-%m-%d")
        if chat_id not in bot_data["message_counts"]:
            bot_data["message_counts"][chat_id] = {}
        if sender_id not in bot_data["message_counts"][chat_id]:
            bot_data["message_counts"][chat_id][sender_id] = {"today": 0, "date": today}
        else:
            # اگه تاریخ عوض شده، ریست کن
            if bot_data["message_counts"][chat_id][sender_id]["date"] != today:
                bot_data["message_counts"][chat_id][sender_id] = {"today": 0, "date": today}
        
        bot_data["message_counts"][chat_id][sender_id]["today"] += 1
        save_data(bot_data)

        # ============================================================
        # دستورات مدیریتی (فقط مالک)
        # ============================================================

        if is_command(clean_text, "فعال", "فاعل"):
            if not is_owner:
                return
            print("✅ ACTIVATE COMMAND", flush=True)
            if bot_is_active:
                reply_text = "✅ ربات از قبل فعال است."
            else:
                bot_is_active = True
                reply_text = "✅ ربات فعال شد."
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "غیرفعال", "غيرفعال"):
            if not is_owner:
                return
            print("🛑 DEACTIVATE COMMAND", flush=True)
            if not bot_is_active:
                reply_text = "⛔ ربات از قبل غیرفعال است."
            else:
                bot_is_active = False
                reply_text = "🛑 ربات غیرفعال شد."
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        mute_match = re.match(r"^سکوت\s+(\d+)$", clean_text)
        if mute_match:
            if not is_owner:
                return
            print("🔇 MUTE COMMAND", flush=True)
            minutes = int(mute_match.group(1))
            if minutes <= 0:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد باید بزرگتر از صفر باشد.", reply_to_message_id=message.message_id)
                return

            target_user_id = None
            reply_id = None
            for attr in ['reply_to_message_id', 'reply_to', 'reply_message_id']:
                if hasattr(message, attr):
                    val = getattr(message, attr)
                    if val:
                        if hasattr(val, 'message_id'):
                            reply_id = str(val.message_id)
                        else:
                            reply_id = str(val)
                        break

            if reply_id:
                message_cache = load_cache()
                if chat_id in message_cache and reply_id in message_cache[chat_id]:
                    target_user_id = message_cache[chat_id][reply_id]

            if not target_user_id:
                target_user_id = sender_id

            end_time = time.time() + (minutes * 60)
            if chat_id not in mute_list:
                mute_list[chat_id] = {}
            mute_list[chat_id][target_user_id] = end_time

            reply_text = f"🔇 کاربر به لیست سکوت اضافه شد ({minutes} دقیقه)."
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # --- دستورات قابلیت‌ها ---
        feature_match = re.match(r"^(لینک|آیدی|اسپم|هایپرلینک|خوش‌آمدگویی|خوش‌امدگویی)\s+(باز|بسته)$", clean_text)
        if feature_match:
            if not is_owner:
                return
            feature = feature_match.group(1)
            state = feature_match.group(2)
            print(f"⚙️ FEATURE: {feature} -> {state}", flush=True)

            feature_key_map = {
                "لینک": "link",
                "آیدی": "id",
                "اسپم": "spam",
                "هایپرلینک": "hyperlink",
                "خوش‌آمدگویی": "welcome",
                "خوش‌امدگویی": "welcome"
            }
            key = feature_key_map.get(feature)
            if key:
                settings[key] = (state == "بسته")
                status_text = "بسته" if settings[key] else "باز"
                reply_text = f"✅ {feature} {status_text} شد."
                await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # --- لیست قفل ---
        if is_command(clean_text, "لیست قفل"):
            if not is_owner:
                return
            print("📋 LOCK LIST COMMAND", flush=True)

            def status_text(val):
                return "🔴 بسته" if val else "🟢 باز"

            reply_text = (
                "📋 **لیست وضعیت قفل‌ها:**\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 لینک: {status_text(settings['link'])}\n"
                f"🆔 آیدی: {status_text(settings['id'])}\n"
                f"📢 اسپم: {status_text(settings['spam'])}\n"
                f"🔗 هایپرلینک: {status_text(settings['hyperlink'])}\n"
                f"👋 خوش‌آمدگویی: {status_text(settings['welcome'])}\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "💡 **دستورات تغییر وضعیت:**\n"
                "• `لینک بسته` / `لینک باز`\n"
                "• `آیدی بسته` / `آیدی باز`\n"
                "• `اسپم بسته` / `اسپم باز`\n"
                "• `هایپرلینک بسته` / `هایپرلینک باز`\n"
                "• `خوش‌آمدگویی بسته` / `خوش‌آمدگویی باز`"
            )
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # --- راهنما / help / دستور ---
        if is_command(clean_text, "راهنما", "help", "دستور", "دستورات"):
            print("📚 HELP COMMAND", flush=True)
            help_text = (
                "📚 **راهنمای ربات مدیریتی**\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "👤 **دستورات کاربران:**\n"
                "• `مقام` : نمایش مقام شما\n"
                "• `پروفایل` / `آمار` / `آمارم` : نمایش پروفایل شما\n"
                "• `تنظیم اصل [نام]` : تنظیم اصل (مثال: `تنظیم اصل گرگ`)\n"
                "• `تنظیم لقب [نام]` : تنظیم لقب (مثال: `تنظیم لقب گنگ`)\n\n"
                "👑 **دستورات مالک:**\n"
                "• `فعال` / `غیرفعال` : روشن/خاموش کردن ربات\n"
                "• `سکوت [عدد]` : سکوت کاربر (ریپلای کنید)\n"
                "• `لینک باز` / `لینک بسته` : مدیریت لینک‌ها\n"
                "• `آیدی باز` / `آیدی بسته` : مدیریت آیدی‌ها\n"
                "• `اسپم باز` / `اسپم بسته` : مدیریت اسپم\n"
                "• `هایپرلینک باز` / `هایپرلینک بسته` : مدیریت هایپرلینک\n"
                "• `خوش‌آمدگویی باز` / `خوش‌آمدگویی بسته` : مدیریت خوش‌آمدگویی\n"
                "• `لیست قفل` : نمایش وضعیت قفل‌ها\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "💎 **ربات مدیریتی حرفه‌ای**"
            )
            await bot.send_message(chat_id=message.chat_id, text=help_text, reply_to_message_id=message.message_id)
            return

        # --- تنظیم اصل ---
        asl_match = re.match(r"^تنظیم\s+اصل\s+(.+)$", clean_text)
        if asl_match:
            print("✍️ SET ASL COMMAND", flush=True)
            asl_value = asl_match.group(1).strip()

            if not asl_value:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ لطفاً یک مقدار برای اصل وارد کنید.", reply_to_message_id=message.message_id)
                return

            # بررسی تکراری نبودن
            if chat_id not in bot_data["taken_asl"]:
                bot_data["taken_asl"][chat_id] = []
            
            if asl_value in bot_data["taken_asl"][chat_id]:
                await bot.send_message(chat_id=message.chat_id, text=f"❌ اصل «{asl_value}» قبلاً توسط کاربر دیگری انتخاب شده است.", reply_to_message_id=message.message_id)
                return

            # ذخیره
            if chat_id not in bot_data["user_titles"]:
                bot_data["user_titles"][chat_id] = {}
            if sender_id not in bot_data["user_titles"][chat_id]:
                bot_data["user_titles"][chat_id][sender_id] = {}
            
            # اگه قبلاً اصل داشت، از لیست حذف کن
            old_asl = bot_data["user_titles"][chat_id][sender_id].get("asl")
            if old_asl and old_asl in bot_data["taken_asl"][chat_id]:
                bot_data["taken_asl"][chat_id].remove(old_asl)

            bot_data["user_titles"][chat_id][sender_id]["asl"] = asl_value
            bot_data["taken_asl"][chat_id].append(asl_value)
            save_data(bot_data)

            reply_text = f"✅ **اصل شما با موفقیت ثبت شد:**\n🐺 اصل: `{asl_value}`"
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # --- تنظیم لقب ---
        laghab_match = re.match(r"^تنظیم\s+لقب\s+(.+)$", clean_text)
        if laghab_match:
            print("✍️ SET LAGHAB COMMAND", flush=True)
            laghab_value = laghab_match.group(1).strip()

            if not laghab_value:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ لطفاً یک مقدار برای لقب وارد کنید.", reply_to_message_id=message.message_id)
                return

            if chat_id not in bot_data["taken_laghab"]:
                bot_data["taken_laghab"][chat_id] = []

            if laghab_value in bot_data["taken_laghab"][chat_id]:
                await bot.send_message(chat_id=message.chat_id, text=f"❌ لقب «{laghab_value}» قبلاً توسط کاربر دیگری انتخاب شده است.", reply_to_message_id=message.message_id)
                return

            if chat_id not in bot_data["user_titles"]:
                bot_data["user_titles"][chat_id] = {}
            if sender_id not in bot_data["user_titles"][chat_id]:
                bot_data["user_titles"][chat_id][sender_id] = {}

            old_laghab = bot_data["user_titles"][chat_id][sender_id].get("laghab")
            if old_laghab and old_laghab in bot_data["taken_laghab"][chat_id]:
                bot_data["taken_laghab"][chat_id].remove(old_laghab)

            bot_data["user_titles"][chat_id][sender_id]["laghab"] = laghab_value
            bot_data["taken_laghab"][chat_id].append(laghab_value)
            save_data(bot_data)

            reply_text = f"✅ **لقب شما با موفقیت ثبت شد:**\n🎭 لقب: `{laghab_value}`"
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # --- پروفایل / آمار ---
        if is_command(clean_text, "پروفایل", "آمار", "آمارم", "امار", "امارم", "profile"):
            print("📊 PROFILE COMMAND", flush=True)

            # دریافت اطلاعات کاربر
            user_titles = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {})
            asl = user_titles.get("asl", "ثبت نشده")
            laghab = user_titles.get("laghab", "ثبت نشده")

            # تعداد پیام‌های امروز
            today = datetime.now().strftime("%Y-%m-%d")
            counts = bot_data["message_counts"].get(chat_id, {}).get(sender_id, {})
            today_count = counts.get("today", 0) if counts.get("date") == today else 0

            # تاریخ پیوست (اگه ثبت نشده باشه، اولین باری که پیام داده رو ثبت می‌کنیم)
            if chat_id not in bot_data["join_dates"]:
                bot_data["join_dates"][chat_id] = {}
            if sender_id not in bot_data["join_dates"][chat_id]:
                bot_data["join_dates"][chat_id][sender_id] = get_now_time()
                save_data(bot_data)
            
            join_date = bot_data["join_dates"][chat_id][sender_id]

            reply_text = (
                f"╭─━━━━━━━━━━━━━━━─╮\n"
                f"   📊 **پروفایل کاربر** 📊\n"
                f"╰─━━━━━━━━━━━━━━━─╯\n\n"
                f"👤 **مشخصات:**\n"
                f"├ 🐺 اصل: `{asl}`\n"
                f"├ 🎭 لقب: `{laghab}`\n"
                f"├ 👑 مقام: {role}\n"
                f"├ 📅 تاریخ پیوست: {join_date}\n"
                f"└ 💬 پیام‌های امروز: {today_count}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💎 **RP Group Manager**"
            )
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # --- مقام ---
        if is_command(clean_text, "مقام"):
            print("✅ RANK COMMAND", flush=True)
            reply_text = f"👤 **مقام شما:** {role}"
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # ============================================================
        # بررسی خودکار پیام‌ها (فقط غیر مالک و وقتی ربات فعاله)
        # ============================================================
        if not bot_is_active:
            return

        if is_owner:
            return

        # اسپم
        if settings["spam"]:
            now = time.time()
            if chat_id not in spam_tracker:
                spam_tracker[chat_id] = {}
            if sender_id not in spam_tracker[chat_id]:
                spam_tracker[chat_id][sender_id] = []

            spam_tracker[chat_id][sender_id] = [
                t for t in spam_tracker[chat_id][sender_id]
                if now - t < 5
            ]
            spam_tracker[chat_id][sender_id].append(now)

            if len(spam_tracker[chat_id][sender_id]) >= 5:
                print(f"🚫 SPAM DETECTED", flush=True)
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    print(f"🗑️ DELETED (spam)", flush=True)
                except Exception as e:
                    print(f"❌ DELETE FAILED: {e}", flush=True)
                return

        # لینک
        if settings["link"] and contains_link(raw_text):
            print(f"🚫 LINK DETECTED", flush=True)
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                print(f"🗑️ DELETED (link)", flush=True)
            except Exception as e:
                print(f"❌ DELETE FAILED: {e}", flush=True)
            return

        # هایپرلینک
        if settings["hyperlink"] and contains_hyperlink(raw_text):
            print(f"🚫 HYPERLINK DETECTED", flush=True)
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                print(f"🗑️ DELETED (hyperlink)", flush=True)
            except Exception as e:
                print(f"❌ DELETE FAILED: {e}", flush=True)
            return

        # آیدی
        if settings["id"] and contains_id(raw_text):
            print(f"🚫 ID DETECTED", flush=True)
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                print(f"🗑️ DELETED (id)", flush=True)
            except Exception as e:
                print(f"❌ DELETE FAILED: {e}", flush=True)
            return

    except Exception as e:
        print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)


async def main():
    print("🤖 RP GROUP MANAGER STARTING...", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN ERROR: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
