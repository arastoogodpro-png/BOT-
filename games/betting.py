# games/betting.py
# 🎰 بازی شرط بندی - نسخه نهایی
# ✅ بانک + وام + استخراج + ربات سریع + فیکس کامل باگ تولید پول
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

# ⚙️ ربات سریع
SLEEP_FAST = 0.4
SLEEP_VERY_FAST = 0.3
SLEEP_BETWEEN_MSG = 0.1

# 🏦 بانک
BANK_MIN = 1000

# 💰 وام
LOAN_MAX = 5_000_000
LOAN_MIN = 50_000
LOAN_DAYS = 5
LOAN_DAYS_SEC = LOAN_DAYS * 86400

# ⛏️ استخراج
WORKER_PRICE = 1_000_000
WORKER_INCOME_PER_HOUR = 50_000

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
    if not text: return ""
    s = str(text)
    for ch in ('\u200c', '\u200d', '\u00a0', '\u202f', '\u2009', '\u2060'):
        s = s.replace(ch, ' ')
    s = s.replace('\u064a', '\u06cc').replace('\u0643', '\u06a9').replace('\u0629', '\u0647')
    s = s.translate(PERSIAN_DIGITS)
    return re.sub(r'\s+', ' ', s).strip()


def _is_special_user(sender_id, sender_display):
    sid = str(sender_id or "").lower()
    sdisp = str(sender_display or "").lstrip("@").lower()
    return any(p in sid for p in SPECIAL_ID_PARTS) or any(un == sdisp for un in SPECIAL_USERNAMES)


# ═══════════ 🆕 فیکس تولید پول ═══════════
def _get_spendable(bal):
    """بیشترین مبلغی که کاربر می‌تونه خرج کنه (بالای کف)"""
    return max(0, bal - MIN_BALANCE)


# ═══════════ داده‌ها ═══════════
def _ensure_balances(bot_data):
    if "balances" not in bot_data or not isinstance(bot_data.get("balances"), dict):
        bot_data["balances"] = {}
        return
    b = bot_data["balances"]
    for k, v in list(b.items())[:10]:
        if not isinstance(v, dict):
            print("🔄 [betting] Migrating balances to per-group", flush=True)
            bot_data["balances"] = {}
            return


def _ensure_gift_codes(bot_data):
    if "gift_codes" not in bot_data or not isinstance(bot_data.get("gift_codes"), dict):
        bot_data["gift_codes"] = {}


def _ensure_cooldowns(bot_data):
    if "betting_cooldowns" not in bot_data or not isinstance(bot_data.get("betting_cooldowns"), dict):
        bot_data["betting_cooldowns"] = {}


def _ensure_pv_chats(bot_data):
    if "pv_chats" not in bot_data or not isinstance(bot_data.get("pv_chats"), dict):
        bot_data["pv_chats"] = {}


def _ensure_bank(bot_data):
    if "bank" not in bot_data or not isinstance(bot_data.get("bank"), dict):
        bot_data["bank"] = {}


def _ensure_loans(bot_data):
    if "loans" not in bot_data or not isinstance(bot_data.get("loans"), dict):
        bot_data["loans"] = {}


def _ensure_workers(bot_data):
    if "workers" not in bot_data or not isinstance(bot_data.get("workers"), dict):
        bot_data["workers"] = {}


def get_balance(bot_data, chat_id, user_id):
    _ensure_balances(bot_data)
    cid, uid = str(chat_id), str(user_id)
    if cid not in bot_data["balances"]:
        bot_data["balances"][cid] = {}
    if uid not in bot_data["balances"][cid]:
        bot_data["balances"][cid][uid] = INITIAL_BALANCE
    try: return int(bot_data["balances"][cid][uid])
    except (ValueError, TypeError):
        bot_data["balances"][cid][uid] = INITIAL_BALANCE
        return INITIAL_BALANCE


def set_balance(bot_data, chat_id, user_id, amount):
    _ensure_balances(bot_data)
    cid, uid = str(chat_id), str(user_id)
    if cid not in bot_data["balances"]:
        bot_data["balances"][cid] = {}
    try: val = int(amount)
    except (ValueError, TypeError): val = MIN_BALANCE
    bot_data["balances"][cid][uid] = max(MIN_BALANCE, val)
    return bot_data["balances"][cid][uid]


# ═══════════ 🏦 بانک ═══════════
def get_bank(bot_data, chat_id, user_id):
    _ensure_bank(bot_data)
    cid, uid = str(chat_id), str(user_id)
    if cid not in bot_data["bank"]:
        bot_data["bank"][cid] = {}
    try: return int(bot_data["bank"][cid].get(uid, 0))
    except: return 0


def set_bank(bot_data, chat_id, user_id, amount):
    _ensure_bank(bot_data)
    cid, uid = str(chat_id), str(user_id)
    if cid not in bot_data["bank"]:
        bot_data["bank"][cid] = {}
    try: val = max(0, int(amount))
    except: val = 0
    bot_data["bank"][cid][uid] = val
    return val


# ═══════════ 💰 وام ═══════════
def get_loan(bot_data, chat_id, user_id):
    _ensure_loans(bot_data)
    cid, uid = str(chat_id), str(user_id)
    return bot_data["loans"].get(cid, {}).get(uid)


def set_loan(bot_data, chat_id, user_id, loan_data):
    _ensure_loans(bot_data)
    cid, uid = str(chat_id), str(user_id)
    if cid not in bot_data["loans"]:
        bot_data["loans"][cid] = {}
    if loan_data is None:
        bot_data["loans"][cid].pop(uid, None)
    else:
        bot_data["loans"][cid][uid] = loan_data


def _get_overdue_loan(bot_data, chat_id, user_id):
    loan = get_loan(bot_data, chat_id, user_id)
    if not loan or loan.get("paid"): return None
    if time.time() > loan.get("due_at", 0): return loan
    return None


def _credit_win(bot_data, chat_id, user_id, amount):
    """اعمال برد — اگه وام سرگذشته داشته باشه، اول وام پرداخت می‌شه"""
    if amount <= 0: return amount, 0
    overdue = _get_overdue_loan(bot_data, chat_id, user_id)
    if not overdue: return amount, 0

    remaining = overdue["amount"] - overdue.get("amount_paid", 0)
    if remaining <= 0:
        overdue["paid"] = True
        return amount, 0

    paid = min(amount, remaining)
    overdue["amount_paid"] = overdue.get("amount_paid", 0) + paid
    if overdue["amount_paid"] >= overdue["amount"]:
        overdue["paid"] = True

    leftover = amount - paid
    return leftover, paid


# ═══════════ ⛏️ استخراج ═══════════
def get_workers_data(bot_data, chat_id, user_id):
    _ensure_workers(bot_data)
    cid, uid = str(chat_id), str(user_id)
    if cid not in bot_data["workers"]:
        bot_data["workers"][cid] = {}
    if uid not in bot_data["workers"][cid]:
        bot_data["workers"][cid][uid] = {"count": 0, "last_claim": time.time()}
    return bot_data["workers"][cid][uid]


def _calc_worker_income(data):
    count = data.get("count", 0)
    if count <= 0: return 0
    last = data.get("last_claim", time.time())
    elapsed_hours = max(0, (time.time() - last) / 3600.0)
    return int(count * WORKER_INCOME_PER_HOUR * elapsed_hours)


# ═══════════ Helpers ═══════════
def _safe_save(save_data, bot_data):
    if save_data:
        try: save_data(bot_data, force=True)
        except Exception as e: print(f"⚠️ betting save: {e}", flush=True)


