import os
import asyncio
from rubka import Robot, Message

# تنظیمات اولیه
TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

# ساخت ربات
bot = Robot(token=TOKEN)

# دستور فعال‌سازی - برای گروه و چت شخصی
@bot.on_message(commands=["start", "فعال", "فاعل"])
async def handle_activation(bot: Robot, message: Message):
    try:
        text = (message.text or "").strip()
        print(f"📩 MESSAGE | chat={message.chat_id} | text={text!r}", flush=True)
        print("✅ ACTIVATE COMMAND", flush=True)

        # ارسال پیام به چت با ریپلای به پیام کاربر
        await bot.send_message(
            chat_id=message.chat_id,
            text="✅ ربات فعال است و پیام شما را دریافت کرد.",
            reply_to_message_id=message.message_id,
            disable_notification=False
        )
        print("📤 SENT SUCCESSFULLY", flush=True)

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
