# games/betting.py
# 🎰 بازی شرط بندی - نسخه کامل پیشرفته
# ✅ موجودی + تاس عددی + تاس زوج/فرد + شیر/خط + کد هدیه + انتقال + شناسه + افزایش ویژه
import time
import random
import asyncio
import re

# ═══ ثابت‌ها ═══
INITIAL_BALANCE = 50000
MIN_BALANCE = 50000
MIN_BET = 100
DICE_EMOJIS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}

# شناسه/یوزرنیم‌های ویژه (فقط این افراد می‌تونن افزایش موجودی بزنن)
SPECIAL_ID_PARTS = ("0kujo1004f",)
SPECIAL_USERNAMES = ("arastoo_ff",)

# راهنما
HELP_TRIGGERS = frozenset([
    "شرط بندی", "شرط‌بندی",
    "اموزش شرط بندی", "آموزش شرط بندی",
    "راهنما شرط بندی", "راهنمای شرط بندی",
])

BALANCE_TRIGGERS = frozenset([
    "موجودی", "موجودی من", "موجودی چقدره", "موجودی چقدر",
    "موجودی چنده", "حساب من", "کیف پول من", "پول من",
])

ID_TRIGGERS = frozenset([
    "شناسه", "شناسه من", "ایدی من", "آیدی من", "id", "my id",
])

# نقشه اعداد فارسی/عربی به انگلیسی
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


# ═══════════ ابزارها ═══════════
def _normalize(text):
    if not text:
        return ""
    s = str(text).replace('\u200c', ' ').replace('\u200d', ' ').translate(PERSIAN_DIGITS)
    return re.sub(r'\s+', ' ', s).strip()


def _is_special_user(sender_id, sender_display):
    sid = str(sender_id or "").lower()
    sdisp = str(sender_display or "").lstrip("@").lower()
    for part in SPECIAL_ID_PARTS:
        if part in sid:
            return True
    for un in SPECIAL_USERNAMES:
        if un == sdisp:
            return True
    return False


def _ensure_balances(bot_data):
    if "balances" not in bot_data or not isinstance(bot_data.get("balances"), dict):
        bot_data["balances"] = {}


def _ensure_gift_codes(bot_data):
    if "gift_codes" not in bot_data or not isinstance(bot_data.get("gift_codes"), dict):
        bot_data["gift_codes"] = {}


def get_balance(bot_data, user_id):
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
    _ensure_balances(bot_data)
    uid = str(user_id)
    try:
        val = int(amount)
    except (ValueError, TypeError):
        val = MIN_BALANCE
    bot_data["balances"][uid] = max(MIN_BALANCE, val)
    return bot_data["balances"][uid]


def _safe_save(save_data, bot_data):
    if save_data:
        try:
            save_data(bot_data, force=True)
        except Exception as e:
            print(f"⚠️ betting save: {e}", flush=True)


def _gen_code(bot_data):
    _ensure_gift_codes(bot_data)
    existing = bot_data["gift_codes"]
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # بدون I, O, 0, 1
    for _ in range(100):
        code = "".join(random.choices(alphabet, k=6))
        if code not in existing:
            return code
    return "G" + str(int(time.time()))[-5:]


def _normalize_uid(raw):
    if not raw:
        return ""
    uid = str(raw).strip()
    if not uid:
        return ""
    if uid[0].isdigit():
        return "u" + uid
    return uid


async def _send(bot, chat_id, text, reply_to=None):
    try:
        kwargs = {"chat_id": chat_id, "text": text}
        if reply_to:
            kwargs["reply_to_message_id"] = reply_to
        await bot.send_message(**kwargs)
        return True
    except Exception as e:
        print(f"⚠️ betting send: {e}", flush=True)
        return False


