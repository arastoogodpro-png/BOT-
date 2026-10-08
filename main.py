import os
import asyncio
import traceback
import time

from rubka import Robot


# =========================================
# CONFIG
# =========================================

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN پیدا نشد.")


bot = Robot(
    token=TOKEN,
    retries=10,
    retry_delay=3,
    timeout=30,
    safeSendMode=True,
)


# =========================================
# DUPLICATE PROTECTION
# =========================================

processed_messages = {}
MAX_CACHE_SIZE = 500


def already_processed(message_id):
    if not message_id:
        return True

    message_id = str(message_id)

    # اگر قبلاً پردازش شده
    if message_id in processed_messages:
        return True

    processed_messages[message_id] = time.time()

    # تمیز کردن cache
    if len(processed_messages) > MAX_CACHE_SIZE:
        oldest = min(
            processed_messages,
            key=processed_messages.get
        )
        processed_messages.pop(oldest, None)

    return False


# =========================================
# SEND RESPONSE
# =========================================

async def send_response(chat_id, message_id):

    try:
        await asyncio.sleep(5)

        result = await bot.send_message(
            chat_id=chat_id,
            text="✅ ربات فعال است و پیام شما را دریافت کرد.",
            reply_to_message_id=message_id
        )

        print(
            f"📤 RESPONSE SENT | result={result}",
            flush=True
        )

    except Exception as e:

        print(
            f"❌ SEND ERROR: {type(e).__name__}: {e}",
            flush=True
        )

        traceback.print_exc()


# =========================================
# PROCESS UPDATE
# =========================================

async def process_update(update):

    try:

        if not isinstance(update, dict):
            return

        update_type = update.get("type")

        print(
            f"🔔 UPDATE TYPE: {update_type}",
            flush=True
        )

        if update_type != "NewMessage":
            return

        msg = update.get("new_message") or {}

        chat_id = update.get("chat_id")
        message_id = msg.get("message_id")
        sender_id = msg.get("sender_id")
        text = str(msg.get("text") or "").strip()

        if not chat_id or not message_id:
            return

        # جلوگیری از تکرار
        if already_processed(message_id):
            print(
                f"⏭ DUPLICATE SKIPPED | message_id={message_id}",
                flush=True
            )
            return

        print(
            f"💬 NEW MESSAGE | "
            f"chat={chat_id} | "
            f"sender={sender_id} | "
            f"text={text!r}",
            flush=True
        )

        # فعال
        # فاعل هم عمداً قبول می‌شود تا اشتباه تایپی باعث مشکل نشود
        if text in ("فعال", "فاعل"):

            print(
                f"✅ ACTIVATE COMMAND | chat={chat_id}",
                flush=True
            )

            asyncio.create_task(
                send_response(
                    chat_id,
                    message_id
                )
            )

    except Exception as e:

        print(
            f"❌ PROCESS UPDATE ERROR: "
            f"{type(e).__name__}: {e}",
            flush=True
        )

        traceback.print_exc()


# =========================================
# MAIN POLLING
# =========================================

async def main():

    print(
        "🤖 RP GROUP MANAGER STARTING...",
        flush=True
    )

    # تست توکن
    try:

        me = await bot.get_me()

        print(
            f"✅ TOKEN OK | {me}",
            flush=True
        )

    except Exception as e:

        print(
            f"❌ GETME ERROR: "
            f"{type(e).__name__}: {e}",
            flush=True
        )

        raise

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
                    f"⚠️ INVALID RESPONSE: {result!r}",
                    flush=True
                )

                await asyncio.sleep(3)
                continue

            data = result.get("data") or {}

            # بسیار مهم:
            # Offset را جلو می‌بریم تا همان صف دوباره خوانده نشود
            next_offset = data.get("next_offset_id")

            if next_offset:
                offset_id = next_offset

            updates = data.get("updates") or []

            if updates:

                print(
                    f"📦 {len(updates)} UPDATES RECEIVED",
                    flush=True
                )

                for update in updates:
                    await process_update(update)

            await asyncio.sleep(1)

        except Exception as e:

            print(
                f"⚠️ MAIN LOOP ERROR: "
                f"{type(e).__name__}: {e}",
                flush=True
            )

            # خطای موقت مثل 502 باعث خاموش شدن نشود
            await asyncio.sleep(5)


# =========================================
# START
# =========================================

try:

    asyncio.run(main())

except KeyboardInterrupt:

    print(
        "🛑 BOT STOPPED",
        flush=True
    )

except Exception as e:

    print(
        f"❌ FATAL ERROR: "
        f"{type(e).__name__}: {e}",
        flush=True
    )

    traceback.print_exc()

finally:

    try:

        if hasattr(bot, "close"):
            asyncio.run(bot.close())

    except Exception:
        pass
