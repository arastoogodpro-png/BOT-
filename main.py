import os
import re
import json
import time
import asyncio
from datetime import datetime
from rubka import Robot, Message
from rubka import InlineBuilder
from rubka.context import InlineMessage

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

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


def is_private_chat(chat_id: str) -> bool:
    if not chat_id:
        return False
    cid = str(chat_id).strip().lower()
    return cid.startswith("u") or cid.startswith("b")


def get_now_time() -> str:
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


# ================== فایل کش پیام‌ها ==================
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


# ================== فایل داده‌ها ==================
def load_data():
    default_data = {
        "welcomed_users": {},
        "user_titles": {},
        "taken_asl": {},
        "taken_laghab": {},
        "message_counts": {},
        "join_dates": {},
        "special_users": {},
        "warnings": {},
        "warn_limit": {},
        "started_users": [],
        "known_groups": [],
        "group_message_count": {},
        "promo_sent": {},
    }
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
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


# ================== وضعیت‌ها ==================
bot_is_active = True
mute_list = {}
settings = {
    "link": False,
    "id": False,
    "spam": False,
    "hyperlink": False,
    "welcome": True,
    "warning": False,
}

spam_tracker = {}
message_cache = load_cache()
bot_data = load_data()


# ================== توابع تشخیص ==================
def contains_link(text: str) -> bool:
    if not text:
        return False
    patterns = [
        r'https?://\S+', r'www\.\S+', r't\.me/\S+', r'rubika\.ir/\S+',
        r'telegram\.me/\S+', r'\.ir/\S+', r'\.com/\S+', r'\.org/\S+',
        r'\.net/\S+', r'\.me/\S+',
    ]
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
    if not text:
        return False
    t = text.strip()
    for c in commands:
        if t == c:
            return True
    return False


# ================== توابع اخطار ==================
async def add_warning(chat_id: str, user_id: str, reason: str = "") -> bool:
    try:
        if chat_id not in bot_data["warnings"]:
            bot_data["warnings"][chat_id] = {}
        if user_id not in bot_data["warnings"][chat_id]:
            bot_data["warnings"][chat_id][user_id] = 0

        bot_data["warnings"][chat_id][user_id] += 1
        count = bot_data["warnings"][chat_id][user_id]
        limit = bot_data["warn_limit"].get(chat_id, 3)
        save_data(bot_data)

        warn_text = (
            f"⚠️ **اخطار!** ⚠️\n\n"
            f"👤 کاربر گرامی، شما یک اخطار دریافت کردید.\n"
            f"📌 **دلیل:** {reason if reason else 'تخلف از قوانین'}\n\n"
            f"📊 **اخطار فعلی:** [{count}/{limit}]\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ **FLUXBOT** | جریان قدرت"
        )

        try:
            await bot.send_message(chat_id=chat_id, text=warn_text)
        except Exception as e:
            print(f"⚠️ WARN SEND ERROR: {e}", flush=True)

        if count >= limit:
            print(f"🚫 WARNING LIMIT REACHED - BANNING {user_id}", flush=True)
            try:
                await bot.ban_member_chat(chat_id, user_id)
                ban_text = (
                    f"🚫 **کاربر اخراج شد!** 🚫\n\n"
                    f"👤 کاربر مورد نظر به دلیل تخلفات مکرر از گروه اخراج شد.\n"
                    f"📊 **تعداد اخطار:** [{count}/{limit}]\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ **FLUXBOT** | جریان قدرت"
                )
                await bot.send_message(chat_id=chat_id, text=ban_text)
                bot_data["warnings"][chat_id][user_id] = 0
                save_data(bot_data)
                return True
            except Exception as e:
                print(f"❌ BAN ERROR: {e}", flush=True)
        return False
    except Exception as e:
        print(f"❌ ADD WARNING ERROR: {e}", flush=True)
        return False


def register_user(user_id: str):
    if user_id and user_id not in bot_data["started_users"]:
        bot_data["started_users"].append(user_id)
        save_data(bot_data)


def register_group(chat_id: str):
    if chat_id and chat_id not in bot_data["known_groups"]:
        bot_data["known_groups"].append(chat_id)
        save_data(bot_data)


