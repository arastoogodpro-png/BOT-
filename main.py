import os
import re
import json
import time
import asyncio
from rubka import Robot, Message

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

DATA_FILE = "/app/message_cache.json"


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


# ================== مدیریت فایل کش ==================
def load_cache():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ LOAD CACHE ERROR: {e}", flush=True)
    return {}


def save_cache(cache):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ SAVE CACHE ERROR: {e}", flush=True)


# ================== تنظیمات و وضعیت ==================
bot_is_active = True
mute_list = {}

# تنظیمات قابلیت‌ها (پیش‌فرض همه بسته)
settings = {
    "link": False,       # لینک (بسته = حذف بشه)
    "id": False,         # آیدی (بسته = حذف بشه)
    "spam": False,       # اسپم (بسته = حذف بشه)
    "hyperlink": False,  # هایپرلینک (بسته = حذف بشه)
}

# برای تشخیص اسپم: {chat_id: {user_id: [timestamps]}}
spam_tracker = {}

message_cache = load_cache()


# ================== توابع بررسی ==================
def contains_link(text: str) -> bool:
    """بررسی وجود لینک در متن"""
    if not text:
        return False
    # الگوهای لینک
    patterns = [
        r'https?://\S+',
        r'www\.\S+',
        r't\.me/\S+',
        r'rubika\.ir/\S+',
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def contains_hyperlink(text: str) -> bool:
    """بررسی وجود هایپرلینک (لینک مخفی در متن)"""
    if not text:
        return False
    # در روبیکا هایپرلینک معمولاً با فرمت خاصی ذخیره می‌شه
    # مثلاً [متن](لینک) یا [متن](url)
    if re.search(r'\[.+?\]\(.+?\)', text):
        return True
    # بررسی وجود لینک مخفی
    if re.search(r'<a\s+href=', text, re.IGNORECASE):
        return True
    return False


def contains_id(text: str) -> bool:
    """بررسی وجود آیدی (@username) در متن"""
    if not text:
        return False
    # آیدی‌ها با @ شروع می‌شن
    return bool(re.search(r'@\w+', text))


# ================== هندلر پیام‌ها ==================
@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    global bot_is_active, message_cache

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
        # دستورات مدیریتی (فقط مالک)
        # ============================================================

        # --- فعال ---
        if clean_text in ("فعال", "فاعل"):
            if not is_owner:
                return
            print("✅ ACTIVATE COMMAND", flush=True)
            if bot_is_active:
                reply_text = "✅ ربات از قبل فعال است."
            else:
                bot_is_active = True
                reply_text = "✅ ربات فعال شد."
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # --- غیرفعال ---
        if clean_text in ("غیرفعال", "غيرفعال"):
            if not is_owner:
                return
            print("🛑 DEACTIVATE COMMAND", flush=True)
            if not bot_is_active:
                reply_text = "⛔ ربات از قبل غیرفعال است."
            else:
                bot_is_active = False
                reply_text = "🛑 ربات غیرفعال شد."
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # --- سکوت ---
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

            print(f"🔍 REPLY ID: {reply_id}", flush=True)

            if reply_id:
                message_cache = load_cache()
                if chat_id in message_cache and reply_id in message_cache[chat_id]:
                    target_user_id = message_cache[chat_id][reply_id]
                    print(f"🎯 TARGET FOUND: {target_user_id}", flush=True)

            if not target_user_id:
                target_user_id = sender_id
                print(f"⚠️ NO TARGET - MUTING SENDER: {target_user_id}", flush=True)

            end_time = time.time() + (minutes * 60)
            if chat_id not in mute_list:
                mute_list[chat_id] = {}
            mute_list[chat_id][target_user_id] = end_time

            print(f"🔇 MUTED {target_user_id} for {minutes} min", flush=True)
            reply_text = f"🔇 کاربر به لیست سکوت اضافه شد ({minutes} دقیقه)."
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # --- دستورات قابلیت‌ها (لینک، آیدی، اسپم، هایپرلینک) ---
        feature_match = re.match(r"^(لینک|آیدی|اسپم|هایپرلینک)\s+(باز|بسته)$", clean_text)
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
                "هایپرلینک": "hyperlink"
            }
            key = feature_key_map.get(feature)
            if key:
                settings[key] = (state == "بسته")
                status_text = "بسته" if settings[key] else "باز"
                reply_text = f"✅ {feature} {status_text} شد."
                await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
                print(f"📤 SENT: {reply_text}", flush=True)
            return

        # --- دستور لیست قفل ---
        if clean_text == "لیست قفل":
            if not is_owner:
                return
            print("📋 LOCK LIST COMMAND", flush=True)

            def status_text(val):
                return "🔴 بسته" if val else "🟢 باز"

            reply_text = (
                "📋 **لیست وضعیت قفل‌ها:**\n\n"
                f"🔗 لینک: {status_text(settings['link'])}\n"
                f"🆔 آیدی: {status_text(settings['id'])}\n"
                f"📢 اسپم: {status_text(settings['spam'])}\n"
                f"🔗 هایپرلینک: {status_text(settings['hyperlink'])}\n\n"
                "💡 برای تغییر وضعیت بنویسید:\n"
                "`لینک بسته` / `لینک باز`\n"
                "`آیدی بسته` / `آیدی باز`\n"
                "`اسپم بسته` / `اسپم باز`\n"
                "`هایپرلینک بسته` / `هایپرلینک باز`"
            )

            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            print(f"📤 SENT lock list", flush=True)
            return

        # ============================================================
        # بررسی خودکار پیام‌ها (فقط وقتی ربات فعاله و فرستنده مالک نیست)
        # ============================================================
        if not bot_is_active:
            return

        if is_owner:
            # مالک از همه قوانین معافه
            return

        # --- بررسی اسپم ---
        if settings["spam"]:
            now = time.time()
            if chat_id not in spam_tracker:
                spam_tracker[chat_id] = {}
            if sender_id not in spam_tracker[chat_id]:
                spam_tracker[chat_id][sender_id] = []

            # نگه‌داشتن زمان‌های 5 ثانیه اخیر
            spam_tracker[chat_id][sender_id] = [
                t for t in spam_tracker[chat_id][sender_id]
                if now - t < 5
            ]
            spam_tracker[chat_id][sender_id].append(now)

            # اگه بیشتر از 5 پیام در 5 ثانیه فرستاده باشه
            if len(spam_tracker[chat_id][sender_id]) >= 5:
                print(f"🚫 SPAM DETECTED from {sender_id}", flush=True)
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    print(f"🗑️ DELETED (spam)", flush=True)
                except Exception as e:
                    print(f"❌ DELETE FAILED: {e}", flush=True)
                return

        # --- بررسی لینک ---
        if settings["link"] and contains_link(raw_text):
            print(f"🚫 LINK DETECTED", flush=True)
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                print(f"🗑️ DELETED (link)", flush=True)
            except Exception as e:
                print(f"❌ DELETE FAILED: {e}", flush=True)
            return

        # --- بررسی هایپرلینک ---
        if settings["hyperlink"] and contains_hyperlink(raw_text):
            print(f"🚫 HYPERLINK DETECTED", flush=True)
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                print(f"🗑️ DELETED (hyperlink)", flush=True)
            except Exception as e:
                print(f"❌ DELETE FAILED: {e}", flush=True)
            return

        # --- بررسی آیدی ---
        if settings["id"] and contains_id(raw_text):
            print(f"🚫 ID DETECTED", flush=True)
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                print(f"🗑️ DELETED (id)", flush=True)
            except Exception as e:
                print(f"❌ DELETE FAILED: {e}", flush=True)
            return

        # --- دستور مقام ---
        if clean_text == "مقام":
            print("✅ RANK COMMAND", flush=True)
            reply_text = f"👤 مقام کاربر: {role}"
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            print(f"📤 SENT: {reply_text}", flush=True)
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