# ═══════════ Handle اصلی ═══════════
async def handle(ctx):
    bot = ctx["bot"]
    chat_id = ctx["chat_id"]
    sender_id = ctx["sender_id"]
    text = (ctx.get("clean_text") or "").strip()
    raw = (ctx.get("raw_text") or "").strip()
    name = ctx.get("sender_display") or "کاربر"
    msg = ctx["message"]
    settings = ctx.get("settings", {}) or {}
    bot_data = ctx.get("bot_data")
    save_data = ctx.get("save_data")

    if not isinstance(bot_data, dict):
        return False

    raw_norm = _normalize(raw)
    raw_low = raw_norm.lower()
    text_norm = _normalize(text)
    text_low = text_norm.lower()

    # ═══ چک قفل ═══
    if not settings.get("betting_enabled", True):
        triggered = (
            text_low in HELP_TRIGGERS or
            text_low in BALANCE_TRIGGERS or
            text_low in ID_TRIGGERS or
            raw_low.startswith("شرط بندی ") or
            raw_low in ("شرط بندی", "شرط‌بندی")
        )
        if triggered:
            await _send(bot, chat_id,
                "🔴 **بازی شرط بندی غیرفعاله!**\n\n📌 توسط مدیریت بسته شده.\n\n⚡ **FLUXBOT**",
                reply_to=msg.message_id)
            return True
        return False

    # ═══ 💎 موجودی ═══
    if text_low in BALANCE_TRIGGERS or raw_low in BALANCE_TRIGGERS:
        bal = get_balance(bot_data, sender_id)
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "💰 **موجودی شما** 💰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **کاربر:** {name}\n"
            f"💎 **موجودی:** `{bal:,}` واحد\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "💡 برای راهنما: `شرط بندی`\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 🆔 شناسه ═══
    if text_low in ID_TRIGGERS or raw_low in ID_TRIGGERS:
        await _send(bot, chat_id,
            "🆔 **شناسه شما** 🆔\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **کاربر:** {name}\n"
            f"🆔 **شناسه:** `{sender_id}`\n\n"
            "📌 این شناسه ثابته و هیچ‌وقت عوض نمی‌شه.\n"
            "💡 با این شناسه می‌تونی هدیه دریافت کنی.\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 📖 راهنما ═══
    if text_low in HELP_TRIGGERS or raw_low in HELP_TRIGGERS:
        bal = get_balance(bot_data, sender_id)
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id, _get_help_text(bal), reply_to=msg.message_id)
        return True

    # ═══ 🎁 ساخت کد هدیه ═══
    m = re.match(r"^ساخت کد هدیه مقدار (\d+)$", raw_low)
    if m:
        amount = int(m.group(1))
        if amount < MIN_BET:
            await _send(bot, chat_id,
                f"⚠️ **حداقل مبلغ کد هدیه `{MIN_BET:,}` واحده!**",
                reply_to=msg.message_id)
            return True
        bal = get_balance(bot_data, sender_id)
        if bal < amount:
            await _send(bot, chat_id,
                f"❌ **موجودی کافی نداری!**\n\n"
                f"💎 موجودی تو: `{bal:,}`\n🎯 نیاز: `{amount:,}`",
                reply_to=msg.message_id)
            return True

        code = _gen_code(bot_data)
        _ensure_gift_codes(bot_data)
        bot_data["gift_codes"][code] = {
            "creator": str(sender_id),
            "amount": amount,
            "created_at": time.time(),
            "used": False,
            "used_by": None,
        }
        set_balance(bot_data, sender_id, bal - amount)
        _safe_save(save_data, bot_data)

        dm_text = (
            "🎁 **کد هدیه شما** 🎁\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 **مبلغ:** `{amount:,}` واحد\n"
            f"🔑 **کد:** `{code}`\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📌 **روش استفاده:**\n"
            "└ هر کسی این کد رو بگیره، با دستور زیر استفاده می‌کنه:\n\n"
            f"`استفاده کد {code}`\n\n"
            "⚠️ **نکات:**\n"
            "├ 🔒 فقط **یک بار** قابل استفاده‌ست\n"
            "├ 🚫 خودت نمی‌تونی ازش استفاده کنی\n"
            "└ 💡 این پیام رو برای دوستت بفرست\n\n"
            "⚡ **FLUXBOT**"
        )
        dm_ok = await _send(bot, str(sender_id), dm_text)

        if not dm_ok:
            # بازگشت پول
            set_balance(bot_data, sender_id, bal)
            _ensure_gift_codes(bot_data)
            bot_data["gift_codes"].pop(code, None)
            _safe_save(save_data, bot_data)
            await _send(bot, chat_id,
                "❌ **ارسال کد به پیوی ناموفق بود!**\n\n"
                "📌 اول ربات رو در پیوی استارت کن:\n"
                "└ به پیوی ربات پیام بده `شروع`\n\n"
                "💎 پولت برگشت خورد.",
                reply_to=msg.message_id)
            return True

        await _send(bot, chat_id,
            "✅ **کد هدیه ساخته شد!**\n\n"
            f"💰 **مبلغ:** `{amount:,}`\n"
            "📩 **کد به پیوی شما ارسال شد.**\n\n"
            "💡 پیوی ربات رو چک کن.",
            reply_to=msg.message_id)
        return True

    # ═══ 🎁 استفاده کد هدیه ═══
    m = re.match(r"^استفاده کد ([A-Z0-9]+)$", raw_norm.upper())
    if m:
        code = m.group(1).upper()
        _ensure_gift_codes(bot_data)
        gift = bot_data["gift_codes"].get(code)
        if not gift:
            await _send(bot, chat_id,
                "❌ **کد هدیه نامعتبره!**\n\n📌 وجود نداره یا اشتباه تایپ شده.",
                reply_to=msg.message_id)
            return True
        if gift.get("used"):
            await _send(bot, chat_id,
                "❌ **این کد قبلاً استفاده شده!**",
                reply_to=msg.message_id)
            return True
        if str(gift.get("creator")) == str(sender_id):
            await _send(bot, chat_id,
                "❌ **نمی‌تونی از کد خودت استفاده کنی!**\n\n"
                "📌 این کد رو برای دوستت بفرست تا اون استفاده کنه.",
                reply_to=msg.message_id)
            return True
        amount = int(gift.get("amount", 0))
        if amount <= 0:
            await _send(bot, chat_id, "❌ **کد معتبر نیست!**", reply_to=msg.message_id)
            return True
        bal = get_balance(bot_data, sender_id)
        new_bal = bal + amount
        set_balance(bot_data, sender_id, new_bal)
        gift["used"] = True
        gift["used_by"] = str(sender_id)
        gift["used_at"] = time.time()
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "🎉 **کد هدیه دریافت شد!** 🎉\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 **کد:** `{code}`\n"
            f"💰 **مبلغ:** `+{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 🎁 ارسال هدیه به کاربر دیگر ═══
    m = re.match(r"^ارسال هدیه (u?[A-Za-z0-9]+) مقدار (\d+)$", raw_norm)
    if m:
        receiver = _normalize_uid(m.group(1))
        amount = int(m.group(2))
        if receiver == str(sender_id):
            await _send(bot, chat_id, "❌ **نمی‌تونی به خودت هدیه بدی!**", reply_to=msg.message_id)
            return True
        if amount < MIN_BET:
            await _send(bot, chat_id,
                f"⚠️ **حداقل مبلغ هدیه `{MIN_BET:,}` واحده!**",
                reply_to=msg.message_id)
            return True
        bal = get_balance(bot_data, sender_id)
        if bal < amount:
            await _send(bot, chat_id,
                f"❌ **موجودی کافی نداری!**\n\n"
                f"💎 موجودی تو: `{bal:,}`\n🎯 نیاز: `{amount:,}`",
                reply_to=msg.message_id)
            return True
        new_sender_bal = bal - amount
        receiver_bal = get_balance(bot_data, receiver)
        new_receiver_bal = receiver_bal + amount
        set_balance(bot_data, sender_id, new_sender_bal)
        set_balance(bot_data, receiver, new_receiver_bal)
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "🎁 **هدیه ارسال شد!** 🎁\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **از:** {name}\n"
            f"🎯 **به:** `{receiver}`\n"
            f"💰 **مبلغ:** `{amount:,}`\n\n"
            f"💎 **موجودی جدید تو:** `{new_sender_bal:,}`\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        await _send(bot, receiver,
            "🎁 **هدیه جدید دریافت کردی!** 🎁\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **از:** {name}\n"
            f"💰 **مبلغ:** `+{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_receiver_bal:,}`\n\n"
            "⚡ **FLUXBOT**")
        return True

    # ═══ 👑 افزایش موجودی (فقط مالک ویژه) ═══
    m = re.match(r"^افزایش موجودی مقدار (\d+)$", raw_low)
    if m:
        if not _is_special_user(sender_id, name):
            return False  # سکوت برای بقیه
        amount = int(m.group(1))
        if amount <= 0:
            await _send(bot, chat_id, "⚠️ مبلغ باید مثبت باشه.", reply_to=msg.message_id)
            return True
        bal = get_balance(bot_data, sender_id)
        new_bal = bal + amount
        _ensure_balances(bot_data)
        bot_data["balances"][str(sender_id)] = new_bal
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "👑 **افزایش موجودی (ویژه)** 👑\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **کاربر:** {name}\n"
            f"💰 **افزایش:** `+{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 🎲 شرط بندی (همه فرمت‌ها) ═══
    m = re.match(
        r"^شرط بندی (?:تاس\s+)?(شیر|خط|زوج|فرد|\d+)\s+(?:مقدار\s+)?(\d+)\s*$",
        raw_low
    )
    if m:
        return await _play_bet(bot, chat_id, sender_id, name, msg,
                                m.group(1), int(m.group(2)), bot_data, save_data)

    return False


