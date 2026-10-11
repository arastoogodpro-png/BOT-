# games/betting.py
# 🎰 بازی شرط بندی - نسخه نهایی کامل
# ✅ موجودی + تاس + شیر/خط + پنالتی + کد هدیه + انتقال + گردونه + اسلات + افزایش ویژه
import time
import random
import asyncio
import re

# ═══════════ ثابت‌ها ═══════════
INITIAL_BALANCE = 50000
MIN_BALANCE = 50000
MIN_BET = 100
COOLDOWN_DAILY = 86400  # ۲۴ ساعت
DICE_EMOJIS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}

# شناسه/یوزرنیم‌های ویژه (افزایش موجودی)
SPECIAL_ID_PARTS = ("0kujo1004f",)
SPECIAL_USERNAMES = ("arastoo_ff",)

# ═══════════ دستورات ═══════════
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
WHEEL_TRIGGERS = frozenset([
    "گردونه", "گردونه شانس", "استفاده گردونه",
    "چرخوندن گردونه", "بچرخون گردونه", "بچرخون گردونه شانس",
])
SLOT_TRIGGERS = frozenset([
    "اسلات", "اسلات ماشین", "استفاده اسلات",
    "چرخوندن اسلات", "بچرخون اسلات", "اسلات بچرخون",
])

# ═══════════ داده‌های گردونه و اسلات ═══════════
# (وزن، جایزه)
WHEEL_SEGMENTS = [
    (30, 100_000),
    (25, 150_000),
    (20, 200_000),
    (12, 250_000),
    (8,  300_000),
    (4,  400_000),
    (1,  500_000),
]
WHEEL_EMOJIS = ["🎯", "🎁", "💎", "⭐", "🔥", "🏆", "👑"]

# نمادهای اسلات
SLOT_SYMBOLS = ["🍒", "🍋", "🍇", "💎", "🔔", "7️⃣"]
SLOT_JACKPOT = 1_000_000

# نقشه اعداد فارسی/عربی
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


def _ensure_cooldowns(bot_data):
    if "betting_cooldowns" not in bot_data or not isinstance(bot_data.get("betting_cooldowns"), dict):
        bot_data["betting_cooldowns"] = {}


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
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
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


def _fmt_time(sec):
    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    parts = []
    if h > 0: parts.append(f"{h} ساعت")
    if m > 0: parts.append(f"{m} دقیقه")
    if s > 0 and h == 0: parts.append(f"{s} ثانیه")
    return " و ".join(parts) if parts else "کمی"


def _check_cooldown(bot_data, uid, key, seconds=COOLDOWN_DAILY):
    _ensure_cooldowns(bot_data)
    last = bot_data["betting_cooldowns"].get(uid, {}).get(key, 0)
    now = time.time()
    if now - last < seconds:
        return False, int(seconds - (now - last))
    return True, 0


