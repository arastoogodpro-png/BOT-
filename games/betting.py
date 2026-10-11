# games/betting.py
# 🎰 بازی شرط بندی - نسخه پیشرفته
# ✅ همه چیز از صفر: موجودی، تاس عددی، تاس زوج/فرد، شیر یا خط
import time
import random
import asyncio
import re

# ═══ ثابت‌ها ═══
INITIAL_BALANCE = 50000   # موجودی اولیه و کف موجودی
MIN_BALANCE = 50000       # موجودی هرگز کمتر از این نمی‌شه
MIN_BET = 100             # حداقل مبلغ شرط
DICE_EMOJIS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}

# ═══ کلیدواژه‌های راهنما ═══
HELP_TRIGGERS = (
    "شرط بندی", "شرط‌بندی",
    "اموزش شرط بندی", "آموزش شرط بندی",
    "راهنما شرط بندی", "راهنمای شرط بندی",
    "help betting", "betting help",
)
BALANCE_TRIGGERS = (
    "موجودی", "موجودی من", "موجودی چقدره", "موجودی چقدر",
    "موجودی چنده", "حساب من", "کیف پول من", "پول من",
)


# ═══ توابع کمکی ═══
def _ensure_balances(bot_data):
    """مطمئن می‌شه که فیلد balances یه دیکشنری معتبره"""
    if "balances" not in bot_data or not isinstance(bot_data.get("balances"), dict):
        bot_data["balances"] = {}


def get_balance(bot_data, user_id):
    """گرفتن موجودی کاربر (اگه نبود، ۵۰۰۰۰ اولیه)"""
    _ensure_balances(bot_data)
    uid = str(user_id)
    if uid not in bot_data["balances"]:
        bot_data["balances"][uid] = INITIAL_BALANCE
    try:
        return int(bot_data["balances"][uid])
    except (ValueError, TypeError):
        bot_data["balances"][uid] = INITIAL_BALANCE
        return INITIAL_BALANCE


def set_balance(bot_data, user_id, amount):
    """تنظیم موجودی با رعایت کف ۵۰۰۰۰"""
    _ensure_balances(bot_data)
    uid = str(user_id)
    try:
        val = int(amount)
    except (ValueError, TypeError):
        val = MIN_BALANCE
    bot_data["balances"][uid] = max(MIN_BALANCE, val)
    return bot_data["balances"][uid]


def _normalize_cmd(raw):
    """نرمال‌سازی دستور: ZWNJ → space، فاصله‌های اضافی → یکی"""
    if not raw:
        return ""
    s = raw.replace('\u200c', ' ').replace('\u200d', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _safe_save(save_data, bot_data):
    """ذخیره امن"""
    if save_data:
        try:
            save_data(bot_data, force=True)
        except Exception as e:
            print(f"⚠️ betting save: {e}", flush=True)


async def _check_balance(bot, chat_id, msg, sender_id, name, amount, bot_data, save_data):
    """چک می‌کنه موجودی کافیه یا نه"""
    if amount < MIN_BET:
        try:
            await bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=msg.message_id,
                text=f"⚠️ **حداقل مبلغ شرط `{MIN_BET:,}` واحده!**",
            )
        except: pass
        return False

    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        try:
            await bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=msg.message_id,
                text=(
                    f"❌ **موجودی کافی نداری!**\n\n"
                    f"💎 موجودی تو: `{bal:,}`\n"
                    f"🎯 نیاز: `{amount:,}`\n\n"
                    f"📌 یادت باشه موجودی هرگز زیر `{MIN_BALANCE:,}` نمی‌ره.\n\n"
                    f"⚡ **FLUXBOT**"
                ),
            )
        except: pass
        return False
    return True


