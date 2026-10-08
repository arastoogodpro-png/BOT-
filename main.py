import os
import re
import asyncio
from rubka import Robot, Message

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)


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
    """
    تشخیص نقش کاربر با استفاده از get_chat_member
    """
    try:
        # دریافت اطلاعات کاربر در گروه
        member_info = await bot.get_chat_member(chat_id, user_id)
        print(f"🔍 MEMBER INFO: {member_info}", flush=True)

        if not member_info:
            return "عضو"

        # استخراج داده‌ها
        data = member_info
        if isinstance(member_info, dict) and "data" in member_info:
            data = member_info["data"]

        # بررسی نقش
        role = str(
            data.get("role") or 
            data.get("access") or 
            data.get("member_type") or 
            data.get("type") or 
            data.get("permission") or 
            ""
        ).lower()

        print(f"🔍 DETECTED ROLE: {role!r}", flush=True)

        if "owner" in role or "مالک" in role or "creator" in role:
            return "مالک"
        if "admin" in role or "ادمین" in role:
            return "ادمین"
        if "member" in role or "عضو" in role:
            return "عضو"

        # اگه هیچکدوم نبود، بررسی فیلدهای دیگه
        if data.get("is_owner"):
            return "مالک"
        if data.get("is_admin"):
            return "ادمین"

        return "عضو"

    except Exception as e:
        print(f"⚠️ ROLE DETECTION ERROR: {type(e).__name__}: {e}", flush=True)
        return "عضو"


bot_was_activated = False


@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    global bot_was_activated

    try:
        raw_text = (message.text or "").strip()
        clean_text = clean_message(raw_text)
        chat_id = str(message.chat_id) if message.chat_id else ""

        print(f"📩 MESSAGE | chat={chat_id} | raw={raw_text!r} | clean={clean_text!r}", flush=True)

        if not is_group_chat(chat_id):
            return

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

        if clean_text == "مقام":
            print("✅ RANK COMMAND", flush=True)
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


async def main():
    print("🤖 RP GROUP MANAGER STARTING...", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN ERROR: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
