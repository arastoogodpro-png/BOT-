import os
import asyncio
from rubka import Robot

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()
bot = Robot(token=TOKEN)

print("===== BOT METHODS =====", flush=True)
for attr in dir(bot):
    if not attr.startswith("__"):
        print(f"🔹 {attr}", flush=True)

async def main():
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