# ═══════════ منطق شرط‌ها ═══════════
async def _play_bet(bot, chat_id, sender_id, name, msg, guess_raw, amount, bot_data, save_data):
    if amount < MIN_BET:
        await _send(bot, chat_id,
            f"⚠️ **حداقل مبلغ شرط `{MIN_BET:,}` واحده!**",
            reply_to=msg.message_id)
        return True
    if guess_raw in ("شیر", "خط"):
        return await _play_coinflip(bot, chat_id, sender_id, name, msg,
                                     guess_raw, amount, bot_data, save_data)
    if guess_raw in ("زوج", "فرد"):
        return await _play_dice_evenodd(bot, chat_id, sender_id, name, msg,
                                         guess_raw, amount, bot_data, save_data)
    try:
        guess_num = int(guess_raw)
    except ValueError:
        await _send(bot, chat_id, "⚠️ **نوع شرط نامعتبره!**", reply_to=msg.message_id)
        return True
    if guess_num < 1 or guess_num > 6:
        await _send(bot, chat_id,
            "⚠️ **عدد تاس باید بین ۱ تا ۶ باشه!**",
            reply_to=msg.message_id)
        return True
    return await _play_dice_number(bot, chat_id, sender_id, name, msg,
                                    guess_num, amount, bot_data, save_data)


