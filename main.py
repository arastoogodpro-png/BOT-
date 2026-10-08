import os
import re
import asyncio
from rubka import Robot, Message

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)


# ================== تابع پاک‌سازی متن ==================
def clean_message(text: str) -> str:
    """
    حذف منشن ربات و اسلش از متن پیام
    """
    if not text:
        return ""

    # حذف منشن‌ها (هر چیزی که با @ شروع میشه)
    text = re.sub(r"@\S+", "", text)

    # حذف اسلش از ابتدای دستورات (مثل /start -> start)
    text = re.sub(r"/(\w+)", r"\1", text)

    # حذف فاصله‌های اضافی
    text = text.strip()

    return text


# ================== تشخیص گروه بودن چت ==================
def is_group_chat(chat_id: str) -> bool:
    """
    تشخیص اینکه آیا چت مورد نظر گروه است یا پیوی.
    در روبیکا، chat_id گروه‌ها معمولاً با حرف 'g' شروع میشه
    و chat_id کاربران با حرف 'u' یا 'b' (برای ربات‌ها).
    """
    if not chat_id:
        return False

    chat_id = str(chat_id).strip().lower()

    # گروه‌ها معمولاً با 'g' شروع میشن
    if chat_id.startswith("g"):
        return True

    # پیوی‌ها معمولاً با 'u' یا 'b' شروع میشن
    if chat_id.startswith("u") or chat_id.startswith("b"):
        return False

    # پیش‌فرض: اگه مطمئن نیستیم، فرض می‌کنیم گروه نیست
    return False


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

        print(
            f"📩 MESSAGE | chat={chat_id} | "
            f"raw={raw_text!r} | clean={clean_text!r}",
            flush=True
        )

        # ============ فقط توی گروه کار کن ============
        if not is_group_chat(chat_id):
            print("⏭️ SKIPPED (not a group)", flush=True)
            return

        # ============ دستور «فعال» ============
        if clean_text == "فعال":
            print("✅ ACTIVATE COMMAND", flush=True)

            if not bot_was_activated:
                reply_text = "✅ ربات فعال شد."
                bot_was_activated = True
            else:
                reply_text = "✅ ربات فعال است."

            result = await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT | {result}", flush=True)
            return

        # ============ دستور «مقام» ============
        if clean_text == "مقام":
            print("✅ RANK COMMAND", flush=True)

            # تشخیص نقش کاربر
            role = "عضو"  # پیش‌فرض

            try:
                # تلاش برای تشخیص نقش از فیلدهای مختلف پیام
                if hasattr(message, "sender_role") and message.sender_role:
                    role = str(message.sender_role)
                elif hasattr(message, "role") and message.role:
                    role = str(message.role)
                elif hasattr(message, "access_list") and message.access_list:
                    access = message.access_list
                    if isinstance(access, list):
                        if "Admin" in access or "Owner" in access:
                            role = "ادمین"
                        else:
                            role = "عضو"
                    elif isinstance(access, str):
                        if "Admin" in access or "Owner" in access:
                            role = "ادمین"
                        else:
                            role = "عضو"

            except Exception as e:
                print(f"⚠️ ROLE DETECTION ERROR: {e}", flush=True)

            reply_text = f"👤 مقام کاربر: {role}"

            result = await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT | {result}", flush=True)
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
