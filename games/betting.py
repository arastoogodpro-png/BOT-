# games/betting.py
# 🎰 بازی شرط بندی - نسخه نهایی با PV Debug
import time
import random
import asyncio
import re

# ═══════════ ثابت‌ها ═══════════
INITIAL_BALANCE = 50000
MIN_BALANCE = 50000
MIN_BET = 100
COOLDOWN_DAILY = 86400
DICE_EMOJIS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}

SPECIAL_ID_PARTS = ("0kujo1004f",)
SPECIAL_USERNAMES = ("arastoo_ff",)

WHEEL_SEGMENTS = [
    (30, 100_000), (25, 150_000), (20, 200_000),
    (12, 250_000), (8, 300_000), (4, 400_000), (1, 500_000),
]
WHEEL_EMOJIS = ["🎯", "🎁", "💎", "⭐", "🔥", "🏆", "👑"]
SLOT_SYMBOLS = ["🍒", "🍋", "🍇", "💎", "🔔", "7️⃣"]
SLOT_JACKPOT = 1_000_000

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


# ═══════════ نرمال‌سازی ═══════════
def _normalize(text):
    if not text:
        return ""
    s = str(text)
    for ch in ('\u200c', '\u200d', '\u00a0', '\u202f', '\u2009', '\u2060'):
        s = s.replace(ch, ' ')
    s = s.replace('\u064a', '\u06cc')
    s = s.replace('\u0643', '\u06a9')
    s = s.replace('\u0629', '\u0647')
    s = s.translate(PERSIAN_DIGITS)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


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


# ═══════════ داده‌ها ═══════════
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


# ═══════════ Send Helpers ═══════════
async def _send(bot, chat_id, text, reply_to=None):
    try:
        kwargs = {"chat_id": chat_id, "text": text}
        if reply_to:
            kwargs["reply_to_message_id"] = reply_to
        result = await bot.send_message(**kwargs)
        return result
    except Exception as e:
        print(f"⚠️ betting send to {chat_id}: {type(e).__name__}: {e}", flush=True)
        return None


async def _send_long(bot, chat_id, text, reply_to=None, max_len=900):
    if not text:
        return None
    if len(text) <= max_len:
        return await _send(bot, chat_id, text, reply_to=reply_to)
    parts = []
    remaining = text
    while len(remaining) > max_len:
        cut = remaining.rfind('\n', 0, max_len)
        if cut < 50:
            cut = max_len
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    first_result = None
    for i, part in enumerate(parts):
        if not part:
            continue
        rt = reply_to if i == 0 else None
        result = await _send(bot, chat_id, part, reply_to=rt)
        if i == 0:
            first_result = result
        if i < len(parts) - 1:
            await asyncio.sleep(0.3)
    return first_result


def _extract_msg_id(result):
    try:
        if isinstance(result, dict):
            data = result.get("data", result)
            if isinstance(data, dict):
                mid = data.get("message_id")
                if mid: return str(mid)
            mid = result.get("message_id")
            if mid: return str(mid)
        elif hasattr(result, "message_id"):
            return str(result.message_id)
    except Exception:
        pass
    return None


async def _auto_delete(bot, chat_id, message_id, delay):
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"⚠️ betting auto_delete: {e}", flush=True)


async def _try_pv_send(bot, user_id, text):
    """
    تلاش قدرتمند برای ارسال به پیوی
    برمی‌گردونه: (موفقیت: bool, جزئیات: str)
    """
    uid = str(user_id or "").strip()
    if not uid:
        return False, "شناسه خالیه"

    print(f"🔍 [PV DEBUG] user_id raw = {uid!r}", flush=True)

    # ساخت همه فرمت‌های ممکن
    variants = []

    def add(v):
        if v and v not in variants:
            variants.append(v)

    add(uid)
    # اگه u داره، بدون u هم امتحان کن
    if uid.startswith("u") and len(uid) > 1:
        add(uid[1:])
    # اگه u نداره، با u هم امتحان کن
    elif not uid.startswith(("u", "b", "g", "c", "U")):
        add("u" + uid)
    # کپی با b (بعضی روبیکاها با b کار می‌کنن)
    if uid.startswith("u"):
        add("b" + uid[1:])

    print(f"🔍 [PV DEBUG] variants = {variants}", flush=True)

    errors = []
    for fmt in variants:
        try:
            print(f"🔍 [PV DEBUG] trying chat_id = {fmt!r}", flush=True)
            # تلاش ساده
            await bot.send_message(chat_id=fmt, text=text)
            print(f"✅ [PV DEBUG] SUCCESS with {fmt!r}", flush=True)
            return True, f"موفق با {fmt}"
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            errors.append(f"{fmt} → {err[:200]}")
            print(f"⚠️ [PV DEBUG] FAILED {fmt!r}: {err[:300]}", flush=True)
            await asyncio.sleep(0.3)

    return False, " | ".join(errors) if errors else "خطای نامشخص"


