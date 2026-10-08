import os
import asyncio
import traceback

from rubka import Robot


# ==========================================
# TOKEN
# ==========================================

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN پیدا نشد.")


# ==========================================
# BOT
# ==========================================

bot = Robot(token=TOKEN)


# ==========================================
# جلوگیری از پردازش تکراری
# ==========================================

processed_ids = set()
MAX_PROCESSED = 1000


def was_processed(message_id):
    message_id = str(message_id)

    if message_id in processed_ids:
        return True

    processed_ids.add(message_id)

    if len(processed_ids) > MAX_PROCESSED:
        processed_ids.pop()

    return False


# ==========================================
# ارسال پیام
# ==========================================

async def send_answer(chat_id):
    try:
        # دقیقاً 5 ثانیه تأخیر
        await asyncio.sleep(5)

        result = await bot.send_message(
            chat_id=chat_id,
            text="✅ ربات فعال است و پیام شما را دریافت کرد."
        )

        print(
            f"📤 MESSAGE SENT | chat={chat_id} | result={result}",
            flush=True
        )

    except Exception as e:
        print(
            f"❌ SEND ERROR: {type(e).__name__}: {e}",
            flush=True
        )
        traceback.print_exc()


# ==========================================
# پردازش Update
# ==========================================

async def process_update(update):
    try:

        if not isinstance(update, dict):
            return

        update_type = update.get("type")

        if update_type != "NewMessage":
            return

        new_message = update.get("new_message") or {}

        if not isinstance(new_message, dict):
            return

        chat_id = update.get("chat_id")
        message_id = new_message.get("message_id")
        sender_id = new_message.get("sender_id")

        text = str(
            new_message.get("text") or ""
        ).strip()

        if not chat_id or not message_id:
            return

        # جلوگیری از دوباره‌کاری
        if was_processed(message_id):
            print(
                f"⏭ DUPLICATE SKIPPED | {message_id}",
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
        # فاعل هم پذیرفته می‌شود
        if text in ("فعال", "فاعل"):

            print(
                f"✅ ACTIVATE COMMAND | chat={chat_id}",
                flush=True
            )

            asyncio.create_task(
                send_answer(chat_id)
            )

    except Exception as e:
        print(
            f"❌ UPDATE ERROR: {type(e).__name__}: {e}",
            flush=True
        )
        traceback.print_exc()


# ==========================================
# MAIN
# ==========================================

async def main():

    print(
        "🤖 RP GROUP MANAGER STARTING...",
        flush=True
    )

    # --------------------------------------
    # بررسی توکن
    # --------------------------------------

    try:
        me = await bot.get_me()

        if not isinstance(me, dict):
            raise RuntimeError(
                f"پاسخ getMe نامعتبر است: {me!r}"
            )

        if me.get("status") != "OK":
            raise RuntimeError(
                f"توکن معتبر نیست: {me!r}"
            )

        bot_info = (me.get("data") or {}).get("bot") or {}

        print(
            f"✅ TOKEN OK | username={bot_info.get('username')}",
            flush=True
        )

    except Exception as e:

        print(
            f"❌ GETME ERROR: {type(e).__name__}: {e}",
            flush=True
        )

        raise


    # --------------------------------------
    # تخلیه آپدیت‌های قدیمی
    # --------------------------------------

    offset_id = None

    try:

        old_result = await bot.get_updates(
            limit=100
        )

        if isinstance(old_result, dict):

            old_data = old_result.get("data") or {}

            offset_id = old_data.get(
                "next_offset_id"
            )

            old_updates = old_data.get(
                "updates"
            ) or []

            print(
                f"🧹 OLD UPDATES SKIPPED: {len(old_updates)}",
                flush=True
            )

    except Exception as e:

        print(
            f"⚠️ STARTUP GET_UPDATES ERROR: "
            f"{type(e).__name__}: {e}",
            flush=True
        )

        await asyncio.sleep(3)


    # --------------------------------------
    # شروع Polling
    # --------------------------------------

    print(
        "🚀 LISTENING FOR NEW MESSAGES...",
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
                    f"⚠️ INVALID API RESPONSE: {result!r}",
                    flush=True
                )

                await asyncio.sleep(3)
                continue


            data = result.get("data") or {}

            # Offset جدید
            next_offset_id = data.get(
                "next_offset_id"
            )

            if next_offset_id:
                offset_id = next_offset_id


            updates = data.get(
                "updates"
            ) or []


            if updates:

                print(
                    f"📦 NEW UPDATES: {len(updates)}",
                    flush=True
                )

                for update in updates:
                    await process_update(update)


            await asyncio.sleep(0.5)


        except Exception as e:

            print(
                f"⚠️ POLLING ERROR: "
                f"{type(e).__name__}: {e}",
                flush=True
            )

            # خطاهایی مثل 502 نباید ربات را خاموش کنند
            await asyncio.sleep(5)


# ==========================================
# START
# ==========================================

try:

    asyncio.run(main())

except KeyboardInterrupt:

    print(
        "🛑 BOT STOPPED",
        flush=True
    )

except Exception as e:

    print(
        f"❌ FATAL ERROR: {type(e).__name__}: {e}",
        flush=True
    )

    traceback.print_exc()
