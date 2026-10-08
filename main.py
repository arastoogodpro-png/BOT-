import os
import asyncio
from rubka import Robot, Message

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

# هندلر بدون هیچ شرطی - هر پیامی که برسه رو لاگ می‌کنه
@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    print(f"📩 RAW MESSAGE RECEIVED: {message}", flush=True)
    print(f"📩 TEXT: {message.text}", flush=True)
    print(f"📩 CHAT_ID: {message.chat_id}", flush=True)

    # هر پیامی که رسید، جواب بده
    try:
        await bot.send_message(
            chat_id=message.chat_id,
            text="✅ تست: پیام شما دریافت شد.",
            reply_to_message_id=message.message_id
        )
        print("📤 SENT SUCCESSFULLY", flush=True)
    except Exception as e:
        print(f"❌ SEND ERROR: {e}", flush=True)

async def main():
    print("🤖 TEST BOT STARTING...", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN ERROR: {type(e).__name__}: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
