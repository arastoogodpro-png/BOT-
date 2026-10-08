import os
import asyncio
import time
import traceback

from rubka import Robot


# ==========================================
# تنظیمات
# ==========================================

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN پیدا نشد.")

bot = Robot(
    token=TOKEN,
    retries=8,
    retry_delay=2,
    timeout=30,
    raise_errors=True,
    safeSendMode=True,
)


# ==========================================
# تبدیل پاسخ Rubka به dict
# ==========================================

def as_dict(value):
    if isinstance(value, dict):
        return value

    try:
        return dict(value)
    except Exception:
        pass

    try:
        return value.to_dict()
    except Exception:
        pass

    return {}


# ==========================================
# پاسخ با تأخیر 5 ثانیه
# ==========================================

async def delayed_reply(chat_id, message_id):
    try:
        await asyncio.sleep(5)

        result = await bot.send_message(
            chat_id=chat_id,
            text="✅ ربات فعال است و پیام شما را دریافت کرد.",
            reply_to_message_id=message_id
        )

        print(
            f"📤 پاسخ ارسال شد | chat={chat_id} | result={result}",
            flush=True
        )

    except Exception as e:
        print(
            f"❌ خطا هنگام ارسال پاسخ: {type(e).__name__}: {e}",
            flush=True
        )


# ==========================================
# پردازش پیام
# ==========================================

async def process_update(update):
    try:
        update = as_dict(update)

        if update.get("type") != "NewMessage":
            return

        msg = as_dict(update.get("new_message", {}))

        if not msg:
            return

        message_id = msg.get("message_id")
        sender_id = msg.get("sender_id")
        chat_id = update.get("chat_id")
        text = str(msg.get("text") or "").strip()

        # پیام بدون شناسه معتبر
        if not message_id or not chat_id:
            return

        # جلوگیری از پردازش پیام‌های خیلی قدیمی
        msg_time = msg.get("time")

        if msg_time:
            try:
                age = time.time() - float(msg_time)

                if age > 90:
                    print(
                        f"⏭ پیام قدیمی رد شد | age={age:.1f}s",
                        flush=True
                    )
                    return

            except Exception:
                pass

        print(
            f"📩 پیام دریافت شد | "
            f"chat={chat_id} | "
            f"sender={sender_id} | "
            f"text={text!r}",
            flush=True
        )

        # دستور فعال
        if text == "فعال":
            print(
                f"✅ دستور فعال دریافت شد | chat={chat_id}",
                flush=True
            )

            # پاسخ غیرمسدودکننده
            asyncio.create_task(
                delayed_reply(
                    chat_id,
                    message_id
                )
            )

    except Exception as e:
        print(
            f"❌ PROCESS UPDATE ERROR: {type(e).__name__}: {e}",
            flush=True
        )
        traceback.print_exc()


# ==========================================
# حلقه اصلی دریافت پیام
# ==========================================

async def main():
    print("🤖 RP GROUP MANAGER STARTING...", flush=True)

    # تست توکن
    try:
        me = await bot.get_me()
        print(
            f"✅ TOKEN OK | getMe={me}",
            flush=True
        )
    except Exception as e:
        print(
            f"❌ TOKEN / GETME ERROR: {type(e).__name__}: {e}",
            flush=True
        )
        raise

    offset_id = None

    print(
        "🚀 شروع دریافت مستقیم پیام‌ها...",
        flush=True
    )

    while True:
        try:
            result = await bot.get_updates(
                offset_id=offset_id,
                limit=100
            )

            data = as_dict(result)

            # بررسی وضعیت پاسخ
            status = data.get("status")

            if status and status != "OK":
                print(
                    f"⚠️ API STATUS: {status}",
                    flush=True
                )

            inner = as_dict(data.get("data", {}))

            # offset جدید
            next_offset = inner.get("next_offset_id")

            if next_offset:
                offset_id = next_offset

            updates = inner.get("updates", [])

            if updates:
                print(
                    f"📦 {len(updates)} آپدیت دریافت شد",
                    flush=True
                )

                for update in updates:
                    await process_update(update)

            # فاصله کوتاه بین درخواست‌ها
            await asyncio.sleep(0.5)

        except Exception as e:
            # 502 و خطاهای موقتی اینجا باعث خاموش شدن ربات نمی‌شوند
            print(
                f"⚠️ MAIN LOOP ERROR: {type(e).__name__}: {e}",
                flush=True
            )

            # کمی صبر و تلاش مجدد
            await asyncio.sleep(5)


# ==========================================
# اجرای برنامه
# ==========================================

try:
    asyncio.run(main())

except KeyboardInterrupt:
    print("🛑 Bot stopped.", flush=True)

except Exception as e:
    print(
        f"❌ FATAL ERROR: {type(e).__name__}: {e}",
        flush=True
    )
    traceback.print_exc()

finally:
    try:
        asyncio.run(bot.close())
    except Exception:
        pass
