import os
import asyncio
from rubka import Robot

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("RUBIKA_TOKEN پیدا نشد")

bot = Robot(
    token=TOKEN,
    retries=10,
    retry_delay=3,
    timeout=30
)

async def test():
    print("🤖 TEST START", flush=True)

    try:
        me = await bot.get_me()
        print("✅ getMe:", me, flush=True)
    except Exception as e:
        print("❌ getMe ERROR:", repr(e), flush=True)

    try:
        updates = await bot.get_updates(limit=10)
        print("✅ getUpdates:", updates, flush=True)
    except Exception as e:
        print("❌ getUpdates ERROR:", repr(e), flush=True)

asyncio.run(test())
