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
    تشخیص نقش کاربر با استفاده از get_chat_info
    """
    try:
        # دریافت اطلاعات کامل گروه
        chat_info = await bot.get_chat_info(chat_id)
        print(f"🔍 CHAT INFO: {chat_info}", flush=True)

        if not chat_info:
            return "عضو"

        # استخراج داده‌ها
        data = chat_info
        if isinstance(chat_info, dict) and "data" in chat_info:
            data = chat_info["data"]

        user_id_str = str(user_id)

        # ۱. بررسی مالک گروه
        owner_id = str(
            data.get("owner_id") or 
            data.get("creator_id") or 
            data.get("owner_guid") or 
            ""
        )
        if owner_id == user_id_str:
            return "مالک"

        # ۲. بررسی ادمین‌ها (در کلیدهای مختلف)
        admins = (
            data.get("admins") or 
            data.get("admin_list") or 
            data.get("administrators") or 
            []
        )

        if isinstance(admins, list):
            for admin in admins:
                if not isinstance(admin, dict):
                    continue
                admin_id = str(
                    admin.get("user_guid") or 
                    admin.get("member_guid") or 
                    admin.get("guid") or 
                    admin.get("user_id") or 
                    ""
                )
                if admin_id == user_id_str:
                    role = str(
                        admin.get("role") or 
                        admin.get("access") or 
                        admin.get("type") or 
                        ""
                    ).lower()
                    if "owner" in role or "مالک" in role:
                        return "مالک"
                    return "ادمین"

        # ۳. اگه توی لیست ادمین‌ها نبود
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