def _set_cooldown(bot_data, uid, key):
    _ensure_cooldowns(bot_data)
    if uid not in bot_data["betting_cooldowns"]:
        bot_data["betting_cooldowns"][uid] = {}
    bot_data["betting_cooldowns"][uid][key] = time.time()


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
            text_low in WHEEL_TRIGGERS or
            text_low in SLOT_TRIGGERS or
            raw_low.startswith("شرط بندی ") or
            raw_low in ("شرط بندی", "شرط‌بندی") or
            raw_low.startswith("ساخت کد هدیه") or
            raw_low.startswith("استفاده کد") or
            raw_low.startswith("ارسال هدیه")
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

    # ═══ 🎡 گردونه شانس ═══
    if text_low in WHEEL_TRIGGERS or raw_low in WHEEL_TRIGGERS:
        return await _spin_wheel(bot, chat_id, sender_id, name, msg, bot_data, save_data)

    # ═══ 🎰 اسلات ماشین ═══
    if text_low in SLOT_TRIGGERS or raw_low in SLOT_TRIGGERS:
        return await _spin_slot(bot, chat_id, sender_id, name, msg, bot_data, save_data)

    # ═══ 🎁 ساخت کد هدیه ═══
    m = re.match(r"^ساخت کد هدیه مقدار (\d+)$", raw_low)
    if m:
        return await _create_gift(bot, chat_id, sender_id, name, msg,
                                   int(m.group(1)), bot_data, save_data)

    # ═══ 🎁 استفاده کد هدیه ═══
    m = re.match(r"^استفاده کد ([A-Z0-9]+)$", raw_norm.upper())
    if m:
        return await _use_gift(bot, chat_id, sender_id, msg, m.group(1), bot_data, save_data)

    # ═══ 🎁 ارسال هدیه به کاربر دیگر ═══
    m = re.match(r"^ارسال هدیه (u?[A-Za-z0-9]+) مقدار (\d+)$", raw_norm)
    if m:
        return await _send_gift(bot, chat_id, sender_id, name, msg,
                                 _normalize_uid(m.group(1)), int(m.group(2)),
                                 bot_data, save_data)

    # ═══ 👑 افزایش موجودی (فقط ویژه) ═══
    m = re.match(r"^افزایش موجودی مقدار (\d+)$", raw_low)
    if m:
        if not _is_special_user(sender_id, name):
            return False
        return await _boost_balance(bot, chat_id, sender_id, name, msg,
                                     int(m.group(1)), bot_data, save_data)

    # ═══ 🎯 پنالتی ═══
    m = re.match(r"^شرط بندی پنالتی (چپ|وسط|راست)\s+(?:مقدار\s+)?(\d+)\s*$", raw_low)
    if m:
        return await _play_penalty(bot, chat_id, sender_id, name, msg,
                                    m.group(1), int(m.group(2)), bot_data, save_data)

    # ═══ 🎲 شرط بندی عمومی (تاس/شیر-خط/زوج-فرد) ═══
    m = re.match(
        r"^شرط بندی (?:تاس\s+)?(شیر|خط|زوج|فرد|\d+)\s+(?:مقدار\s+)?(\d+)\s*$",
        raw_low
    )
    if m:
        return await _play_bet(bot, chat_id, sender_id, name, msg,
                                m.group(1), int(m.group(2)), bot_data, save_data)

    return False


