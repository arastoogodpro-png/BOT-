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
    # حذف منشن‌ها (هر چیزی که با @ شروع میشه)
    text = re.sub(r"@\S+", "", text)
    # حذف اسلش از ابتدای دستورات (مثل /start -> start)
    text = re.sub(r"/(\w+)", r"\1", text)
    return text.strip()


def is_group_chat(chat_id: str) -> bool:
    """تشخیص چت گروهی (شناسه‌های گروه در روبیکا با 'g' شروع می‌شوند)"""
    if not chat_id:
        return False
    return str(chat_id).strip().lower().startswith("g")


async def get_user_role(chat_id: str, user_id: str, bot_username: str = "") -> str:
    """
    دریافت نقش واقعی کاربر با استفاده از لیست مدیران گروه.
    """
    try:
        # ۱. دریافت لیست مدیران از API
        admins = await bot.get_chat_administrators(chat_id)
        
        # ۲. نرمال‌سازی پاسخ (اگر به صورت dict یا لیست برگشت)
        if isinstance(admins, dict):
            admin_list = admins.get("data", {}).get("members", []) or admins.get("members", [])
        else:
            admin_list = admins

        # ۳. بررسی اینکه کاربر در لیست مدیران هست یا نه
        for admin in admin_list:
            # شناسه‌ی هر مدیر ممکنه در کلیدهای مختلف باشه
            admin_id = str(admin.get("user_guid") or admin.get("member_guid") or admin.get("guid") or "")
            if admin_id == str(user_id):
                # اگر سطح دسترسی یا نقشش نوشته شده بود، برگردون
                role = admin.get("role") or admin.get("access") or admin.get("member_type", "")
                if role:
                    if "Owner" in role or "مالک" in role:
                        return "مالک"
                    if "Admin" in role or "ادمین" in role:
                        return "ادمین"
                # اگر همه ادمین‌ها در لیست بودن ولی نوعشون مشخص نبود
                return "ادمین"

        # ۴. اگر کاربر توی لیست نبود، یعنی کاربر عادیه
        return "عضو"
        
    except Exception as e:
        print(f"⚠️ ROLE DETECTION ERROR: {e}", flush=True)
        return "عضو"


# ================== متغیر وضعیت ربات ==================
bot_was_activated = False


# ================== هندلر پیام‌ها ==================
@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    global bot_was_activated

    try:
        raw_text = (message.text or "").strip()
        clean_text = clean_message(raw_text)
        chat_id = str(message.chat_id) if message.chat_id else ""

        print(f"📩 MESSAGE | chat={chat_id} | raw={raw_text!r} | clean={clean_text!r}", flush=True)

        # ============ فقط توی گروه کار کن ============
        if not is_group_chat(chat_id):
            return

        # ============ دستور «فعال» ============
        if clean_text in ("فعال", "فاعل"):
            print("✅ ACTIVATE COMMAND", flush=True)

            if not bot_was_activated:
                reply_text = "✅ ربات فعال شد."
                bot_was_activated = True
            else:
                reply_text = "✅ ربات فعال است."

            await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # ============ دستور «مقام» ============
        if clean_text == "مقام":
            print("✅ RANK COMMAND", flush=True)

            # دریافت نقش واقعی با استفاده از لیست مدیران
            role = await get_user_role(chat_id, message.sender_id)

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
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN ERROR: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