# ═══ هندلر اصلی ═══
async def handle(ctx):
    """هندلر بازی شرط بندی"""
    bot = ctx["bot"]
    chat_id = ctx["chat_id"]
    sender_id = ctx["sender_id"]
    text = ctx["clean_text"].strip()
    raw = ctx["raw_text"].strip()
    name = ctx["sender_display"]
    msg = ctx["message"]
    settings = ctx.get("settings", {})
    bot_data = ctx.get("bot_data")
    save_data = ctx.get("save_data")

    # ═══ چک وجود bot_data ═══
    if not isinstance(bot_data, dict):
        return False

    text_lower = text.lower()
    raw_norm = _normalize_cmd(raw)
    raw_norm_lower = raw_norm.lower()

    # ═══ چک قفل شرط بندی ═══
    if not settings.get("betting_enabled", True):
        # اگه کاربر داره بازی رو صدا می‌زنه، پیام بده که بسته‌ست
        if (text_lower in HELP_TRIGGERS or text_lower in BALANCE_TRIGGERS
                or raw_norm_lower.startswith("شرط بندی ")
                or raw_norm_lower == "شرط بندی"):
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

    # ═══ 💎 نمایش موجودی ═══
    if text_lower in BALANCE_TRIGGERS or raw_norm_lower in BALANCE_TRIGGERS:
        try:
            bal = get_balance(bot_data, sender_id)
            _safe_save(save_data, bot_data)
            await bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=msg.message_id,
                text=(
                    "💰 **موجودی شما** 💰\n"
                    "━━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 **کاربر:** {name}\n"
                    f"💎 **موجودی:** `{bal:,}` واحد\n\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 برای راهنما: `شرط بندی`\n\n"
                    "⚡ **FLUXBOT**"
                ),
            )
        except Exception as e:
            print(f"⚠️ balance cmd: {e}", flush=True)
        return True

    # ═══ 📖 راهنما / آموزش شرط بندی ═══
    if text_lower in HELP_TRIGGERS or raw_norm_lower in HELP_TRIGGERS:
        try:
            bal = get_balance(bot_data, sender_id)
            _safe_save(save_data, bot_data)
            await bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=msg.message_id,
                text=(
                    "🎰 **راهنمای کامل شرط بندی** 🎰\n"
                    "━━━━━━━━━━━━━━━━━━━\n\n"
                    "💎 **موجودی تو:**\n"
                    f"└ `{bal:,}` واحد (شروع و کف: `{INITIAL_BALANCE:,}`)\n\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🎲 **۱. تاس عددی (سود ۳ برابر)**\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "`شرط بندی تاس [۱-۶] مقدار [عدد]`\n\n"
                    "📌 **مثال:**\n"
                    "`شرط بندی تاس 3 مقدار 10000`\n\n"
                    "🎁 اگه عددت با تاس یکی بشه:\n"
                    "└ **۳ برابر** مبلغ شرط سود می‌کنی\n\n"
                    "❌ اگه نباشه:\n"
                    "└ مقدار شرط از دست می‌ره\n\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🎲 **۲. تاس زوج/فرد (سود ۲ برابر)**\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "`شرط بندی تاس [زوج/فرد] مقدار [عدد]`\n\n"
                    "📌 **مثال:**\n"
                    "`شرط بندی تاس زوج مقدار 5000`\n\n"
                    "🎁 اگه درست بگی:\n"
                    "└ **۲ برابر** مبلغ شرط سود می‌کنی\n\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🪙 **۳. شیر یا خط (سود نصف)**\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "`شرط بندی [شیر/خط] مقدار [عدد]`\n\n"
                    "📌 **مثال:**\n"
                    "`شرط بندی شیر مقدار 2000`\n\n"
                    "🎁 اگه درست بگی:\n"
                    "└ **نصف** مبلغ شرط سود می‌کنی\n\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "💰 **دستورات دیگه:**\n"
                    "├ 💎 `موجودی` → نمایش موجودی\n"
                    "└ 📖 `راهنما شرط بندی` → همین متن\n\n"
                    "⚠️ **قوانین مهم:**\n"
                    f"├ 💎 کف موجودی: `{MIN_BALANCE:,}` (هرگز کمتر نمی‌شه)\n"
                    f"├ 🎯 حداقل شرط: `{MIN_BET:,}` واحد\n"
                    "├ 🎲 مقدار شرط نمی‌تونه از موجودی بیشتر باشه\n"
                    "└ 🔒 مدیریت: `شرط بندی باز` / `شرط بندی بسته`\n\n"
                    "⚡ **FLUXBOT**"
                ),
            )
        except Exception as e:
            print(f"⚠️ help cmd: {e}", flush=True)
        return True

    # ═══ 🎲 شرط بندی تاس عددی ═══
    m = re.match(r"^شرط بندی تاس (\d+) مقدار (\d+)$", raw_norm_lower)
    if m:
        try:
            guess = int(m.group(1))
            amount = int(m.group(2))
        except (ValueError, TypeError):
            return False
        return await _play_dice_number(bot, chat_id, sender_id, name, msg,
                                        guess, amount, bot_data, save_data)

    # ═══ 🎲 شرط بندی تاس زوج/فرد ═══
    m = re.match(r"^شرط بندی تاس (زوج|فرد) مقدار (\d+)$", raw_norm_lower)
    if m:
        try:
            amount = int(m.group(2))
        except (ValueError, TypeError):
            return False
        return await _play_dice_evenodd(bot, chat_id, sender_id, name, msg,
                                         m.group(1), amount, bot_data, save_data)

    # ═══ 🪙 شرط بندی شیر یا خط ═══
    m = re.match(r"^شرط بندی (شیر|خط) مقدار (\d+)$", raw_norm_lower)
    if m:
        try:
            amount = int(m.group(2))
        except (ValueError, TypeError):
            return False
        return await _play_coinflip(bot, chat_id, sender_id, name, msg,
                                     m.group(1), amount, bot_data, save_data)

    return False