# ═══════════ تشخیص راهنما ═══════════
def _is_help_cmd(raw, clean):
    """تشخیص راهنما با حداکثر تلرانس"""
    candidates = []
    for s in (raw, clean):
        if not s:
            continue
        s_str = str(s).strip()
        if not s_str:
            continue
        norm = _normalize(s_str)
        candidates.append(norm)
        candidates.append(norm.replace(" ", ""))
        candidates.append(norm.lower())
        candidates.append(norm.replace(" ", "").lower())

    exact_matches = {
        "شرط بندی", "شرطبندی",
        "اموزش شرط بندی", "اموزششرطبندی", "آموزششرطبندی",
        "آموزش شرط بندی",
        "راهنما شرط بندی", "راهنماشرطبندی",
        "راهنمای شرط بندی", "راهنمایشرطبندی",
    }

    for c in candidates:
        if not c:
            continue
        if c in exact_matches:
            return True

    # Fallback: هرچی "شرط" و "بندی" داره و کوتاهه
    for c in candidates:
        if c and len(c) <= 25 and "شرط" in c and "بندی" in c:
            return True

    return False


# ═══════════ Handle اصلی ═══════════
async def handle(ctx):
    try:
        return await _handle_inner(ctx)
    except Exception as e:
        print(f"❌ betting.handle ERROR: {type(e).__name__}: {e}", flush=True)
        import traceback
        try: traceback.print_exc()
        except: pass
        return False


