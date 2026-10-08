import os
import asyncio
from rubka import Robot, Message

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

# هندلر عمومی برای همه پیام‌ها
@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    try:
        text = (message.text or "").strip()
        print(f"📩 MESSAGE | chat={message.chat_id} | text={text!r}", flush=True)

        # فقط به کلمات فعال‌سازی جواب بده
        if text not in ("فعال", "فاعل", "/start"):
            return

        print("✅ ACTIVATE COMMAND", flush=True)

        # ارسال پیام به گروه
        result = await bot.send_message(
            chat_id=message.chat_id,
            text="✅ ربات فعال است و پیام شما را دریافت کرد.",
            reply_to_message_id=message.message_id,
            disable_notification=False
        )
        print(f"📤 SENT | {result}", flush=True)

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
