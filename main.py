import os
import time
import traceback

from rubka import Robot

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

print("🤖 TEST STARTING...", flush=True)

# راه‌اندازی 30 ثانیه‌ای
time.sleep(30)

print("🚀 DIRECT getUpdates TEST STARTED", flush=True)

offset_id = None

while True:
    try:
        result = bot.get_updates(
            offset_id=offset_id,
            limit=100
        )

        print(
            "📥 RAW UPDATE RESPONSE:",
            repr(result),
            flush=True
        )

        if isinstance(result, dict):
            data = result.get("data", {})

            if isinstance(data, dict):
                new_offset = data.get("next_offset_id")

                if new_offset:
                    offset_id = new_offset

                updates = data.get("updates", [])

                for update in updates:
                    print(
                        "🔔 UPDATE RECEIVED:",
                        repr(update),
                        flush=True
                    )

                    if update.get("type") != "NewMessage":
                        continue

                    chat_id = update.get("chat_id")
                    msg = update.get("new_message", {})

                    text = (msg.get("text") or "").strip()

                    print(
                        f"💬 MESSAGE: chat={chat_id} text={text!r}",
                        flush=True
                    )

                    if text == "فعال" and chat_id:

                        print(
                            "✅ فعال RECEIVED - waiting 5 seconds...",
                            flush=True
                        )

                        time.sleep(5)

                        try:
                            bot.send_message(
                                chat_id,
                                "✅ ربات پیام «فعال» را دریافت کرد."
                            )

                            print(
                                "📤 RESPONSE SENT",
                                flush=True
                            )

                        except Exception:
                            print(
                                "❌ SEND ERROR:",
                                flush=True
                            )
                            traceback.print_exc()

        time.sleep(1)

    except Exception:
        print(
            "❌ GET UPDATES ERROR:",
            flush=True
        )
        traceback.print_exc()
        time.sleep(5)
