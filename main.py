import os
import asyncio
from rubka import Robot, InlineBuilder

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()
bot = Robot(token=TOKEN)

print("===== INLINEBUILDER METHODS =====", flush=True)
for attr in dir(InlineBuilder):
    if not attr.startswith('_'):
        print(f"🔹 {attr}", flush=True)

# تست ساخت یک نمونه
print("\n===== TRYING TO INSTANTIATE =====", flush=True)
try:
    b = InlineBuilder()
    print(f"✅ InlineBuilder() created: {b}", flush=True)
    print(f"✅ Type: {type(b)}", flush=True)
    for attr in dir(b):
        if not attr.startswith('_'):
            try:
                val = getattr(b, attr)
                print(f"🔸 instance.{attr} = {val} ({type(val).__name__})", flush=True)
            except Exception as e:
                print(f"🔸 instance.{attr} (error: {e})", flush=True)
except Exception as e:
    print(f"❌ ERROR: {e}", flush=True)

async def main():
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