# ═══════════ 🎡 گردونه شانس ═══════════
async def _spin_wheel(bot, chat_id, sender_id, name, msg, bot_data, save_data):
    ok, remaining = _check_cooldown(bot_data, str(sender_id), "wheel")
    if not ok:
        await _send(bot, chat_id,
            "⏰ **هنوز آماده نیست!**\n\n"
            f"🎡 گردونه روزانه‌ست.\n"
            f"⌛ **باقی‌مونده:** {_fmt_time(remaining)}\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    await _send(bot, chat_id,
        "🎡 **گردونه شانس در حال چرخش...** 🎡\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n\n"
        "🎯 گردونه داره می‌چرخه...\n\n"
        "⚡ **FLUXBOT**",
        reply_to=msg.message_id)

    await asyncio.sleep(1.5)

    weights = [w for w, _ in WHEEL_SEGMENTS]
    prizes = [p for _, p in WHEEL_SEGMENTS]
    prize = random.choices(prizes, weights=weights, k=1)[0]
    emoji = random.choice(WHEEL_EMOJIS)

    bal = get_balance(bot_data, sender_id)
    new_bal = bal + prize
    set_balance(bot_data, sender_id, new_bal)
    _set_cooldown(bot_data, str(sender_id), "wheel")
    _safe_save(save_data, bot_data)

    await _send(bot, chat_id,
        "🎉 **گردونه ایستاد!** 🎉\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n"
        f"{emoji} **جایزه:** `+{prize:,}` واحد\n\n"
        f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
        "🎁 **دوباره:** ۲۴ ساعت دیگه!\n\n"
        "⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    return True


# ═══════════ 🎰 اسلات ماشین ═══════════
async def _spin_slot(bot, chat_id, sender_id, name, msg, bot_data, save_data):
    ok, remaining = _check_cooldown(bot_data, str(sender_id), "slot")
    if not ok:
        await _send(bot, chat_id,
            "⏰ **هنوز آماده نیست!**\n\n"
            f"🎰 اسلات ماشین روزانه‌ست.\n"
            f"⌛ **باقی‌مونده:** {_fmt_time(remaining)}\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    await _send(bot, chat_id,
        "🎰 **اسلات ماشین در حال چرخش...** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n\n"
        "🎰 | ❓ | ❓ | ❓ |\n\n"
        "🎲 داره می‌چرخه...\n\n"
        "⚡ **FLUXBOT**",
        reply_to=msg.message_id)

    await asyncio.sleep(1.5)

    # چرخش سه نماد
    r1 = random.choice(SLOT_SYMBOLS)
    r2 = random.choice(SLOT_SYMBOLS)
    r3 = random.choice(SLOT_SYMBOLS)

    slot_line = f"🎰 | {r1} | {r2} | {r3} |"

    # ۳ تا مثل هم = جایزه بزرگ
    if r1 == r2 == r3:
        prize = SLOT_JACKPOT
        bal = get_balance(bot_data, sender_id)
        new_bal = bal + prize
        set_balance(bot_data, sender_id, new_bal)
        _set_cooldown(bot_data, str(sender_id), "slot")
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "🎉 **جکپات! جکپات!** 🎉\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n\n"
            f"{slot_line}\n\n"
            "✨ **۳ تا مثل هم!** ✨\n\n"
            f"🏆 **جایزه:** `+{prize:,}` واحد\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "🎁 **دوباره:** ۲۴ ساعت دیگه!\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
    else:
        _set_cooldown(bot_data, str(sender_id), "slot")
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "🎰 **اسلات ایستاد** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n\n"
            f"{slot_line}\n\n"
            "😢 **این بار نشد!**\n\n"
            "💡 **برای برد:** ۳ نماد یکسان لازمه\n"
            "🎁 **دوباره:** ۲۴ ساعت دیگه\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
    return True


# ═══════════ 🎯 پنالتی ═══════════
async def _play_penalty(bot, chat_id, sender_id, name, msg, direction, amount, bot_data, save_data):
    if amount < MIN_BET:
        await _send(bot, chat_id,
            f"⚠️ **حداقل مبلغ شرط `{MIN_BET:,}` واحده!**",
            reply_to=msg.message_id)
        return True

    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n\n"
            f"💎 موجودی: `{bal:,}`\n🎯 نیاز: `{amount:,}`",
            reply_to=msg.message_id)
        return True

    dir_emoji = {"چپ": "⬅️", "وسط": "⬆️", "راست": "➡️"}.get(direction, "🎯")

    await _send(bot, chat_id,
        "⚽ **شرط بندی پنالتی** ⚽\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n"
        f"🎯 **جهت شوت:** {dir_emoji} `{direction}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n"
        "🧤 دروازه‌بان آماده‌ست...\n\n"
        "⚡ **FLUXBOT**",
        reply_to=msg.message_id)

    await asyncio.sleep(1.2)

    keeper = random.choice(["چپ", "وسط", "راست"])
    keeper_emoji = {"چپ": "⬅️", "وسط": "⬆️", "راست": "➡️"}.get(keeper, "🧤")

    # اگه جهت شوت با دروازه‌بان فرق داشت → گل
    won = (direction != keeper)

    if won:
        profit = amount * 2
        new_bal = bal + profit
    else:
        profit = -amount
        new_bal = max(MIN_BALANCE, bal - amount)

    set_balance(bot_data, sender_id, new_bal)
    _safe_save(save_data, bot_data)

    if won:
        result = (
            "⚽ **گلللللل!** ⚽\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شوت:** {dir_emoji} `{direction}`\n"
            f"🧤 **دروازه‌بان:** {keeper_emoji} `{keeper}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            "🎉 **توپ رفت تو دروازه!** 🎉\n"
            f"📈 **سود (۲x):** `+{profit:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "⚡ **FLUXBOT**"
        )
    else:
        result = (
            "⚽ **دروازه‌بان گرفت!** ⚽\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شوت:** {dir_emoji} `{direction}`\n"
            f"🧤 **دروازه‌بان:** {keeper_emoji} `{keeper}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            "😢 **دروازه‌بان توپ رو گرفت!**\n"
            f"📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "💡 **دوباره تلاش کن!**\n\n"
            "⚡ **FLUXBOT**"
        )

    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


