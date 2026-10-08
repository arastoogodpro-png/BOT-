import os
import asyncio
import traceback

from rubka import Robot, Message


TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("RUBIKA_TOKEN تنظیم نشده است.")


bot = Robot(
    token=TOKEN,
    retries=10,
    retry_delay=2,
    timeout=30,
    safeSendMode=True,
    max_cache_size=2000,
    max_msg_age=60,
)


@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    try:
        text = (message.text or "").strip()

        print(
            f"📩 MESSAGE | chat={message.chat_id} "
            f"| sender={message.sender_id} | text={text!r}",
            flush=True
        )

        if text not in ("فعال", "فاعل"):
            return

        print("✅ ACTIVATE COMMAND", flush=True)

        await asyncio.sleep(5)

        # اول reply معمولی
        try:
            result = await message.reply(
                "✅ ربات فعال است و پیام شما را دریافت کرد."
            )

            print(
                f"📤 REPLY OK | {result}",
                flush=True
            )
            return

        except Exception as reply_error:
            print(
                f"⚠️ REPLY FAILED: "
                f"{type(reply_error).__name__}: {reply_error}",
                flush=True
            )

        # اگر reply شکست خورد، ارسال مستقیم
        try:
            result = await bot.send_message(
                chat_id=message.chat_id,
                text="✅ ربات فعال است و پیام شما را دریافت کرد.",
                disable_notification=False
            )

            print(
                f"📤 DIRECT SEND OK | {result}",
                flush=True
            )

        except Exception as send_error:
            print(
                f"❌ DIRECT SEND FAILED: "
                f"{type(send_error).__name__}: {send_error}",
                flush=True
            )

    except Exception as e:
        print(
            f"❌ HANDLER ERROR: {type(e).__name__}: {e}",
            flush=True
        )
        traceback.print_exc()


print("🤖 RP GROUP MANAGER STARTING...", flush=True)
print("🚀 BOT RUNNING...", flush=True)

bot.run()