async def _handle_inner(ctx):
    bot = ctx["bot"]
    chat_id = ctx["chat_id"]
    sender_id = ctx["sender_id"]
    text = (ctx.get("clean_text") or "").strip()
    raw = (ctx.get("raw_text") or "").strip()
    name = ctx.get("sender_display") or "کاربر"
    msg = ctx["message"]
    settings = ctx.get("settings") or {}
    bot_data = ctx.get("bot_data")
    save_data = ctx.get("save_data")

    if not isinstance(bot_data, dict):
        return False

    raw_norm = _normalize(raw)
    raw_low = raw_norm.lower()
    text_norm = _normalize(text)
    text_low = text_norm.lower()
    t_nospace = text_low.replace(" ", "")

    # ═══ 🔬 تست پیوی (Debug) ═══
    if text_low == "تست پیوی" or raw_low == "تست پیوی":
        ok, info = await _try_pv_send(bot, sender_id, "✅ تست موفق! پیوی کار می‌کنه.")
        status = "✅ پیوی باز شد" if ok else "❌ پیوی کار نمی‌کنه"
        await _send(bot, chat_id,
            f"🔬 **تست پیوی**\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **شناسه تو:** `{sender_id}`\n"
            f"{status}\n\n"
            f"📋 **جزئیات:**\n{info[:500]}\n\n"
            f"💡 اگه خطا داشت، همین متن رو برای سازنده بفرست.\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 📖 راهنما (اول از همه) ═══
    if _is_help_cmd(raw, text):
        print(f"🎯 [betting] HELP triggered", flush=True)
        bal = get_balance(bot_data, sender_id)
        _safe_save(save_data, bot_data)
        await _send_long(bot, chat_id, _get_help_text(bal), reply_to=msg.message_id)
        return True

    # ═══ چک قفل ═══
    if not settings.get("betting_enabled", True):
        triggered = (
            text_low in ("موجودی", "شناسه", "گردونه", "اسلات", "اسلات ماشین")
            or raw_low.startswith(("شرط بندی ", "ساخت کد هدیه", "استفاده کد", "ارسال هدیه"))
            or raw_low in ("شرط بندی", "شرط‌بندی")
        )
        if triggered:
            await _send(bot, chat_id,
                "🔴 **بازی شرط بندی غیرفعاله!**\n\n📌 توسط مدیریت بسته شده.\n\n⚡ **FLUXBOT**",
                reply_to=msg.message_id)
            return True
        return False

    # ═══ 💎 موجودی ═══
    if text_low in ("موجودی", "موجودی من", "موجودی چقدره", "حساب من",
                    "کیف پول من", "پول من") or raw_low in ("موجودی", "موجودی من"):
        bal = get_balance(bot_data, sender_id)
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "💰 **موجودی شما** 💰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **کاربر:** {name}\n"
            f"💎 **موجودی:** `{bal:,}` واحد\n\n"
            "💡 راهنما: `شرط بندی`\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 🆔 شناسه ═══
    if text_low in ("شناسه", "شناسه من", "ایدی من", "آیدی من") \
       or raw_low in ("شناسه", "شناسه من"):
        await _send(bot, chat_id,
            "🆔 **شناسه شما** 🆔\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **کاربر:** {name}\n"
            f"🆔 **شناسه:** `{sender_id}`\n\n"
            "💡 این شناسه ثابته.\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 🎡 گردونه ═══
    if text_low in ("گردونه", "گردونه شانس", "استفاده گردونه") \
       or t_nospace in ("گردونه", "گردونهشانس", "استفادهگردونه"):
        return await _spin_wheel(bot, chat_id, sender_id, name, msg, bot_data, save_data)

    # ═══ 🎰 اسلات ═══
    if text_low in ("اسلات", "اسلات ماشین", "استفاده اسلات") \
       or t_nospace in ("اسلات", "اسلاتماشین", "استفادهاسلات"):
        return await _spin_slot(bot, chat_id, sender_id, name, msg, bot_data, save_data)

    # ═══ 🎁 ساخت کد هدیه ═══
    m = re.match(r"^ساخت کد هدیه مقدار (\d+)$", raw_low)
    if m:
        return await _create_gift(bot, chat_id, sender_id, name, msg,
                                   int(m.group(1)), bot_data, save_data)

    # ═══ 🎁 استفاده کد ═══
    m = re.match(r"^استفاده کد ([A-Z0-9]+)$", raw_norm.upper())
    if m:
        return await _use_gift(bot, chat_id, sender_id, msg, m.group(1), bot_data, save_data)

    # ═══ 🎁 ارسال هدیه ═══
    m = re.match(r"^ارسال هدیه (u?[A-Za-z0-9]+) مقدار (\d+)$", raw_norm)
    if m:
        return await _send_gift(bot, chat_id, sender_id, name, msg,
                                 _normalize_uid(m.group(1)), int(m.group(2)),
                                 bot_data, save_data)

    # ═══ 👑 افزایش موجودی ═══
    m = re.match(r"^افزایش موجودی مقدار (\d+)$", raw_low)
    if m:
        if not _is_special_user(sender_id, name):
            return False
        return await _boost_balance(bot, chat_id, sender_id, name, msg,
                                     int(m.group(1)), bot_data, save_data)

    # ═══ ⚽ پنالتی ═══
    m = re.match(r"^شرط بندی پنالتی (چپ|وسط|راست)\s+(?:مقدار\s+)?(\d+)\s*$", raw_low)
    if m:
        return await _play_penalty(bot, chat_id, sender_id, name, msg,
                                    m.group(1), int(m.group(2)), bot_data, save_data)

    # ═══ 🎲 شرط عمومی ═══
    m = re.match(
        r"^شرط بندی (?:تاس\s+)?(شیر|خط|زوج|فرد|\d+)\s+(?:مقدار\s+)?(\d+)\s*$",
        raw_low
    )
    if m:
        return await _play_bet(bot, chat_id, sender_id, name, msg,
                                m.group(1), int(m.group(2)), bot_data, save_data)

    return False


# ═══════════ 🎡 گردونه ═══════════
async def _spin_wheel(bot, chat_id, sender_id, name, msg, bot_data, save_data):
    ok, remaining = _check_cooldown(bot_data, str(sender_id), "wheel")
    if not ok:
        await _send(bot, chat_id,
            f"⏰ **هنوز آماده نیست!**\n\n🎡 گردونه روزانه‌ست.\n"
            f"⌛ **باقی‌مونده:** {_fmt_time(remaining)}\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True
    await _send(bot, chat_id,
        "🎡 **گردونه در حال چرخش...** 🎡\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n\n🎯 گردونه داره می‌چرخه...\n\n⚡ **FLUXBOT**",
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
        f"👤 **بازیکن:** {name}\n{emoji} **جایزه:** `+{prize:,}`\n\n"
        f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
        "🎁 **دوباره:** ۲۴ ساعت دیگه!\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    return True


# ═══════════ 🎰 اسلات ═══════════
async def _spin_slot(bot, chat_id, sender_id, name, msg, bot_data, save_data):
    ok, remaining = _check_cooldown(bot_data, str(sender_id), "slot")
    if not ok:
        await _send(bot, chat_id,
            f"⏰ **هنوز آماده نیست!**\n\n🎰 اسلات روزانه‌ست.\n"
            f"⌛ **باقی‌مونده:** {_fmt_time(remaining)}\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True
    await _send(bot, chat_id,
        "🎰 **اسلات در حال چرخش...** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n\n🎰 | ❓ | ❓ | ❓ |\n\n"
        "🎲 داره می‌چرخه...\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    await asyncio.sleep(1.5)
    r1 = random.choice(SLOT_SYMBOLS)
    r2 = random.choice(SLOT_SYMBOLS)
    r3 = random.choice(SLOT_SYMBOLS)
    slot_line = f"🎰 | {r1} | {r2} | {r3} |"
    if r1 == r2 == r3:
        prize = SLOT_JACKPOT
        bal = get_balance(bot_data, sender_id)
        new_bal = bal + prize
        set_balance(bot_data, sender_id, new_bal)
        _set_cooldown(bot_data, str(sender_id), "slot")
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "🎉 **جکپات!** 🎉\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n\n{slot_line}\n\n"
            f"🏆 **جایزه:** `+{prize:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "🎁 دوباره: ۲۴ ساعت دیگه!\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
    else:
        _set_cooldown(bot_data, str(sender_id), "slot")
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "🎰 **اسلات ایستاد** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n\n{slot_line}\n\n"
            "😢 **این بار نشد!**\n"
            "💡 برای برد: ۳ نماد یکسان\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
    return True


# ═══════════ ⚽ پنالتی ═══════════
async def _play_penalty(bot, chat_id, sender_id, name, msg, direction, amount, bot_data, save_data):
    if amount < MIN_BET:
        await _send(bot, chat_id,
            f"⚠️ **حداقل شرط `{MIN_BET:,}`!**", reply_to=msg.message_id)
        return True
    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n💎 `{bal:,}` | نیاز: `{amount:,}`",
            reply_to=msg.message_id)
        return True
    dir_emoji = {"چپ": "⬅️", "وسط": "⬆️", "راست": "➡️"}.get(direction, "🎯")
    await _send(bot, chat_id,
        "⚽ **پنالتی** ⚽\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n🎯 **جهت:** {dir_emoji} `{direction}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n🧤 آماده...\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    await asyncio.sleep(1.2)
    keeper = random.choice(["چپ", "وسط", "راست"])
    keeper_emoji = {"چپ": "⬅️", "وسط": "⬆️", "راست": "➡️"}.get(keeper, "🧤")
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
            f"🎉 **گل!** 📈 **سود:** `+{profit:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    else:
        result = (
            "⚽ **دروازه‌بان گرفت!** ⚽\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n"
            f"🎯 **شوت:** {dir_emoji} `{direction}`\n"
            f"🧤 **دروازه‌بان:** {keeper_emoji} `{keeper}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"😢 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


# ═══════════ 🎁 ساخت کد هدیه ═══════════
async def _create_gift(bot, chat_id, sender_id, name, msg, amount, bot_data, save_data):
    if amount < MIN_BET:
        await _send(bot, chat_id,
            f"⚠️ **حداقل کد هدیه `{MIN_BET:,}`!**", reply_to=msg.message_id)
        return True
    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n💎 `{bal:,}` | نیاز: `{amount:,}`",
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
        f"💰 **مبلغ:** `{amount:,}`\n"
        f"🔑 **کد:** `{code}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📌 **استفاده:** `استفاده کد {code}`\n\n"
        "⚠️ فقط یک بار | برای دوستت بفرست\n\n"
        "⚡ **FLUXBOT**"
    )

    ok, info = await _try_pv_send(bot, sender_id, dm_text)

    if ok:
        # PV موفق
        await _send(bot, chat_id,
            "✅ **کد هدیه ساخته شد!**\n\n"
            f"💰 **مبلغ:** `{amount:,}`\n"
            "📩 **کد به پیوی شما ارسال شد.**\n\n"
            "💡 پیوی ربات رو چک کن.",
            reply_to=msg.message_id)
        return True

    # PV ناموفق → Fallback به گروه
    print(f"⚠️ [betting] PV failed, using group fallback. Info: {info}", flush=True)
    fallback = (
        "⚠️ **پیوی ربات بسته‌ست!**\n\n"
        "📌 کد رو اینجا نشون می‌دم:\n"
        "⏱️ **۲ دقیقه — سریع سیو کن!**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 **کد:** `{code}`\n"
        f"💰 **مبلغ:** `{amount:,}`\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 **استفاده:** `استفاده کد {code}`\n\n"
        "💡 **دفعه بعد:**\n"
        "├ به پیوی ربات برو\n"
        "├ `شروع` رو بزن\n"
        "└ بعد `تست پیوی` بزن\n\n"
        "⚡ **FLUXBOT**"
    )
    result = await _send(bot, chat_id, fallback, reply_to=msg.message_id)
    mid = _extract_msg_id(result)
    if mid:
        try:
            asyncio.create_task(_auto_delete(bot, chat_id, mid, 120))
        except Exception as e:
            print(f"⚠️ auto_delete task: {e}", flush=True)
    return True


# ═══════════ 🎁 استفاده کد ═══════════
async def _use_gift(bot, chat_id, sender_id, msg, code, bot_data, save_data):
    _ensure_gift_codes(bot_data)
    gift = bot_data["gift_codes"].get(code)
    if not gift:
        await _send(bot, chat_id, "❌ **کد نامعتبره!**", reply_to=msg.message_id)
        return True
    if gift.get("used"):
        await _send(bot, chat_id, "❌ **این کد قبلاً استفاده شده!**", reply_to=msg.message_id)
        return True
    if str(gift.get("creator")) == str(sender_id):
        await _send(bot, chat_id, "❌ **نمی‌تونی از کد خودت استفاده کنی!**", reply_to=msg.message_id)
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
        "🎉 **کد دریافت شد!** 🎉\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 **کد:** `{code}`\n"
        f"💰 **مبلغ:** `+{amount:,}`\n"
        f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**",
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
        await _send(bot, chat_id, f"⚠️ **حداقل `{MIN_BET:,}`!**", reply_to=msg.message_id)
        return True
    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n💎 `{bal:,}` | نیاز: `{amount:,}`",
            reply_to=msg.message_id)
        return True
    new_sender = bal - amount
    new_receiver = get_balance(bot_data, receiver) + amount
    set_balance(bot_data, sender_id, new_sender)
    set_balance(bot_data, receiver, new_receiver)
    _safe_save(save_data, bot_data)
    await _send(bot, chat_id,
        "🎁 **هدیه ارسال شد!** 🎁\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **از:** {name}\n"
        f"🎯 **به:** `{receiver}`\n"
        f"💰 **مبلغ:** `{amount:,}`\n\n"
        f"💎 **موجودی جدید تو:** `{new_sender:,}`\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    # اطلاع به دریافت‌کننده (اختیاری - اگه PV بسته باشه، بی‌خیال)
    await _try_pv_send(bot, receiver,
        "🎁 **هدیه جدید!** 🎁\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **از:** {name}\n"
        f"💰 **مبلغ:** `+{amount:,}`\n"
        f"💎 **موجودی جدید:** `{new_receiver:,}`\n\n⚡ **FLUXBOT**")
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
        f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    return True


# ═══════════ 🎲 شرط عمومی ═══════════
async def _play_bet(bot, chat_id, sender_id, name, msg, guess_raw, amount, bot_data, save_data):
    if amount < MIN_BET:
        await _send(bot, chat_id, f"⚠️ **حداقل `{MIN_BET:,}`!**", reply_to=msg.message_id)
        return True
    if guess_raw in ("شیر", "خط"):
        return await _play_coinflip(bot, chat_id, sender_id, name, msg,
                                     guess_raw, amount, bot_data, save_data)
    if guess_raw in ("زوج", "فرد"):
        return await _play_dice_evenodd(bot, chat_id, sender_id, name, msg,
                                         guess_raw, amount, bot_data, save_data)
    try:
        gn = int(guess_raw)
    except ValueError:
        await _send(bot, chat_id, "⚠️ **نوع شرط نامعتبره!**", reply_to=msg.message_id)
        return True
    if gn < 1 or gn > 6:
        await _send(bot, chat_id, "⚠️ **عدد ۱ تا ۶!**", reply_to=msg.message_id)
        return True
    return await _play_dice_number(bot, chat_id, sender_id, name, msg,
                                    gn, amount, bot_data, save_data)


async def _play_dice_number(bot, chat_id, sender_id, name, msg, guess, amount, bot_data, save_data):
    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n💎 `{bal:,}` | نیاز: `{amount:,}`",
            reply_to=msg.message_id)
        return True
    await _send(bot, chat_id,
        "🎲 **تاس عددی** 🎲\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n🎯 **شرط:** عدد `{guess}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n🎲 در حال پرتاب...\n\n⚡ **FLUXBOT**",
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
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** عدد `{guess}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}**\n\n"
            f"🎉 **بردی!** 📈 **سود:** `+{profit:,}`\n"
            f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    else:
        result = (
            "🎰 **نتیجه** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** عدد `{guess}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}**\n\n"
            f"😢 **باختی!** 📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


async def _play_dice_evenodd(bot, chat_id, sender_id, name, msg, choice, amount, bot_data, save_data):
    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n💎 `{bal:,}` | نیاز: `{amount:,}`",
            reply_to=msg.message_id)
        return True
    await _send(bot, chat_id,
        "🎲 **تاس زوج/فرد** 🎲\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n🎲 در حال پرتاب...\n\n⚡ **FLUXBOT**",
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
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}** ({parity})\n\n"
            f"🎉 **بردی!** 📈 **سود:** `+{profit:,}`\n"
            f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    else:
        result = (
            "🎰 **نتیجه** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}** ({parity})\n\n"
            f"😢 **باختی!** 📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


async def _play_coinflip(bot, chat_id, sender_id, name, msg, choice, amount, bot_data, save_data):
    bal = get_balance(bot_data, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n💎 `{bal:,}` | نیاز: `{amount:,}`",
            reply_to=msg.message_id)
        return True
    await _send(bot, chat_id,
        "🪙 **شیر یا خط** 🪙\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n🪙 در حال پرتاب...\n\n⚡ **FLUXBOT**",
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
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🪙 **نتیجه:** {result_emoji} **{result_side}**\n\n"
            f"🎉 **بردی!** 📈 **سود:** `+{profit:,}`\n"
            f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    else:
        result = (
            "🪙 **نتیجه** 🪙\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🪙 **نتیجه:** {result_emoji} **{result_side}**\n\n"
            f"😢 **باختی!** 📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


# ═══════════ 📖 راهنما ═══════════
def _get_help_text(bal):
    return (
        "🎰 **راهنمای شرط بندی** 🎰\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 **موجودی:** `{bal:,}`\n"
        f"📌 کف: `{MIN_BALANCE:,}` | حداقل: `{MIN_BET:,}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎲 **۱. تاس عددی (۳x)**\n"
        "`شرط بندی 3 10000`\n"
        "`شرط بندی تاس 5 مقدار 5000`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎲 **۲. تاس زوج/فرد (۲x)**\n"
        "`شرط بندی زوج 5000`\n"
        "`شرط بندی فرد 3000`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🪙 **۳. شیر یا خط (نصف)**\n"
        "`شرط بندی شیر 2000`\n"
        "`شرط بندی خط 5000`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚽ **۴. پنالتی (۲x)**\n"
        "`شرط بندی پنالتی چپ مقدار 5000`\n"
        "(چپ / وسط / راست)\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎡 **۵. گردونه (روزانه)**\n"
        "`گردونه`\n"
        "🎁 **۱۰۰K تا ۵۰۰K**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎰 **۶. اسلات (روزانه)**\n"
        "`اسلات ماشین`\n"
        "🎁 ۳ نماد یکسان → **۱M**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎁 **کد هدیه**\n"
        "├ `ساخت کد هدیه مقدار 10000`\n"
        "└ `استفاده کد ABC123`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎁 **ارسال هدیه**\n"
        "`ارسال هدیه [شناسه] مقدار 5000`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💰 **دستورات دیگه:**\n"
        "├ `موجودی` → موجودی\n"
        "├ `شناسه` → شناسه خودت\n"
        "├ `تست پیوی` → تست PV\n"
        "└ `راهنما شرط بندی` → این متن\n\n"
        "⚠️ **نکات:**\n"
        f"├ 💎 کف: `{MIN_BALANCE:,}`\n"
        "├ 🎲 شرط ≤ موجودی\n"
        "└ 🔒 `شرط بندی باز/بسته`\n\n"
        "⚡ **FLUXBOT**"
    )


def cleanup():
    pass
