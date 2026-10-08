import os
import time

from rubka import Robot, Message


# =========================
# Token
# =========================

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("RUBIKA_TOKEN پیدا نشد.")


# =========================
# Bot
# =========================

bot = Robot(token=TOKEN)


# =========================
# Message Handler
# =========================

@bot.on_message()
def handle_message(bot: Robot, message: Message):

    try:
        text = (message.text or "").strip()

        print(
            f"📩 MESSAGE RECEIVED | "
            f"chat_id={message.chat_id} | "
            f"sender_id={message.sender_id} | "
            f"text={text!r}",
            flush=True
        )

        if text == "فعال":

            print("✅ COMMAND فعال RECEIVED", flush=True)

            # پاسخ دقیقاً بعد از 5 ثانیه
            time.sleep(5)

            message.reply(
                "✅ فعال شدم!\n"
                "🤖 ربات پیام شما را دریافت کرد."
            )

            print("📤 REPLY SENT", flush=True)

    except Exception as e:
        print(
            f"❌ HANDLER ERROR: {type(e).__name__}: {e}",
            flush=True
        )


# =========================
# Startup
# =========================

print("🤖 RP Group Manager TEST starting...", flush=True)

# 30 ثانیه زمان راه‌اندازی
time.sleep(30)

print("🚀 BOT READY - LISTENING...", flush=True)


# =========================
# Run
# =========================

bot.run()