# ================== ساخت منوی شیشه‌ای ==================
def build_main_menu():
    """ساخت کیبورد شیشه‌ای با InlineBuilder"""
    try:
        builder = InlineBuilder()
        
        # ردیف اول - کانال
        builder.add_button(text="📢 کانال رسمی", callback_data="btn_channel")
        
        # ردیف دوم - آموزش
        builder.add_button(text="📚 آموزش فعال‌سازی", callback_data="btn_help")
        
        # ردیف سوم - کاربران و گروه‌ها
        builder.add_button(text="👥 کاربران", callback_data="btn_users")
        builder.add_button(text="🏠 گروه‌های فعال", callback_data="btn_groups")
        
        return builder.build()
    except Exception as e:
        print(f"❌ BUILD MENU ERROR: {e}", flush=True)
        return None


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

        # ثبت کاربر و گروه
        if sender_id:
            register_user(sender_id)
        if is_group_chat(chat_id):
            register_group(chat_id)

        # ذخیره در کش
        if chat_id and msg_id and sender_id:
            if chat_id not in message_cache:
                message_cache[chat_id] = {}
            message_cache[chat_id][msg_id] = sender_id
            if len(message_cache[chat_id]) > 500:
                keys = list(message_cache[chat_id].keys())
                for k in keys[:-500]:
                    del message_cache[chat_id][k]
            save_cache(message_cache)

        # فیلتر تکراری
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
            return
        handle_message.processed[msg_id] = current_time

        print(f"📩 MESSAGE | chat={chat_id} | sender={sender_id} | raw={raw_text!r}", flush=True)

        # ============================================================
        # پیوی (چت خصوصی)
        # ============================================================
        if is_private_chat(chat_id):
            if is_command(clean_text, "start", "شروع", "منو"):
                print("📤 SENDING PV MENU", flush=True)
                
                welcome_text = (
                    "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                    "   ⚡ **FLUXBOT** ⚡\n"
                    "   🌊 جریان قدرت 🌊\n"
                    "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                    "🌟 **به ربات مدیریتی FluxBot خوش آمدید!**\n\n"
                    "🤖 من یک ربات مدیریتی حرفه‌ای برای گروه‌های روبیکا هستم.\n"
                    "با من می‌تونید گروهتون رو به بهترین شکل مدیریت کنید.\n\n"
                    "👇 **لطفاً یکی از گزینه‌های زیر رو انتخاب کنید:**"
                )
                
                # تلاش برای ارسال با کیبورد
                try:
                    builder = InlineBuilder()
                    builder.add_button(text="📢 کانال رسمی", callback_data="btn_channel")
                    builder.add_button(text="📚 آموزش فعال‌سازی", callback_data="btn_help")
                    builder.add_button(text="👥 کاربران", callback_data="btn_users")
                    builder.add_button(text="🏠 گروه‌های فعال", callback_data="btn_groups")
                    
                    keypad = builder.build()
                    
                    await bot.send_message(
                        chat_id=chat_id,
                        text=welcome_text,
                        inline_keypad=keypad
                    )
                    print("📤 PV MENU WITH KEYPAD SENT", flush=True)
                except Exception as e1:
                    print(f"⚠️ KEYPAD ATTEMPT 1 FAILED: {e1}", flush=True)
                    # تلاش دوم با اسم پارامتر دیگه
                    try:
                        builder = InlineBuilder()
                        builder.add_button(text="📢 کانال رسمی", callback_data="btn_channel")
                        builder.add_button(text="📚 آموزش فعال‌سازی", callback_data="btn_help")
                        builder.add_button(text="👥 کاربران", callback_data="btn_users")
                        builder.add_button(text="🏠 گروه‌های فعال", callback_data="btn_groups")
                        
                        keypad = builder.build()
                        
                        await bot.send_message(
                            chat_id=chat_id,
                            text=welcome_text,
                            keypad=keypad
                        )
                        print("📤 PV MENU WITH KEYPAD SENT (attempt 2)", flush=True)
                    except Exception as e2:
                        print(f"❌ KEYPAD ATTEMPT 2 FAILED: {e2}", flush=True)
                        # اگه هیچ کیبوردی کار نکرد، حداقل متن رو بفرست
                        await bot.send_message(
                            chat_id=chat_id,
                            text=welcome_text + "\n\n⚠️ (دکمه‌ها در دسترس نیستند)"
                        )
                return
            return

        # ============================================================
        # گروه
        # ============================================================
        if not is_group_chat(chat_id):
            return

        # شمارنده پیام گروه (تبلیغ 200 پیامی)
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
                "برای حمایت از ما و دریافت آخرین اخبار و به‌روزرسانی‌ها،\n"
                "لطفاً در کانال رسمی ما عضو شوید. 🙏\n\n"
                "📢 **کانال رسمی ربات:**\n"
                "➣ **@Fluxbot1**\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            try:
                await bot.send_message(chat_id=chat_id, text=promo_text)
            except Exception as e:
                print(f"❌ PROMO SEND ERROR: {e}", flush=True)
        else:
            save_data(bot_data)

        # بررسی سکوت
        now = time.time()
        chat_mutes = mute_list.get(chat_id, {})
        if sender_id in chat_mutes:
            end_time = chat_mutes[sender_id]
            if now < end_time:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                except Exception as e:
                    print(f"❌ DELETE FAILED: {e}", flush=True)
                return
            else:
                del chat_mutes[sender_id]

        # تشخیص نقش
        role = await get_user_role(chat_id, sender_id)
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
                    f"👤 **کاربر گرامی:**\n"
                    f"از اینکه به جمع ما پیوستید بی‌نهایت خوشحالیم. 🌹\n\n"
                    f"⏰ **زمان ورود:** {now_str}\n\n"
                    f"💎 **امکانات FluxBot:**\n"
                    f"├ 📊 `پروفایل` - مشاهده پروفایل\n"
                    f"├ 🐺 `تنظیم اصل [نام]` - تنظیم اصل\n"
                    f"├ 🎭 `تنظیم لقب [نام]` - تنظیم لقب\n"
                    f"├ 👑 `مقام` - مشاهده مقام\n"
                    f"└ 📚 `راهنما` - مشاهده راهنما\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ **FLUXBOT** | جریان قدرت"
                )
                
                try:
                    await bot.send_message(chat_id=chat_id, text=welcome_text, reply_to_message_id=message.message_id)
                except Exception as e:
                    print(f"❌ WELCOME ERROR: {e}", flush=True)
                
                if chat_id not in bot_data["welcomed_users"]:
                    bot_data["welcomed_users"][chat_id] = {}
                bot_data["welcomed_users"][chat_id][sender_id] = True
                save_data(bot_data)

        # آمار پیام
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

        # --- دستورات ---
        if is_command(clean_text, "فعال", "فاعل"):
            if not can_manage:
                return
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
            if not bot_is_active:
                reply_text = "⛔ ربات از قبل غیرفعال است."
            else:
                bot_is_active = False
                reply_text = "🛑 ربات غیرفعال شد."
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        mute_match = re.match(r"^سکوت\s+(\d+)$", clean_text)
        if mute_match:
            if not can_manage:
                return
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

            await bot.send_message(chat_id=message.chat_id, text=f"🔇 کاربر سکوت شد ({minutes} دقیقه).", reply_to_message_id=message.message_id)
            return

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

        if is_command(clean_text, "اخطار"):
            if not is_owner:
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
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            await add_warning(chat_id, target_user_id, "اخطار دستی")
            return

        if is_command(clean_text, "ویژه", "ادمین", "ویژه کردن", "ادمین کردن"):
            if not is_owner:
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
            if target_user_id and chat_id in bot_data["special_users"]:
                if target_user_id in bot_data["special_users"][chat_id]:
                    del bot_data["special_users"][chat_id][target_user_id]
                    save_data(bot_data)
                    await bot.send_message(chat_id=message.chat_id, text="❌ کاربر از لیست ویژه حذف شد.", reply_to_message_id=message.message_id)
                    return
            await bot.send_message(chat_id=message.chat_id, text="⚠️ کاربر در لیست ویژه نبود.", reply_to_message_id=message.message_id)
            return

        feature_match = re.match(r"^(لینک|آیدی|اسپم|هایپرلینک|خوش‌آمدگویی|خوش‌امدگویی)\s+(باز|بسته)$", clean_text)
        if feature_match:
            if not can_manage:
                return
            feature = feature_match.group(1)
            state = feature_match.group(2)
            feature_key_map = {
                "لینک": "link", "آیدی": "id", "اسپم": "spam",
                "هایپرلینک": "hyperlink", "خوش‌آمدگویی": "welcome",
                "خوش‌امدگویی": "welcome"
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
                f"⚠️ **اخطار:** {warn_status} (حداکثر: {warn_limit})\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "راهنما", "help", "دستور", "دستورات"):
            help_text = (
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                "   ⚡ **FLUXBOT** ⚡\n"
                "   📚 راهنمای ربات 📚\n"
                "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                "👤 **دستورات کاربران:**\n"
                "├ 👑 `مقام` - نمایش مقام\n"
                "├ 📊 `پروفایل` - نمایش پروفایل\n"
                "├ 🐺 `تنظیم اصل [نام]`\n"
                "├ 🎭 `تنظیم لقب [نام]`\n"
                "└ 📚 `راهنما`\n\n"
                "👑 **دستورات مالک / ویژه:**\n"
                "├ ✅ `فعال`\n"
                "├ 🛑 `غیرفعال` (فقط مالک)\n"
                "├ 🔇 `سکوت [عدد]`\n"
                "├ ⚠️ `اخطار` (فقط مالک)\n"
                "├ ⚙️ `تنظیم اخطار [عدد]` (فقط مالک)\n"
                "├ ⭐ `ویژه` (فقط مالک)\n"
                "├ ❌ `حذف ویژه` (فقط مالک)\n"
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

        if is_command(clean_text, "پروفایل", "آمار", "آمارم", "امار", "امارم", "profile"):
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
                "┌──── 👤 مشخصات ────┐\n"
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

        if is_command(clean_text, "مقام"):
            await bot.send_message(chat_id=message.chat_id, text=f"👤 **مقام شما:** {role}", reply_to_message_id=message.message_id)
            return

        # --- بررسی خودکار ---
        if not bot_is_active:
            return
        if can_manage:
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


# ================== هندلر کلیک روی دکمه‌ها ==================
@bot.on_inline_query()
async def handle_inline(bot: Robot, inline: InlineMessage):
    try:
        data = getattr(inline, 'data', None) or getattr(inline, 'callback_data', None)
        print(f"🔘 INLINE QUERY | data={data}", flush=True)

        # دریافت chat_id
        chat_id = None
        if hasattr(inline, 'chat_id'):
            chat_id = str(inline.chat_id)
        elif hasattr(inline, 'message') and hasattr(inline.message, 'chat_id'):
            chat_id = str(inline.message.chat_id)

        if not chat_id:
            print("⚠️ NO CHAT ID IN INLINE", flush=True)
            return

        if data == "btn_channel":
            channel_text = (
                "📢 **کانال رسمی ربات FluxBot**\n\n"
                "➣ **@Fluxbot1**\n\n"
                "🌟 برای حمایت از ما، دریافت آخرین اخبار،\n"
                "به‌روزرسانی‌ها و آموزش‌های ویژه،\n"
                "لطفاً در کانال رسمی ما عضو شوید. 🙏\n\n"
                "💎 **عضویت شما، انگیزه ما برای بهتر شدن است.**\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=chat_id, text=channel_text)
            return

        if data == "btn_help":
            help_text = (
                "📚 **آموزش فعال‌سازی ربات FluxBot**\n\n"
                "🌟 **مراحل فعال‌سازی:**\n\n"
                "1️⃣ **ربات را به گروه خود اضافه کنید**\n\n"
                "2️⃣ **دسترسی کامل بدهید:**\n"
                "   └ ربات را **ادمین** کنید\n"
                "   └ دسترسی «حذف پیام» و «مشاهده پیام‌ها» را فعال کنید\n\n"
                "3️⃣ **منتظر بمانید:**\n"
                "   └ بین ۱ تا ۲ دقیقه صبر کنید\n\n"
                "4️⃣ **فعال‌سازی:**\n"
                "   └ در گروه بنویسید: `فعال`\n"
                "   └ ربات با پیام «✅ ربات فعال شد» پاسخ می‌دهد\n\n"
                "💡 **نکته مهم:**\n"
                "برای دیدن همه پیام‌ها، گزینه\n"
                "«دریافت همه پیام‌های گروه» را فعال کنید.\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=chat_id, text=help_text)
            return

        if data == "btn_users":
            user_count = len(bot_data.get("started_users", []))
            users_text = (
                "👥 **آمار کاربران FluxBot**\n\n"
                f"📊 **تعداد کاربران استارت‌زده:**\n"
                f"└ **{user_count}** کاربر\n\n"
                "🌟 از اعتماد شما سپاسگزاریم.\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=chat_id, text=users_text)
            return

        if data == "btn_groups":
            group_count = len(bot_data.get("known_groups", []))
            groups_text = (
                "🏠 **آمار گروه‌های فعال FluxBot**\n\n"
                f"📊 **تعداد گروه‌های فعال:**\n"
                f"└ **{group_count}** گروه\n\n"
                "🌟 از اعتماد شما سپاسگزاریم.\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=chat_id, text=groups_text)
            return

    except Exception as e:
        print(f"❌ INLINE HANDLER ERROR: {type(e).__name__}: {e}", flush=True)


async def main():
    print("🤖 FLUXBOT STARTING...", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN ERROR: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
