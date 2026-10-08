import os
import asyncio

from rubka import Robot, Message


TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("RUBIKA_TOKEN پیدا نشد.")


bot = Robot(token=TOKEN)


@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    try:
        text = (message.text or "").strip()

        print(
            f"📩 MESSAGE RECEIVED | "
            f"chat={message.chat_id} | "
            f"sender={message.sender_id} | "
            f"text={text!r}",
            flush=True
        )

        if text == "فعال":
            print("✅ فعال دریافت شد", flush=True)

            await asyncio.sleep(5)

            await message.reply(
                "✅ فعال شدم!\n"
                "🤖 پیام شما با موفقیت دریافت شد."
            )

            print("📤 RESPONSE SENT", flush=True)

    except Exception as e:
        print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)


print("🤖 RP GROUP MANAGER STARTING...", flush=True)

print("🚀 BOT STARTING...", flush=True)

bot.run()