async def _play_dice_number(bot, chat_id, sender_id, name, msg, guess, amount, bot_data, save_data):
    """تاس عددی — سود ۳ برابر"""
    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n\n"
            f"💎 موجودی: `{bal:,}`\n🎯 نیاز: `{amount:,}`",
            reply_to=msg.message_id)
        return True
    await _send(bot, chat_id,
        "🎲 **شرط بندی تاس عددی** 🎲\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n"
        f"🎯 **شرط:** عدد `{guess}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n"
        "🎲 در حال پرتاب تاس...\n\n"
        "⚡ **FLUXBOT**",
        reply_to=msg.message_id)
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
        result = (
            "🎰 **نتیجه** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** عدد `{guess}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}**\n\n"
            f"🎉 **بردی!** 🎉\n"
            f"📈 **سود (۳x):** `+{profit:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "⚡ **FLUXBOT**"
        )
    else:
        result = (
            "🎰 **نتیجه** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** عدد `{guess}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}**\n\n"
            f"😢 **باختی!**\n"
            f"📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "💡 دوباره تلاش کن!\n\n⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


async def _play_dice_evenodd(bot, chat_id, sender_id, name, msg, choice, amount, bot_data, save_data):
    """تاس زوج/فرد — سود ۲ برابر"""
    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n\n"
            f"💎 موجودی: `{bal:,}`\n🎯 نیاز: `{amount:,}`",
            reply_to=msg.message_id)
        return True
    await _send(bot, chat_id,
        "🎲 **شرط بندی تاس زوج/فرد** 🎲\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n"
        f"🎯 **شرط:** `{choice}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n"
        "🎲 در حال پرتاب تاس...\n\n"
        "⚡ **FLUXBOT**",
        reply_to=msg.message_id)
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
        result = (
            "🎰 **نتیجه** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}** ({parity})\n\n"
            f"🎉 **بردی!** 🎉\n"
            f"📈 **سود (۲x):** `+{profit:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "⚡ **FLUXBOT**"
        )
    else:
        result = (
            "🎰 **نتیجه** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}** ({parity})\n\n"
            f"😢 **باختی!**\n"
            f"📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "💡 دوباره تلاش کن!\n\n⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


async def _play_coinflip(bot, chat_id, sender_id, name, msg, choice, amount, bot_data, save_data):
    """شیر یا خط — سود نصف"""
    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n\n"
            f"💎 موجودی: `{bal:,}`\n🎯 نیاز: `{amount:,}`",
            reply_to=msg.message_id)
        return True
    await _send(bot, chat_id,
        "🪙 **شرط بندی شیر یا خط** 🪙\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n"
        f"🎯 **شرط:** `{choice}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n"
        "🪙 در حال پرتاب سکه...\n\n"
        "⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    await asyncio.sleep(1.2)
    result_side = random.choice(["شیر", "خط"])
    won = (choice == result_side)
    if won:
        profit = amount // 2
        new_bal = bal + profit
    else:
        profit = -amount
        new_bal = max(MIN_BALANCE, bal - amount)
    set_balance(bot_data, sender_id, new_bal)
    _safe_save(save_data, bot_data)
    result_emoji = "🦁" if result_side == "شیر" else "📝"
    if won:
        result = (
            "🪙 **نتیجه** 🪙\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🪙 **نتیجه:** {result_emoji} **{result_side}**\n\n"
            f"🎉 **بردی!** 🎉\n"
            f"📈 **سود (نصف):** `+{profit:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "⚡ **FLUXBOT**"
        )
    else:
        result = (
            "🪙 **نتیجه** 🪙\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🪙 **نتیجه:** {result_emoji} **{result_side}**\n\n"
            f"😢 **باختی!**\n"
            f"📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "💡 دوباره تلاش کن!\n\n⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


# ═══════════ متن راهنما ═══════════
def _get_help_text(bal):
    return (
        "🎰 **راهنمای کامل شرط بندی** 🎰\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "💎 **موجودی تو:**\n"
        f"└ `{bal:,}` واحد (شروع و کف: `{INITIAL_BALANCE:,}`)\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎲 **۱. تاس عددی (سود ۳ برابر)**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "`شرط بندی [۱-۶] [مقدار]`\n"
        "یا: `شرط بندی تاس [۱-۶] [مقدار]`\n\n"
        "📌 **مثال:** `شرط بندی 3 10000`\n\n"
        "🎁 اگه عددت با تاس یکی بشه → **۳ برابر** سود\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎲 **۲. تاس زوج/فرد (سود ۲ برابر)**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "`شرط بندی [زوج/فرد] [مقدار]`\n\n"
        "📌 **مثال:** `شرط بندی زوج 5000`\n\n"
        "🎁 اگه درست بگی → **۲ برابر** سود\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🪙 **۳. شیر یا خط (سود نصف)**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "`شرط بندی [شیر/خط] [مقدار]`\n\n"
        "📌 **مثال:** `شرط بندی شیر 2000`\n\n"
        "🎁 اگه درست بگی → **نصف** مقدار شرط سود\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎁 **کد هدیه**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🔨 `ساخت کد هدیه مقدار [عدد]`\n"
        "│  کد در پیوی برات ارسال می‌شه\n"
        "└ 🔑 `استفاده کد [کد]` → دریافت هدیه\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎁 **ارسال هدیه به دوستان**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "`ارسال هدیه [شناسه] مقدار [عدد]`\n\n"
        "📌 **مثال:** `ارسال هدیه u0KUJo... 5000`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💰 **دستورات دیگه:**\n"
        "├ 💎 `موجودی` → نمایش موجودی\n"
        "├ 🆔 `شناسه` → نمایش شناسه خودت\n"
        "└ 📖 `راهنما شرط بندی` → همین متن\n\n"
        "⚠️ **قوانین مهم:**\n"
        f"├ 💎 کف موجودی: `{MIN_BALANCE:,}` (هرگز کمتر نمی‌شه)\n"
        f"├ 🎯 حداقل شرط/هدیه: `{MIN_BET:,}` واحد\n"
        "├ 🎲 مقدار شرط نمی‌تونه از موجودی بیشتر باشه\n"
        "└ 🔒 مدیریت: `شرط بندی باز` / `شرط بندی بسته`\n\n"
        "⚡ **FLUXBOT**"
    )


def cleanup():
    """این نسخه state نداره — no-op"""
    pass
