import os
import asyncio
from rubka import Robot

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()
bot = Robot(token=TOKEN)

print("===== SEARCHING KEYPAD CLASSES =====", flush=True)

# جستجو در کل rubka برای کلاس‌های مرتبط با کیبورد
import rubka
for module_name in dir(rubka):
    if not module_name.startswith('_'):
        obj = getattr(rubka, module_name)
        name_lower = module_name.lower()
        if 'key' in name_lower or 'button' in name_lower or 'inline' in name_lower or 'callback' in name_lower:
            print(f"🎯 FOUND: rubka.{module_name} = {obj}", flush=True)

# جستجو در زیر ماژول‌ها
print("\n===== SUBMODULES =====", flush=True)
try:
    import rubka.keypad as kp
    for attr in dir(kp):
        if not attr.startswith('_'):
            print(f"🔹 rubka.keypad.{attr}", flush=True)
except Exception as e:
    print(f"❌ rubka.keypad not available: {e}", flush=True)

try:
    import rubka.context as ctx
    for attr in dir(ctx):
        if not attr.startswith('_'):
            print(f"🔹 rubka.context.{attr}", flush=True)
except Exception as e:
    print(f"❌ rubka.context not available: {e}", flush=True)

# بررسی متدهای ربات برای ارسال کیبورد
print("\n===== BOT SEND METHODS =====", flush=True)
for attr in dir(bot):
    if not attr.startswith('_'):
        if 'keypad' in attr.lower() or 'button' in attr.lower() or 'inline' in attr.lower() or 'callback' in attr.lower():
            print(f"🤖 bot.{attr}", flush=True)

async def main():
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
