# games/betting.py
# 🎰 بازی شرط بندی - نسخه پایه
# بعداً می‌تونی بازی رو گسترش بدی
import time
import random

# ═══ دیتای بازی ═══
# (فقط برای بازی‌های در حال اجرا - بقیه تو bot_data["points"] ذخیره می‌شه)
active_bets = {}  # {chat_id: {...}}


# ═══ حالت‌های بازی ═══
DICE_EMOJIS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}


async def handle(ctx):
    """هندلر بازی شرط بندی"""
    bot = ctx["bot"]
    chat_id = ctx["chat_id"]
    sender_id = ctx["sender_id"]
    text = ctx["clean_text"]
    raw = ctx["raw_text"]
    name = ctx["sender_display"]
    msg = ctx["message"]
    settings = ctx.get("settings", {})
    points_getter = ctx.get("points_getter")
    points_setter = ctx.get("points_setter")

    # ═══ چک قفل شرط بندی ═══
    # (اگه بسته باشه، پیام مربوط به بازی رو نادیده بگیر)
    if not settings.get("betting_enabled", True):
        # اگه کاربر داره بازی رو صدا می‌زنه، پیام بده که بسته‌ست
        if text in ("شرط بندی", "شرط‌بندی") or raw.startswith("شرط بندی ") or raw.startswith("شرط‌بندی "):
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=msg.message_id,
                    text=(
                        "🔴 **بازی شرط بندی غیرفعاله!**\n\n"
                        "📌 توسط مدیریت بسته شده.\n\n"
                        "⚡ **FLUXBOT**"
                    ),
                )
            except: pass
            return True
        return False

    # ═══ راهنما ═══
    if text in ("شرط بندی", "شرط‌بندی"):
        # امتیاز فعلی کاربر
        my_pts = 0
        if points_getter:
            try: my_pts = points_getter(sender_id)
            except: my_pts = 0

        await bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg.message_id,
            text=(
                "🎰 **بازی شرط بندی** 🎰\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "🎲 **نحوه بازی:**\n"
                "`شرط بندی [عدد ۱-۶] [مقدار]`\n\n"
                "🎯 **مثال:**\n"
                "├ `شرط بندی 3 10`\n"
                "│  (شرط روی عدد ۳ به مقدار ۱۰ امتیاز)\n"
                "├ `شرط بندی 5 50`\n"
                "└ `شرط بندی 1 100`\n\n"
                "🎁 **قوانین:**\n"
                "├ 🎲 ربات یه تاس ۱ تا ۶ می‌ندازه\n"
                "├ ✅ اگه عددت بیاد → **۲ برابر** می‌بری\n"
                "├ ❌ اگه نیاد → مقدار شرط از دست می‌ره\n"
                "└ 💎 برد و باخت به امتیاز اضافه/کم می‌شه\n\n"
                f"💎 **امتیاز فعلی تو:** `{my_pts}`\n\n"
                "🔒 **مدیریت:**\n"
                "├ 🟢 `شرط بندی باز`\n"
                "└ 🔴 `شرط بندی بسته`\n\n"
                "⚡ **FLUXBOT**"
            ),
        )
        return True

    # ═══ انجام شرط: "شرط بندی 3 10" ═══
    import re
    m = re.match(r"^شرط\s*بندی\s+(\d+)\s+(\d+)$", raw.strip())
    if m:
        guess = int(m.group(1))
        amount = int(m.group(2))

        # اعتبارسنجی
        if guess < 1 or guess > 6:
            await bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=msg.message_id,
                text="⚠️ **عدد باید بین ۱ تا ۶ باشه!**",
            )
            return True

        if amount < 1:
            await bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=msg.message_id,
                text="⚠️ **مقدار شرط باید حداقل ۱ باشه!**",
            )
            return True

        # گرفتن امتیاز فعلی
        current_pts = 0
        if points_getter:
            try: current_pts = points_getter(sender_id)
            except: current_pts = 0

        # چک امتیاز کافی
        if current_pts < amount:
            await bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=msg.message_id,
                text=(
                    f"❌ **امتیاز کافی نداری!**\n\n"
                    f"💎 امتیاز تو: `{current_pts}`\n"
                    f"🎯 نیاز: `{amount}`\n\n"
                    f"📌 برای گرفتن امتیاز:\n"
                    f"├ از دکمه «🎫 کد دعوت من» استفاده کن\n"
                    f"└ یا از دوستات بخواه کد تو رو بزنن\n\n"
                    f"⚡ **FLUXBOT**"
                ),
            )
            return True

        # نگه داشتن شرط فعال
        active_bets[chat_id] = {
            "player": str(sender_id),
            "player_name": name,
            "guess": guess,
            "amount": amount,
            "started_at": time.time(),
        }

        # پیام شروع
        await bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg.message_id,
            text=(
                f"🎰 **شرط بندی شروع شد!**\n\n"
                f"👤 **بازیکن:** {name}\n"
                f"🎯 **شرط:** عدد `{guess}`\n"
                f"💰 **مقدار:** `{amount}` امتیاز\n\n"
                f"🎲 در حال پرتاب تاس...\n\n"
                f"⚡ **FLUXBOT**"
            ),
        )

        # مکث ۱ ثانیه برای جذابیت
        await asyncio.sleep(1.0)

        # پرتاب تاس
        dice = random.randint(1, 6)
        dice_emoji = DICE_EMOJIS.get(dice, "🎲")
        won = (guess == dice)

        # محاسبه امتیاز جدید
        if won:
            new_pts = current_pts + amount  # بردن: +amount (یعنی 2x)
        else:
            new_pts = current_pts - amount  # باختن: -amount

        # ذخیره امتیاز
        if points_setter:
            try: points_setter(sender_id, new_pts)
            except Exception as e:
                print(f"⚠️ betting points setter: {e}", flush=True)

        # پاک کردن شرط فعال
        active_bets.pop(chat_id, None)

        # پیام نتیجه
        if won:
            result_text = (
                f"🎰 **نتیجه شرط بندی** 🎰\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 **بازیکن:** {name}\n"
                f"🎯 **شرط:** عدد `{guess}`\n"
                f"💰 **مقدار:** `{amount}`\n\n"
                f"🎲 **تاس:** {dice_emoji} **{dice}**\n\n"
                f"🎉 **بردی!** 🎉\n"
                f"📈 **+{amount}** امتیاز\n"
                f"💎 **امتیاز جدید:** `{new_pts}`\n\n"
                f"⚡ **FLUXBOT**"
            )
        else:
            result_text = (
                f"🎰 **نتیجه شرط بندی** 🎰\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 **بازیکن:** {name}\n"
                f"🎯 **شرط:** عدد `{guess}`\n"
                f"💰 **مقدار:** `{amount}`\n\n"
                f"🎲 **تاس:** {dice_emoji} **{dice}**\n\n"
                f"😢 **باختی!**\n"
                f"📉 **-{amount}** امتیاز\n"
                f"💎 **امتیاز جدید:** `{new_pts}`\n\n"
                f"💡 **دوباره تلاش کن!**\n\n"
                f"⚡ **FLUXBOT**"
            )

        await bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg.message_id,
            text=result_text,
        )
        return True

    # ═══ ادامه بازی (اگه بازی فعاله) ═══
    if chat_id in active_bets:
        bet = active_bets[chat_id]
        # اگه کاربر دیگه‌ای خواست شروع کنه
        if str(sender_id) != bet["player"]:
            return False  # بذار بقیه کد جواب بده

        # اگه ۳۰ ثانیه گذشت، پاکش کن
        if time.time() - bet["started_at"] > 30:
            active_bets.pop(chat_id, None)
            return False

        # اگه کاربر انصراف داد
        if text in ("انصراف", "لغو", "بستن"):
            active_bets.pop(chat_id, None)
            await bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=msg.message_id,
                text="🚪 **بازی لغو شد!**",
            )
            return True

    return False


def cleanup():
    """پاکسازی بازی‌های قدیمی"""
    now = time.time()
    expired = [c for c, b in active_bets.items() if now - b.get("started_at", 0) > 300]
    for c in expired:
        del active_bets[c]
