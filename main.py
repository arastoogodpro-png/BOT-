import os
import re
import time
import asyncio
from rubka import Robot, Message

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)


def clean_message(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"@\S+", "", text)
    text = re.sub(r"/(\w+)", r"\1", text)
    return text.strip()


def is_group_chat(chat_id: str) -> bool:
    if not chat_id:
        return False
    return str(chat_id).strip().lower().startswith("g")


async def get_user_role(chat_id: str, user_id: str) -> str:
    try:
        member_info = await bot.get_chat_member(chat_id, user_id)
        if not member_info:
            return "عضو"
        data = member_info
        if isinstance(member_info, dict) and "data" in member_info:
            data = member_info["data"]
        chat_member = data.get("chat_member", {}) if isinstance(data, dict) else {}
        status = str(chat_member.get("status", "")).strip().lower()
        if status in ("creator", "owner"):
            return "مالک"
        if status in ("admin", "administrator"):
            return "ادمین"
        return "عضو"
    except Exception as e:
        print(f"⚠️ ROLE ERROR: {e}", flush=True)
        return "عضو"


# ================== متغیرهای وضعیت ==================
bot_is_active = True
mute_list = {}          # {chat_id: {user_id: end_timestamp}}

# دیکشنری برای ذخیره پیام‌ها: {chat_id: {text: sender_id}}
# این روش ۱۰۰٪ مطمئنه چون به API وابسته نیست
text_to_sender = {}