# ═══════════ 🎁 کد هدیه - ساخت ═══════════
async def _create_gift(bot, chat_id, sender_id, name, msg, amount, bot_data, save_data):
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


# ═══════════ 🎁 کد هدیه - استفاده ═══════════
async def _use_gift(bot, chat_id, sender_id, msg, code, bot_data, save_data):
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
            "📌 این کد رو برای دوستت بفرست.",
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


# ═══════════ 🎁 ارسال هدیه ═══════════
async def _send_gift(bot, chat_id, sender_id, name, msg, receiver, amount, bot_data, save_data):
    if not receiver:
        await _send(bot, chat_id, "❌ **شناسه نامعتبره!**", reply_to=msg.message_id)
        return True
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


# ═══════════ 👑 افزایش موجودی ═══════════
async def _boost_balance(bot, chat_id, sender_id, name, msg, amount, bot_data, save_data):
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


# ═══════════ 🎲 شرط بندی عمومی ═══════════
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
        "🎲 در حال پرتاب تاس...\n\n⚡ **FLUXBOT**",
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
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
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
        "🎲 در حال پرتاب تاس...\n\n⚡ **FLUXBOT**",
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
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
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
        "🪙 در حال پرتاب سکه...\n\n⚡ **FLUXBOT**",
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
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
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
        "├ `شرط بندی 3 10000`\n"
        "└ `شرط بندی تاس 5 مقدار 5000`\n\n"
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
        "🎁 اگه درست بگی → **نصف** سود\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚽ **۴. پنالتی (سود ۲ برابر)**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "`شرط بندی پنالتی [چپ/وسط/راست] مقدار [عدد]`\n\n"
        "📌 **مثال:**\n"
        "`شرط بندی پنالتی چپ مقدار 5000`\n\n"
        "🎁 اگه دروازه‌بان جهت دیگه بپره → **۲ برابر** سود\n"
        "❌ اگه همون‌جا بپره → باخت\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎡 **۵. گردونه شانس (روزانه)**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "`گردونه` یا `گردونه شانس`\n\n"
        "🎁 جایزه تصادفی: **۱۰۰,۰۰۰ تا ۵۰۰,۰۰۰** واحد\n"
        "⏰ فقط **یک بار در ۲۴ ساعت**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎰 **۶. اسلات ماشین (روزانه)**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "`اسلات ماشین`\n\n"
        "🎁 اگه **۳ نماد یکسان** بیاد → **۱,۰۰۰,۰۰۰** واحد\n"
        "⏰ فقط **یک بار در ۲۴ ساعت**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎁 **کد هدیه**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🔨 `ساخت کد هدیه مقدار [عدد]`\n"
        "│   (کد در پیوی برات ارسال می‌شه)\n"
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
        "├ 🎲 مقدار شرط ≤ موجودی\n"
        "└ 🔒 مدیریت: `شرط بندی باز` / `شرط بندی بسته`\n\n"
        "⚡ **FLUXBOT**"
    )


def cleanup():
    """بدون state موندگار"""
    pass