# ═══ منطق بازی‌ها ═══

async def _play_dice_number(bot, chat_id, sender_id, name, msg, guess, amount, bot_data, save_data):
    """تاس عددی — سود ۳ برابر"""
    if guess < 1 or guess > 6:
        try:
            await bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=msg.message_id,
                text="⚠️ **عدد باید بین ۱ تا ۶ باشه!**",
            )
        except: pass
        return True

    if not await _check_balance(bot, chat_id, msg, sender_id, name, amount, bot_data, save_data):
        return True

    bal = get_balance(bot_data, sender_id)

    try:
        await bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg.message_id,
            text=(
                f"🎲 **شرط بندی تاس عددی** 🎲\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 **بازیکن:** {name}\n"
                f"🎯 **شرط:** عدد `{guess}`\n"
                f"💰 **مقدار:** `{amount:,}`\n\n"
                f"🎲 در حال پرتاب تاس...\n\n"
                f"⚡ **FLUXBOT**"
            ),
        )
    except: pass

    await asyncio.sleep(1.2)

    dice = random.randint(1, 6)
    dice_emoji = DICE_EMOJIS.get(dice, "🎲")
    won = (guess == dice)

    if won:
        profit = amount * 3
        new_bal = bal + profit
    else:
        profit = -amount
        new_bal = max(MIN_BALANCE, bal - amount)

    set_balance(bot_data, sender_id, new_bal)
    _safe_save(save_data, bot_data)

    if won:
        result_text = (
            f"🎰 **نتیجه شرط بندی** 🎰\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** عدد `{guess}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}**\n\n"
            f"🎉 **بردی!** 🎉\n"
            f"📈 **سود (۳ برابر):** `+{profit:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            f"⚡ **FLUXBOT**"
        )
    else:
        result_text = (
            f"🎰 **نتیجه شرط بندی** 🎰\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** عدد `{guess}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}**\n\n"
            f"😢 **باختی!**\n"
            f"📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            f"💡 **دوباره تلاش کن!**\n\n"
            f"⚡ **FLUXBOT**"
        )

    try:
        await bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg.message_id,
            text=result_text,
        )
    except: pass
    return True


