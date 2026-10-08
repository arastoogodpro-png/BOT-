import os
import asyncio
from rubka import Robot
from rubka.keypad import ChatKeypadBuilder

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()
bot = Robot(token=TOKEN)

print("===== TEST button_simple =====", flush=True)

# تست ۱: button_simple چه چیزی برمی‌گردونه؟
try:
    b = ChatKeypadBuilder()
    btn = b.button_simple(id="test_id", text="Test Text")
    print(f"✅ button_simple returned: {btn!r}", flush=True)
    print(f"✅ Type: {type(btn)}", flush=True)
except Exception as e:
    print(f"❌ button_simple ERROR: {e}", flush=True)
    try:
        b = ChatKeypadBuilder()
        btn = b.button_simple("test_id", "Test Text")
        print(f"✅ button_simple (positional) returned: {btn!r}", flush=True)
    except Exception as e2:
        print(f"❌ button_simple positional ERROR: {e2}", flush=True)

# تست ۲: با button_simple در row
print("\n===== TEST row with buttons =====", flush=True)
try:
    b = ChatKeypadBuilder()
    btn1 = b.button_simple(id="btn1", text="📢 کانال رسمی")
    btn2 = b.button_simple(id="btn2", text="📚 آموزش")
    b.row(btn1, btn2)
    print(f"✅ Builder state after row: {b.__dict__}", flush=True)
    keypad = b.build()
    print(f"✅ Keypad: {keypad}", flush=True)
except Exception as e:
    print(f"❌ ROW WITH BUTTONS ERROR: {e}", flush=True)

# تست ۳: ساخت دستی کیبورد
print("\n===== MANUAL KEYPAD STRUCTURE =====", flush=True)
manual_keypad = {
    "rows": [
        {"buttons": [
            {"id": "btn_channel", "type": "Simple", "button_text": "📢 کانال رسمی"},
            {"id": "btn_help", "type": "Simple", "button_text": "📚 آموزش فعال‌سازی"}
        ]},
        {"buttons": [
            {"id": "btn_users", "type": "Simple", "button_text": "👥 کاربران"},
            {"id": "btn_groups", "type": "Simple", "button_text": "🏠 گروه‌های فعال"}
        ]}
    ],
    "resize_keyboard": True,
    "on_time_keyboard": False
}
print(f"✅ Manual keypad: {manual_keypad}", flush=True)

async def main():
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
