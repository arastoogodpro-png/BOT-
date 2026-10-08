import os
import time
import asyncio

from rubka import Robot, Message


# =========================
# تنظیمات
# =========================

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN در Environment Variables پیدا نشد.")


# =========================
# ساخت ربات
# =========================

bot = Robot(token=TOKEN)


# =========================
# دریافت تمام پیام‌ها
# =========================

@bot.on_message()
async def handle_message(bot: Robot, message: Message):

    try:
        text = (message.text or "").strip()

        # لاگ برای اینکه بفهمیم پیام واقعاً به ربات رسیده
        print(
            f"📩 MESSAGE RECEIVED | "
            f"chat_id={message.chat_id} | "
            f"sender_id={message.sender_id} | "
            f"text={text!r}",
            flush=True
        )

        # فقط برای تست
        if text == "فعال":

            print("✅ فعال دریافت شد؛ پاسخ تا 5 ثانیه دیگر ارسال می‌شود.", flush=True)

            await asyncio.sleep(5)

            await message.reply(
                "✅ ربات پیام «فعال» را دریافت کرد.\n"
                "🤖 مسیر دریافت پیام درست کار می‌کند."
            )

            print("📤 پاسخ ارسال شد.", flush=True)

    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}", flush=True)


# =========================
# شروع
# =========================

print("🤖 RP Group Manager TEST is starting...", flush=True)

# راه‌اندازی اولیه 30 ثانیه
time.sleep(30)

print("🚀 Bot is ready and listening for messages...", flush=True)

# اجرای ربات
bot.run()
