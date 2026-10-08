import os
import re
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
    """تشخیص نقش واقعی کاربر با استفاده از فیلد status"""
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
# وضعیت کلی ربات (فعال / غیرفعال) - پیش‌فرض: فعال
bot_is_active = True

# برای پیام «ربات فعال شد» یا «ربات فعال است»
first_activation_in_session = True


# ================== هندلر پیام‌ها ==================
@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    global bot_is_active, first_activation_in_session

    try:
        raw_text = (message.text or "").strip()
        clean_text = clean_message(raw_text)
        chat_id = str(message.chat_id) if message.chat_id else ""
        sender_id = str(message.sender_id) if message.sender_id else ""

        print(f"📩 MESSAGE | chat={chat_id} | sender={sender_id} | raw={raw_text!r} | clean={clean_text!r}", flush=True)

        # ============ فقط توی گروه کار کن ============
        if not is_group_chat(chat_id):
            return

        # ============ تشخیص نقش فرستنده ============
        role = await get_user_role(chat_id, sender_id)
        is_owner = (role == "مالک")

        print(f"👤 SENDER ROLE: {role} | is_owner={is_owner}", flush=True)

        # ============================================================
        # بخش اول: دستورات مدیریتی (فقط برای مالک)
        # ============================================================

        # --- دستور «فعال» (فقط مالک) ---
        if clean_text in ("فعال", "فاعل"):
            if not is_owner:
                print("⛔ NOT OWNER - IGNORED", flush=True)
                return

            print("✅ ACTIVATE COMMAND (by owner)", flush=True)

            if bot_is_active:
                # اگه از قبل فعال بود
                reply_text = "✅ ربات از قبل فعال است."
            else:
                # اگه غیرفعال بود و الان فعال شد
                bot_is_active = True
                first_activation_in_session = True
                reply_text = "✅ ربات فعال شد."

            await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # --- دستور «غیرفعال» (فقط مالک) ---
        if clean_text in ("غیرفعال", "غيرفعال"):
            if not is_owner:
                print("⛔ NOT OWNER - IGNORED", flush=True)
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

        # ============================================================
        # بخش دوم: دستورات عمومی (فقط وقتی ربات فعال است)
        # ============================================================

        # --- اگه ربات غیرفعاله، به هیچ پیام دیگه‌ای جواب نده ---
        if not bot_is_active:
            print("⏸️ BOT INACTIVE - IGNORED", flush=True)
            return

        # --- دستور «مقام» (برای همه اعضا) ---
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