async def _play_dice_evenodd(bot, chat_id, sender_id, name, msg, choice, amount, bot_data, save_data):
    """تاس زوج/فرد — سود ۲ برابر"""
    if not await _check_balance(bot, chat_id, msg, sender_id, name, amount, bot_data, save_data):
        return True

    bal = get_balance(bot_data, sender_id)

    try:
        await bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg.message_id,
            text=(
                f"🎲 **شرط بندی تاس زوج/فرد** 🎲\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 **بازیکن:** {name}\n"
                f"🎯 **شرط:** `{choice}`\n"
                f"💰 **مقدار:** `{amount:,}`\n\n"
                f"🎲 در حال پرتاب تاس...\n\n"
                f"⚡ **FLUXBOT**"
            ),
        )
    except: pass

    await asyncio.sleep(1.2)

    dice = random.randint(1, 6)
    dice_emoji = DICE_EMOJIS.get(dice, "🎲")
    is_even = (dice % 2 == 0)
    won = (choice == "زوج" and is_even) or (choice == "فرد" and not is_even)

    if won:
        profit = amount * 2
        new_bal = bal + profit
    else:
        profit = -amount
        new_bal = max(MIN_BALANCE, bal - amount)

    set_balance(bot_data, sender_id, new_bal)
    _safe_save(save_data, bot_data)

    parity = "زوج" if is_even else "فرد"

    if won:
        result_text = (
            f"🎰 **نتیجه شرط بندی** 🎰\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}** ({parity})\n\n"
            f"🎉 **بردی!** 🎉\n"
            f"📈 **سود (۲ برابر):** `+{profit:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            f"⚡ **FLUXBOT**"
        )
    else:
        result_text = (
            f"🎰 **نتیجه شرط بندی** 🎰\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}** ({parity})\n\n"
            f"😢 **باختی!**\n"
            f"📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            f"💡 **دوباره تلاش کن!**\n\n"
            f"⚡ **FLUXBOT**"
        )

    try:
        await bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg.message_id,
            text=result_text,
        )
    except: pass
    return True


async def _play_coinflip(bot, chat_id, sender_id, name, msg, choice, amount, bot_data, save_data):
    """شیر یا خط — سود نصف"""
    if not await _check_balance(bot, chat_id, msg, sender_id, name, amount, bot_data, save_data):
        return True

    bal = get_balance(bot_data, sender_id)

    try:
        await bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg.message_id,
            text=(
                f"🪙 **شرط بندی شیر یا خط** 🪙\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 **بازیکن:** {name}\n"
                f"🎯 **شرط:** `{choice}`\n"
                f"💰 **مقدار:** `{amount:,}`\n\n"
                f"🪙 در حال پرتاب سکه...\n\n"
                f"⚡ **FLUXBOT**"
            ),
        )
    except: pass

    await asyncio.sleep(1.2)

    result = random.choice(["شیر", "خط"])
    won = (choice == result)

    if won:
        profit = amount // 2
        new_bal = bal + profit
    else:
        profit = -amount
        new_bal = max(MIN_BALANCE, bal - amount)

    set_balance(bot_data, sender_id, new_bal)
    _safe_save(save_data, bot_data)

    result_emoji = "🦁" if result == "شیر" else "📝"

    if won:
        result_text = (
            f"🪙 **نتیجه شرط بندی** 🪙\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🪙 **نتیجه:** {result_emoji} **{result}**\n\n"
            f"🎉 **بردی!** 🎉\n"
            f"📈 **سود (نصف):** `+{profit:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            f"⚡ **FLUXBOT**"
        )
    else:
        result_text = (
            f"🪙 **نتیجه شرط بندی** 🪙\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🪙 **نتیجه:** {result_emoji} **{result}**\n\n"
            f"😢 **باختی!**\n"
            f"📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            f"💡 **دوباره تلاش کن!**\n\n"
            f"⚡ **FLUXBOT**"
        )

    try:
        await bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg.message_id,
            text=result_text,
        )
    except: pass
    return True


def cleanup():
    """پاکسازی — این نسخه نیازی به state نداره"""
    pass
