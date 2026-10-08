import os
import asyncio
import traceback

from rubka import Robot

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("RUBIKA_TOKEN پیدا نشد.")

bot = Robot(
    token=TOKEN,
    retries=10,
    retry_delay=3,
    timeout=30,
    safeSendMode=True,
)


async def send_delayed(chat_id, message_id):
    try:
        await asyncio.sleep(5)

        await bot.send_message(
            chat_id=chat_id,
            text="✅ ربات فعال است.",
            reply_to_message_id=message_id
        )

        print("📤 پاسخ ارسال شد", flush=True)

    except Exception as e:
        print(
            f"❌ SEND ERROR: {type(e).__name__}: {e}",
            flush=True
        )


async def process_update(update):
    try:
        if not isinstance(update, dict):
            return

        update_type = update.get("type")

        print(
            f"🔔 UPDATE TYPE: {update_type}",
            flush=True
        )

        # فقط پیام جدید
        if update_type != "NewMessage":
            return

        msg = update.get("new_message") or {}

        chat_id = update.get("chat_id")
        message_id = msg.get("message_id")
        sender_id = msg.get("sender_id")
        text = str(msg.get("text") or "").strip()

        print(
            f"💬 NEW MESSAGE | "
            f"chat={chat_id} | "
            f"sender={sender_id} | "
            f"text={text!r}",
            flush=True
        )

        if text == "فعال" and chat_id and message_id:
            print("✅ فعال دریافت شد", flush=True)

            asyncio.create_task(
                send_delayed(
                    chat_id,
                    message_id
                )
            )

    except Exception as e:
        print(
            f"❌ PROCESS ERROR: {type(e).__name__}: {e}",
            flush=True
        )
        traceback.print_exc()


async def main():
    print("🤖 RP GROUP MANAGER STARTING...", flush=True)

    # تست توکن
    me = await bot.get_me()

    if not me or me.get("status") != "OK":
        raise RuntimeError(
            f"getMe ناموفق بود: {me}"
        )

    print("✅ TOKEN OK", flush=True)

    offset_id = None

    print(
        "🚀 DIRECT POLLING STARTED",
        flush=True
    )

    while True:
        try:
            result = await bot.get_updates(
                offset_id=offset_id,
                limit=100
            )

            if not isinstance(result, dict):
                print(
                    f"⚠️ پاسخ غیرمنتظره: {result!r}",
                    flush=True
                )
                await asyncio.sleep(3)
                continue

            data = result.get("data") or {}

            next_offset = data.get("next_offset_id")

            if next_offset:
                offset_id = next_offset

            updates = data.get("updates") or []

            if updates:
                print(
                    f"📦 {len(updates)} آپدیت دریافت شد",
                    flush=True
                )

                for update in updates:
                    await process_update(update)

            await asyncio.sleep(1)

        except Exception as e:
            print(
                f"⚠️ GET UPDATES ERROR: "
                f"{type(e).__name__}: {e}",
                flush=True
            )

            await asyncio.sleep(5)


try:
    asyncio.run(main())

except KeyboardInterrupt:
    print("🛑 STOPPED", flush=True)

except Exception as e:
    print(
        f"❌ FATAL: {type(e).__name__}: {e}",
        flush=True
    )
    traceback.print_exc()

finally:
    try:
        if hasattr(bot, "close"):
            asyncio.run(bot.close())
    except Exception:
        pass