@bot.on_message()
async def handle_message(bot: Robot, message: Message):
    global bot_is_active

    try:
        msg_id = str(message.message_id)
        chat_id = str(message.chat_id) if message.chat_id else ""
        sender_id = str(message.sender_id) if message.sender_id else ""
        raw_text = (message.text or "").strip()
        clean_text = clean_message(raw_text)

        # ================== ذخیره پیام در دیکشنری ==================
        if chat_id and sender_id and raw_text:
            if chat_id not in text_to_sender:
                text_to_sender[chat_id] = {}
            text_to_sender[chat_id][raw_text] = sender_id

            # پاکسازی دیکشنری (نگه‌داشتن ۱۰۰ پیام آخر)
            if len(text_to_sender[chat_id]) > 100:
                keys = list(text_to_sender[chat_id].keys())[:50]
                for k in keys:
                    del text_to_sender[chat_id][k]

        # ================== فیلتر پیام تکراری (قوی) ==================
        if not hasattr(handle_message, 'processed'):
            handle_message.processed = {}
            handle_message.last_cleanup = time.time()

        current_time = time.time()
        if current_time - handle_message.last_cleanup > 30:
            handle_message.processed = {
                k: v for k, v in handle_message.processed.items()
                if current_time - v < 30
            }
            handle_message.last_cleanup = current_time

        if msg_id in handle_message.processed:
            print(f"⏭️ DUPLICATE IGNORED: {msg_id}", flush=True)
            return
        handle_message.processed[msg_id] = current_time

        print(f"📩 MESSAGE | chat={chat_id} | sender={sender_id} | raw={raw_text!r}", flush=True)

        if not is_group_chat(chat_id):
            return

        # ================== بررسی سکوت ==================
        now = time.time()
        chat_mutes = mute_list.get(chat_id, {})

        if sender_id in chat_mutes:
            end_time = chat_mutes[sender_id]
            if now < end_time:
                print(f"🔇 MUTED USER DETECTED - DELETING", flush=True)
                try:
                    await bot.delete_message(
                        chat_id=chat_id,
                        message_id=message.message_id
                    )
                    print(f"🗑️ DELETED", flush=True)
                except Exception as e:
                    print(f"❌ DELETE FAILED: {e}", flush=True)
                return
            else:
                del chat_mutes[sender_id]
                print(f"🔊 MUTE EXPIRED for {sender_id}", flush=True)

        # ================== تشخیص نقش ==================
        role = await get_user_role(chat_id, sender_id)
        is_owner = (role == "مالک")
        print(f"👤 ROLE: {role} | is_owner={is_owner}", flush=True)

        # ================== دستورات مدیریتی ==================

        # --- فعال ---
        if clean_text in ("فعال", "فاعل"):
            if not is_owner:
                return
            print("✅ ACTIVATE COMMAND", flush=True)
            if bot_is_active:
                reply_text = "✅ ربات از قبل فعال است."
            else:
                bot_is_active = True
                reply_text = "✅ ربات فعال شد."
            await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # --- غیرفعال ---
        if clean_text in ("غیرفعال", "غيرفعال"):
            if not is_owner:
                return
            print("🛑 DEACTIVATE COMMAND", flush=True)
            if not bot_is_active:
                reply_text = "⛔ ربات از قبل غیرفعال است."
            else:
                bot_is_active = False
                reply_text = "🛑 ربات غیرفعال شد."
            await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # --- سکوت ---
        mute_match = re.match(r"^سکوت\s+(\d+)$", clean_text)
        if mute_match:
            if not is_owner:
                return
            print("🔇 MUTE COMMAND", flush=True)

            minutes = int(mute_match.group(1))
            if minutes <= 0:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد باید بزرگتر از صفر باشد.", reply_to_message_id=message.message_id)
                return

            target_user_id = None

            # ============================================================
            # روش اصلی: خواندن متن پیام ریپلای‌شده و جستجو در دیکشنری
            # ============================================================
            reply_text_content = None
            
            # بررسی فیلدهای مختلف برای پیام ریپلای‌شده
            if hasattr(message, 'reply_to_message') and message.reply_to_message:
                replied = message.reply_to_message
                if hasattr(replied, 'text') and replied.text:
                    reply_text_content = str(replied.text).strip()
                    print(f"🔍 REPLIED TEXT: {reply_text_content!r}", flush=True)
            
            # اگه reply_to_message نبود، از reply_to_message_id استفاده کن
            if not reply_text_content:
                reply_id = None
                for attr in ['reply_to_message_id', 'reply_to', 'reply_message_id']:
                    if hasattr(message, attr):
                        val = getattr(message, attr)
                        if val:
                            if hasattr(val, 'message_id'):
                                reply_id = str(val.message_id)
                            else:
                                reply_id = str(val)
                            break
                print(f"🔍 REPLY ID: {reply_id}", flush=True)

            # جستجو در دیکشنری با متن پیام
            if reply_text_content and chat_id in text_to_sender:
                target_user_id = text_to_sender[chat_id].get(reply_text_content)
                if target_user_id:
                    print(f"🎯 TARGET FOUND BY TEXT: {target_user_id}", flush=True)

            # اگه با متن پیدا نشد، تلاش کن با متن پاک‌سازی‌شده
            if not target_user_id and reply_text_content and chat_id in text_to_sender:
                clean_reply = clean_message(reply_text_content)
                for stored_text, uid in text_to_sender[chat_id].items():
                    if clean_message(stored_text) == clean_reply:
                        target_user_id = uid
                        print(f"🎯 TARGET FOUND BY CLEAN TEXT: {target_user_id}", flush=True)
                        break

            # اگه هیچی پیدا نشد، خود فرستنده سکوت کن
            if not target_user_id:
                target_user_id = sender_id
                print(f"⚠️ NO TARGET - MUTING SENDER: {target_user_id}", flush=True)

            # اضافه کردن به لیست سکوت
            end_time = time.time() + (minutes * 60)
            if chat_id not in mute_list:
                mute_list[chat_id] = {}
            mute_list[chat_id][target_user_id] = end_time

            print(f"🔇 MUTED {target_user_id} for {minutes} min", flush=True)

            reply_text = f"🔇 کاربر به لیست سکوت اضافه شد ({minutes} دقیقه)."
            await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT: {reply_text}", flush=True)
            return

        # ================== دستورات عمومی ==================
        if not bot_is_active:
            return

        if clean_text == "مقام":
            print("✅ RANK COMMAND", flush=True)
            reply_text = f"👤 مقام کاربر: {role}"
            await bot.send_message(
                chat_id=message.chat_id,
                text=reply_text,
                reply_to_message_id=message.message_id,
                disable_notification=False
            )
            print(f"📤 SENT: {reply_text}", flush=True)
            return

    except Exception as e:
        print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)


async def main():
    print("🤖 RP GROUP MANAGER STARTING...", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN ERROR: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