def _gen_code(bot_data):
    _ensure_gift_codes(bot_data)
    existing = bot_data["gift_codes"]
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(100):
        code = "".join(random.choices(alphabet, k=6))
        if code not in existing: return code
    return "G" + str(int(time.time()))[-5:]


def _normalize_uid(raw):
    if not raw: return ""
    uid = str(raw).strip()
    if not uid: return ""
    if uid[0].isdigit(): return "u" + uid
    return uid


def _fmt_time(sec):
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    parts = []
    if h > 0: parts.append(f"{h} ساعت")
    if m > 0: parts.append(f"{m} دقیقه")
    if s > 0 and h == 0: parts.append(f"{s} ثانیه")
    return " و ".join(parts) if parts else "کمی"


def _fmt_days(sec):
    d = int(sec // 86400)
    h = int((sec % 86400) // 3600)
    parts = []
    if d > 0: parts.append(f"{d} روز")
    if h > 0: parts.append(f"{h} ساعت")
    return " و ".join(parts) if parts else "کمتر از ۱ ساعت"


def _check_cooldown(bot_data, chat_id, uid, key, seconds=COOLDOWN_DAILY):
    _ensure_cooldowns(bot_data)
    ckey = f"{chat_id}:{uid}"
    last = bot_data["betting_cooldowns"].get(ckey, {}).get(key, 0)
    now = time.time()
    if now - last < seconds:
        return False, int(seconds - (now - last))
    return True, 0


def _set_cooldown(bot_data, chat_id, uid, key):
    _ensure_cooldowns(bot_data)
    ckey = f"{chat_id}:{uid}"
    if ckey not in bot_data["betting_cooldowns"]:
        bot_data["betting_cooldowns"][ckey] = {}
    bot_data["betting_cooldowns"][ckey][key] = time.time()


# ═══════════ Send ═══════════
async def _send(bot, chat_id, text, reply_to=None):
    try:
        kwargs = {"chat_id": chat_id, "text": text}
        if reply_to: kwargs["reply_to_message_id"] = reply_to
        return await bot.send_message(**kwargs)
    except Exception as e:
        print(f"⚠️ betting send to {chat_id}: {type(e).__name__}: {e}", flush=True)
        return None


async def _send_long(bot, chat_id, text, reply_to=None, max_len=900):
    if not text: return None
    if len(text) <= max_len:
        return await _send(bot, chat_id, text, reply_to=reply_to)
    parts, remaining = [], text
    while len(remaining) > max_len:
        cut = remaining.rfind('\n', 0, max_len)
        if cut < 50: cut = max_len
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining: parts.append(remaining)
    first = None
    for i, part in enumerate(parts):
        if not part: continue
        r = await _send(bot, chat_id, part, reply_to=(reply_to if i == 0 else None))
        if i == 0: first = r
        if i < len(parts) - 1:
            await asyncio.sleep(SLEEP_BETWEEN_MSG)
    return first


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
    except: pass
    return None


async def _auto_delete(bot, chat_id, message_id, delay):
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e: print(f"⚠️ auto_delete: {e}", flush=True)


def _get_pv_chat_id(bot_data, user_id):
    _ensure_pv_chats(bot_data)
    return bot_data["pv_chats"].get(str(user_id))


def _save_pv_chat_id(bot_data, save_data, user_id, chat_id):
    if not chat_id: return
    cid = str(chat_id).strip()
    if not cid.startswith("b"): return
    _ensure_pv_chats(bot_data)
    uid = str(user_id)
    if bot_data["pv_chats"].get(uid) == cid:
        return
    bot_data["pv_chats"][uid] = cid
    _safe_save(save_data, bot_data)


async def _try_pv_send(bot, user_id, text, current_chat_id=None, bot_data=None, save_data=None):
    uid = str(user_id or "").strip()
    if not uid: return False, "شناسه خالیه"
    print(f"🔍 [PV] user_id={uid!r} current={current_chat_id!r}", flush=True)

    if current_chat_id and str(current_chat_id).startswith("b"):
        if bot_data is not None:
            _save_pv_chat_id(bot_data, save_data, uid, current_chat_id)
        try:
            await bot.send_message(chat_id=str(current_chat_id), text=text)
            print(f"✅ [PV] SUCCESS current", flush=True)
            return True, "موفق با b0 فعلی"
        except Exception as e: print(f"⚠️ [PV] current failed: {e}", flush=True)

    if bot_data is not None:
        cached = _get_pv_chat_id(bot_data, uid)
        if cached:
            try:
                await bot.send_message(chat_id=cached, text=text)
                print(f"✅ [PV] SUCCESS cached", flush=True)
                return True, "موفق با b0 ذخیره‌شده"
            except Exception as e: print(f"⚠️ [PV] cached failed: {e}", flush=True)

    for method_name in ("get_chat_info", "get_chat"):
        if not hasattr(bot, method_name): continue
        try:
            method = getattr(bot, method_name)
            info = await method(uid)
            if not info: continue
            data = info.get("data", info) if isinstance(info, dict) else info
            if not isinstance(data, dict): continue
            containers = []
            if isinstance(data.get("chat"), dict):
                containers.append(data["chat"])
            containers.append(data)
            seen_ids = set()
            for container in containers:
                for key in ("chat_id", "object_guid", "object_id", "guid", "id"):
                    real_id = container.get(key)
                    if not real_id: continue
                    real_id_str = str(real_id)
                    if real_id_str in seen_ids or real_id_str == uid: continue
                    seen_ids.add(real_id_str)
                    try:
                        await bot.send_message(chat_id=real_id_str, text=text)
                        print(f"✅ [PV] SUCCESS {method_name} {real_id_str}", flush=True)
                        if bot_data is not None and real_id_str.startswith("b"):
                            _save_pv_chat_id(bot_data, save_data, uid, real_id_str)
                        return True, f"موفق با {method_name}"
                    except Exception as e:
                        print(f"⚠️ [PV] {method_name} send failed: {e}", flush=True)
        except Exception as e:
            print(f"⚠️ [PV] {method_name} failed: {e}", flush=True)

    base = uid[1:] if uid.startswith("u") else uid
    variants = [uid, "b" + base, base]
    seen, unique = set(), []
    for v in variants:
        if v and v not in seen:
            unique.append(v); seen.add(v)
    for fmt in unique:
        try:
            await bot.send_message(chat_id=fmt, text=text)
            print(f"✅ [PV] SUCCESS direct {fmt}", flush=True)
            return True, f"موفق با {fmt}"
        except Exception as e:
            print(f"⚠️ [PV] direct {fmt} failed: {e}", flush=True)
            await asyncio.sleep(0.1)
    return False, "همه روش‌ها ناموفق"


# ═══════════ تشخیص راهنما ═══════════
def _is_help_cmd(raw, clean):
    exact = {
        "شرط بندی", "شرطبندی",
        "اموزش شرط بندی", "اموزششرطبندی",
        "آموزش شرط بندی", "آموزششرطبندی",
        "راهنما شرط بندی", "راهنماشرطبندی",
        "راهنمای شرط بندی", "راهنمایشرطبندی",
    }
    for s in (raw, clean):
        if not s: continue
        norm = _normalize(s)
        if not norm: continue
        if norm in exact: return True
        if norm.replace(" ", "") in exact: return True
        if norm.lower() in exact: return True
        if norm.replace(" ", "").lower() in exact: return True
    return False


# ═══════════ Handle ═══════════
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

    if not isinstance(bot_data, dict): return False

    if str(chat_id).startswith("b"):
        _save_pv_chat_id(bot_data, save_data, sender_id, chat_id)

    raw_norm = _normalize(raw)
    raw_low = raw_norm.lower()
    text_norm = _normalize(text)
    text_low = text_norm.lower()
    t_nospace = text_low.replace(" ", "")

    # ═══ 🔬 تست پیوی ═══
    if text_low == "تست پیوی" or raw_low == "تست پیوی":
        if str(chat_id).startswith("b"):
            _save_pv_chat_id(bot_data, save_data, sender_id, chat_id)
        ok, info = await _try_pv_send(bot, sender_id, "✅ تست موفق!",
                                       current_chat_id=chat_id, bot_data=bot_data, save_data=save_data)
        status = "✅ پیوی باز شد" if ok else "❌ پیوی کار نمی‌کنه"
        where = "📩 PV" if str(chat_id).startswith("b") else "👥 گروه"
        await _send(bot, chat_id,
            f"🔬 **تست پیوی**\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **شناسه:** `{sender_id}`\n📍 **محل:** {where}\n{status}\n\n"
            f"📋 **جزئیات:**\n{info[:500]}\n\n"
            f"💡 اگه خطا داشت، این متن رو برای سازنده بفرست.\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 📖 راهنما ═══
    if _is_help_cmd(raw, text):
        print(f"🎯 [betting] HELP triggered: {raw!r}", flush=True)
        bal = get_balance(bot_data, chat_id, sender_id)
        _safe_save(save_data, bot_data)
        await _send_long(bot, chat_id, _get_help_text(bal), reply_to=msg.message_id)
        return True

    # ═══ چک قفل ═══
    if not settings.get("betting_enabled", True):
        triggered = (
            text_low in ("موجودی", "شناسه", "گردونه", "اسلات", "اسلات ماشین",
                         "بانک", "وام", "کارگر")
            or raw_low.startswith(("شرط بندی ", "ساخت کد هدیه", "استفاده کد", "ارسال هدیه",
                                    "واریز در بانک", "برداشت از بانک", "گرفتن وام",
                                    "پرداخت وام", "خرید کارگر"))
            or raw_low in ("شرط بندی", "شرط‌بندی")
        )
        if triggered:
            await _send(bot, chat_id, "🔴 **بازی شرط بندی غیرفعاله!**\n\n⚡ **FLUXBOT**",
                        reply_to=msg.message_id)
            return True
        return False

    # ═══ 💎 موجودی ═══
    if text_low in ("موجودی", "موجودی من", "موجودی چقدره", "حساب من",
                    "کیف پول من", "پول من") or raw_low in ("موجودی", "موجودی من"):
        bal = get_balance(bot_data, chat_id, sender_id)
        bank = get_bank(bot_data, chat_id, sender_id)
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "💰 **موجودی شما** 💰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **کاربر:** {name}\n"
            f"💵 **در دست:** `{bal:,}` واحد\n"
            f"🏦 **در بانک:** `{bank:,}` واحد\n"
            f"💎 **کل دارایی:** `{bal+bank:,}` واحد\n\n"
            "📌 **هر گروه موجودی جدا داره!**\n"
            "💡 راهنما: `شرط بندی`\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 🆔 شناسه ═══
    if text_low in ("شناسه", "شناسه من", "ایدی من", "آیدی من") or raw_low in ("شناسه", "شناسه من"):
        await _send(bot, chat_id,
            "🆔 **شناسه شما** 🆔\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **کاربر:** {name}\n🆔 **شناسه:** `{sender_id}`\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 🏦 بانک ═══
    if text_low == "بانک" or raw_low == "بانک":
        bal = get_balance(bot_data, chat_id, sender_id)
        bank = get_bank(bot_data, chat_id, sender_id)
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            "🏦 **بانک شما** 🏦\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **کاربر:** {name}\n"
            f"🏦 **موجودی بانک:** `{bank:,}` واحد\n"
            f"💵 **در دست:** `{bal:,}` واحد\n"
            f"💎 **کل دارایی:** `{bal+bank:,}` واحد\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **حداقل واریز:** `{BANK_MIN:,}`\n"
            f"💡 `واریز در بانک مقدار [عدد]`\n"
            f"💡 `برداشت از بانک مقدار [عدد]`\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    # ═══ 🏦 واریز در بانک ═══
    m = re.match(r"^واریز در بانک مقدار (\d+)$", raw_low)
    if m:
        return await _bank_deposit(bot, chat_id, sender_id, name, msg,
                                    int(m.group(1)), bot_data, save_data)

    # ═══ 🏦 برداشت از بانک ═══
    m = re.match(r"^برداشت از بانک مقدار (\d+)$", raw_low)
    if m:
        return await _bank_withdraw(bot, chat_id, sender_id, name, msg,
                                     int(m.group(1)), bot_data, save_data)

    # ═══ 💰 گرفتن وام ═══
    m = re.match(r"^گرفتن وام مقدار (\d+)$", raw_low)
    if m:
        return await _loan_take(bot, chat_id, sender_id, name, msg,
                                 int(m.group(1)), bot_data, save_data)

    # ═══ 💰 نمایش وام‌ها ═══
    if text_low == "وام" or raw_low == "وام":
        return await _loan_show(bot, chat_id, sender_id, name, msg, bot_data, save_data)

    # ═══ 💰 پرداخت وام ═══
    m = re.match(r"^پرداخت وام مقدار (\d+)$", raw_low)
    if m:
        return await _loan_pay(bot, chat_id, sender_id, name, msg,
                                int(m.group(1)), bot_data, save_data)
    if text_low in ("پرداخت وام", "تسویه وام") or raw_low in ("پرداخت وام", "تسویه وام"):
        return await _loan_pay(bot, chat_id, sender_id, name, msg,
                                None, bot_data, save_data)

    # ═══ ⛏️ خرید کارگر ═══
    m = re.match(r"^خرید کارگر مقدار (\d+)$", raw_low)
    if m:
        return await _buy_workers(bot, chat_id, sender_id, name, msg,
                                   int(m.group(1)), bot_data, save_data)

    # ═══ ⛏️ نمایش کارگرها ═══
    if text_low == "کارگر" or raw_low == "کارگر":
        return await _show_workers(bot, chat_id, sender_id, name, msg, bot_data, save_data)

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
        if not _is_special_user(sender_id, name): return False
        return await _boost_balance(bot, chat_id, sender_id, name, msg,
                                     int(m.group(1)), bot_data, save_data)

    # ═══ ⚽ پنالتی ═══
    m = re.match(r"^شرط بندی پنالتی (چپ|وسط|راست)\s+(?:مقدار\s+)?(\d+)\s*$", raw_low)
    if m:
        return await _play_penalty(bot, chat_id, sender_id, name, msg,
                                    m.group(1), int(m.group(2)), bot_data, save_data)

    # ═══ 🎲 شرط عمومی ═══
    m = re.match(r"^شرط بندی (?:تاس\s+)?(شیر|خط|زوج|فرد|\d+)\s+(?:مقدار\s+)?(\d+)\s*$", raw_low)
    if m:
        return await _play_bet(bot, chat_id, sender_id, name, msg,
                                m.group(1), int(m.group(2)), bot_data, save_data)

    return False


# ═══════════ 🏦 بانک - واریز (✅ فیکس‌شده) ═══════════
async def _bank_deposit(bot, chat_id, sender_id, name, msg, amount, bot_data, save_data):
    if amount < BANK_MIN:
        await _send(bot, chat_id,
            f"⚠️ **حداقل واریز `{BANK_MIN:,}` واحده!**",
            reply_to=msg.message_id); return True
    bal = get_balance(bot_data, chat_id, sender_id)
    spendable = _get_spendable(bal)
    if amount > spendable:
        await _send(bot, chat_id,
            f"❌ **نمی‌تونی اینقدر واریز کنی!**\n\n"
            f"💵 **در دست:** `{bal:,}`\n"
            f"💎 **کف موجودی:** `{MIN_BALANCE:,}`\n"
            f"✅ **قابل واریز:** `{spendable:,}`\n\n"
            "📌 کف موجودی باید باقی بمونه.",
            reply_to=msg.message_id); return True
    bank = get_bank(bot_data, chat_id, sender_id)
    new_bal = bal - amount
    new_bank = bank + amount
    set_balance(bot_data, chat_id, sender_id, new_bal)
    set_bank(bot_data, chat_id, sender_id, new_bank)
    _safe_save(save_data, bot_data)
    await _send(bot, chat_id,
        "🏦 **واریز موفق!** 🏦\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **کاربر:** {name}\n"
        f"💰 **واریز شده:** `{amount:,}`\n\n"
        f"💵 **در دست:** `{new_bal:,}`\n"
        f"🏦 **در بانک:** `{new_bank:,}`\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    return True


# ═══════════ 🏦 بانک - برداشت ═══════════
async def _bank_withdraw(bot, chat_id, sender_id, name, msg, amount, bot_data, save_data):
    if amount <= 0:
        await _send(bot, chat_id, "⚠️ مبلغ باید مثبت باشه.", reply_to=msg.message_id); return True
    bank = get_bank(bot_data, chat_id, sender_id)
    if bank < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی بانک کافی نیست!**\n🏦 `{bank:,}` | نیاز: `{amount:,}`",
            reply_to=msg.message_id); return True
    bal = get_balance(bot_data, chat_id, sender_id)
    new_bal = bal + amount
    new_bank = bank - amount
    set_balance(bot_data, chat_id, sender_id, new_bal)
    set_bank(bot_data, chat_id, sender_id, new_bank)
    _safe_save(save_data, bot_data)
    await _send(bot, chat_id,
        "🏦 **برداشت موفق!** 🏦\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **کاربر:** {name}\n"
        f"💰 **برداشت شده:** `{amount:,}`\n\n"
        f"💵 **در دست:** `{new_bal:,}`\n"
        f"🏦 **در بانک:** `{new_bank:,}`\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    return True


# ═══════════ 💰 وام - گرفتن ═══════════
async def _loan_take(bot, chat_id, sender_id, name, msg, amount, bot_data, save_data):
    if amount < LOAN_MIN:
        await _send(bot, chat_id,
            f"⚠️ **حداقل وام `{LOAN_MIN:,}` واحده!**",
            reply_to=msg.message_id); return True
    if amount > LOAN_MAX:
        await _send(bot, chat_id,
            f"⚠️ **حداکثر وام `{LOAN_MAX:,}` واحده!**",
            reply_to=msg.message_id); return True

    existing = get_loan(bot_data, chat_id, sender_id)
    if existing and not existing.get("paid"):
        remaining = existing["amount"] - existing.get("amount_paid", 0)
        await _send(bot, chat_id,
            f"❌ **اول وام قبلی رو تسویه کن!**\n\n"
            f"💰 **وام فعلی:** `{existing['amount']:,}`\n"
            f"💵 **پرداخت‌شده:** `{existing.get('amount_paid',0):,}`\n"
            f"📉 **باقی‌مونده:** `{remaining:,}`\n\n"
            f"💡 برای تسویه: `پرداخت وام مقدار [عدد]`\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    now = time.time()
    due_at = now + LOAN_DAYS_SEC
    loan = {
        "amount": amount,
        "amount_paid": 0,
        "taken_at": now,
        "due_at": due_at,
        "paid": False,
    }
    set_loan(bot_data, chat_id, sender_id, loan)

    bal = get_balance(bot_data, chat_id, sender_id)
    new_bal = bal + amount
    set_balance(bot_data, chat_id, sender_id, new_bal)
    _safe_save(save_data, bot_data)

    due_str = time.strftime("%Y/%m/%d - %H:%M", time.localtime(due_at))
    await _send(bot, chat_id,
        "💰 **وام دریافت شد!** 💰\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **کاربر:** {name}\n"
        f"💵 **مبلغ وام:** `{amount:,}`\n"
        f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
        f"⏰ **مهلت پرداخت:** {LOAN_DAYS} روز\n"
        f"📅 **تاریخ سررسید:** {due_str}\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ **هشدار:**\n"
        "اگه تا سررسید پرداخت نکنی:\n"
        "├ 🚫 تمام بردهای آینده به وام می‌ره\n"
        "└ 💎 تا تسویه کامل، به موجودیت اضافه نمی‌شه\n\n"
        "💡 **پرداخت:** `پرداخت وام مقدار [عدد]`\n"
        "📋 **مشاهده وام:** `وام`\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    return True


# ═══════════ 💰 وام - نمایش ═══════════
async def _loan_show(bot, chat_id, sender_id, name, msg, bot_data, save_data):
    loan = get_loan(bot_data, chat_id, sender_id)
    if not loan:
        await _send(bot, chat_id,
            "💰 **وام شما** 💰\n━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ **شما هیچ وام فعالی ندارید!**\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "💡 **گرفتن وام:**\n"
            f"`گرفتن وام مقدار [عدد]`\n\n"
            f"📌 **محدوده:** `{LOAN_MIN:,}` تا `{LOAN_MAX:,}`\n"
            f"⏰ **مهلت پرداخت:** {LOAN_DAYS} روز\n\n"
            "⚠️ **اگه پرداخت نکنی:**\n"
            "├ 🚫 همه بردها به وام می‌ره\n"
            "└ 💎 تا تسویه، پولی به دستت نمی‌رسه\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    amount = loan["amount"]
    paid = loan.get("amount_paid", 0)
    remaining = amount - paid
    due_at = loan["due_at"]
    now = time.time()
    overdue = now > due_at
    time_left = due_at - now if not overdue else 0
    overdue_time = now - due_at if overdue else 0

    if loan.get("paid"):
        status = "✅ تسویه شده"
    elif overdue:
        status = "🚨 سرگذشته!"
    else:
        status = "⏳ در جریان"

    due_str = time.strftime("%Y/%m/%d - %H:%M", time.localtime(due_at))

    text = (
        "💰 **وضعیت وام شما** 💰\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **کاربر:** {name}\n"
        f"📊 **وضعیت:** {status}\n\n"
        f"💵 **مبلغ وام:** `{amount:,}`\n"
        f"✅ **پرداخت‌شده:** `{paid:,}`\n"
        f"📉 **باقی‌مونده:** `{remaining:,}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📅 **سررسید:** {due_str}\n"
    )

    if loan.get("paid"):
        text += "\n🎉 **وام تسویه شده!**\n"
    elif overdue:
        text += (
            f"🚨 **{_fmt_days(overdue_time)} گذشته!**\n\n"
            "⚠️ **پنالتی فعال:**\n"
            "├ 🚫 تمام بردهای آینده به وام می‌ره\n"
            "└ 💎 تا تسویه، به موجودیت اضافه نمی‌شه\n"
        )
    else:
        text += f"⌛ **مونده:** {_fmt_days(time_left)}\n"

    text += (
        "\n━━━━━━━━━━━━━━━━━━━\n"
        "💡 **پرداخت وام:**\n"
        "├ `پرداخت وام مقدار [عدد]`\n"
        "└ `پرداخت وام` → پرداخت همه\n\n"
        "⚡ **FLUXBOT**"
    )
    await _send(bot, chat_id, text, reply_to=msg.message_id)
    return True


# ═══════════ 💰 وام - پرداخت (✅ فیکس‌شده) ═══════════
async def _loan_pay(bot, chat_id, sender_id, name, msg, amount, bot_data, save_data):
    loan = get_loan(bot_data, chat_id, sender_id)
    if not loan or loan.get("paid"):
        await _send(bot, chat_id,
            "❌ **وام فعالی نداری!**\n\n💡 برای گرفتن وام: `گرفتن وام مقدار [عدد]`",
            reply_to=msg.message_id)
        return True

    remaining = loan["amount"] - loan.get("amount_paid", 0)
    if remaining <= 0:
        loan["paid"] = True
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id, "✅ **وام قبلاً تسویه شده!**", reply_to=msg.message_id)
        return True

    bal = get_balance(bot_data, chat_id, sender_id)
    spendable = _get_spendable(bal)
    if spendable <= 0:
        await _send(bot, chat_id,
            f"❌ **موجودی قابل استفاده نداری!**\n\n"
            f"💵 **در دست:** `{bal:,}`\n"
            f"💎 **کف موجودی:** `{MIN_BALANCE:,}`\n\n"
            "📌 اول باید موجودیت رو بیشتر کنی.",
            reply_to=msg.message_id)
        return True

    pay_amount = remaining if amount is None else min(amount, remaining)
    if pay_amount <= 0:
        await _send(bot, chat_id, "⚠️ مبلغ باید مثبت باشه.", reply_to=msg.message_id); return True
    if pay_amount > spendable:
        await _send(bot, chat_id,
            f"❌ **نمی‌تونی اینقدر پرداخت کنی!**\n\n"
            f"💵 **در دست:** `{bal:,}`\n"
            f"💎 **کف موجودی:** `{MIN_BALANCE:,}`\n"
            f"✅ **قابل پرداخت:** `{spendable:,}`\n\n"
            "📌 کف موجودی باید باقی بمونه.",
            reply_to=msg.message_id)
        return True

    new_bal = bal - pay_amount
    loan["amount_paid"] = loan.get("amount_paid", 0) + pay_amount
    if loan["amount_paid"] >= loan["amount"]:
        loan["paid"] = True
    set_balance(bot_data, chat_id, sender_id, new_bal)
    set_loan(bot_data, chat_id, sender_id, loan)
    _safe_save(save_data, bot_data)

    remaining_after = loan["amount"] - loan["amount_paid"]
    if loan["paid"]:
        result_text = (
            "🎉 **وام تسویه شد!** 🎉\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **کاربر:** {name}\n"
            f"💵 **پرداخت:** `{pay_amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "✅ **دیگه هیچ بدهی نداری!**\n"
            "🚀 از این به بعد بردها به موجودیت اضافه می‌شه.\n\n"
            "⚡ **FLUXBOT**"
        )
    else:
        result_text = (
            "💰 **پرداخت وام** 💰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **کاربر:** {name}\n"
            f"💵 **پرداخت:** `{pay_amount:,}`\n"
            f"📉 **باقی‌مونده:** `{remaining_after:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
            "💡 برای تسویه کامل: `پرداخت وام`\n\n"
            "⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result_text, reply_to=msg.message_id)
    return True


# ═══════════ ⛏️ خرید کارگر (✅ فیکس‌شده) ═══════════
async def _buy_workers(bot, chat_id, sender_id, name, msg, count, bot_data, save_data):
    if count <= 0:
        await _send(bot, chat_id, "⚠️ تعداد باید مثبت باشه.", reply_to=msg.message_id); return True
    if count > 1000:
        await _send(bot, chat_id, "⚠️ حداکثر ۱۰۰۰ کارگر در یک بار.", reply_to=msg.message_id); return True

    total_cost = count * WORKER_PRICE
    bal = get_balance(bot_data, chat_id, sender_id)
    spendable = _get_spendable(bal)
    if total_cost > spendable:
        await _send(bot, chat_id,
            f"❌ **نمی‌تونی اینقدر کارگر بخری!**\n\n"
            f"🔢 **تعداد:** `{count}`\n"
            f"💵 **قیمت هر کارگر:** `{WORKER_PRICE:,}`\n"
            f"💰 **هزینه کل:** `{total_cost:,}`\n"
            f"💵 **در دست:** `{bal:,}`\n"
            f"💎 **کف موجودی:** `{MIN_BALANCE:,}`\n"
            f"✅ **قابل خرید:** `{spendable:,}`\n\n"
            "📌 کف موجودی باید باقی بمونه.",
            reply_to=msg.message_id); return True

    data = get_workers_data(bot_data, chat_id, sender_id)
    old_income = _calc_worker_income(data)
    if old_income > 0:
        data["last_claim"] = time.time()

    data["count"] = data.get("count", 0) + count
    data["last_claim"] = time.time()

    new_bal = bal - total_cost + old_income
    set_balance(bot_data, chat_id, sender_id, new_bal)
    _safe_save(save_data, bot_data)

    total_workers = data["count"]
    hourly = total_workers * WORKER_INCOME_PER_HOUR

    text = (
        "⛏️ **کارگر خریدی!** ⛏️\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **کاربر:** {name}\n"
        f"🔢 **تعداد خرید:** `{count}`\n"
        f"💰 **هزینه:** `{total_cost:,}`\n"
    )
    if old_income > 0:
        text += f"💰 **درآمد قبلی:** `+{old_income:,}`\n"
    text += (
        f"\n━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **کل کارگرها:** `{total_workers}`\n"
        f"💵 **درآمد ساعتی:** `{hourly:,}`\n"
        f"💎 **موجودی جدید:** `{new_bal:,}`\n\n"
        "💡 **جمع‌آوری درآمد:** `کارگر`\n\n⚡ **FLUXBOT**"
    )
    await _send(bot, chat_id, text, reply_to=msg.message_id)
    return True


# ═══════════ ⛏️ نمایش کارگرها ═══════════
async def _show_workers(bot, chat_id, sender_id, name, msg, bot_data, save_data):
    data = get_workers_data(bot_data, chat_id, sender_id)
    count = data.get("count", 0)
    income = _calc_worker_income(data)

    if count <= 0:
        await _send(bot, chat_id,
            "⛏️ **استخراج** ⛏️\n━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ **هنوز کارگری نداری!**\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📌 **چی هست؟**\n"
            "کارگرها هر ساعت برات درآمد می‌سازن!\n\n"
            f"💵 **قیمت هر کارگر:** `{WORKER_PRICE:,}`\n"
            f"💰 **درآمد ساعتی هر کارگر:** `{WORKER_INCOME_PER_HOUR:,}`\n\n"
            "💡 **خرید:** `خرید کارگر مقدار [تعداد]`\n\n"
            "⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True

    bal = get_balance(bot_data, chat_id, sender_id)
    new_bal = bal + income
    if income > 0:
        data["last_claim"] = time.time()
        set_balance(bot_data, chat_id, sender_id, new_bal)
        _safe_save(save_data, bot_data)

    hourly = count * WORKER_INCOME_PER_HOUR
    text = (
        "⛏️ **استخراج شما** ⛏️\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **کاربر:** {name}\n"
        f"🔢 **تعداد کارگرها:** `{count}`\n"
        f"💵 **درآمد ساعتی:** `{hourly:,}`\n"
    )
    if income > 0:
        text += f"\n🎁 **درآمد جمع‌آوری‌شده:** `+{income:,}`\n"
    else:
        text += "\n⌛ **هنوز درآمدی جمع نشده**\n"
    text += (
        f"\n💎 **موجودی جدید:** `{new_bal:,}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💡 **خرید کارگر بیشتر:**\n"
        "`خرید کارگر مقدار [تعداد]`\n\n"
        "⚡ **FLUXBOT**"
    )
    await _send(bot, chat_id, text, reply_to=msg.message_id)
    return True


# ═══════════ 🎡 گردونه ═══════════
async def _spin_wheel(bot, chat_id, sender_id, name, msg, bot_data, save_data):
    ok, rem = _check_cooldown(bot_data, chat_id, str(sender_id), "wheel")
    if not ok:
        await _send(bot, chat_id,
            f"⏰ **هنوز آماده نیست!**\n🎡 گردونه روزانه‌ست.\n"
            f"⌛ **باقی‌مونده:** {_fmt_time(rem)}\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id); return True
    await _send(bot, chat_id,
        "🎡 **گردونه در حال چرخش...** 🎡\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n\n🎯 در حال چرخش...\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    await asyncio.sleep(SLEEP_VERY_FAST)
    weights = [w for w, _ in WHEEL_SEGMENTS]
    prizes = [p for _, p in WHEEL_SEGMENTS]
    prize = random.choices(prizes, weights=weights, k=1)[0]
    emoji = random.choice(WHEEL_EMOJIS)
    bal = get_balance(bot_data, chat_id, sender_id)
    to_bal, to_loan = _credit_win(bot_data, chat_id, sender_id, prize)
    new_bal = bal + to_bal
    set_balance(bot_data, chat_id, sender_id, new_bal)
    _set_cooldown(bot_data, chat_id, str(sender_id), "wheel")
    _safe_save(save_data, bot_data)
    text = (
        f"🎉 **گردونه ایستاد!** 🎉\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n{emoji} **جایزه:** `+{prize:,}`\n"
    )
    if to_loan > 0:
        text += f"\n⚠️ **پرداخت به وام:** `{to_loan:,}`\n"
    text += (
        f"\n💎 **موجودی جدید:** `{new_bal:,}`\n\n"
        "🎁 **دوباره:** ۲۴ ساعت دیگه!\n\n⚡ **FLUXBOT**"
    )
    await _send(bot, chat_id, text, reply_to=msg.message_id)
    return True


# ═══════════ 🎰 اسلات ═══════════
async def _spin_slot(bot, chat_id, sender_id, name, msg, bot_data, save_data):
    ok, rem = _check_cooldown(bot_data, chat_id, str(sender_id), "slot")
    if not ok:
        await _send(bot, chat_id,
            f"⏰ **هنوز آماده نیست!**\n🎰 اسلات روزانه‌ست.\n"
            f"⌛ **باقی‌مونده:** {_fmt_time(rem)}\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id); return True
    await _send(bot, chat_id,
        "🎰 **اسلات در حال چرخش...** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n\n🎰 | ❓ | ❓ | ❓ |\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    await asyncio.sleep(SLEEP_VERY_FAST)
    r1, r2, r3 = (random.choice(SLOT_SYMBOLS) for _ in range(3))
    slot_line = f"🎰 | {r1} | {r2} | {r3} |"
    if r1 == r2 == r3:
        prize = SLOT_JACKPOT
        bal = get_balance(bot_data, chat_id, sender_id)
        to_bal, to_loan = _credit_win(bot_data, chat_id, sender_id, prize)
        new_bal = bal + to_bal
        set_balance(bot_data, chat_id, sender_id, new_bal)
        _set_cooldown(bot_data, chat_id, str(sender_id), "slot")
        _safe_save(save_data, bot_data)
        text = (
            f"🎉 **جکپات!** 🎉\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n\n{slot_line}\n\n"
            f"🏆 **جایزه:** `+{prize:,}`\n"
        )
        if to_loan > 0:
            text += f"\n⚠️ **پرداخت به وام:** `{to_loan:,}`\n"
        text += f"\n💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        await _send(bot, chat_id, text, reply_to=msg.message_id)
    else:
        _set_cooldown(bot_data, chat_id, str(sender_id), "slot")
        _safe_save(save_data, bot_data)
        await _send(bot, chat_id,
            f"🎰 **اسلات ایستاد** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n\n{slot_line}\n\n"
            "😢 **این بار نشد!**\n💡 برای برد: ۳ نماد یکسان\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
    return True


# ═══════════ ⚽ پنالتی ═══════════
async def _play_penalty(bot, chat_id, sender_id, name, msg, direction, amount, bot_data, save_data):
    if amount < MIN_BET:
        await _send(bot, chat_id, f"⚠️ **حداقل `{MIN_BET:,}`!**", reply_to=msg.message_id); return True
    bal = get_balance(bot_data, chat_id, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n💎 `{bal:,}` | نیاز: `{amount:,}`",
            reply_to=msg.message_id); return True
    dir_emoji = {"چپ": "⬅️", "وسط": "⬆️", "راست": "➡️"}.get(direction, "🎯")
    await _send(bot, chat_id,
        f"⚽ **پنالتی** ⚽\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n🎯 **جهت:** {dir_emoji} `{direction}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n🧤 آماده...\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    await asyncio.sleep(SLEEP_FAST)
    keeper = random.choice(["چپ", "وسط", "راست"])
    keeper_emoji = {"چپ": "⬅️", "وسط": "⬆️", "راست": "➡️"}.get(keeper, "🧤")
    won = (direction != keeper)
    if won:
        profit = amount * 2
        to_bal, to_loan = _credit_win(bot_data, chat_id, sender_id, profit)
        new_bal = bal + to_bal
    else:
        profit = -amount
        to_loan = 0
        new_bal = max(MIN_BALANCE, bal - amount)
    set_balance(bot_data, chat_id, sender_id, new_bal)
    _safe_save(save_data, bot_data)
    if won:
        result = (
            f"⚽ **گلللللل!** ⚽\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شوت:** {dir_emoji} `{direction}`\n"
            f"🧤 **دروازه‌بان:** {keeper_emoji} `{keeper}`\n\n"
            f"🎉 **گل!** 📈 **سود:** `+{profit:,}`\n"
        )
        if to_loan > 0:
            result += f"⚠️ **پرداخت به وام:** `{to_loan:,}`\n"
        result += f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
    else:
        result = (
            f"⚽ **دروازه‌بان گرفت!** ⚽\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شوت:** {dir_emoji} `{direction}`\n"
            f"🧤 **دروازه‌بان:** {keeper_emoji} `{keeper}`\n\n"
            f"😢 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


# ═══════════ 🎁 ساخت کد (✅ فیکس‌شده) ═══════════
async def _create_gift(bot, chat_id, sender_id, name, msg, amount, bot_data, save_data):
    if amount < MIN_BET:
        await _send(bot, chat_id, f"⚠️ **حداقل کد هدیه `{MIN_BET:,}`!**", reply_to=msg.message_id); return True
    bal = get_balance(bot_data, chat_id, sender_id)
    spendable = _get_spendable(bal)
    if amount > spendable:
        await _send(bot, chat_id,
            f"❌ **نمی‌تونی اینقدر کد هدیه بسازی!**\n\n"
            f"💵 **در دست:** `{bal:,}`\n"
            f"💎 **کف موجودی:** `{MIN_BALANCE:,}`\n"
            f"✅ **قابل استفاده:** `{spendable:,}`\n\n"
            "📌 کف موجودی باید باقی بمونه.",
            reply_to=msg.message_id); return True
    code = _gen_code(bot_data)
    _ensure_gift_codes(bot_data)
    bot_data["gift_codes"][code] = {
        "creator": str(sender_id), "amount": amount,
        "chat_id": str(chat_id), "created_at": time.time(),
        "used": False, "used_by": None,
    }
    set_balance(bot_data, chat_id, sender_id, bal - amount)
    _safe_save(save_data, bot_data)
    dm_text = (
        "🎁 **کد هدیه شما** 🎁\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 **مبلغ:** `{amount:,}`\n🔑 **کد:** `{code}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📌 **استفاده:** `استفاده کد {code}`\n\n"
        "⚠️ فقط یک بار | برای دوستت بفرست\n\n⚡ **FLUXBOT**"
    )
    ok, info = await _try_pv_send(bot, sender_id, dm_text,
                                   current_chat_id=chat_id, bot_data=bot_data, save_data=save_data)
    if ok:
        await _send(bot, chat_id,
            "✅ **کد هدیه ساخته شد!**\n\n"
            f"💰 **مبلغ:** `{amount:,}`\n📩 **کد به پیوی ارسال شد.**\n\n⚡ **FLUXBOT**",
            reply_to=msg.message_id)
        return True
    fallback = (
        "⚠️ **پیوی ربات بسته‌ست!**\n\n"
        "📌 کد اینجا نشون داده می‌شه:\n⏱️ **۲ دقیقه — سریع سیو کن!**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 **کد:** `{code}`\n💰 **مبلغ:** `{amount:,}`\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 **استفاده:** `استفاده کد {code}`\n\n"
        "💡 **برای فعال کردن PV:**\n"
        "├ به پیوی ربات برو\n├ `/start` رو بزن\n"
        "└ **داخل پیوی** بنویس `تست پیوی`\n\n⚡ **FLUXBOT**"
    )
    result = await _send(bot, chat_id, fallback, reply_to=msg.message_id)
    mid = _extract_msg_id(result)
    if mid:
        try: asyncio.create_task(_auto_delete(bot, chat_id, mid, 120))
        except: pass
    return True


# ═══════════ 🎁 استفاده کد ═══════════
async def _use_gift(bot, chat_id, sender_id, msg, code, bot_data, save_data):
    _ensure_gift_codes(bot_data)
    gift = bot_data["gift_codes"].get(code)
    if not gift:
        await _send(bot, chat_id, "❌ **کد نامعتبره!**", reply_to=msg.message_id); return True
    if gift.get("used"):
        await _send(bot, chat_id, "❌ **این کد قبلاً استفاده شده!**", reply_to=msg.message_id); return True
    if str(gift.get("creator")) == str(sender_id):
        await _send(bot, chat_id, "❌ **نمی‌تونی از کد خودت استفاده کنی!**", reply_to=msg.message_id); return True
    amount = int(gift.get("amount", 0))
    if amount <= 0:
        await _send(bot, chat_id, "❌ **کد معتبر نیست!**", reply_to=msg.message_id); return True
    bal = get_balance(bot_data, chat_id, sender_id)
    to_bal, to_loan = _credit_win(bot_data, chat_id, sender_id, amount)
    new_bal = bal + to_bal
    set_balance(bot_data, chat_id, sender_id, new_bal)
    gift["used"] = True
    gift["used_by"] = str(sender_id)
    gift["used_at"] = time.time()
    gift["used_in_chat"] = str(chat_id)
    _safe_save(save_data, bot_data)
    text = (
        f"🎉 **کد دریافت شد!** 🎉\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 **کد:** `{code}`\n💰 **مبلغ:** `+{amount:,}`\n"
    )
    if to_loan > 0:
        text += f"\n⚠️ **پرداخت به وام:** `{to_loan:,}`\n"
    text += f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
    await _send(bot, chat_id, text, reply_to=msg.message_id)
    return True


# ═══════════ 🎁 ارسال هدیه (✅ فیکس‌شده) ═══════════
async def _send_gift(bot, chat_id, sender_id, name, msg, receiver, amount, bot_data, save_data):
    if not receiver:
        await _send(bot, chat_id, "❌ **شناسه نامعتبره!**", reply_to=msg.message_id); return True
    if receiver == str(sender_id):
        await _send(bot, chat_id, "❌ **نمی‌تونی به خودت هدیه بدی!**", reply_to=msg.message_id); return True
    if amount < MIN_BET:
        await _send(bot, chat_id, f"⚠️ **حداقل `{MIN_BET:,}`!**", reply_to=msg.message_id); return True
    bal = get_balance(bot_data, chat_id, sender_id)
    spendable = _get_spendable(bal)
    if amount > spendable:
        await _send(bot, chat_id,
            f"❌ **نمی‌تونی اینقدر هدیه بدی!**\n\n"
            f"💵 **در دست:** `{bal:,}`\n"
            f"💎 **کف موجودی:** `{MIN_BALANCE:,}`\n"
            f"✅ **قابل ارسال:** `{spendable:,}`\n\n"
            "📌 کف موجودی باید باقی بمونه.",
            reply_to=msg.message_id); return True
    new_sender = bal - amount
    rcv_bal = get_balance(bot_data, chat_id, receiver)
    to_bal, to_loan = _credit_win(bot_data, chat_id, receiver, amount)
    new_receiver = rcv_bal + to_bal
    set_balance(bot_data, chat_id, sender_id, new_sender)
    set_balance(bot_data, chat_id, receiver, new_receiver)
    _safe_save(save_data, bot_data)
    await _send(bot, chat_id,
        f"🎁 **هدیه ارسال شد!** 🎁\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **از:** {name}\n🎯 **به:** `{receiver}`\n"
        f"💰 **مبلغ:** `{amount:,}`\n\n"
        f"💎 **موجودی جدید تو:** `{new_sender:,}`\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    return True


# ═══════════ 👑 افزایش موجودی ═══════════
async def _boost_balance(bot, chat_id, sender_id, name, msg, amount, bot_data, save_data):
    if amount <= 0:
        await _send(bot, chat_id, "⚠️ مبلغ باید مثبت باشه.", reply_to=msg.message_id); return True
    bal = get_balance(bot_data, chat_id, sender_id)
    new_bal = bal + amount
    set_balance(bot_data, chat_id, sender_id, new_bal)
    _safe_save(save_data, bot_data)
    await _send(bot, chat_id,
        f"👑 **افزایش موجودی (ویژه)** 👑\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **کاربر:** {name}\n💰 **افزایش:** `+{amount:,}`\n"
        f"💎 **موجودی جدید:** `{new_bal:,}`\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    return True


# ═══════════ 🎲 شرط عمومی ═══════════
async def _play_bet(bot, chat_id, sender_id, name, msg, guess_raw, amount, bot_data, save_data):
    if amount < MIN_BET:
        await _send(bot, chat_id, f"⚠️ **حداقل `{MIN_BET:,}`!**", reply_to=msg.message_id); return True
    if guess_raw in ("شیر", "خط"):
        return await _play_coinflip(bot, chat_id, sender_id, name, msg, guess_raw, amount, bot_data, save_data)
    if guess_raw in ("زوج", "فرد"):
        return await _play_dice_evenodd(bot, chat_id, sender_id, name, msg, guess_raw, amount, bot_data, save_data)
    try: gn = int(guess_raw)
    except ValueError:
        await _send(bot, chat_id, "⚠️ **نوع شرط نامعتبره!**", reply_to=msg.message_id); return True
    if gn < 1 or gn > 6:
        await _send(bot, chat_id, "⚠️ **عدد ۱ تا ۶!**", reply_to=msg.message_id); return True
    return await _play_dice_number(bot, chat_id, sender_id, name, msg, gn, amount, bot_data, save_data)


async def _play_dice_number(bot, chat_id, sender_id, name, msg, guess, amount, bot_data, save_data):
    bal = get_balance(bot_data, chat_id, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n💎 `{bal:,}` | نیاز: `{amount:,}`",
            reply_to=msg.message_id); return True
    await _send(bot, chat_id,
        f"🎲 **تاس عددی** 🎲\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n🎯 **شرط:** عدد `{guess}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n🎲 در حال پرتاب...\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    await asyncio.sleep(SLEEP_FAST)
    dice = random.randint(1, 6)
    dice_emoji = DICE_EMOJIS.get(dice, "🎲")
    won = (guess == dice)
    if won:
        profit = amount * 3
        to_bal, to_loan = _credit_win(bot_data, chat_id, sender_id, profit)
        new_bal = bal + to_bal
    else:
        profit = -amount
        to_loan = 0
        new_bal = max(MIN_BALANCE, bal - amount)
    set_balance(bot_data, chat_id, sender_id, new_bal)
    _safe_save(save_data, bot_data)
    if won:
        result = (
            f"🎰 **نتیجه** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** عدد `{guess}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}**\n\n"
            f"🎉 **بردی!** 📈 **سود:** `+{profit:,}`\n"
        )
        if to_loan > 0:
            result += f"⚠️ **پرداخت به وام:** `{to_loan:,}`\n"
        result += f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
    else:
        result = (
            f"🎰 **نتیجه** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** عدد `{guess}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}**\n\n"
            f"😢 **باختی!** 📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


async def _play_dice_evenodd(bot, chat_id, sender_id, name, msg, choice, amount, bot_data, save_data):
    bal = get_balance(bot_data, chat_id, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n💎 `{bal:,}` | نیاز: `{amount:,}`",
            reply_to=msg.message_id); return True
    await _send(bot, chat_id,
        f"🎲 **تاس زوج/فرد** 🎲\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n🎲 در حال پرتاب...\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    await asyncio.sleep(SLEEP_FAST)
    dice = random.randint(1, 6)
    dice_emoji = DICE_EMOJIS.get(dice, "🎲")
    is_even = (dice % 2 == 0)
    won = (choice == "زوج" and is_even) or (choice == "فرد" and not is_even)
    if won:
        profit = amount * 2
        to_bal, to_loan = _credit_win(bot_data, chat_id, sender_id, profit)
        new_bal = bal + to_bal
    else:
        profit = -amount
        to_loan = 0
        new_bal = max(MIN_BALANCE, bal - amount)
    set_balance(bot_data, chat_id, sender_id, new_bal)
    _safe_save(save_data, bot_data)
    parity = "زوج" if is_even else "فرد"
    if won:
        result = (
            f"🎰 **نتیجه** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}** ({parity})\n\n"
            f"🎉 **بردی!** 📈 **سود:** `+{profit:,}`\n"
        )
        if to_loan > 0:
            result += f"⚠️ **پرداخت به وام:** `{to_loan:,}`\n"
        result += f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
    else:
        result = (
            f"🎰 **نتیجه** 🎰\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🎲 **تاس:** {dice_emoji} **{dice}** ({parity})\n\n"
            f"😢 **باختی!** 📉 **باخت:** `-{amount:,}`\n"
            f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
        )
    await _send(bot, chat_id, result, reply_to=msg.message_id)
    return True


async def _play_coinflip(bot, chat_id, sender_id, name, msg, choice, amount, bot_data, save_data):
    bal = get_balance(bot_data, chat_id, sender_id)
    if bal < amount:
        await _send(bot, chat_id,
            f"❌ **موجودی کافی نداری!**\n💎 `{bal:,}` | نیاز: `{amount:,}`",
            reply_to=msg.message_id); return True
    await _send(bot, chat_id,
        f"🪙 **شیر یا خط** 🪙\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
        f"💰 **مقدار:** `{amount:,}`\n\n🪙 در حال پرتاب...\n\n⚡ **FLUXBOT**",
        reply_to=msg.message_id)
    await asyncio.sleep(SLEEP_FAST)
    result_side = random.choice(["شیر", "خط"])
    won = (choice == result_side)
    if won:
        profit = amount // 2
        to_bal, to_loan = _credit_win(bot_data, chat_id, sender_id, profit)
        new_bal = bal + to_bal
    else:
        profit = -amount
        to_loan = 0
        new_bal = max(MIN_BALANCE, bal - amount)
    set_balance(bot_data, chat_id, sender_id, new_bal)
    _safe_save(save_data, bot_data)
    emoji = "🦁" if result_side == "شیر" else "📝"
    if won:
        result = (
            f"🪙 **نتیجه** 🪙\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🪙 **نتیجه:** {emoji} **{result_side}**\n\n"
            f"🎉 **بردی!** 📈 **سود:** `+{profit:,}`\n"
        )
        if to_loan > 0:
            result += f"⚠️ **پرداخت به وام:** `{to_loan:,}`\n"
        result += f"💎 **موجودی:** `{new_bal:,}`\n\n⚡ **FLUXBOT**"
    else:
        result = (
            f"🪙 **نتیجه** 🪙\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **بازیکن:** {name}\n🎯 **شرط:** `{choice}`\n"
            f"💰 **مقدار:** `{amount:,}`\n\n"
            f"🪙 **نتیجه:** {emoji} **{result_side}**\n\n"
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
        f"💎 **موجودی تو:** `{bal:,}`\n"
        f"📌 کف: `{MIN_BALANCE:,}` | حداقل شرط: `{MIN_BET:,}`\n"
        f"🎯 **هر گروه موجودی جدا داره!**\n\n"
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
        "`گردونه` → **۱۰۰K تا ۵۰۰K**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎰 **۶. اسلات (روزانه)**\n"
        "`اسلات ماشین` → ۳ نماد = **۱M**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🏦 **۷. بانک**\n"
        "├ `واریز در بانک مقدار [عدد]`\n"
        "├ `برداشت از بانک مقدار [عدد]`\n"
        "└ `بانک` → نمایش موجودی بانک\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💰 **۸. وام**\n"
        f"├ `گرفتن وام مقدار [عدد]` ({LOAN_MIN:,} تا {LOAN_MAX:,})\n"
        "├ `وام` → نمایش وام‌ها\n"
        "├ `پرداخت وام مقدار [عدد]`\n"
        "└ `پرداخت وام` → تسویه کامل\n\n"
        f"⏰ **مهلت:** {LOAN_DAYS} روز\n"
        "⚠️ **اگه پرداخت نشه:**\n"
        "├ 🚫 همه بردها به وام می‌ره\n"
        "└ 💎 تا تسویه، به موجودیت اضافه نمی‌شه\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⛏️ **۹. استخراج**\n"
        f"├ `خرید کارگر مقدار [تعداد]`\n"
        f"│  (هر کارگر `{WORKER_PRICE:,}`)\n"
        "└ `کارگر` → نمایش + جمع‌آوری درآمد\n\n"
        f"💰 **درآمد هر کارگر:** `{WORKER_INCOME_PER_HOUR:,}` در ساعت\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎁 **۱۰. کد هدیه**\n"
        "├ `ساخت کد هدیه مقدار [عدد]`\n"
        "└ `استفاده کد ABC123`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎁 **۱۱. ارسال هدیه**\n"
        "`ارسال هدیه [شناسه] مقدار 5000`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💰 **دستورات دیگه:**\n"
        "├ `موجودی` → موجودی این گروه\n"
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
