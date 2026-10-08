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
    """
    تشخیص نقش واقعی کاربر با استفاده از فیلد status
    """
    try:
        member_info = await bot.get_chat_member(chat_id, user_id)
        print(f"🔍 MEMBER INFO: {member_info}", flush=True)

        if not member_info:
            return "عضو"

        # استخراج داده‌ها
        data = member_info
        if isinstance(member_info, dict) and "data" in member_info:
            data = member_info["data"]

        # استخراج chat_member
        chat_member = data.get("chat_member", {}) if isinstance(data, dict) else {}
        
        # دریافت status (Creator / Admin / Member)
        status = str(chat_member.get("status", "")).strip().lower()
        
        # دریافت access_list برای بررسی بیشتر
        access_list = chat_member.get("access_list", [])
        if not isinstance(access_list, list):
            access_list = []

        print(f"🔍 STATUS: {status!r} | ACCESS: {access_list}", flush=True)

        # ============ تشخیص نقش ============
        if status in ("creator", "owner"):
            return "مالک"
        
        if status in ("admin", "administrator"):
            return "ادمین"
        
        if status in ("member", "normal"):
            return "عضو"

        # اگه status خالی بود، از access_list استفاده کن
        if access_list:
            admin_permissions = [
                "BanMember", "DeleteGlobalAllMessages", 
                "EditMyMessages", "SendMessages", "ViewMembers"
            ]
            if any(perm in access_list for perm in ["BanMember", "DeleteGlobalAllMessages"]):
                return "ادمین"
            return "عضو"

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

            # دریافت نقش واقعی
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
