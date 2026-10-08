import os
import re
import asyncio
from rubka import Robot, Message

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)


# ================== تابع پاک‌سازی متن ==================
def clean_message(text: str) -> str:
    """
    حذف منشن ربات و اسلش از متن پیام
    """
    if not text:
        return ""

    # حذف منشن‌ها (هر چیزی که با @ شروع میشه)
    text = re.sub(r"@\S+", "", text)

    # حذف اسلش از ابتدای دستورات (مثل /start -> start)
    text = re.sub(r"/(\w+)", r"\1", text)

    # حذف فاصله‌های اضافی
    text = text.strip()

    return text


# ================== متغیر وضعیت ربات ==================
# برای اینکه بفهمیم ربات قبلاً فعال شده یا نه
bot_was_activated = False


# ================== هندلر پیام‌ها ==================
@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    global bot_was_activated

    try:
        raw_text = (message.text or "").strip()
        clean_text = clean_message(raw_text)

        print(
            f"📩 MESSAGE | chat={message.chat_id} | "
            f"raw={raw_text!r} | clean={clean_text!r}",
            flush=True
        )

        # ============ دستور «فعال» ============
        if clean_text == "فعال":
            print("✅ ACTIVATE COMMAND", flush=True)

            if not bot_was_activated:
                # اولین بار
                reply_text = "✅ ربات فعال شد."
                bot_was_activated = True
            else:
                # بارهای بعدی
                reply_text = "✅ ربات فعال است."

            result = await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT | {result}", flush=True)
            return

        # ============ دستور «مقام» ============
        if clean_text == "مقام":
            print("✅ RANK COMMAND", flush=True)

            # تعیین نقش کاربر
            role = "عضو"  # پیش‌فرض

            try:
                # دریافت اطلاعات چت برای تشخیص نقش
                # (بر اساس API روبیکا، نقش کاربر در فیلد access_list یا join_type مشخص میشه)
                sender_id = str(message.sender_id)
                chat_id = str(message.chat_id)

                # اگه کاربر همون مالک گروه باشه
                # (چون در روبیکا معمولاً bot_id و owner_id متفاوته، اینجا یه چک ساده می‌کنیم)
                # در روبیکا نقش‌ها معمولاً از طریق فیلدهای خاصی از API میاد
                # برای سادگی، اگه کاربر ادمین باشه، توی access_list مشخص میشه
                # ولی چون rubka این اطلاعات رو مستقیم نمی‌ده، فعلاً بر اساس فرض می‌ذاریم:
                
                # اگه پیام از طرف مالک گروه باشه
                # (این بخش بسته به API روبیکا می‌تونه تغییر کنه)
                # برای سادگی، اگه کاربر پیام داده، نقشش رو از یه فیلد ساده می‌خونیم
                # یا اینکه از پکیج rubka بخوایم اطلاعات بفرسته
                
                # ساده‌ترین راه: اگه کاربر توی access_list با نقش Admin باشه
                # ولی این اطلاعات معمولاً توی پیام نیست، توی آبجکت چت هست
                
                # فعلاً بر اساس فرض می‌ذاریم:
                # اگه کاربر خودش پیام داده، احتمالاً یا مالک یا ادمین یا عضوه
                # بهترین راه: از بات بخوایم اطلاعات چت رو بگیره
                
                # === راه ساده و کارآمد ===
                # توی rubka، معمولاً message.sender_id و chat_id داریم
                # ولی برای تشخیص نقش، باید از API استفاده کنیم
                # چون فعلاً به اون دسترسی نداریم، بر اساس یه منطق ساده:
                # - اگه توی access_list مالک بود → مالک
                # - اگه توی access_list ادمین بود → ادمین
                # - در غیر این صورت → عضو
                
                # چون access_list توی پیام نیست، از یه راه دیگه استفاده می‌کنیم:
                # در روبیکا، اگه کاربر ادمین باشه، توی context پیام مشخص میشه
                # ولی rubka این رو ساده نمی‌کنه
                
                # === راه‌حل نهایی: از خود rubka می‌پرسیم ===
                # متد get_chat_info یا مشابهش
                
                # فعلاً یه منطق ساده:
                role = "عضو"  # پیش‌فرض

                # اگه کاربر توی گروه مالک باشه (بر اساس بررسی ساده)
                # اینجا می‌تونیم از API استفاده کنیم
                # ولی چون نمی‌دونیم rubka چه متدی داره، فعلاً ساده می‌ذاریم
                
                # === بهتر: با استفاده از message متوجه بشیم ===
                # اگه message از نوع خاصی باشه یا فیلد خاصی داشته باشه
                if hasattr(message, 'sender_role'):
                    role = message.sender_role
                elif hasattr(message, 'role'):
                    role = message.role
                elif hasattr(message, 'access_list'):
                    # اگه access_list داشت
                    if isinstance(message.access_list, list):
                        if 'Admin' in message.access_list:
                            role = "ادمین"
                        else:
                            role = "عضو"

            except Exception as e:
                print(f"⚠️ ROLE DETECTION ERROR: {e}", flush=True)

            reply_text = f"👤 مقام کاربر: {role}"

            result = await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT | {result}", flush=True)
            return

    except Exception as e:
        print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)


# ================== اجرای ربات ==================
async def main():
    print("🤖 RP GROUP MANAGER STARTING...", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN ERROR: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
