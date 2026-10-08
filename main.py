import os
import asyncio
from rubka import Robot
from rubka.keypad import ChatKeypadBuilder

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()
bot = Robot(token=TOKEN)

print("===== ChatKeypadBuilder METHODS =====", flush=True)
for attr in dir(ChatKeypadBuilder):
    if not attr.startswith('_'):
        print(f"🔹 {attr}", flush=True)

# تست ساخت
print("\n===== TRYING TO BUILD =====", flush=True)
try:
    b = ChatKeypadBuilder()
    print(f"✅ Instance created", flush=True)
    for attr in dir(b):
        if not attr.startswith('_'):
            try:
                val = getattr(b, attr)
                if not callable(val):
                    print(f"🔸 instance.{attr} = {val!r}", flush=True)
            except:
                pass
except Exception as e:
    print(f"❌ ERROR: {e}", flush=True)

# تست ساخت با row
print("\n===== TRYING row() =====", flush=True)
try:
    b = ChatKeypadBuilder()
    result = b.row("دکمه1", "دکمه2")
    print(f"✅ row() returned: {result!r}", flush=True)
    print(f"✅ Builder state: {b.__dict__}", flush=True)
    keypad = b.build()
    print(f"✅ build() returned: {keypad!r}", flush=True)
    print(f"✅ Keypad type: {type(keypad)}", flush=True)
    if hasattr(keypad, '__dict__'):
        print(f"✅ Keypad dict: {keypad.__dict__}", flush=True)
except Exception as e:
    print(f"❌ ROW ERROR: {e}", flush=True)

# لیست متدهای bot که به keypad ربط دارن
print("\n===== BOT KEYPAD METHODS =====", flush=True)
for attr in dir(bot):
    if not attr.startswith('_'):
        if 'keypad' in attr.lower() or 'keyboard' in attr.lower() or 'reply' in attr.lower() or 'chat' in attr.lower():
            print(f"🤖 bot.{attr}", flush=True)

# بررسی امضای send_message
print("\n===== send_message SIGNATURE =====", flush=True)
try:
    import inspect
    sig = inspect.signature(bot.send_message)
    print(f"📋 {sig}", flush=True)
except Exception as e:
    print(f"❌ SIG ERROR: {e}", flush=True)

# بررسی متدهای دیگه برای ارسال کیبورد
print("\n===== ALL SEND METHODS =====", flush=True)
for attr in dir(bot):
    if not attr.startswith('_') and attr.startswith('send'):
        try:
            import inspect
            sig = inspect.signature(getattr(bot, attr))
            print(f"📤 bot.{attr}{sig}", flush=True)
        except:
            print(f"📤 bot.{attr}", flush=True)

async def main():
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
