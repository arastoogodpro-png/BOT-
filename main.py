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


async def get_user_role(chat_id: str, user_id: str) -> str:
    """
    دریافت نقش واقعی کاربر با استفاده از متد get_chat_admins
    """
    try:
        # دریافت لیست ادمین‌های گروه
        admins_response = await bot.get_chat_admins(chat_id)
        
        # استخراج لیست ادمین‌ها (ساختار پاسخ ممکنه dict یا لیست باشه)
        admin_list = []
        if isinstance(admins_response, dict):
            data = admins_response.get("data", {})
            admin_list = data.get("admins", []) or data.get("members", []) or data.get("list", [])
        elif isinstance(admins_response, list):
            admin_list = admins_response

        # اگر لیست خالی بود، شاید نیاز باشه به شکل دیگه‌ای استخراج کنیم
        if not admin_list and isinstance(admins_response, dict):
            # جستجوی بازگشتی برای پیدا کردن لیست اعضا
            for key, value in admins_response.items():
                if isinstance(value, list) and len(value) > 0:
                    if isinstance(value[0], dict) and ("user_guid" in value[0] or "member_guid" in value[0] or "guid" in value[0]):
                        admin_list = value
                        break

        # بررسی اینکه کاربر در لیست ادمین‌ها هست یا نه
        for admin in admin_list:
            if not isinstance(admin, dict):
                continue
                
            admin_id = str(
                admin.get("user_guid") or 
                admin.get("member_guid") or 
                admin.get("guid") or 
                admin.get("user_id") or 
                ""
            )
            
            if admin_id == str(user_id):
                # پیدا کردن نقش دقیق (مالک یا ادمین)
                role = str(
                    admin.get("role") or 
                    admin.get("access") or 
                    admin.get("member_type") or 
                    admin.get("type") or 
                    ""
                ).lower()
                
                if "owner" in role or "مالک" in role:
                    return "مالک"
                if "admin" in role or "ادمین" in role:
                    return "ادمین"
                # اگه توی لیست ادمین‌ها بود ولی نقشش مشخص نبود، حداقل ادمین حسابش می‌کنیم
                return "ادمین"

        # اگه کاربر توی لیست ادمین‌ها نبود
        return "عضو"

    except Exception as e:
        print(f"⚠️ ROLE DETECTION ERROR: {type(e).__name__}: {e}", flush=True)
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

            # دریافت نقش واقعی با استفاده از get_chat_admins
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
