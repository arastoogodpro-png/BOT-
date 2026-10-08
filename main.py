import os
import re
import time
import asyncio
from rubka import Robot, Message

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)


# ================== توابع کمکی ==================
def clean_message(text: str) -> str:
    """حذف منشن ربات و اسلش از متن پیام"""
    if not text:
        return ""
    text = re.sub(r"@\S+", "", text)
    text = re.sub(r"/(\w+)", r"\1", text)
    return text.strip()


def is_group_chat(chat_id: str) -> bool:
    """تشخیص چت گروهی"""
    if not chat_id:
        return False
    return str(chat_id).strip().lower().startswith("g")


async def get_user_role(chat_id: str, user_id: str) -> str:
    """تشخیص نقش واقعی کاربر"""
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
        print(f"⚠️ ROLE DETECTION ERROR: {type(e).__name__}: {e}", flush=True)
        return "عضو"


# ================== متغیرهای وضعیت ==================
bot_is_active = True

# لیست سکوت: {chat_id: {user_id: end_timestamp}}
mute_list = {}


# ================== هندلر پیام‌ها ==================
@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    global bot_is_active

    try:
        raw_text = (message.text or "").strip()
        clean_text = clean_message(raw_text)
        chat_id = str(message.chat_id) if message.chat_id else ""
        sender_id = str(message.sender_id) if message.sender_id else ""

        print(f"📩 MESSAGE | chat={chat_id} | sender={sender_id} | raw={raw_text!r} | clean={clean_text!r}", flush=True)

        if not is_group_chat(chat_id):
            return

        # ============================================================
        # بررسی سکوت کاربر (قبل از هر پردازش دیگه‌ای)
        # ============================================================
        now = time.time()
        chat_mutes = mute_list.get(chat_id, {})
        
        if sender_id in chat_mutes:
            end_time = chat_mutes[sender_id]
            if now < end_time:
                # کاربر در حال سکوت هست - پیامش رو پاک کن
                print(f"🔇 MUTED USER - DELETING MESSAGE", flush=True)
                try:
                    await bot.delete_message(
                        chat_id=message.chat_id,
                        message_id=message.message_id
                    )
                    print(f"🗑️ MESSAGE DELETED", flush=True)
                except Exception as e:
                    print(f"⚠️ DELETE ERROR: {e}", flush=True)
                return
            else:
                # زمان سکوت تمام شده - از لیست حذف کن
                del chat_mutes[sender_id]
                print(f"🔊 MUTE EXPIRED for {sender_id}", flush=True)

        # ============================================================
        # تشخیص نقش فرستنده
        # ============================================================
        role = await get_user_role(chat_id, sender_id)
        is_owner = (role == "مالک")

        print(f"👤 SENDER ROLE: {role} | is_owner={is_owner}", flush=True)

        # ============================================================
        # بخش اول: دستورات مدیریتی (فقط مالک)
        # ============================================================

        # --- دستور «فعال» ---
        if clean_text in ("فعال", "فاعل"):
            if not is_owner:
                return
            print("✅ ACTIVATE COMMAND (by owner)", flush=True)
            if bot_is_active:
                reply_text = "✅ ربات از قبل فعال است."
            else:
                bot_is_active = True
                reply_text = "✅ ربات فعال شد."
            await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # --- دستور «غیرفعال» ---
        if clean_text in ("غیرفعال", "غيرفعال"):
            if not is_owner:
                return
            print("🛑 DEACTIVATE COMMAND (by owner)", flush=True)
            if not bot_is_active:
                reply_text = "⛔ ربات از قبل غیرفعال است."
            else:
                bot_is_active = False
                reply_text = "🛑 ربات غیرفعال شد."
            await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # --- دستور «سکوت [عدد]» ---
        # الگو: سکوت 1 یا سکوت 5 یا سکوت 10
        mute_match = re.match(r"^سکوت\s+(\d+)$", clean_text)
        if mute_match:
            if not is_owner:
                return
            print("🔇 MUTE COMMAND (by owner)", flush=True)

            minutes = int(mute_match.group(1))
            if minutes <= 0:
                await bot.send_message(
                    chat_id=message.chat_id,
                    text="⚠️ عدد باید بزرگتر از صفر باشد.",
                    reply_to_message_id=message.message_id
                )
                return

            # پیدا کردن کاربری که بهش سکوت داده میشه
            # توی گروه، اگه پیام ریپلای باشه، کاربر ریپلای شده سکوت میشه
            # وگرنه کاربری که پیام داده
            target_user_id = None

            # چک کردن اینکه پیام ریپلای هست یا نه
            reply_to = None
            if hasattr(message, 'reply_to_message_id') and message.reply_to_message_id:
                reply_to = message.reply_to_message_id
            elif hasattr(message, 'reply_to_message') and message.reply_to_message:
                reply_to = message.reply_to_message.message_id

            if reply_to:
                # دریافت پیام ریپلای شده
                try:
                    replied_msg = await bot.get_message(
                        chat_id=message.chat_id,
                        message_id=reply_to
                    )
                    if replied_msg:
                        target_user_id = str(replied_msg.sender_id)
                except Exception as e:
                    print(f"⚠️ GET REPLIED MESSAGE ERROR: {e}", flush=True)

            # اگه ریپلای نبود، از کاربری که پیام داده استفاده کن
            if not target_user_id:
                target_user_id = sender_id

            # اضافه کردن به لیست سکوت
            end_time = time.time() + (minutes * 60)
            if chat_id not in mute_list:
                mute_list[chat_id] = {}
            mute_list[chat_id][target_user_id] = end_time

            print(f"🔇 MUTED {target_user_id} for {minutes} minute(s)", flush=True)

            reply_text = f"🔇 کاربر به لیست سکوت اضافه شد ({minutes} دقیقه)."
            await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # ============================================================
        # بخش دوم: دستورات عمومی (فقط وقتی ربات فعال است)
        # ============================================================

        if not bot_is_active:
            print("⏸️ BOT INACTIVE - IGNORED", flush=True)
            return

        # --- دستور «مقام» ---
        if clean_text == "مقام":
            print("✅ RANK COMMAND", flush=True)
            reply_text = f"👤 مقام کاربر: {role}"
            await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT: {reply_text}", flush=True)
            return

    except Exception as e:
        print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)


# ================== اجرای ربات ==================
async def main():
    print("🤖 RP GROUP MANAGER STARTING...", flush=True)
    print(f"⚙️ Initial state: bot_is_active={bot_is_active}", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN ERROR: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
