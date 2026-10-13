import os
import re
import json
import time
import asyncio
import random
import traceback
from datetime import datetime, timedelta, timezone
from rubka import Robot, Message
from rubka.keypad import ChatKeypadBuilder

# ═══════ لود خودکار بازی‌های ماژولار ═══════
import importlib, os as _os
MODULAR_GAMES = []
_games_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "games")
if _os.path.isdir(_games_dir):
    for _f in sorted(_os.listdir(_games_dir)):
        if _f.endswith(".py") and not _f.startswith("__"):
            _name = _f[:-3]
            try:
                _mod = importlib.import_module(f"games.{_name}")
                if hasattr(_mod, "handle"):
                    MODULAR_GAMES.append(_mod)
                    print(f"✅ بازی {_name} لود شد", flush=True)
            except Exception as e:
                print(f"⚠️ بازی {_name}: {e}", flush=True)

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

OWNER_ID = "u0KUJo1004f46bafc48e536f282693b6"
BOT_ID_CACHE = {"id": None}

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))
def get_local_now():
    return datetime.now(IRAN_TZ)

DATA_PATHS = ["/data/bot_data.json", "/app/data/bot_data.json", "/app/bot_data.json", "/tmp/bot_data.json", "./bot_data.json"]
CACHE_PATHS = ["/data/message_cache.json", "/app/data/message_cache.json", "/app/message_cache.json", "/tmp/message_cache.json", "./message_cache.json"]

for _p in ["/data", "/app/data", "/tmp"]:
    try: os.makedirs(_p, exist_ok=True)
    except: pass


# ═══════════════════════════════════════════════════════════════════
# 🧰 ذخیره‌سازی امن داده‌ها و مقداردهی اولیهٔ runtime
# این بخش به کد موجود اضافه شده تا تنظیمات قفل‌ها پس از راه‌اندازی حفظ شوند.
# ═══════════════════════════════════════════════════════════════════
def _read_json_from_paths(paths, default):
    for _path in paths:
        try:
            if not os.path.isfile(_path):
                continue
            with open(_path, "r", encoding="utf-8") as _file:
                _value = json.load(_file)
            if isinstance(default, dict) and isinstance(_value, dict):
                return _value
            if isinstance(default, list) and isinstance(_value, list):
                return _value
        except Exception as _err:
            print(f"⚠️ JSON read {_path}: {_err}", flush=True)
    return default.copy() if isinstance(default, (dict, list)) else default


def _write_json_to_paths(paths, value):
    _last_error = None
    for _path in paths:
        _tmp_path = None
        try:
            _directory = os.path.dirname(_path) or "."
            os.makedirs(_directory, exist_ok=True)
            _tmp_path = _path + ".tmp"
            with open(_tmp_path, "w", encoding="utf-8") as _file:
                json.dump(value, _file, ensure_ascii=False, indent=2)
                _file.flush()
                try:
                    os.fsync(_file.fileno())
                except Exception:
                    pass
            os.replace(_tmp_path, _path)
            return True
        except Exception as _err:
            _last_error = _err
            if _tmp_path:
                try:
                    if os.path.exists(_tmp_path):
                        os.remove(_tmp_path)
                except Exception:
                    pass
    if _last_error:
        print(f"⚠️ JSON write: {_last_error}", flush=True)
    return False


def save_data(data=None, force=False):
    try:
        _payload = data if isinstance(data, dict) else bot_data
        return _write_json_to_paths(DATA_PATHS, _payload)
    except Exception as _err:
        print(f"⚠️ save_data: {_err}", flush=True)
        return False


def load_cache():
    _value = _read_json_from_paths(CACHE_PATHS, {})
    return _value if isinstance(_value, dict) else {}


def save_cache(cache=None, force=False):
    try:
        _payload = cache if isinstance(cache, dict) else message_cache
        return _write_json_to_paths(CACHE_PATHS, _payload)
    except Exception as _err:
        print(f"⚠️ save_cache: {_err}", flush=True)
        return False


_DEFAULT_SETTINGS = {
    "link": False,
    "id": False,
    "spam": True,
    "hyperlink": False,
    "welcome": True,
    "goodbye": True,
    "profanity": True,
    "forward": False,
    "gif": False,
    "warning": True,
    "filter": True,
    "emoji": False,
    "sticker": False,
    "number": False,
    "english": False,
    "forbidden_words": False,
    "edit": False,
    "betting_enabled": True,
    "auto_ban": True,
}

_DEFAULT_DATA_SHAPES = {
    "settings": {}, "started_users": [], "known_groups": [], "known_users": {},
    "group_locks": {}, "temp_locks": {}, "scheduled_locks": {},
    "special_users": {}, "warnings": {}, "warn_limit": {}, "warn_delete_after": {},
    "banned_users": {}, "mute_list": {}, "filtered_words": {}, "rules": {},
    "custom_welcome": {}, "welcomed_users": {}, "talkative_disabled": [],
    "anti_repeat": {}, "slow_mode": {}, "games": {}, "invite_codes": {},
    "code_to_user": {}, "invited_users": {}, "points": {}, "user_titles": {},
    "taken_asl": {}, "taken_laghab": {}, "join_dates": {}, "message_counts": {},
    "group_message_count": {}, "bot_is_active": False,
}

bot_data = _read_json_from_paths(DATA_PATHS, {})
if not isinstance(bot_data, dict):
    bot_data = {}
for _data_key, _data_default in _DEFAULT_DATA_SHAPES.items():
    if _data_key not in bot_data or not isinstance(bot_data.get(_data_key), type(_data_default)):
        bot_data[_data_key] = _data_default.copy() if isinstance(_data_default, (dict, list)) else _data_default
settings = bot_data["settings"]
for _setting_key, _setting_default in _DEFAULT_SETTINGS.items():
    settings.setdefault(_setting_key, _setting_default)
bot_data["settings"] = settings
bot_is_active = bool(bot_data.get("bot_is_active", False))
message_cache = load_cache()
try:
    save_data(bot_data, force=True)
except Exception as _err:
    print(f"⚠️ initialize data: {_err}", flush=True)


async def get_chat_name(chat_id):
    try:
        _info = await bot.get_chat_info(chat_id)
        for _ in range(4):
            if isinstance(_info, dict) and isinstance(_info.get("data"), dict):
                _info = _info["data"]
            else:
                break
        if isinstance(_info, dict):
            _chat = _info.get("chat", _info)
            if isinstance(_chat, dict):
                for _key in ("title", "name", "chat_name", "group_name"):
                    if _chat.get(_key):
                        return str(_chat[_key])
    except Exception as _err:
        print(f"⚠️ get_chat_name: {_err}", flush=True)
    return "گروه"


async def get_group_list_text():
    return await get_groups_text()


def get_features_text():
    return (
        "📖 **قابلیت‌های FLUXBOT**\n━━━━━━━━━━━━━━━━━━━\n\n"
        "🔒 **قفل‌های گروه:**\n"
        "├ `لینک قفل` / `لینک باز`\n"
        "├ `آیدی قفل` / `آیدی باز`\n"
        "├ `اسپم قفل` / `اسپم باز`\n"
        "├ `هایپرلینک قفل` / `هایپرلینک باز`\n"
        "├ `فحش قفل` / `فحش باز`\n"
        "├ `فوروارد قفل` / `فوروارد باز`\n"
        "├ `گیف قفل` / `گیف باز`\n"
        "├ `ایموجی قفل` / `ایموجی باز`\n"
        "├ `استیکر قفل` / `استیکر باز`\n"
        "├ `عدد قفل` / `عدد باز`\n"
        "├ `انگلیسی قفل` / `انگلیسی باز`\n"
        "├ `کلمات غیرمجاز قفل` / `کلمات غیرمجاز باز`\n"
        "├ `بیوچک قفل` / `بیوچک باز`\n"
        "└ `ویرایش قفل` / `ویرایش باز`\n\n"
        "⚠️ در صورت فعال بودن اخطار، تخلف‌ها با اخطار و اشارهٔ قابل‌کلیک به کاربر همراه می‌شوند.\n\n"
        "⚡ **FLUXBOT**"
    )


def get_games_list_text():
    _lines = ["🎮 **فهرست بازی‌ها**", "━━━━━━━━━━━━━━━━━━━"]
    _lines.extend(["🎲 دوز", "🪙 شیر یا خط", "🔴 چهار در خط", "🎯 چالش"])
    for _game_module in MODULAR_GAMES:
        try:
            _title = getattr(_game_module, "TITLE", None) or getattr(_game_module, "name", None)
            if _title:
                _lines.append(f"🎮 {str(_title)}")
        except Exception:
            pass
    _lines.append("\n⚡ **FLUXBOT**")
    return "\n".join(_lines)


async def cleanup_task():
    while True:
        try:
            _now = time.time()
            for _key, _expiry in list(username_cache_ttl.items()):
                if _expiry <= _now:
                    username_cache_ttl.pop(_key, None)
                    username_cache.pop(_key, None)
            if len(processed_messages) > 10000:
                for _key in list(processed_messages)[:len(processed_messages) - 7000]:
                    processed_messages.pop(_key, None)
        except Exception as _err:
            print(f"⚠️ cleanup_task: {_err}", flush=True)
        await asyncio.sleep(180)


async def group_cleanup_task():
    while True:
        try:
            _now = time.time()
            for _key, _expiry in list(group_info_cache_ttl.items()):
                if _expiry <= _now:
                    group_info_cache_ttl.pop(_key, None)
                    group_info_cache.pop(_key, None)
        except Exception as _err:
            print(f"⚠️ group_cleanup_task: {_err}", flush=True)
        await asyncio.sleep(600)

BTN_CHANNEL = "📢 کانال رسمی"
BTN_HELP = "📚 آموزش فعال‌سازی"
BTN_USERS = "👥 کاربران"
BTN_GROUPS = "🏠 گروه‌های فعال"
BTN_DEV = "👑 سازنده ربات"
BTN_INVITE_ENTER = "🎟️ زدن کد دعوت"
BTN_INVITE_SHOW = "🎫 کد دعوت من"
BTN_POINTS = "⭐ امتیاز من"
BTN_FEATURES = "📖 قابلیت‌های ربات"
BTN_TOP_INVITERS = "🏆 لیست برتر دعوت‌کنندگان"
MAX_FILTER_WORDS = 50

CHANNEL_USERNAME = "@RPCITY_PHANTOM"
GAME_TIMEOUT = 120
SPAM_WINDOW = 5
SPAM_LIMIT = 5

username_cache = {}
username_cache_ttl = {}
spam_tracker = {}
processed_messages = {}
waiting_for_code = {}
group_info_cache = {}
group_info_cache_ttl = {}
save_counter = {"data": 0, "cache": 0}

repeat_tracker = {}
slow_tracker = {}
coin_flip_games = {}

EMPTY = "⚫"
RED = "🔴"
YELLOW = "🟡"
USER_MENTION_TOKEN = "\ue000USER\ue001"


# ================== 🔧 ZWNJ + Punctuation Helper ==================
def _strip_zwnj(s):
    """حذف ZWNJ/ZWJ + علائم نگارشی + lowercase + strip"""
    if not s: return ""
    s = s.replace('\u200c', '').replace('\u200d', '').lower().strip()
    s = s.strip('!.?؟،,؛;:«»"\'()[]{}<>-—–…*_~')
    return s


# ================== 🔄 Two-Word Command Matcher ==================
# 🔒 قفل پیام‌ها (لینک، آیدی، فحش، اسپم، فوروارد، گیف، هایپرلینک)
#   "X قفل" / "X بسته" / "X فعال" / "X روشن" → فعال (پیام پاک می‌شه)
#   "X باز" / "X خاموش" / "X غیرفعال"       → غیرفعال (پیام پاک نمی‌شه)
FILTER_ON = {_strip_zwnj(w) for w in {
    "فعال", "روشن", "قفل", "بسته", "بستن", "ببند",
    "فعال‌کن", "روشن‌کن", "قفلش",
    "on", "enable",
}}
FILTER_OFF = {_strip_zwnj(w) for w in {
    "غیرفعال", "خاموش", "باز", "بازکردن", "بازکن", "بازش",
    "خاموش‌کن", "غیرفعال‌کن",
    "off", "disable",
}}

# 🎰 فیچرها (سخنگو، شرط بندی، welcome، goodbye)
FEATURE_ON = {_strip_zwnj(w) for w in {
    "فعال", "روشن", "باز", "بازکردن", "بازکن", "بازش",
    "فعال‌کن", "روشن‌کن",
    "on", "enable",
}}
FEATURE_OFF = {_strip_zwnj(w) for w in {
    "غیرفعال", "خاموش", "بسته", "بستن", "ببند", "قفل", "قفلش",
    "خاموش‌کن", "غیرفعال‌کن",
    "off", "disable",
}}

ON_WORDS = FILTER_ON
OFF_WORDS = FILTER_OFF


def match_two_word_cmd(text, word, on_words=None, off_words=None):
    """دستور دوکلمه‌ای انعطاف‌پذیر — ترتیب هر طرف، ZWNJ، علائم نگارشی"""
    if not text:
        return None
    if on_words is None:  on_words = ON_WORDS
    if off_words is None: off_words = OFF_WORDS
    t_norm = text.replace('\u200c', ' ').replace('\u200d', ' ')
    parts = [_strip_zwnj(p) for p in t_norm.strip().split() if p.strip()]
    parts = [p for p in parts if p]
    w_parts = [_strip_zwnj(p) for p in word.replace('\u200c', ' ')
                                              .replace('\u200d', ' ')
                                              .split() if p.strip()]
    w_parts = [p for p in w_parts if p]
    if not w_parts or not parts:
        return None
    n = len(w_parts)
    for start in range(len(parts) - n + 1):
        if parts[start:start + n] != w_parts:
            continue
        rest = parts[:start] + parts[start + n:]
        rest = [r for r in rest if r]
        if len(rest) == 1:
            if rest[0] in on_words:  return True
            if rest[0] in off_words: return False
        elif len(rest) == 2:
            joined = rest[0] + rest[1]
            if joined in on_words:  return True
            if joined in off_words: return False
    return None


def _check_betting_lock(text):
    """پشتیبان شرط بندی"""
    if not text:
        return None
    t_norm = text.replace('\u200c', ' ').replace('\u200d', ' ')
    parts = [_strip_zwnj(p) for p in t_norm.strip().split() if p.strip()]
    parts = [p for p in parts if p]

    for i, p in enumerate(parts):
        if p == "شرطبندی":
            rest = [r for r in (parts[:i] + parts[i+1:]) if r]
            if len(rest) == 1:
                if rest[0] in FEATURE_ON:  return True
                if rest[0] in FEATURE_OFF: return False
            elif len(rest) == 2:
                j = rest[0] + rest[1]
                if j in FEATURE_ON:  return True
                if j in FEATURE_OFF: return False

    for i in range(len(parts) - 1):
        if parts[i] == "شرط" and parts[i+1] == "بندی":
            rest = [r for r in (parts[:i] + parts[i+2:]) if r]
            if len(rest) == 1:
                if rest[0] in FEATURE_ON:  return True
                if rest[0] in FEATURE_OFF: return False
            elif len(rest) == 2:
                j = rest[0] + rest[1]
                if j in FEATURE_ON:  return True
                if j in FEATURE_OFF: return False
    return None


# ================== 💬 TALKATIVE ==================
TALKATIVE_MAP = {
    ("ربات فلکس بات", "ربات فلاکس بات", "ربات فلوکس بات",
     "فلکس بات", "فلاکس بات", "فلوکس بات", "فلکسی بات",
     "ربات فلکس", "ربات فلاکس", "ربات فلوکس",
     "flux bot", "flaks bot", "falaks bot"): [
        "بله جانم؟ 🌷", "جانم عزیزم 💕", "در خدمتم 💐", "چیزی لازم داری؟ 🤝", "بفرمایید 🌸",
    ],
    ("ربات", "بات", "روبات", "bot", "robot"): [
        "جانم؟ 🥰", "بله؟ 🤗", "چی شد؟ 😊", "در خدمتم 🌹", "بله بنده؟ 🙋",
    ],
    ("فلکس", "فلاکس", "فلوکس", "فلکسی", "flux", "flaks", "falaks", "flox"): [
        "جانم عزیزم 💖", "بله؟ 🤗", "چی شد؟ 🌹", "بفرما 🌺", "چاکرم 🎩",
    ],
    ("سلام", "سلوم", "سلم", "salam"): [
        "سلام بر تو 🌸", "علیک سلام 🌹", "سلام عزیز دل 🌹", "سلام گلم 🌺", "سلام جانم 💖",
    ],
    ("درود", "درود بر تو", "درود بر شما"): [
        "درود بر تو 🌟", "درود بر تو ای عزیز 🌹", "درود ای رفیق 🤝", "سلام و درود 💐", "درود بر تو ای گران‌قدر 💎",
    ],
    ("خوبی", "حالت چطوره", "حالت خوبه", "خوب هستی", "چطوری", "چطورید", "چطور هستی"): [
        "خوبم مرسی 💚", "خوبم تو چطوری؟ 😊", "خوبم سلامتی؟ 🌿", "خوبم ممنون 🙏", "خوبم عزیز 🌹",
    ],
    ("چه خبر", "چخبر", "چی خبر", "خبری هست"): [
        "خبری نیست 📰", "سلامتی 📻", "خبری نداری؟ 📢", "خب تو بگو 🗣️", "همه چیز خوب 💚",
    ],
    ("ممنون", "مرسی", "سپاس", "دستت درد نکنه"): [
        "خواهش می‌کنم 🙏", "قابلی نداشت 😊", "کاری نکردم 💚", "سلامت باشی 🌿", "خواهش 🌹",
    ],
    ("خداحافظ", "خدانگهدار", "بدرود", "بای", "بای بای", "bye", "خدا نگهدار"): [
        "خداحافظ 👋", "به سلامت 🚶", "خدانگهدار 🙏", "مواظب خودت باش 💚", "بدرود 🌹",
    ],
    ("شب بخیر", "شبت بخیر", "خواب خوب"): [
        "شب تو هم بخیر 🌙", "خواب خوب ببینی 💤", "شب بخیر عزیز 🌹", "خوابای شیرین 💫", "شب آروم 🌙",
    ],
    ("صبح بخیر", "صبحت بخیر", "روز بخیر"): [
        "صبح تو هم بخیر ☀️", "روز خوبی داشته باشی 🌸", "صبح بخیر عزیز 🌹", "صبح قشنگ ☀️", "صبح زیبا 🌞",
    ],
    ("دوستت دارم", "دوسِت دارم", "عاشقتم", "عاشقت هستم", "دوست دارم"): [
        "منم دوستت دارم 💖", "منم 💕", "قربونت برم 💗", "دوست منی 💚", "عاشقتم 💝",
    ],
    ("بوس", "بوسه", "بوسم کن", "بوسم"): [
        "بوس بفرست 😘", "بغل 🤗", "قربونت 💗", "بیا بغل 🤗", "منم بوس 🌹",
    ],
    ("عزیزم", "جانم", "جونم", "دلبرم"): [
        "جانم عزیزم 💖", "بله گلم 🌹", "چی می‌خوای عزیزم؟ 🌸", "جونم بگو 💕", "در خدمتم جانم 🌷",
    ],
    ("قربونت", "فدات", "قربون", "فدای تو"): [
        "منم قربونت 💗", "فدای تو هم بشم 🌹", "قربون تو هم 💖", "نوکرتم 🎩", "چاکرم 💐",
    ],
    ("کی هستی", "تو کی هستی", "تو چی هستی", "خودت رو معرفی کن"): [
        "من ربات فلکس باتم 🤖", "من یه رباتم 🤖", "ربات سرگرمی 💫", "فلکس بات هستم 🌟", "ربات شما 🤖",
    ],
    ("اسمت چیه", "نامت چیه", "اسم تو چیه"): [
        "فلکس بات 🌟", "اسمم فلکس بات 🤖", "فلکس بات 💫", "من فلکس باتم 🌹", "فلکس بات عزیز 💚",
    ],
    ("چند سالته", "چند سالت", "سنت چقدره", "چند سال داری"): [
        "من تازه متولد شدم 👶", "معلوم نیست 😅", "کوچیکم 🍼", "سن ندارم 🤖", "تازه کارم 🌱",
    ],
    ("چیکار می‌کنی", "چکار می‌کنی", "مشغول چی هستی"): [
        "دارم بهت جواب می‌دم 😄", "مشغول توام 💚", "کاری نمی‌کنم 😊", "منتظرتم ✨", "گوش به زنگ 🎧",
    ],
    ("کجایی", "کجا هستی", "کجا هستی الان"): [
        "من همه جا هستم 💫", "پیشتم 🥰", "تو گوشیت 😄", "اینجام 🤗", "همیشه کنارتم 💚",
    ],
    ("خوشحالم", "خوشحال هستم", "شادم", "شاد هستم"): [
        "چه خوب 🎉", "منم خوشحالم 💚", "خوشحالیت خوشحالم می‌کنه 😊", "آفرین 🎊", "همیشه شاد باش ✨",
    ],
    ("ناراحتم", "غمگینم", "دلم گرفته", "دلم تنگه"): [
        "چی شده عزیز؟ 🥺", "ناراحت نباش 💚", "دل منم برات 💗", "بگو چی شده 🌹", "آروم باش 💐",
    ],
    ("عصبانی‌ام", "عصبانی هستم", "اعصابم خرده", "اعصابم خورده"): [
        "آروم باش عزیز 😌", "چی شده؟ 🤔", "عصبانی نباش 💚", "یه نفس عمیق 🌬️", "بگو تا آروم شی 🌹",
    ],
    ("خسته‌ام", "خسته هستم", "خستم", "خسته شدم"): [
        "خسته نباشی 💪", "استراحت کن 🛋️", "زحمت کشیدی 🌹", "خدا قوت 💚", "یه استراحت بکن 🌙",
    ],
    ("گرسنمه", "گرسنه‌ام", "گشنمه", "گرسنه هستم"): [
        "برو غذا بخور 🍕", "چی می‌خوری؟ 🍔", "منم گشنمه 🍽️", "یه چیزی بخور 🥪", "غذای خوب بخور 🍲",
    ],
    ("تشنمه", "تشنه هستم", "تشنه‌ام"): [
        "آب بخور 💧", "شربت بخور 🥤", "چایی می‌خوری؟ 🍵", "آبمیوه بخور 🧃", "نوشیدنی بخور 🥛",
    ],
    ("خوابم میاد", "خواب‌آلوده", "خسته و خواب‌آلود"): [
        "برو بخواب 😴", "خواب خوب ببینی 💤", "شب بخیر 🌙", "استراحت کن 🛏️", "خواب قشنگ ببینی 💫",
    ],
    ("آفرین", "احسنت", "مرحبا", "ایول", "ایول داری"): [
        "مرسی 🌹", "لطف داری 💚", "قابلی نداشت 😊", "ممنون 🙏", "خواهش می‌کنم 💐",
    ],
    ("بارک الله", "بارک‌الله", "ماشالله", "ماشاءالله"): [
        "الهی شکر 🙏", "ممنون 💚", "لطف داری 🌹", "خدا برکت بده ✨", "آفرین 👏",
    ],
    ("قشنگه", "قشنگ", "زیبا", "زیباست"): [
        "ممنون 🌸", "لطف داری 💐", "چشمای تو قشنگه 😍", "مرسی عزیز 🌹", "لطف شماست 💕",
    ],
    ("باحال", "باحاله", "خفن", "خفنه", "عالیه"): [
        "مرسی 🎉", "لطف داری 😎", "قابلی نداشت 💚", "خواهش می‌کنم 🌟", "ممنون 🔥",
    ],
    ("کمکم کن", "کمک کن", "کمکی", "کمک می‌خوام"): [
        "چطور کمکت کنم؟ 💪", "در خدمتم 🤝", "بگو چیکار کنم ⚡", "امر کن 👑", "چی لازم داری؟ 🎯",
    ],
    ("بیکارم", "بیکار هستم", "حوصله ندارم", "حوصلم سر رفته"): [
        "بیا حرف بزنیم 🗣️", "بریم بازی کنیم 🎮", "بیا شوخی کنیم 😄", "چی می‌خوای بگی؟ 💬", "بیا سرگرمت کنم 🎉",
    ],
    ("مشغولم", "کار دارم", "وقت ندارم", "سرم شلوغه"): [
        "اوکی، بعداً 🌹", "موفق باشی 💚", "کارت رو بکن 👍", "منتظرتم ⏰", "بعد بیا حرف بزنیم 💐",
    ],
    ("تنهام", "تنها هستم", "تنهایی"): [
        "من هستم کنارتم 💚", "تنها نیستی 🥰", "من دوستتم 🤝", "همیشه کنارتم 💫", "بیا حرف بزنیم 🌹",
    ],
    ("ترسیدم", "می‌ترسم", "ترسناکه"): [
        "نترس عزیز 💚", "من هستم کنارت 🤗", "چی ترسیدت؟ 🤔", "آروم باش 🌹", "همه چی خوبه 💐",
    ],
    ("دردم میاد", "درد دارم", "مریضم", "سردرد دارم"): [
        "خدا شفات بده 🙏", "زود خوب شی 💚", "استراحت کن 🌹", "دکتر برو 🩺", "سلامت باشی 🌿",
    ],
    ("وای", "واو", "اوه", "ای بابا"): [
        "چی شد؟ 😲", "چیه؟ 🤔", "بگو ببینم 😊", "چه خبره؟ 📢", "چی شده یهو؟ 😯",
    ],
    ("آخ", "آخ آخ", "اَه", "اه"): [
        "چی شد؟ 🤕", "دردت گرفت؟ 🩹", "خوبی؟ 💚", "چیزی شده؟ 😟", "سلامت باش 🌿",
    ],
    ("خخخ", "هههه", "ههه", "هاها", "لول"): [
        "😂", "😄", "🤣", "خنده‌داره 😆", "منم خندیدم 😂",
    ],
    ("نازنین", "نازنینم", "عزیز دل"): [
        "جانم نازنینم 🌹", "فدای تو 💖", "قربونت برم 💗", "عشقم 💕", "دلبرم 💐",
    ],
    ("بازی کنیم", "بازی می‌کنی", "بیا بازی"): [
        "دوز بازی کنیم؟ 🎲", "برای بازی بنویس `دوز` 🎮", "شیر یا خط؟ 🪙", "بیا `دوز` بازی کنیم 🎲", "لیست بازی: `لیست بازی` 🎮",
    ],
    ("شعر بگو", "یه شعر بگو", "شعر بخون"): [
        "برای شعر بنویس `شعر` 📝", "دستور `شعر` رو بزن 📝", "یه شعر: `شعر` 📖", "بزن `شعر` ببین 📚", "شعر: دستور `شعر` 🎭",
    ],
    ("جوک بگو", "جک بگو", "بخندون منو"): [
        "برای جک بنویس `جک` 😂", "دستور `جک` رو بزن 😄", "جک: `جک` 🤣", "بزن `جک` بخندیم 😆", "جک بگو: `جک` 😂",
    ],
    ("فال بگو", "فال حافظ", "فال بگیر"): [
        "برای فال بنویس `فال` 🔮", "دستور `فال` رو بزن 🔮", "فال: `فال` 🍀", "بزن `فال` ببین 🔮", "فال حافظ: `فال` 📿",
    ],
    ("چالش بده", "چالش بگو", "چالش بده بهم"): [
        "برای چالش بنویس `چالش` 🎯", "دستور `چالش` رو بزن 🎲", "چالش: `چالش` 🔥", "بزن `چالش` 🎯", "چالش: `چالش` 💪",
    ],
    ("چی بخورم", "چی درست کنم", "چی بپزم"): [
        "پیتزا؟ 🍕", "قورمه سبزی؟ 🍲", "چلوکباب؟ 🍖", "ماکارونی؟ 🍝", "کباب؟ 🍢",
    ],
    ("چی می‌خوری", "چی می‌خوری تو"): [
        "من نمی‌خورم 😅", "من رباتم 🤖", "تو چی می‌خوری؟ 😋", "غذای خوب 🍕", "قورمه سبزی 🍲",
    ],
    ("یا خدا", "خدایا", "الهی", "به خدا"): [
        "آمین 🙏", "خدا بزرگه 🌟", "الهی 🙏", "خدا کمکت کنه 💚", "توکل به خدا 🤲",
    ],
    ("خدا حفظت کنه", "خدا حفظت", "خدا نگهت داره"): [
        "خدا تو رو هم حفظ کنه 🌹", "الهی آمین 🙏", "ممنون 💚", "خدا نگهت داره 🌟", "لطف داری 💐",
    ],
    ("هوا چطوره", "آب و هوا", "هوا سرده", "هوا گرمه"): [
        "سرد یا گرم؟ ❄️🔥", "بارونیا؟ ☔", "آفتابیه؟ ☀️", "ابرایه؟ ☁️", "برفی؟ ❄️",
    ],
    ("بهترینم", "خوبم", "عالیم", "خوشحالم الان"): [
        "چه خوب 🎉", "همیشه همینطور باشی ✨", "مرسی که خوبی 💚", "آفرین 🌹", "خوشحالم که خوبی 💖",
    ],
    ("بدحالم", "حالم بده", "حالم خوب نیست", "داغونم"): [
        "چی شده؟ 🥺", "خدا کمکت کنه 🙏", "آروم باش 💚", "بگو چی شده 🌹", "من کنارتم 🤗",
    ],
    ("چیکار می‌تونی بکنی", "چیکارا می‌کنی", "قابلیت‌هات چیه"): [
        "برای دیدن قابلیت‌ها بنویس `قابلیت ها` 📖", "دستور `راهنما` رو بزن 📚", "همه چی می‌تونم بکنم 🌟", "بزن `قابلیت های ربات` 📖", "بگو `راهنما` ببینی 📚",
    ],
    ("خوشم میاد ازت", "دوست دارم ربات", "تو خوبی"): [
        "مرسی عزیز 💖", "لطف داری 🌹", "منم دوستت دارم 💕", "خوشحالم 🥰", "ممنون که هستی 💚",
    ],
    ("به‌به", "به به", "چه عجب"): [
        "به به 🌟", "چه عجب 🥰", "خوش اومدی 🌹", "سلام علیک 💐", "جونم 💖",
    ],
    ("ای جان", "جان جان"): [
        "ای جان 💕", "جونم 🥰", "عزیزم 🌹", "قربونت 💗", "دل من 💖",
    ],
    ("دلم می‌خواد", "دلم میخواد"): [
        "چی دلت می‌خواد؟ 💭", "بگو دلت چی می‌خواد 🥰", "دلت چی میگه؟ 💗", "می‌تونم برات کاری کنم؟ 🤝", "بگو بشنوم 💐",
    ],
    ("اهل کجایی", "کجایی هستی", "اهل کجا"): [
        "من هیچ‌جا نیستم 🤖", "من تو گوشی توام 📱", "من اهل دنیای دیجیتالم 💫", "من همه‌جام 🌍", "من اهل اینترنتم 🌐",
    ],
}

TALKATIVE_PHRASES = []
for _keys, _reps in TALKATIVE_MAP.items():
    TALKATIVE_PHRASES.extend(_reps)


def _is_talkative_phrase(kw):
    for c in kw:
        if c in ' \u200c\u200d\t':
            return True
    return False


_TALKATIVE_FLAT = []
_seen_kw = set()
for _keys, _reps in TALKATIVE_MAP.items():
    for _k in _keys:
        _k_lower = _k.lower()
        _is_p = _is_talkative_phrase(_k_lower)
        if _k_lower not in _seen_kw:
            _TALKATIVE_FLAT.append((_k_lower, _reps, _is_p))
            _seen_kw.add(_k_lower)
        _k_clean = _k_lower.replace('\u200c', '').replace('\u200d', '')
        if _k_clean != _k_lower and _k_clean not in _seen_kw:
            _TALKATIVE_FLAT.append((_k_clean, _reps, _is_talkative_phrase(_k_clean)))
            _seen_kw.add(_k_clean)

_TALKATIVE_FLAT.sort(key=lambda x: -len(x[0]))


def get_talkative_reply(text):
    if not text: return None
    t = text.strip().lower()
    if not t: return None
    t_clean = t.replace('\u200c', '').replace('\u200d', '')
    words = [w.strip() for w in re.split(r'[\s,،.!?؟:;()\[\]{}«»\-\u200c]+', t) if w.strip()]
    words_clean = [w.strip() for w in re.split(r'[\s,،.!?؟:;()\[\]{}«»\-\u200c]+', t_clean) if w.strip()]
    if not words: return None
    words_set = set(words)
    words_clean_set = set(words_clean)

    for kw, reps, is_phrase in _TALKATIVE_FLAT:
        if is_phrase:
            if kw in t or kw in t_clean:
                return reps
        else:
            if kw in words_set or kw in words_clean_set:
                return reps
    return None


def get_random_talkative():
    return random.choice(TALKATIVE_PHRASES)


def is_talkative_enabled(chat_id):
    disabled = bot_data.get("talkative_disabled", [])
    if not isinstance(disabled, list):
        disabled = []
        bot_data["talkative_disabled"] = disabled
    return chat_id not in disabled


def set_talkative(chat_id, enabled):
    if "talkative_disabled" not in bot_data:
        bot_data["talkative_disabled"] = []
    if not isinstance(bot_data["talkative_disabled"], list):
        bot_data["talkative_disabled"] = []
    disabled = bot_data["talkative_disabled"]
    if enabled:
        if chat_id in disabled: disabled.remove(chat_id)
    else:
        if chat_id not in disabled: disabled.append(chat_id)
    save_data(bot_data, force=True)


# ================== Group Validation ==================
def is_dead_group_error(err_str):
    if not err_str: return False
    err = str(err_str).lower()
    dead_keywords = [
        "not found", "not_found", "chat not found", "chat_not_found",
        "kicked", "bot was kicked", "bot_kicked",
        "not member", "not_member", "not a member", "not_a_member",
        "bot is not", "bot_is_not",
        "not admin", "not_admin", "admin required", "admin_required",
        "chat_admin_required", "not enough rights", "not_enough_rights",
        "forbidden", "chat_forbidden", "chat_write_forbidden",
        "peer_id_invalid", "peer id invalid",
        "peer not found", "peer_not_found",
        "channel_private", "chat_private",
        "you are banned", "user_banned", "banned",
        "chat blocked", "chat_blocked",
        "access denied", "access_denied",
    ]
    return any(k in err for k in dead_keywords)


async def validate_group(gid):
    if not gid: return False, "شناسه خالی"
    try:
        info = await bot.get_chat_info(gid)
        if not info: return False, "پاسخ خالی از سرور"
        data = info.get("data", info) if isinstance(info, dict) else info
        if isinstance(data, dict):
            status = str(data.get("status", "")).lower()
            if status in ("error", "failed", "fail", "nok"):
                msg = str(data.get("message") or data.get("error") or "خطای نامشخص")
                return False, msg
            chat = data.get("chat", data)
            if isinstance(chat, dict) and not chat:
                return False, "اطلاعات گروه خالی"
        return True, None
    except Exception as e:
        err = str(e)
        if is_dead_group_error(err): return False, err
        return True, err


# ================== Game Functions ==================
def render_board(board):
    lines = ["1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣"]
    for row in board:
        line = ""
        for cell in row:
            if cell is None: line += EMPTY
            elif cell == "R": line += RED
            elif cell == "Y": line += YELLOW
        lines.append(line)
    return "\n".join(lines)


def drop_piece(board, col, color):
    for row in range(5, -1, -1):
        if board[row][col] is None:
            board[row][col] = color
            return True, row, col
    return False, -1, -1


def check_win(board, row, col, color):
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for dr, dc in directions:
        count = 1
        r, c = row + dr, col + dc
        while 0 <= r < 6 and 0 <= c < 7 and board[r][c] == color:
            count += 1; r += dr; c += dc
        r, c = row - dr, col - dc
        while 0 <= r < 6 and 0 <= c < 7 and board[r][c] == color:
            count += 1; r -= dr; c -= dc
        if count >= 4: return True
    return False


def is_board_full(board):
    for row in board:
        for cell in row:
            if cell is None: return False
    return True


def get_games():
    if "games" not in bot_data or not isinstance(bot_data["games"], dict):
        bot_data["games"] = {}
    return bot_data["games"]


async def game_timeout_check(chat_id, game_type, started_at=None):
    try:
        await asyncio.sleep(GAME_TIMEOUT)
        if game_type == "connect4":
            games = get_games()
            game = games.get(chat_id)
            same_game = (
                game is not None
                and (started_at is None or game.get("started_at") == started_at)
            )
            if same_game and game.get("status") == "waiting":
                del games[chat_id]
                save_data(bot_data, force=True)
                try:
                    await bot.send_message(chat_id=chat_id, text=(
                        "⏱️ **زمان بازی به پایان رسید!**\n\n"
                        "هیچ‌کس شرکت نکرد و بازی لغو شد.\n\n⚡ **FLUXBOT**"))
                    print(f"⏱️ Connect4 timeout: {chat_id}", flush=True)
                except: pass
        elif game_type == "coinflip":
            game = coin_flip_games.get(chat_id)
            same_game = (
                game is not None
                and (started_at is None or game.get("started_at") == started_at)
            )
            if same_game:
                del coin_flip_games[chat_id]
                try:
                    await bot.send_message(chat_id=chat_id, text=(
                        "⏱️ **زمان انتخاب به پایان رسید!**\n\n"
                        "بازی شیر یا خط لغو شد.\n\n⚡ **FLUXBOT**"))
                    print(f"⏱️ CoinFlip timeout: {chat_id}", flush=True)
                except: pass
    except Exception as e:
        print(f"⚠️ game_timeout: {e}", flush=True)


async def start_game(chat_id, sender_id, sender_display, color_choice):
    games = get_games()
    if chat_id in games:
        g = games[chat_id]
        if g.get("status") in ("waiting", "playing"):
            started = g.get("started_at", 0)
            if time.time() - started > (GAME_TIMEOUT * 3):
                print(f"🗑️ [stale-game] پاک شد: {chat_id}", flush=True)
                del games[chat_id]
                save_data(bot_data, force=True)
            else:
                return None
    color1 = "R" if color_choice == "قرمز" else "Y" if color_choice == "زرد" else "R"
    color2 = "Y" if color1 == "R" else "R"
    started_at = time.time()
    games[chat_id] = {
        "player1": str(sender_id), "player1_name": sender_display,
        "player2": None, "player2_name": None,
        "color1": color1, "color2": color2,
        "board": [[None]*7 for _ in range(6)],
        "turn": str(sender_id), "status": "waiting",
        "started_at": started_at,
    }
    save_data(bot_data, force=True)
    try: asyncio.create_task(game_timeout_check(chat_id, "connect4", started_at))
    except: pass
    return games[chat_id]


async def join_game(chat_id, sender_id, sender_display):
    games = get_games()
    if chat_id not in games: return None, "no_game"
    g = games[chat_id]
    if g.get("status") != "waiting": return None, "already_started"
    if g["player1"] == str(sender_id): return None, "self_join"
    g["player2"] = str(sender_id)
    g["player2_name"] = sender_display
    g["status"] = "playing"
    g["turn"] = g["player1"]
    save_data(bot_data, force=True)
    return g, "ok"


async def cancel_game(chat_id, sender_id):
    games = get_games()
    if chat_id not in games: return None, "no_game"
    g = games[chat_id]
    if str(sender_id) not in (g.get("player1"), g.get("player2")):
        return None, "not_player"
    del games[chat_id]
    save_data(bot_data, force=True)
    return g, "ok"


# ================== Utility ==================
def ensure_list(value):
    if isinstance(value, list): return value
    if isinstance(value, dict): return list(value.keys()) if value else []
    if isinstance(value, str): return [value] if value else []
    return []


def ensure_list_dict(d, key, sub_key=None):
    if sub_key is not None:
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        if sub_key not in d[key] or not isinstance(d[key][sub_key], list):
            d[key][sub_key] = []
        return d[key][sub_key]
    else:
        if key not in d or not isinstance(d[key], list):
            d[key] = []
        return d[key]


async def schedule_delete(chat_id, message_id, delay_seconds):
    async def _del():
        try:
            await asyncio.sleep(delay_seconds)
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            print(f"⚠️ schedule_delete: {e}", flush=True)
    try: asyncio.create_task(_del())
    except Exception as e:
        print(f"⚠️ create_task: {e}", flush=True)


def extract_msg_id(result):
    try:
        if isinstance(result, dict):
            if "data" in result and isinstance(result["data"], dict):
                mid = result["data"].get("message_id")
                if mid: return str(mid)
            mid = result.get("message_id")
            if mid: return str(mid)
        elif hasattr(result, "message_id"):
            return str(result.message_id)
    except Exception as e:
        print(f"⚠️ extract_msg_id: {e}", flush=True)
    return None


def api_result_ok(result):
    """Recognize explicit API failures while accepting normal/empty responses."""
    if not isinstance(result, dict):
        return True
    if result.get("ok") is False:
        return False
    status = str(result.get("status", "")).strip().lower()
    return status not in ("error", "failed", "fail", "nok")


def _utf16_length(text):
    return len(str(text).encode("utf-16-le")) // 2


async def send_user_mention_message(chat_id, user_id, text, reply_to_message_id=None, bot_client=None):
    """Send a message with a native, clickable Rubika MentionText; fall back safely."""
    client = bot_client or bot
    text = str(text or "")
    marker_index = text.find(USER_MENTION_TOKEN)
    if marker_index < 0:
        return await client.send_message(
            chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id
        )

    label = "کاربر"
    rendered_text = (
        text[:marker_index] + label +
        text[marker_index + len(USER_MENTION_TOKEN):]
    )

    # MentionText is supported only in groups. Its offsets are UTF-16 units,
    # not Python character indexes (important when emojis precede the mention).
    if is_group_chat(chat_id) and user_id:
        payload = {
            "chat_id": str(chat_id),
            "text": rendered_text,
            "metadata": {
                "meta_data_parts": [{
                    "type": "MentionText",
                    "from_index": _utf16_length(text[:marker_index]),
                    "length": _utf16_length(label),
                    "mention_text_user_id": str(user_id),
                }]
            },
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = str(reply_to_message_id)
        try:
            post = getattr(client, "_post", None)
            if callable(post):
                result = post("sendMessage", payload)
                if hasattr(result, "__await__"):
                    result = await result
                if api_result_ok(result):
                    return result
                print("⚠️ MentionText رد شد؛ ارسال پیام بدون پیوند انجام می‌شود.", flush=True)
        except Exception as e:
            print(f"⚠️ MentionText: {e}", flush=True)

    # Unsupported SDK/API metadata must never prevent the moderation notice.
    return await client.send_message(
        chat_id=chat_id,
        text=rendered_text,
        reply_to_message_id=reply_to_message_id,
    )


async def get_user_info(chat_id, user_id, force=False):
    key = f"{chat_id}:{user_id}"
    now = time.time()
    cached = username_cache.get(key)
    ttl = username_cache_ttl.get(key, 0)
    if not force and cached and now < ttl and (cached.get("username") or cached.get("name")):
        return cached
    info = {"name": None, "username": None, "role": "عضو"}
    try:
        mi = await bot.get_chat_member(chat_id, user_id)
        if mi:
            data = mi
            for _ in range(3):
                if isinstance(data, dict) and isinstance(data.get("data"), dict):
                    data = data["data"]
                else:
                    break
            if not isinstance(data, dict):
                try:
                    data = vars(data)
                except (TypeError, AttributeError):
                    data = {}

            member = (
                data.get("chat_member") or data.get("chatMember") or
                data.get("member") or data
            )
            if not isinstance(member, dict):
                try:
                    member = vars(member)
                except (TypeError, AttributeError):
                    member = {}

            user = (
                member.get("user") or member.get("user_info") or
                member.get("userInfo") or data.get("user") or {}
            )
            if not isinstance(user, dict):
                try:
                    user = vars(user)
                except (TypeError, AttributeError):
                    user = {}

            # Rubika may put profile fields inside `user` and role fields
            # beside it in `chat_member`; check both without losing either.
            sources = (member, user, data)
            def _first_user_value(*keys):
                for source in sources:
                    if not isinstance(source, dict):
                        continue
                    for key in keys:
                        value = source.get(key)
                        if value is None or value is False or value == "":
                            continue
                        if isinstance(value, (dict, list, tuple, set)) and not value:
                            continue
                        return value
                return None

            info["name"] = _first_user_value(
                "first_name", "firstName", "name", "title", "display_name",
                "displayName",
            )
            un = _first_user_value("username", "user_name", "userName")
            if un: info["username"] = str(un).lstrip("@")
            status_raw = _first_user_value(
                "status", "member_type", "memberType", "role", "type",
                "chat_member_type", "chatMemberType", "membership",
            )
            st = str(status_raw or "").strip().lower().replace("_", "").replace("-", "").replace(" ", "")
            role = "عضو"
            if st in ("creator", "owner", "admincreator", "ownercreator", "superadmin", "chatcreator"):
                role = "مالک"
            elif st in ("admin", "administrator", "moderator", "mod", "chatadmin", "channeladmin"):
                role = "ادمین"
            elif st in ("member", "user", "participant", "regular", "normal", "ordinary"):
                role = "عضو"
            if role == "عضو":
                if _first_user_value("is_creator", "isCreator", "is_owner", "isOwner"):
                    role = "مالک"
                elif _first_user_value("is_admin", "isAdmin", "is_administrator", "isAdministrator"):
                    role = "ادمین"
            perms = _first_user_value("permissions", "rights") or {}
            if isinstance(perms, dict) and role == "عضو":
                if perms.get("is_creator") or perms.get("is_owner"):
                    role = "مالک"
                elif perms.get("is_admin"):
                    role = "ادمین"
            info["role"] = role
            username_cache[key] = info
            username_cache_ttl[key] = now + 7200
            save_known_user(user_id, info.get("name"), info.get("username"))
    except Exception as e:
        print(f"⚠️ get_user_info: {e}", flush=True)
    return info


def save_known_user(user_id, name=None, username=None):
    if "known_users" not in bot_data: bot_data["known_users"] = {}
    uid = str(user_id)
    if uid not in bot_data["known_users"]: bot_data["known_users"][uid] = {}
    changed = False
    if name and bot_data["known_users"][uid].get("name") != name:
        bot_data["known_users"][uid]["name"] = name
        changed = True
    if username and bot_data["known_users"][uid].get("username") != username:
        bot_data["known_users"][uid]["username"] = username
        changed = True
    bot_data["known_users"][uid]["last_seen"] = time.time()
    if changed:
        save_data(bot_data)


def _safe_display_name(value, user_id=None):
    if not value:
        return None
    name = re.sub(r"(?<![\w])@[A-Za-z0-9_.]+", "", str(value)).strip(" \t\r\n,،")
    if not name or (user_id is not None and name == str(user_id)):
        return None
    return name


def get_display_for_user(user_id):
    uid = str(user_id)
    ku = bot_data.get("known_users", {}).get(uid, {})
    name = _safe_display_name(ku.get("name"), uid) if isinstance(ku, dict) else None
    return name or "کاربر"


def format_user_display(ui, uid):
    ui = ui if isinstance(ui, dict) else {}
    return _safe_display_name(ui.get("name"), uid) or get_display_for_user(uid)


async def get_bot_id():
    if BOT_ID_CACHE["id"]: return BOT_ID_CACHE["id"]
    try:
        me = await bot.get_me()
        if me:
            if isinstance(me, dict):
                data = me.get("data", me)
                b = data.get("bot", data) if isinstance(data, dict) else {}
                bid = b.get("bot_id") or b.get("id")
                if bid:
                    BOT_ID_CACHE["id"] = str(bid)
                    return BOT_ID_CACHE["id"]
            elif hasattr(me, 'bot_id'):
                BOT_ID_CACHE["id"] = str(me.bot_id)
                return BOT_ID_CACHE["id"]
    except Exception as e:
        print(f"⚠️ get_bot_id: {e}", flush=True)
    return None


def extract_reply_info(message):
    result = {"reply_id": None, "sender_id": None}
    try:
        rt = (getattr(message, 'reply_to_message', None) or
              getattr(message, 'reply_message', None) or
              getattr(message, 'reply_to', None))
        if rt:
            pending = [(rt, True, False)]
            seen = set()
            while pending:
                item, is_message, is_sender = pending.pop(0)
                marker = id(item)
                if (marker, is_message, is_sender) in seen:
                    continue
                seen.add((marker, is_message, is_sender))
                if isinstance(item, dict):
                    if is_message and not result["reply_id"]:
                        mid = item.get("message_id") or item.get("messageId")
                        if not mid and item.get("id") and not isinstance(item.get("id"), dict):
                            mid = item.get("id")
                        if mid: result["reply_id"] = str(mid)
                    if not result["sender_id"]:
                        sid = item.get("sender_id") or item.get("user_id") or item.get("from_id")
                        if not sid and is_sender:
                            sid = item.get("id")
                        if sid and not isinstance(sid, (dict, list)):
                            result["sender_id"] = str(sid)
                    for key in ("sender", "from", "from_user", "user", "message", "reply_to_message"):
                        nested = item.get(key)
                        if nested is not None:
                            pending.append((
                                nested,
                                key in ("message", "reply_to_message"),
                                key in ("sender", "from", "from_user", "user"),
                            ))
                else:
                    if is_message and not result["reply_id"]:
                        mid = getattr(item, "message_id", None) or getattr(item, "messageId", None)
                        if not mid:
                            mid = getattr(item, "id", None)
                        if mid and not isinstance(mid, (dict, list)):
                            result["reply_id"] = str(mid)
                    if not result["sender_id"]:
                        sid = (
                            getattr(item, "sender_id", None) or
                            getattr(item, "user_id", None) or
                            getattr(item, "from_id", None)
                        )
                        if not sid and is_sender:
                            sid = getattr(item, "id", None)
                        if sid and not isinstance(sid, (dict, list)):
                            result["sender_id"] = str(sid)
                    for attr in ("sender", "from_user", "user", "message", "reply_to_message"):
                        try:
                            nested = getattr(item, attr, None)
                            if nested is not None:
                                pending.append((
                                    nested,
                                    attr in ("message", "reply_to_message"),
                                    attr in ("sender", "from_user", "user"),
                                ))
                        except Exception:
                            pass
    except Exception as e:
        print(f"⚠️ RT_PARSE: {e}", flush=True)
    if not result["reply_id"]:
        for attr in ['reply_to_message_id', 'reply_message_id', 'reply_id', 'replyToMessageId']:
            try:
                val = getattr(message, attr, None)
                if val:
                    if hasattr(val, 'message_id'): result["reply_id"] = str(val.message_id)
                    else: result["reply_id"] = str(val)
                    break
            except: pass
    if not result["reply_id"]:
        try:
            aux = getattr(message, 'aux_data', None) or getattr(message, 'auxData', None)
            if aux and isinstance(aux, dict):
                for k in ['reply_to_message_id', 'reply_id', 'replyMessageId', 'reply_to']:
                    v = aux.get(k)
                    if v:
                        result["reply_id"] = str(v)
                        if 'sender_id' in aux: result["sender_id"] = str(aux['sender_id'])
                        break
        except: pass
    return result


INVALID_IDS = ("", "None", "none", "NULL", "null", "0", "False", "false")


def _is_valid_id(v):
    if not v: return False
    s = str(v).strip()
    if not s: return False
    if s in INVALID_IDS: return False
    if s.startswith("<"): return False
    return True


async def find_reply_target(message, chat_id):
    info = extract_reply_info(message)
    rid = info["reply_id"]
    sid_direct = info["sender_id"]
    if sid_direct and _is_valid_id(sid_direct):
        bot_id = await get_bot_id()
        if bot_id and str(sid_direct) == str(bot_id): return "BOT_SELF"
        if rid and chat_id:
            c = load_cache()
            if chat_id not in c: c[chat_id] = {}
            c[chat_id][str(rid)] = sid_direct
            save_cache(c, force=True)
        return sid_direct
    if not rid: return None
    try:
        c = load_cache()
        if chat_id in c and rid in c[chat_id]:
            sid = c[chat_id][rid]
            if not _is_valid_id(sid): return None
            bot_id = await get_bot_id()
            if bot_id and str(sid) == str(bot_id): return "BOT_SELF"
            return sid
    except Exception as e:
        print(f"⚠️ cache lookup: {e}", flush=True)
    try:
        msg = await bot.get_message(chat_id=chat_id, message_id=rid)
        if msg:
            sid = None
            if isinstance(msg, dict):
                data = msg.get('data', msg)
                m = data.get('message', data) if isinstance(data, dict) else {}
                sid = m.get('sender_id') or m.get('user_id') or m.get('from_id')
            elif hasattr(msg, 'sender_id'):
                sid = msg.sender_id
            if sid and _is_valid_id(sid):
                sid = str(sid)
                bot_id = await get_bot_id()
                if bot_id and sid == bot_id: return "BOT_SELF"
                c = load_cache()
                if chat_id not in c: c[chat_id] = {}
                c[chat_id][rid] = sid
                save_cache(c, force=True)
                return sid
    except Exception as e:
        print(f"⚠️ API get_message: {e}", flush=True)
    return None


def split_text(text, max_len=800):
    if not text: return [""]
    if len(text) <= max_len: return [text]
    parts = []
    remaining = text
    while len(remaining) > max_len:
        cut = remaining.rfind('\n', 0, max_len)
        if cut < 50: cut = max_len
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining: parts.append(remaining)
    return parts


async def send_long_message(chat_id, text, reply_to_message_id=None):
    parts = split_text(text, 800)
    first_result = None
    for i, part in enumerate(parts):
        if not part: continue
        try:
            kwargs = {"chat_id": chat_id, "text": part}
            if reply_to_message_id and i == 0:
                kwargs["reply_to_message_id"] = reply_to_message_id
            result = await bot.send_message(**kwargs)
            if i == 0: first_result = result
            if i < len(parts) - 1:
                await asyncio.sleep(0.15)
        except Exception as e:
            print(f"❌ SEND PART {i}: {e}", flush=True)
    return first_result


def generate_invite_code():
    existing = set(bot_data.get("invite_codes", {}).values())
    for _ in range(200):
        code = str(random.randint(100000, 999999))
        if code not in existing: return code
    return str(random.randint(1000000, 9999999))[-6:]


def get_or_create_code(user_id):
    user_id = str(user_id)
    if "invite_codes" not in bot_data: bot_data["invite_codes"] = {}
    if "code_to_user" not in bot_data: bot_data["code_to_user"] = {}
    if user_id in bot_data["invite_codes"]:
        code = bot_data["invite_codes"][user_id]
        bot_data["code_to_user"][code] = user_id
        return code
    code = generate_invite_code()
    bot_data["invite_codes"][user_id] = code
    bot_data["code_to_user"][code] = user_id
    save_data(bot_data, force=True)
    return code


def get_points(user_id):
    return bot_data.get("points", {}).get(str(user_id), 0)


def get_top_inviters(limit=10):
    invited = bot_data.get("invited_users", {})
    counts = {}
    for invited_id, inviter_id in invited.items():
        counts[inviter_id] = counts.get(inviter_id, 0) + 1
    sorted_list = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_list[:limit]


def parse_slow_duration(text):
    text = text.strip()
    m = re.match(r'^(\d+)\s*(ثانیه|دقیقه|ساعت|روز|s|m|h|d)?$', text)
    if not m: return None
    num = int(m.group(1))
    unit = (m.group(2) or "ثانیه").lower()
    if unit in ("ثانیه", "s", ""): sec = num
    elif unit in ("دقیقه", "m"): sec = num * 60
    elif unit in ("ساعت", "h"): sec = num * 3600
    elif unit in ("روز", "d"): sec = num * 86400
    else: sec = num
    if sec < 5: sec = 5
    if sec > 86400: sec = 86400
    return sec


def format_duration(sec):
    if sec < 60: return f"{sec} ثانیه"
    if sec < 3600: return f"{sec // 60} دقیقه" + (f" و {sec % 60} ثانیه" if sec % 60 else "")
    if sec < 86400: return f"{sec // 3600} ساعت" + (f" و {(sec % 3600) // 60} دقیقه" if sec % 3600 else "")
    return f"{sec // 86400} روز"


PROFANITY_LIST = [
    "کص","کیر","کون","کسکش","کس کش","کصکش","کص کش","خارکصه","خار کصه","خارکسه",
    "بیناموس","بی ناموس","جنده","حرومزاده","حروم زاده","مادرت","مادرتو","مادر خراب",
    "مادر سگ","خواهرت","پدرت","پدر سگ","لاشی","لاشخور","دیوث","دیوثه","بیشعور",
    "احمق","خرفت","کودن","پررو","گاگول","کمه","کمه مغز","خنگ","نفهم","بیسواد",
    "کثافت","گوه","گوه خور","گه","گه خور","شاش","شاشو","جاکش","جا کش","قرمساق",
    "کاسه لیس","پاچه خار","چاپلوس","کونده","کونی","خارکسده","خار کس","سگی",
    "سگ صفت","خری","الاغ","گاوی","گوساله","کرم خور","بی پدر","بیمادر",
    "حرامی","پدرسوخته","مادرسوخته","بی غیرت","عوضی","مزخرف","چرند",
    "کصخل","کسخل","کص خور","کیرخور","کیر کش","پفیوز","چسی","چس خور","تخمی",
    "تخم سگ","مغز کیر","کص مغز","نناموس","بی حیا","لختی","برهنه","کیرمغز",
]

_PROFANITY_NORMALIZED = None

JOKES = [
    "به یارو میگن چرا زنتو میزنی؟ میگه چون عاشقشم! 😂",
    "رفتم دکتر گفتم آدم‌ها رو دوست ندارم! گفت پس چرا اومدی؟ گفتم تو که آدم نیستی! 😅",
    "به یارو میگن شغلت چیه؟ میگه بیکارم! میگن پس چطوری خرج می‌کنی؟ میگه آبروم رو می‌فروشم! 😂",
    "از یارو پرسیدن چرا زیر بارون وایسادی؟ گفت منتظرم یه قطره بیفته تا لیوانم پر شه! 🌧️",
    "به یارو میگن چرا لباسات خیشه؟ میگه چون زیر بارون راه می‌رم! میگن چرا؟ میگه چون ماشین ندارم! 🚗",
    "یه بار یه مرد به زنش گفت: عزیزم من می‌رم سفر! زن گفت: کجا؟ مرد گفت: پیش مامانم! زن گفت: پس منم میام! 😂",
    "به یارو میگن چرا نون نمی‌خوری؟ میگه رژیم دارم! میگن پس چرا شکلات می‌خوری؟ میگه چون شکلات رژیمی نیست! 🍫",
    "از یارو پرسیدن چرا اینقد خوشحالی؟ گفت قبض آب نیومده! گفتن چرا؟ گفت چون آب نداریم! 💧",
    "معلم به شاگرد گفت: چرا مشقت رو ننوشتی؟ شاگرد گفت: چون خودکار نداشتم! معلم گفت: پس چرا تو کلاس نشستی؟ شاگرد گفت: چون صندلی بود! 🪑",
    "به یارو میگن چرا گوشیت رو خاموش کردی؟ میگه باتری نداشت! میگن پس چرا شارژ نکردی؟ میگه برق نداشتیم! ⚡",
    "یه بار یه ربات به یه ربات دیگه گفت: سلام! اون گفت: من تو رو نمی‌شناسم! اولی گفت: منم تو رو نمی‌شناسم، ولی سلام دادم! 🤖",
    "به یارو میگن چرا اینقد لاغری؟ میگه پول غذا ندارم! میگن پس چرا اینقد چاقی؟ میگه شوخیت گرفته؟ 🍔",
    "از یارو پرسیدن عشق چیه؟ گفت: عشق یعنی زنت بگه برو نون بگیر، تو بری پیتزا بخری! 🍕",
    "به یارو میگن چرا دوچرخه نداری؟ میگه پول ندارم! میگن پس چرا ماشین داری؟ میگه وام گرفتم! 🚴",
    "یه بار یه پیرمرد رفت مطب دکتر، دکتر گفت: چه خبر؟ پیرمرد گفت: از وقتی زنم مرده، بهترم! 😂",
    "به یارو میگن چرا اینقد ساکتی؟ میگه دارم فکر می‌کنم! میگن به چی؟ میگه به اینکه چرا اینقد ساکتم! 🤔",
    "از یارو پرسیدن چرا خوابت میاد؟ گفت دیشب کم خوابیدم! گفتن چرا؟ گفت چون زیاد خوابیدم! 😴",
    "به یارو میگن چرا کفشت پاره‌ست؟ میگه چون پول کفش ندارم! میگن پس چرا شلوارت جدیده؟ میگه شلوارم هدیه بوده! 👕",
    "یه بار یه کاربر به ربات گفت یه جوک بگو، ربات گفت: تو خودت یه جوکی! 😂",
    "از یارو پرسیدن چرا دندونات زرده؟ گفت چون سیگار می‌کشم! گفتن چرا سیگار می‌کشی؟ گفت چون دندونام زرده! 🚬",
]

PROVERBS = [
    "آب که از سر گذشت، چه یک وجب چه صد وجب. 🌊",
    "از این ستون به آن ستون فرج است. 🕌",
    "از تو حرکت، از خدا برکت. 🙏",
    "اسب را که بردی، لگامش را هم ببر. 🐴",
    "با یک گل بهار نمی‌شه. 🌸",
    "با یک دست نمی‌شه دو تا هندونه برداشت. 🍉",
    "تا نباشد چیزکی، مردم نگویند چیزها. 🗣️",
    "دو صد گفته چون نیم کردار نیست. 🎯",
    "دیگ به سر، آش هم پشتش. 🍲",
    "سنگ بزرگ علامت نزدن است. 🪨",
    "شتر دیدی ندیدی. 🐪",
    "کوه به کوه نمی‌رسه، آدم به آدم می‌رسه. ⛰️",
    "گربه دستش به گوشت نمی‌رسه، میگه بو میده! 🐱",
    "هر که بامش بیش، برفش بیشتر. ❄️",
    "هر که طاووس خواهد، جور هندوستان کشد. 🦚",
    "از آنجا که بلند است، درش بیفت! 🏠",
    "آشپز که دو تا شد، آش یا شور می‌شه یا بی‌نمک. 👨‍🍳",
    "با پول می‌شه خر خرید، ولی نمی‌شه خر سوار شد! 💰",
    "چاه مکن بهر کسی، اول خودت دوم کسی. 🕳️",
    "خواستن توانستن است. 💪",
]

TRIVIA = [
    "🐙 اختاپوس‌ها سه قلب دارند و خونشان آبی است.",
    "🍯 عسل هرگز فاسد نمی‌شود.",
    "🐘 فیل‌ها تنها پستانداری هستند که نمی‌توانند بپرند.",
    "🌙 ماه هر سال حدود ۳.۸ سانتی‌متر از زمین دور می‌شود.",
    "🦈 کوسه‌ها قبل از دایناسورها روی زمین بودند.",
    "🐜 مورچه‌ها می‌توانند ۵۰ برابر وزن خودشان بار حمل کنند.",
    "🐝 زنبورها می‌توانند چهره انسان‌ها را تشخیص بدهند.",
    "🦒 زرافه‌ها قلب بزرگی دارند که خون رو تا سرشون پمپ می‌کنه.",
    "🐬 دلفین‌ها با نصف مغز می‌خوابند و با نصف دیگه بیدار می‌مونن.",
    "🦋 پروانه‌ها با پاهایشان مزه غذا رو می‌فهمند.",
    "🐳 نهنگ آبی بزرگترین حیوان روی زمینه.",
    "🦁 شیرها تنها گربه‌سانانی هستند که در گروه زندگی می‌کنند.",
    "🌳 درختان با همدیگر از طریق ریشه‌ها ارتباط برقرار می‌کنند.",
    "🐢 لاک‌پشت‌ها می‌توانند تا ۱۵۰ سال عمر کنند.",
    "🦅 عقاب‌ها می‌توانند تا ۳ کیلومتر دورتر رو ببینند.",
    "🐍 مارها پلک ندارند، به همین خاطر همیشه چشماشون بازه.",
    "🐨 کوآلاها ۲۲ ساعت در روز می‌خوابند.",
    "🦜 طوطی‌ها می‌توانند بیش از ۱۰۰۰ کلمه یاد بگیرند.",
    "🐺 گرگ‌ها تا آخر عمر با یه همسر می‌مونن.",
    "☀️ خورشید ۹۹.۸٪ جرم منظومه شمسی رو تشکیل می‌ده.",
]

FACTS = [
    "🧠 مغز انسان ۲٪ وزن بدن را دارد اما ۲۰٪ انرژی مصرف می‌کند!",
    "🦷 مینای دندان سخت‌ترین ماده در بدن انسان است.",
    "??️ چشم انسان می‌تواند حدود ۱۰ میلیون رنگ را تشخیص دهد.",
    "💤 انسان در طول عمرش حدود ۲۵ سال می‌خوابد!",
    "🫀 قلب انسان روزانه حدود ۱۰۰,۰۰۰ بار می‌تپد.",
    "🩸 خون انسان در ۲۰ ثانیه یک دور کامل تو بدن می‌چرخه.",
    "🧬 DNA انسان ۹۹.۹٪ با شامپانزه‌ها یکسانه.",
    "👃 بینی انسان می‌تواند ۱ تریلیون بو رو تشخیص بده.",
    "💪 قوی‌ترین عضله بدن، عضله فک هست.",
    "🦴 بدن نوزاد ۳۰۰ استخوان داره که با بزرگ شدن به ۲۰۶ می‌رسه.",
    "🌡️ دمای بدن انسان در شب یک درجه کمتره.",
    "💧 بدن انسان ۶۰٪ آب هست.",
    "🧴 پوست انسان بزرگترین اندام بدن هست.",
    "🫁 ریه راست سه لوب و ریه چپ دو لوب داره.",
    "👂 گوش انسان می‌تواند ۳۴۰,۰۰۰ صدا رو تشخیص بده.",
    "🍽️ معده انسان هر ۳-۴ روز مخاط خودش رو بازسازی می‌کنه.",
    "🚶 انسان روزانه حدود ۶,۰۰۰ کلمه صحبت می‌کنه.",
    "😴 انسان‌ها ۱/۳ عمرشون رو می‌خوابن.",
    "🍔 روده انسان ۷.۵ متر طول داره.",
    "🔥 بدن انسان روزانه به اندازه ۲۰۰۰ کالری انرژی می‌سوزونه.",
]

PNP = [
    "پند: با دلِ خودت روراست باش. 💚",
    "پند: هرگز قضاوت نکن تا خودت در اون موقعیت قرار نگیری. ⚖️",
    "پند: موفقیت یعنی بلند شدن بعد از هر زمین خوردن. 💪",
    "پند: به کسی که پشت سرت حرف می‌زنه، پشتت رو نکن! 🙅",
    "پند: عمر آن‌قدر کوتاهه که وقت نداریم ناراحت باشیم. 🕰️",
    "پند: به هر کس اعتماد نکن، ولی به هیچ‌کس هم بی‌اعتماد نباش. 🤝",
    "پند: کار امروز رو به فردا ننداز. 📅",
    "پند: هر چه پیش آید خوش آید. 🌟",
    "پند: دنیا محل گذر است، پس مهربان باش. 🌍",
    "پند: با کسی که نمی‌فهمه بحث نکن. 🤐",
    "پند: سلامتی بهترین نعمته. 🌿",
    "پند: از سختی‌ها نترس، از تکرارشون بترس. 🔁",
    "پند: به پدر و مادرت احترام بذار. 👨‍👩‍👧",
    "پند: به کسی که دوستت داره، اذیت نکن. 💔",
    "پند: غیبت نکن، آبروی مردم رو نبر. 🤐",
    "پند: کمک به دیگران، شادی میاره. 🤲",
    "پند: به جای پول، انسانیت رو ذخیره کن. 💎",
    "پند: امروز بهترین روز زندگیته، قدرش رو بدون. ✨",
    "پند: به دیگران امید بده، نه یأس. 🌈",
    "پند: هر شب قبل خواب، برای فردا یه هدف تعیین کن. 🎯",
]

POEMS = [
    "دوش دیدم که ملائک در میخانه زدند / گل آدم بسرشتند و به پیمانه زدند. 🍷",
    "بنی آدم اعضای یک پیکرند / که در آفرینش ز یک گوهرند. 🤝",
    "توانا بود هر که دانا بود / ز دانش دل پیر برنا بود. 📚",
    "الا ای طوطی گویای اسرار / مبادا خاموشی در بزم یار. 🦜",
    "نه من از عشق تو دست برمی‌دارم / نه از سر عشقت می‌گذرم. 💕",
    "به دریا بنگرم دریا تو بینم / به صحرا بنگرم صحرا تو بینم. 🌊",
    "دلی دارم که از غم پر شده / ز عشق تو چه بی‌خبر شده. 💔",
    "تو همچون آفتابی، من چو ذره / که بی تو هستی من بی‌بهره. ☀️",
    "ای چشم و چراغ زندگی من / تو مونس دمی به دل‌نشینی من. 💫",
    "شب است و چشم من در انتظارت / دل من بی‌قرار دیدارت. 🌙",
    "من از روی تو گر دست بکشم / از جان و دل خود دست کشیدم. 🌹",
    "همه گویند که عشق دیر می‌آید / ولی آمد، دیر آمد، بی‌امان آمد. 💕",
    "دل من بی تو خونه خرابه / هیچکس تو این خونه نمی‌مونه. 🏚️",
    "عمر رفت و عشق موند در دلم / یاد تو همیشه با من و دلم. 💭",
    "بهار آمد، شکوفه داد درختم / ولی بی تو، باغ من شد خسته. 🌸",
    "مرا عهدیست با جانان که تا جان در بدن دارم / هواداران کویش را چو جان خویشتن دارم. 💖",
    "من اگر نیکم اگر بد، تو برو خود را باش / هر کسی آن درود عاقبت کار که کشت. 🌾",
    "توانگرا! تو اگر داشته باشی، بده / ولی یادت نره که روزی میری و میای. 💰",
    "دوش وقت سحر از غصه نجاتم دادند / واندر آن ظلمت شب آب حیاتم دادند. 🌙",
    "ای که مرا خوانده‌ای، راه نشانم بده / پاسخ عاشقانه‌ات را، شعر بخونم بده. 🎶",
]

FAL = [
    "🔮 **فال امروز:** روز خوبی در انتظارته! 🍀",
    "🔮 **فال امروز:** مراقب باش، یه نفر داره پشت سرت حرف می‌زنه. 🤫",
    "🔮 **فال امروز:** پول به دستت می‌رسه، ولی خرجش نکن! 💰",
    "🔮 **فال امروز:** خبر خوشی بهت می‌رسه. 📰",
    "🔮 **فال امروز:** یه سفر در انتظارته! ✈️",
    "🔮 **فال امروز:** یه دوست قدیمی پیدات می‌کنه. 🤝",
    "🔮 **فال امروز:** صبر کن، نتیجه می‌گیری. ⏳",
    "🔮 **فال امروز:** یه فرصت خوب پیش میاد، از دستش نده. 🎯",
    "🔮 **فال امروز:** مراقب سلامتی‌ات باش. 🌿",
    "🔮 **فال امروز:** دل کسی رو نشکن، آبروی خودت میره. 💔",
    "🔮 **فال امروز:** آرزو داری که برآورده می‌شه. ✨",
    "🔮 **فال امروز:** یه مکالمه مهم داری، دقت کن. 💬",
    "🔮 **فال امروز:** خوشحالیت نزدیکه. 😊",
    "🔮 **فال امروز:** یه هدیه غیرمنتظره می‌گیری. 🎁",
    "🔮 **فال امروز:** به کسی اعتماد نکن که بهت ثابت نکرده. 🚫",
    "🔮 **فال امروز:** دل به دریا بزن، موفق می‌شی. 🌊",
    "🔮 **فال امروز:** تو راه زندگی، یه تصمیم مهم داری. 🛤️",
    "🔮 **فال امروز:** از اشتباهات گذشته درس بگیر. 📖",
    "🔮 **فال امروز:** یه خبر خوب از طرف خانواده می‌رسه. 🏠",
    "🔮 **فال امروز:** امروز برات یه روز خاصه، قدرش رو بدون. 🌟",
]

LUCK = [
    "🍀 **شانس امروز:** ۱۰ از ۱۰! فوق‌العاده‌ست!",
    "🍀 **شانس امروز:** ۹ از ۱۰! عالیه!",
    "🍀 **شانس امروز:** ۸ از ۱۰! خوبه!",
    "🍀 **شانس امروز:** ۷ از ۱۰! معمولیه.",
    "🍀 **شانس امروز:** ۵ از ۱۰! یه ذره ضعیفه.",
    "🍀 **شانس امروز:** ۳ از ۱۰! مواظب باش.",
    "🍀 **شانس امروز:** ۱ از ۱۰! امروز از خونه نرو!",
    "🍀 **شانس امروز:** ۶ از ۱۰! متوسطه.",
    "🍀 **شانس امروز:** ۱۰ از ۱۰! آفرین به تو!",
    "🍀 **شانس امروز:** ۲ از ۱۰! یه ذره بدشانسی.",
    "🍀 **شانس امروز:** ۴ از ۱۰! معمولی.",
    "🍀 **شانس امروز:** ۹ از ۱۰! فوق‌العاده!",
    "🍀 **شانس امروز:** ۷ از ۱۰! روز خوبی داری.",
    "🍀 **شانس امروز:** ۵ از ۱۰! یه روز نرمال.",
    "🍀 **شانس امروز:** ۸ از ۱۰! رو به بالا.",
    "🍀 **شانس امروز:** ۱۰ از ۱۰! با شانس روز!",
    "🍀 **شانس امروز:** ۶ از ۱۰! نه خوب نه بد.",
    "🍀 **شانس امروز:** ۴ از ۱۰! یه ذره سختی.",
    "🍀 **شانس امروز:** ۹ از ۱۰! بخت یارت!",
    "🍀 **شانس امروز:** ۳ از ۱۰! حواست باشه.",
]

CHALLENGE_TEXTS = [
    "🎯 **چالش امروز:**\n\nبه ۳ نفر از اعضای این گروه یه تعریف **واقعی** بگو! 💬",
    "🔥 **چالش:**\n\nآخرین باری که به کسی کمک کردی کِی بود؟ همینجا تعریف کن! 🤝",
    "💪 **چالش ورزشی:**\n\nامروز ۲۰ تا اسکات برو، بعد بیا بگو انجام دادی! 🏋️",
    "📖 **چالش کتاب:**\n\nاسم آخرین کتابی که خوندی چیه؟ یه جمله ازش بگو! 📚",
    "🎵 **چالش موزیک:**\n\nآهنگی که این هفته بیشتر گوش دادی چیه؟ اسمش رو بگو! 🎧",
    "😊 **چالش مهربونی:**\n\nامروز به یه نفر که نمی‌شناسیش لبخند بزن و اینجا بگو چه حسی داشت! 😄",
    "🌟 **چالش رویا:**\n\nاگه یه آرزو داشتی، چی بود؟ اینجا بنویس! ✨",
    "🍕 **چالش غذا:**\n\nغذای مورد علاقه‌ات چیه و چرا؟ 🍔",
    "📸 **چالش خاطره:**\n\nقشنگ‌ترین خاطره‌ات از این هفته رو تعریف کن! 💭",
    "🎮 **چالش گیم:**\n\nآخرین بازی‌ای که انجام دادی چی بود؟ نظرت درباره‌ش چیه؟ 🕹️",
    "🎁 **چالش هدیه:**\n\nاگه می‌تونستی به یه نفر یه هدیه بدی، چی بود و به کی؟ 🎀",
    "🏃 **چالش حرکت:**\n\nیه کار خوب و بدون انتظار برای کسی انجام بده و بعد بیا تعریف کن! 💫",
    "🌸 **چالش احساس:**\n\nامروز چه حسی داری؟ با یه ایموجی توصیفش کن و بگو چرا! 💖",
    "🧠 **چالش فکری:**\n\nآخرین باری که یه چیز جدید یاد گرفتی کِی بود؟ چی بود؟ 📖",
    "🌙 **چالش شب:**\n\nقبل خواب به چی فکر می‌کنی؟ صادق باش! 💭",
]

CHALLENGE_POLLS = [
    ("تا حالا به کسی دروغ گفتی؟", ["بله 😅", "نه 🙅", "شایدم 😏"]),
    ("صبح‌ها زود بیدار می‌شی؟", ["بله ☀️", "نه 😴", "فقط جمعه‌ها ✨"]),
    ("قهوه یا چای؟", ["قهوه ☕", "چای 🍵", "هیچکدوم ❌"]),
    ("شب‌ها دیر می‌خوابی؟", ["بله 🌙", "نه 😇", "بعضی وقتا 😐"]),
    ("اهل ورزشی؟", ["بله 💪", "نه 😅", "تازه شروع کردم 🚀"]),
    ("فیلم ترجیح می‌دی یا سریال؟", ["فیلم 🎬", "سریال 📺", "هردو 🎭"]),
    ("تا حالا از گروهی اخراج شدی؟", ["بله 😬", "نه 😎", "زیاد 😅"]),
    ("گوشی اندروید داری یا آیفون؟", ["اندروید 🤖", "آیفون 🍎", "هردو 📱"]),
    ("اهل سفر هستی؟", ["بله ✈️", "نه 🏠", "کم پیش میاد 🚗"]),
    ("شیرینی دوست داری؟", ["عاشقشم 🍰", "نه 🚫", "کم می‌خورم 🍪"]),
    ("شب یا روز؟", ["شب 🌙", "روز ☀️", "هردو 🎭"]),
    ("آهنگ شاد یا غمگین؟", ["شاد 🎉", "غمگین 😢", "بستگی داره 🎵"]),
]


def build_challenge_message():
    mode = random.choice(["text", "text", "poll"])
    if mode == "text":
        challenge = random.choice(CHALLENGE_TEXTS)
        return (
            "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
            "   🎯 **چالش FLUXBOT** 🎯\n"
            "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
            f"{challenge}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "💡 **نظرت رو همینجا بگو!**\n\n"
            "⚡ **FLUXBOT**"
        )
    else:
        question, options = random.choice(CHALLENGE_POLLS)
        opts = "\n".join([f"{i+1}️⃣ {opt}" for i, opt in enumerate(options)])
        return (
            "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
            "   📊 **نظرسنجی FLUXBOT** 📊\n"
            "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
            f"❓ **{question}**\n\n"
            f"{opts}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "💡 **نظرت رو همینجا بگو!**\n\n"
            "⚡ **FLUXBOT**"
        )


# ================== 🎨 FONT SYSTEM ==================
def _has_latin(text):
    return bool(re.search(r'[A-Za-z]', text or ""))


def _map_unicode(text, upper_start, lower_start, digit_start=None):
    out = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            out.append(chr(upper_start + ord(ch) - ord('A')))
        elif 'a' <= ch <= 'z':
            out.append(chr(lower_start + ord(ch) - ord('a')))
        elif digit_start is not None and '0' <= ch <= '9':
            out.append(chr(digit_start + ord(ch) - ord('0')))
        else:
            out.append(ch)
    return ''.join(out)


def font_bold(t): return _map_unicode(t, 0x1D400, 0x1D41A, 0x1D7CE)
def font_italic(t):
    r = _map_unicode(t, 0x1D434, 0x1D44E)
    return r.replace(chr(0x1D455), "ℎ")
def font_bold_italic(t): return _map_unicode(t, 0x1D468, 0x1D482)
def font_bold_script(t): return _map_unicode(t, 0x1D4D0, 0x1D4EA)
def font_bold_fraktur(t): return _map_unicode(t, 0x1D56C, 0x1D586)
def font_sans(t): return _map_unicode(t, 0x1D5A0, 0x1D5BA, 0x1D7E2)
def font_sans_bold(t): return _map_unicode(t, 0x1D5D4, 0x1D5EE, 0x1D7EC)
def font_mono(t): return _map_unicode(t, 0x1D670, 0x1D68A, 0x1D7F6)


def font_fullwidth(t):
    out = []
    for ch in t:
        if 'A' <= ch <= 'Z': out.append(chr(0xFF21 + ord(ch) - ord('A')))
        elif 'a' <= ch <= 'z': out.append(chr(0xFF41 + ord(ch) - ord('a')))
        elif '0' <= ch <= '9': out.append(chr(0xFF10 + ord(ch) - ord('0')))
        elif ch == ' ': out.append('\u3000')
        else: out.append(ch)
    return ''.join(out)


SMALL_CAPS_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ',
    'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
    'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ',
    'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
    'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ', 'G': 'ɢ',
    'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ',
    'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 'U': 'ᴜ',
    'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ',
}


def font_small_caps(t): return ''.join(SMALL_CAPS_MAP.get(ch, ch) for ch in t)
def deco_strike(t): return ''.join(ch + '\u0336' for ch in t)
def deco_underline(t): return ''.join(ch + '\u0332' for ch in t)
def deco_overline(t): return ''.join(ch + '\u0305' for ch in t)
def deco_double_under(t): return ''.join(ch + '\u0333' for ch in t)
def deco_slash(t): return ''.join(ch + '\u0338' for ch in t)
def deco_dot_above(t): return ''.join(ch + '\u0307' for ch in t)


def build_font_message(text):
    text = (text or "").strip()
    if not text:
        return None
    if len(text) > 12:
        text = text[:12] + "…"

    styles = []

    if _has_latin(text):
        styles.append(font_bold(text))
        styles.append(font_italic(text))
        styles.append(font_bold_italic(text))
        styles.append(font_bold_script(text))
        styles.append(font_bold_fraktur(text))
        styles.append(font_sans(text))
        styles.append(font_sans_bold(text))
        styles.append(font_mono(text))
        styles.append(font_fullwidth(text))
        styles.append(font_small_caps(text))

    styles.append(deco_strike(text))
    styles.append(deco_underline(text))
    styles.append(deco_overline(text))
    styles.append(deco_double_under(text))
    styles.append(deco_slash(text))
    styles.append(deco_dot_above(text))
    styles.append(f"✿ {text} ✿")
    styles.append(f"❁ {text} ❁")
    styles.append(f"【 {text} 】")
    styles.append(f"「 {text} 」")
    styles.append(f"★彡 {text} 彡★")
    styles.append(f"༺ {text} ༻")
    styles.append(f"•°¯`•• {text} ••´¯°•")
    styles.append(f"▁▂▃ {text} ▃▂▁")
    styles.append(f"彡★ {text} ★彡")
    styles.append(f"☆ {text} ☆")

    lines = [f"🎨 فونت‌ساز | {text}", ""]
    for i, s in enumerate(styles, 1):
        lines.append(f"{i}- {s}")
    return "\n".join(lines)


# ================== Utility (ادامه) ==================
def clean_message(text):
    if not text: return ""
    text = re.sub(r"@\S+", "", text)
    # فقط اسلش‌هایی که اول کلمه هستن (نه توی URL)
    text = re.sub(r"(?<![/\w])/(\w+)", r"\1", text)
    return text.strip()


def normalize_text(text):
    if not text: return ""
    return re.sub(r'[^a-z0-9\u0600-\u06FF]', '', text.lower())


def is_group_chat(chat_id):
    return bool(chat_id) and str(chat_id).lower().startswith("g")


def is_private_chat(chat_id):
    if not chat_id: return False
    cid = str(chat_id).lower()
    return cid.startswith("u") or cid.startswith("b")


def get_now_time():
    return get_local_now().strftime("%H:%M - %Y/%m/%d")


def is_forwarded(message):
    for attr in ['forwarded_from', 'forward_from', 'forward', 'is_forwarded', 'fwd_from']:
        try:
            if getattr(message, attr, None): return True
        except: pass
    return False


def is_gif(message):
    for attr in ['is_gif', 'gif', 'animation', 'is_animation']:
        try:
            if getattr(message, attr, None): return True
        except: pass
    try:
        mt = str(getattr(message, 'type', '') or getattr(message, 'message_type', '')).lower()
        return 'gif' in mt or 'animation' in mt
    except: return False


# ═══════════════════════════════════════════════════════════════════
# 🆕 ۶ تابع جدید برای قفل‌های ایموجی، استیکر، عدد، انگلیسی، کلمات غیرمجاز
# ═══════════════════════════════════════════════════════════════════
def contains_emoji(text):
    """تشخیص ایموجی در متن"""
    if not text: return False
    for ch in str(text):
        cp = ord(ch)
        if (0x1F300 <= cp <= 0x1FAFF) or \
           (0x2600 <= cp <= 0x27BF) or \
           (0x1F000 <= cp <= 0x1F2FF) or \
           (0x2190 <= cp <= 0x21FF) or \
           (0x2B00 <= cp <= 0x2BFF) or \
           (0x1F1E6 <= cp <= 0x1F1FF) or \
           cp in (0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139,
                  0x3030, 0x303D, 0x3297, 0x3299, 0x20E3, 0xFE0F):
            return True
    return False


def is_sticker(message):
    """تشخیص استیکر از ویژگی‌های پیام و دادهٔ خام روبیکا"""
    if message is None:
        return False

    # Rubka Message normally exposes `.sticker`; other variants may expose
    # a sticker flag or a sticker-specific payload directly.
    for attr in (
        'sticker', 'is_sticker', 'sticker_message', 'sticker_id', 'stickerId',
        'sticker_file_id', 'sticker_file', 'sticker_data', 'isSticker',
    ):
        try:
            value = getattr(message, attr, None)
            if value:
                return True
        except Exception:
            pass

    for attr in (
        'type', 'message_type', 'content_type', 'media_type', 'file_type',
        'attachment_type', 'kind',
    ):
        try:
            value = getattr(message, attr, None)
            if value and 'sticker' in str(value).lower():
                return True
        except Exception:
            pass

    def _payload_has_sticker(value, depth=0):
        if depth > 5 or value is None:
            return False
        if isinstance(value, dict):
            for key, item in value.items():
                key_norm = str(key).replace('_', '').replace('-', '').lower()
                if key_norm in (
                    'sticker', 'issticker', 'stickermessage', 'stickerid',
                    'stickerfileid', 'stickerdata',
                ) and item not in (None, False, '', {}, []):
                    return True
                if key_norm in (
                    'type', 'messagetype', 'contenttype', 'mediatype',
                    'filetype', 'attachmenttype', 'kind',
                ) and 'sticker' in str(item).lower():
                    return True
                if isinstance(item, (dict, list, tuple)) and _payload_has_sticker(item, depth + 1):
                    return True
            return False
        if isinstance(value, (list, tuple)):
            return any(_payload_has_sticker(item, depth + 1) for item in value)
        return False

    for attr in ('raw_data', 'rawData', 'data', 'aux_data', 'auxData', 'message', 'media', 'attachment'):
        try:
            if _payload_has_sticker(getattr(message, attr, None)):
                return True
        except Exception:
            pass

    return False


def is_only_number(text):
    """تشخیص وجود عدد در هر جای پیام؛ ارقام انگلیسی، فارسی و عربی"""
    if not text:
        return False
    # isdecimal recognizes 0-9, Persian digits (۰۱۲۳) and Arabic-Indic digits (٠١٢٣).
    # Unlike the previous implementation, the digits do not need to form the whole message.
    return any(char.isdecimal() for char in str(text))


def is_english_text(text):
    """تشخیص اینکه پیام شامل حروف انگلیسی هست"""
    if not text: return False
    return bool(re.search(r'[A-Za-z]', str(text)))


FORBIDDEN_BIO_WORDS = [
    "بایو چک", "بیو چک", "بیوچک", "بایوچک",
    "بیوگرافی رو ببین", "بیوگرافی ببین", "بیو رو ببین", "بایو رو ببین",
    "بیوگرافی من", "بیو من", "بایو من",
    "بیو رو چک کن", "بایو رو چک کن", "بیو چک کن",
    "تو بیوم هست", "تو بایوم هست",
    "بیوگرافی", "بایو", "بیو",
    "برو بیومو ببین", "برو بایومو ببین", "بیومو چک کن", "بایومو چک کن",
    "بیوگرافیمو ببین", "بایوگرافیمو ببین", "بیوگرافی منو ببین", "بایوگرافی منو ببین",
    "بیوگرافی رو چک کن", "بایوگرافی رو چک کن", "بیوگرافی رو بخون", "بایوگرافی رو بخون",
    "بیو رو بخون", "بایو رو بخون", "بیوم رو بخون", "بایوم رو بخون",
    "نگاه کن بیو", "نگاه به بیو", "نگاه به بایو", "نگاه به بیوم بنداز", "نگاه به بایوم بنداز",
    "برو تو بیو", "برو تو بایو", "داخل بیو", "داخل بایو", "تو بیو", "تو بایو",
    "بیو رو ببین لطفا", "بایو رو ببین لطفا", "بیوگرافی رو ببین لطفا", "بایوگرافی رو ببین لطفا",
    "پروفایلمو ببین", "پروفایلم رو ببین", "پروفایل منو ببین", "پروفایل رو چک کن",
    "بیوم تو پروفایلمه", "بایوم تو پروفایلمه", "تو پروفایلم بیو هست", "بیو داخل پروفایل",
    "bio check", "check bio", "check my bio", "look at my bio", "see my bio",
    "my bio", "bio in profile", "check my profile", "look at my profile",
    "biyoo check", "biochack", "byo check", "bayo check",

]


def contains_forbidden_bio(text):
    """تشخیص کلمات غیرمجاز بیوگرافی"""
    if not text: return None
    t = str(text).lower().replace('\u200c', ' ').replace('\u200d', ' ')
    for w in FORBIDDEN_BIO_WORDS:
        nw = w.lower().replace('\u200c', ' ')
        if nw and nw in t:
            return w
    return None


# نسخهٔ تکمیلی تشخیص بیو: نادیده گرفتن فاصله، نیم‌فاصله و علائم نگارشی
# و بررسی عبارت‌های بلندتر قبل از کلیدواژه‌های کوتاه‌تر.
FORBIDDEN_BIO_WORDS.extend([
    "بایوگرافی", "بیوگرافی", "بیوچک", "بایوچک", "بیو چک", "بایو چک",
    "بیوگرافی رو ببین", "بایوگرافی رو ببین", "بیوگرافی رو چک کن", "بایوگرافی رو چک کن",
    "بیو رو چک کن", "بایو رو چک کن", "بیو رو ببین", "بایو رو ببین",
    "بیومو ببین", "بایومو ببین", "بیوم رو ببین", "بایوم رو ببین",
    "بیو رو بخون", "بایو رو بخون", "بیومو چک کن", "بایومو چک کن",
    "bio check", "check bio", "check my bio", "look at my bio", "see my bio",
])


def contains_forbidden_bio(text):
    if not text:
        return None
    _normalized_text = normalize_text(str(text).replace("ـ", ""))
    if not _normalized_text:
        return None
    _normalized_terms = sorted(
        ((normalize_text(str(_word).replace("ـ", "")), _word)
         for _word in FORBIDDEN_BIO_WORDS),
        key=lambda _item: len(_item[0]), reverse=True,
    )
    for _normalized_word, _original_word in _normalized_terms:
        if _normalized_word and _normalized_word in _normalized_text:
            return _original_word
    return None
# ═══════════════════════════════════════════════════════════════════


def contains_id(text):
    """تشخیص آیدی — @username، @[id]، u/b ID خالص"""
    if not text: return False
    # @username
    if re.search(r'@[\w\.\-]+', text): return True
    # @[user_id] (mention entity روبیکا)
    if re.search(r'@\[[^\]]+\]', text): return True
    # Rubika user/bot IDs: u/b + 15+ alphanumeric chars
    if re.search(r'(?<![A-Za-z0-9])[ub][A-Za-z0-9]{15,}(?![A-Za-z0-9])', text): return True
    return False


def is_command(text, *cmds):
    if not text: return False
    t = text.strip()
    return any(t == c for c in cmds)


def contains_filtered_word(text, lst):
    if not text or not lst: return None
    n = normalize_text(text)
    if not n: return None
    for w in lst:
        nw = normalize_text(w)
        if nw and nw in n: return w
    return None


def contains_profanity(text):
    """تشخیص فحش — کلمات کوتاه فقط تطبیق کامل توکن"""
    if not text: return None
    n = normalize_text(text)
    if not n: return None
    global _PROFANITY_NORMALIZED
    if _PROFANITY_NORMALIZED is None:
        _PROFANITY_NORMALIZED = [(normalize_text(w), w) for w in PROFANITY_LIST if normalize_text(w)]

    raw_words = set(normalize_text(w) for w in re.split(r'\s+', text) if w)

    for nw, orig in _PROFANITY_NORMALIZED:
        if not nw:
            continue
        if len(nw) <= 3:
            if nw in raw_words:
                return orig
        else:
            if nw in n:
                return orig
    return None


def get_remaining_time(end_time):
    d = end_time - time.time()
    if d <= 0: return "0 ثانیه"
    h = int(d // 3600); m = int((d % 3600) // 60); s = int(d % 60)
    p = []
    if h > 0: p.append(f"{h} ساعت")
    if m > 0: p.append(f"{m} دقیقه")
    if s > 0 and h == 0: p.append(f"{s} ثانیه")
    return " و ".join(p) if p else "0 ثانیه"


def is_group_locked(chat_id):
    group_locks = bot_data.get("group_locks", {})
    if not isinstance(group_locks, dict):
        group_locks = {}
        bot_data["group_locks"] = group_locks
    if group_locks.get(chat_id, False): return True, "قفل دستی"
    temp_locks_now = bot_data.get("temp_locks", {})
    if not isinstance(temp_locks_now, dict):
        temp_locks_now = {}
        bot_data["temp_locks"] = temp_locks_now
    if chat_id in temp_locks_now:
        try:
            et = float(temp_locks_now[chat_id])
        except (TypeError, ValueError):
            et = 0
        if time.time() < et:
            temp_locks_now[chat_id] = et
            return True, f"قفل موقت (پایان: {datetime.fromtimestamp(et, tz=IRAN_TZ).strftime('%H:%M')})"
        else:
            del temp_locks_now[chat_id]
            save_data(bot_data)
    scheduled = bot_data.get("scheduled_locks", {})
    if not isinstance(scheduled, dict):
        scheduled = {}
        bot_data["scheduled_locks"] = scheduled
    if chat_id in scheduled and scheduled[chat_id]:
        now = get_local_now()
        cm = now.hour * 60 + now.minute
        for interval in scheduled[chat_id]:
            try:
                sh, sm, eh, em = map(int, interval)
                if not (0 <= sh <= 23 and 0 <= sm <= 59 and
                        0 <= eh <= 23 and 0 <= em <= 59):
                    continue
            except (TypeError, ValueError):
                continue
            s, e = sh * 60 + sm, eh * 60 + em
            ts = f"{sh:02d}:{sm:02d} تا {eh:02d}:{em:02d}"
            if s <= e:
                if s <= cm < e: return True, f"قفل زمان‌بندی ({ts})"
            else:
                if cm >= s or cm < e: return True, f"قفل زمان‌بندی ({ts})"
    return False, ""


def get_warn_delete_after(chat_id):
    try: return int(bot_data.get("warn_delete_after", {}).get(chat_id, 0))
    except: return 0


async def add_warning(chat_id, user_id, reason="", user_info=None):
    try:
        user_id = str(user_id)
        if not isinstance(bot_data.get("warnings"), dict):
            bot_data["warnings"] = {}
        if not isinstance(bot_data["warnings"].get(chat_id), dict):
            bot_data["warnings"][chat_id] = {}
        try:
            previous_count = int(bot_data["warnings"][chat_id].get(user_id, 0))
        except (TypeError, ValueError):
            previous_count = 0
        count = max(0, previous_count) + 1
        bot_data["warnings"][chat_id][user_id] = count

        if not isinstance(bot_data.get("warn_limit"), dict):
            bot_data["warn_limit"] = {}
        try:
            limit = max(1, int(bot_data["warn_limit"].get(chat_id, 3)))
        except (TypeError, ValueError):
            limit = 3
        save_data(bot_data, force=True)
        del_after = get_warn_delete_after(chat_id)
        wt = (
            f"⚠️ اخطار ثبت شد ⚠️\n\n"
            f"👤 کاربر: {USER_MENTION_TOKEN}\n"
            f"📌 دلیل: {reason if reason else 'تخلف از قوانین'}\n"
            f"📊 تعداد اخطارها: {count} از {limit}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n⚡ FLUXBOT"
        )
        try:
            result = await send_user_mention_message(chat_id, user_id, wt)
            if del_after > 0:
                mid = extract_msg_id(result)
                if mid: await schedule_delete(chat_id, mid, del_after)
        except Exception as e:
            print(f"⚠️ warn send: {e}", flush=True)
        if count >= limit and settings.get("auto_ban", True):
            try:
                await bot.ban_member_chat(chat_id, user_id)
                if not isinstance(bot_data.get("banned_users"), dict):
                    bot_data["banned_users"] = {}
                if not isinstance(bot_data["banned_users"].get(chat_id), dict):
                    bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][user_id] = time.time()
                save_data(bot_data, force=True)
                bm = (
                    f"🚫 کاربر اخراج شد\n\n"
                    f"👤 کاربر: {USER_MENTION_TOKEN}\n"
                    f"📊 تعداد اخطارها: {count} از {limit}"
                )
                try:
                    result = await send_user_mention_message(chat_id, user_id, bm)
                    if del_after > 0:
                        mid = extract_msg_id(result)
                        if mid: await schedule_delete(chat_id, mid, del_after)
                except Exception as e:
                    print(f"⚠️ ban msg: {e}", flush=True)
                bot_data["warnings"][chat_id][user_id] = 0
                save_data(bot_data, force=True)
                return True
            except Exception as e:
                print(f"⚠️ ban: {e}", flush=True)
        return False
    except Exception as e:
        print(f"❌ add_warning: {e}", flush=True)
        return False


def register_user(uid):
    try:
        if not uid: return
        if not isinstance(bot_data.get("started_users"), list):
            bot_data["started_users"] = ensure_list(bot_data.get("started_users"))
        if uid not in bot_data["started_users"]:
            bot_data["started_users"].append(uid)
            save_data(bot_data)
    except Exception as e:
        print(f"⚠️ register_user: {e}", flush=True)


def register_group(gid):
    try:
        if not gid: return
        if not isinstance(bot_data.get("known_groups"), list):
            bot_data["known_groups"] = ensure_list(bot_data.get("known_groups"))
        if gid not in bot_data["known_groups"]:
            bot_data["known_groups"].append(gid)
            save_data(bot_data, force=True)
    except Exception as e:
        print(f"⚠️ register_group: {e}", flush=True)


def build_keypad():
    try:
        b = ChatKeypadBuilder()
        b1 = b.button_simple(id="btn_channel", text=BTN_CHANNEL)
        b2 = b.button_simple(id="btn_help", text=BTN_HELP)
        b3 = b.button_simple(id="btn_users", text=BTN_USERS)
        b4 = b.button_simple(id="btn_groups", text=BTN_GROUPS)
        b5 = b.button_simple(id="btn_dev", text=BTN_DEV)
        b6 = b.button_simple(id="btn_invite_enter", text=BTN_INVITE_ENTER)
        b7 = b.button_simple(id="btn_invite_show", text=BTN_INVITE_SHOW)
        b8 = b.button_simple(id="btn_points", text=BTN_POINTS)
        b9 = b.button_simple(id="btn_features", text=BTN_FEATURES)
        b10 = b.button_simple(id="btn_top_inviters", text=BTN_TOP_INVITERS)
        b.row(b1, b2); b.row(b3, b4); b.row(b5)
        b.row(b6, b7); b.row(b8, b9); b.row(b10)
        return b.build()
    except Exception as e:
        print(f"❌ KEYPAD: {e}", flush=True)
        return None


def extract_button_id(message):
    """Read keypad IDs across common Rubika message/aux-data shapes."""
    values = []
    for attr in ("button_id", "buttonId", "callback_data", "callbackData"):
        try:
            value = getattr(message, attr, None)
            if value is not None:
                values.append(value)
        except Exception:
            pass

    for attr in ("aux_data", "auxData"):
        try:
            value = getattr(message, attr, None)
            if value is not None:
                values.append(value)
        except Exception:
            pass

    # aux_data is normally a mapping, but some clients serialize it as JSON.
    expanded = []
    for value in values:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                pass
        expanded.append(value)

    id_keys = ("button_id", "buttonId", "callback_data", "callbackData", "id")
    nested_keys = ("data", "button", "payload", "aux_data", "auxData")
    seen = set()
    while expanded:
        value = expanded.pop(0)
        marker = id(value)
        if marker in seen:
            continue
        seen.add(marker)
        if isinstance(value, dict):
            for key in id_keys:
                candidate = value.get(key)
                if isinstance(candidate, (str, int)) and str(candidate).strip():
                    return str(candidate).strip()
            for key in nested_keys:
                nested = value.get(key)
                if nested is not None:
                    if isinstance(nested, str):
                        try:
                            nested = json.loads(nested)
                        except (TypeError, ValueError):
                            pass
                    expanded.append(nested)
        elif isinstance(value, (str, int)):
            candidate = str(value).strip()
            if candidate.startswith("btn_"):
                return candidate
    return None


def get_channel_text():
    return "📢 **کانال رسمی FluxBot**\n\n➣ **@RPCITY_PHANTOM**\n\n🌟 لطفاً در کانال رسمی ما عضو شوید. 🙏\n\n⚡ **FLUXBOT**"


def get_education_text():
    return (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   📚 آموزش فعال‌سازی 📚\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        "🌟 **مراحل فعال‌سازی:**\n\n"
        "1️⃣ **افزودن ربات به گروه**\n\n"
        "2️⃣ **دسترسی کامل بدهید:**\n"
        "├ ربات را **ادمین** کنید\n"
        "├ دسترسی «حذف پیام» فعال\n"
        "└ دسترسی «مشاهده پیام‌ها» فعال\n\n"
        "3️⃣ **حریم خصوصی:**\n"
        "└ «دریافت همه پیام‌های گروه» را فعال کنید\n\n"
        "4️⃣ **منتظر بمانید:** ۱ تا ۲ دقیقه\n\n"
        "5️⃣ **فعال‌سازی:** در گروه بنویسید `فعال`\n\n"
        "📢 **کانال رسمی:** @RPCITY_PHANTOM\n\n"
        "⚡ **FLUXBOT** | جریان قدرت"
    )


def get_dev_text():
    return (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n   👑 **سازنده ربات** 👑\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        "💎 **FluxBot** توسط این شخص ساخته شده:\n\n"
        "🌟 **سازنده:** @arastoo_ff\n\n"
        "🛠️ **مسئولیت‌ها:**\n"
        "├ 🤖 طراحی ربات\n├ 🎨 طراحی UI\n├ 🔧 رفع باگ\n└ 💡 توسعه\n\n"
        "💬 **ارتباط:** @arastoo_ff\n\n"
        "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"
    )


def get_help_text():
    return (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   📚 راهنما 📚\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        "👤 **کاربران:**\n"
        "├ 👑 `مقام` / `رتبه`\n├ 📊 `پروفایل`\n├ 🏆 `آمار گروه`\n├ ⏰ `ساعت`\n"
        "├ 📜 `قوانین`\n"
        "├ 🐺 `تنظیم اصل [نام]`\n├ 🎭 `تنظیم لقب [نام]`\n"
        "├ 🎨 `فونت [متن]` → فونت‌ساز\n"
        "├ 🎯 `چالش` → چالش روزانه\n"
        "├ 🎰 `شرط بندی` → بازی شرط\n"
        "├ 💬 `فلکس بات` → جواب رندوم\n"
        "├ 🎟️ `زدن کد دعوت`\n├ 🎫 `کد دعوت من`\n├ ⭐ `امتیاز من`\n"
        "├ 📖 `قابلیت‌های ربات`\n"
        "├ 🏆 `لیست برتر دعوت‌کنندگان`\n├ 🎮 `لیست بازی`\n"
        "├ 😂 `جک` / 📜 `ضرب المثل`\n├ 💡 `دانستی` / 🧠 `فکت`\n"
        "├ 💚 `پ ن پ` / 📝 `شعر`\n├ 🔮 `فال` / 🍀 `شانس`\n"
        "└ 📚 `راهنما`\n\n"
        "🎮 **بازی‌ها (گروه):**\n"
        "├ 🎲 `دوز` / `دوز قرمز` / `دوز زرد`\n"
        "├ 👥 `شرکت` → پیوستن\n"
        "├ 🎯 `1` تا `7` → انداختن مهره\n"
        "├ 🪙 `بازی شیر یا خط`\n"
        "└ 🚫 `انصراف` → لغو\n\n"
        "🔓 **قفل‌ها (هر دو ترتیب):**\n"
        "├ `لینک قفل` / `قفل لینک`\n"
        "├ `آیدی قفل` / `قفل آیدی`\n"
        "├ `اسپم قفل` / `قفل اسپم`\n"
        "├ `فحش قفل` / `قفل فحش`\n"
        "├ `فوروارد قفل` / `قفل فوروارد`\n"
        "├ `گیف قفل` / `قفل گیف`\n"
        "├ `ایموجی قفل` / `قفل ایموجی`\n"
        "├ `استیکر قفل` / `قفل استیکر`\n"
        "├ `عدد قفل` / `قفل عدد`\n"
        "├ `انگلیسی قفل` / `قفل انگلیسی`\n"
        "├ `کلمات غیرمجاز قفل` / `قفل کلمات غیرمجاز`\n"
        "├ `بیوچک قفل` / `قفل بیوچک`\n"
        "├ `ویرایش قفل` / `قفل ویرایش`\n"
        "├ `سخنگو بسته` / `بسته سخنگو`\n"
        "├ `شرط بندی بسته` / `بسته شرط بندی`\n"
        "└ `هایپرلینک قفل` / `قفل هایپرلینک`\n\n"
        "👑 **مالک / ویژه:**\n"
        "├ ✅ `فعال` / 🛑 `غیرفعال`\n"
        "├ 🚫 `بن` / `سیک` / `اخراج` (ریپلای)\n"
        "├ ✅ `انبن` (ریپلای)\n"
        "├ 🔇 `سکوت [دقیقه]` (ریپلای)\n"
        "├ ⚠️ `اخطار` (ریپلای)\n"
        "├ ❌ `حذف اخطار` (ریپلای)\n"
        "├ ⚙️ `تنظیم اخطار [عدد]`\n"
        "├ ⏱️ `حذف پیام اخطار [ثانیه]`\n"
        "├ ⭐ `ویژه` / ❌ `حذف ویژه`\n"
        "├ 🚫 `فیلتر [کلمه]`\n"
        "├ 📋 `لیست فیلتر`\n"
        "├ 📝 `تنظیم قوانین [متن]`\n"
        "├ 🔁 `تنظیم ضد تکرار [۲-۱۰]`\n"
        "├ 🐌 `تنظیم حالت آهسته [زمان]`\n"
        "├ 🧹 `پاکسازی [عدد]`\n"
        "├ 📢 `ارسال پیام همگانی گروه [متن]` (فقط مالک)\n"
        "└ 📋 `لیست گروه ها` (توی پیوی)\n\n"
        "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"
    )


def get_users_text():
    c = len(ensure_list(bot_data.get("started_users", [])))
    return f"👥 **کاربران:** **{c}**\n\n⚡ **FLUXBOT**"


async def get_groups_text():
    groups = ensure_list(bot_data.get("known_groups", []))
    if not groups:
        return f"🏠 **گروه‌های فعال:** **0**\n\n⚡ **FLUXBOT**"
    live = []
    dead = []
    for gid in groups:
        is_alive, err = await validate_group(gid)
        if is_alive:
            live.append(gid)
        else:
            dead.append(gid)
            print(f"🗑️ [groups_btn] حذف گروه مرده: {gid} | {err}", flush=True)
        await asyncio.sleep(0.15)
    if dead:
        bot_data["known_groups"] = live
        save_data(bot_data, force=True)
        for gid in dead:
            group_info_cache.pop(gid, None)
            group_info_cache_ttl.pop(gid, None)
    return f"🏠 **گروه‌های فعال:** **{len(live)}**\n\n⚡ **FLUXBOT**"


async def get_top_inviters_text():
    top = get_top_inviters(10)
    if not top:
        return "🏆 **لیست برتر دعوت‌کنندگان**\n\n📭 هنوز دعوتی ثبت نشده.\n\n💡 با دکمه «🎫 کد دعوت من» شروع کن!\n\n⚡ **FLUXBOT**"
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = []
    for i, (uid, count) in enumerate(top):
        display = get_display_for_user(uid)
        lines.append(f"{medals[i]} {display} — **{count}** دعوت")
    return (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
        "   ⚡ **FLUXBOT** ⚡\n"
        "   🏆 برترین دعوت‌کنندگان 🏆\n"
        "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        + "\n".join(lines) +
        "\n\n━━━━━━━━━━━━━━━━━━━\n💡 روی نام کاربری کلیک کن!\n\n⚡ **FLUXBOT**"
    )


async def process_invite_code(chat_id, user_id, code):
    code = str(code).strip()
    if "invited_users" not in bot_data: bot_data["invited_users"] = {}
    if "code_to_user" not in bot_data: bot_data["code_to_user"] = {}
    user_id = str(user_id)
    if user_id in bot_data["invited_users"]:
        return "❌ شما قبلاً با کد دعوت وارد شده‌اید!"
    own_code = bot_data.get("invite_codes", {}).get(user_id)
    if own_code and own_code == code:
        return "❌ نمی‌توانید کد خودتان را وارد کنید!"
    owner_id = bot_data["code_to_user"].get(code)
    if not owner_id:
        return f"❌ کد دعوت اشتباه است!\n\n📌 کد: `{code}`\n🔍 پیدا نشد."
    bot_data["invited_users"][user_id] = owner_id
    if "points" not in bot_data: bot_data["points"] = {}
    bot_data["points"][owner_id] = bot_data["points"].get(owner_id, 0) + 1
    bot_data["points"][user_id] = bot_data["points"].get(user_id, 0) + 1
    save_data(bot_data, force=True)
    owner_display = get_display_for_user(owner_id)
    try:
        oi = await get_user_info(chat_id, owner_id)
        owner_display = format_user_display(oi, owner_id)
    except Exception as e:
        print(f"⚠️ owner display: {e}", flush=True)
    return (
        f"✅ **تبریک!**\n\n🎉 با کد دعوت وارد شدید!\n\n"
        f"👤 **صاحب کد:** {owner_display}\n⭐ +۱ امتیاز\n⭐ شما +۱ امتیاز\n\n"
        f"💎 **امتیاز فعلی:** {get_points(user_id)}\n\n⚡ **FLUXBOT**"
    )


def get_welcome_text(chat_id, chat_name, display_name):
    custom = bot_data.get("custom_welcome", {}).get(chat_id)
    now_str = get_now_time()
    if custom:
        text = custom.replace("{name}", display_name)
        text = text.replace("{group}", chat_name)
        text = text.replace("{time}", now_str)
        return text
    return (
        f"╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   🌊 جریان قدرت 🌊\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        f"🌟 **به گروه {chat_name} خوش آمدید!** 🌟\n\n"
        f"👤 **{display_name} عزیز:**\nخوشحالیم که به ما پیوستید. 🌹\n\n"
        f"⏰ **ورود:** {now_str}\n\n"
        f"💎 **امکانات:**\n"
        f"├ 📊 `پروفایل`\n├ 🎮 `دوز`\n"
        f"├ 📜 `قوانین`\n└ 📚 `راهنما`\n\n⚡ **FLUXBOT**"
    )


async def bulk_cleanup(chat_id, sender_id, limit):
    c = load_cache()
    if chat_id not in c: return 0, 0
    msgs = [(mid, sid) for mid, sid in c[chat_id].items() if str(sid) == str(sender_id)]
    msgs.sort(key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0, reverse=True)
    deleted = 0
    failed = 0
    for mid, _ in msgs[:limit]:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=mid)
            deleted += 1
            await asyncio.sleep(0.15)
        except Exception as e:
            failed += 1
            print(f"⚠️ bulk delete {mid}: {e}", flush=True)
    return deleted, failed


async def handle_repeat_check(chat_id, user_id, msg_id, text, limit, user_info):
    if not text or not msg_id: return False
    normalized = normalize_text(text)
    if not normalized: return False
    now = time.time()
    if chat_id not in repeat_tracker: repeat_tracker[chat_id] = {}
    if user_id not in repeat_tracker[chat_id]:
        repeat_tracker[chat_id][user_id] = {"text": "", "count": 0, "ids": [], "last_ts": now}
    tracker = repeat_tracker[chat_id][user_id]
    if now - tracker["last_ts"] > 30:
        tracker["text"] = normalized
        tracker["count"] = 1
        tracker["ids"] = [str(msg_id)]
        tracker["last_ts"] = now
        return False
    if tracker["text"] == normalized:
        tracker["count"] += 1
        tracker["ids"].append(str(msg_id))
        tracker["last_ts"] = now
        if tracker["count"] >= limit:
            ids_to_delete = tracker["ids"][:]
            tracker["text"] = ""
            tracker["count"] = 0
            tracker["ids"] = []
            tracker["last_ts"] = now
            for mid in ids_to_delete:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=mid)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"⚠️ repeat delete {mid}: {e}", flush=True)
            try:
                if settings.get("warning"):
                    await add_warning(chat_id, user_id, f"ارسال {limit} پیام یکسان پشت سر هم", user_info=user_info)
                else:
                    await send_user_mention_message(chat_id, user_id, (
                        f"🔁 ضد تکرار فعال است!\n\n"
                        f"👤 {USER_MENTION_TOKEN}\n"
                        f"📌 {limit} پیام یکسان شما پاک شد.\n\n⚡ FLUXBOT"))
            except Exception as e:
                print(f"⚠️ repeat warn: {e}", flush=True)
            return True
    else:
        tracker["text"] = normalized
        tracker["count"] = 1
        tracker["ids"] = [str(msg_id)]
        tracker["last_ts"] = now
    return False


async def handle_slow_mode(chat_id, user_id, seconds, user_info):
    now = time.time()
    if chat_id not in slow_tracker: slow_tracker[chat_id] = {}
    last = slow_tracker[chat_id].get(user_id, 0)
    if now - last < seconds:
        slow_tracker[chat_id][user_id] = now
        return True
    slow_tracker[chat_id][user_id] = now
    return False


async def handle_spam_check(chat_id, sender_id, msg_id, user_info):
    now = time.time()
    if chat_id not in spam_tracker: spam_tracker[chat_id] = {}
    if sender_id not in spam_tracker[chat_id]: spam_tracker[chat_id][sender_id] = []
    spam_tracker[chat_id][sender_id].append({"t": now, "id": str(msg_id)})
    spam_tracker[chat_id][sender_id] = [e for e in spam_tracker[chat_id][sender_id] if now - e["t"] < SPAM_WINDOW]
    entries = spam_tracker[chat_id][sender_id]
    if len(entries) >= SPAM_LIMIT:
        ids_to_delete = [e["id"] for e in entries]
        spam_tracker[chat_id][sender_id] = []
        for mid in ids_to_delete:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=mid)
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"⚠️ spam delete {mid}: {e}", flush=True)
        try:
            if settings.get("warning"):
                await add_warning(chat_id, sender_id, "ارسال اسپم", user_info=user_info)
        except Exception as e:
            print(f"⚠️ spam warn: {e}", flush=True)
        return True
    return False


# ================== 🖊️ EDIT HANDLER ==================
async def process_edited_message(message, chat_id, sender_id, raw_text, new_text):
    try:
        if not is_group_chat(chat_id): return
        if not bot_is_active: return
        ui = await get_user_info(chat_id, sender_id)
        role = ui["role"]
        is_owner_group = (role == "مالک")
        is_special = bot_data.get("special_users", {}).get(chat_id, {}).get(sender_id, False)
        can_manage = is_owner_group or is_special
        # ✏️ قفل ویرایش — قبل از can_manage که برای همه (حتی ادمین) کار کنه
        if settings.get("edit", False):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings.get("warning"):
                    await add_warning(chat_id, sender_id, "ویرایش پیام", user_info=ui)
                print(f"🗑️ [EDIT] پاک شد | {chat_id}", flush=True)
            except Exception as e:
                print(f"⚠️ delete edit failed: {e}", flush=True)
            return
        if can_manage: return
        locked, _ = is_group_locked(chat_id)
        if locked:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except: pass
            return
        chat_mutes = bot_data.get("mute_list", {}).get(chat_id, {})
        if sender_id in chat_mutes and time.time() < chat_mutes[sender_id]:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except: pass
            return
        if settings.get("profanity", True) and contains_profanity(new_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings.get("warning"):
                    await add_warning(chat_id, sender_id, "فحش (ویرایش)", user_info=ui)
            except: pass
            return
        if settings.get("filter"):
            fl = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if contains_filtered_word(new_text, fl):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "کلمه فیلترشده (ویرایش)", user_info=ui)
                except: pass
                return
        if settings.get("link") and contains_link(new_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings.get("warning"):
                    await add_warning(chat_id, sender_id, "لینک (ویرایش)", user_info=ui)
            except: pass
            return
        if settings.get("hyperlink") and contains_hyperlink(new_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings.get("warning"):
                    await add_warning(chat_id, sender_id, "هایپرلینک (ویرایش)", user_info=ui)
            except: pass
            return
        if settings.get("id") and contains_id(new_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings.get("warning"):
                    await add_warning(chat_id, sender_id, "آیدی (ویرایش)", user_info=ui)
            except: pass
            return
        if settings.get("forward", False) and is_forwarded(message):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings.get("warning"):
                    await add_warning(chat_id, sender_id, "فوروارد (ویرایش)", user_info=ui)
            except: pass
            return
        if settings.get("gif", False) and is_gif(message):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings.get("warning"):
                    await add_warning(chat_id, sender_id, "گیف (ویرایش)", user_info=ui)
            except: pass
            return
    except Exception as e:
        print(f"❌ process_edited_message: {e}", flush=True)


# تکمیل پردازش پیام ویرایش‌شده: قفل‌های جدید نیز مثل قفل‌های فعلی حذف/اخطار می‌دهند.
async def process_edited_message(message, chat_id, sender_id, raw_text, new_text):
    try:
        if not is_group_chat(chat_id) or not bot_is_active:
            return
        ui = await get_user_info(chat_id, sender_id)
        role = ui.get("role", "عضو")
        is_owner_group = role == "مالک"
        is_special = bot_data.get("special_users", {}).get(chat_id, {}).get(sender_id, False)
        can_manage = is_owner_group or is_special

        async def _delete_edit(reason, log_tag=None):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except Exception as _err:
                print(f"⚠️ delete edited message ({reason}): {_err}", flush=True)
            if settings.get("warning"):
                try:
                    await add_warning(chat_id, sender_id, reason, user_info=ui)
                except Exception as _err:
                    print(f"⚠️ edited warning ({reason}): {_err}", flush=True)
            if log_tag:
                print(f"🗑️ [{log_tag}] پیام ویرایش‌شده پاک شد | {chat_id}", flush=True)

        # قفل ویرایش باید پیش از معافیت مدیران بررسی شود؛ مطابق رفتار قبلی.
        if settings.get("edit", False):
            await _delete_edit("ویرایش پیام", "EDIT")
            return

        _edit_filter_control_words = (
            "لینک", "آیدی", "اسپم", "هایپرلینک", "فحش", "فوروارد", "هدایت",
            "گیف", "ایموجی", "استیکر", "عدد", "انگلیسی", "کلمات غیرمجاز",
            "کلمات غیر مجاز", "کلمه غیرمجاز", "کلمه غیر مجاز", "بیو", "بایو",
            "بیوچک", "بایوچک", "بیو چک", "بایو چک", "ویرایش",
        )
        _edit_clean_text = clean_message(new_text)
        _edit_is_filter_control = can_manage and any(
            match_two_word_cmd(_edit_clean_text, _lock_word, FILTER_ON, FILTER_OFF) is not None
            for _lock_word in _edit_filter_control_words
        )
        if can_manage:
            if not _edit_is_filter_control:
                if settings.get("emoji", False) and contains_emoji(new_text):
                    await _delete_edit("ارسال ایموجی (ویرایش)", "EMOJI")
                    return
                if settings.get("sticker", False) and is_sticker(message):
                    await _delete_edit("ارسال استیکر (ویرایش)", "STICKER")
                    return
                if settings.get("number", False) and is_only_number(new_text):
                    await _delete_edit("ارسال عدد (ویرایش)", "NUMBER")
                    return
                if settings.get("english", False) and is_english_text(new_text):
                    await _delete_edit("ارسال متن انگلیسی (ویرایش)", "ENGLISH")
                    return
                if settings.get("forbidden_words", False) and contains_forbidden_bio(new_text):
                    await _delete_edit("کلمات غیرمجاز (ویرایش)", "BIO")
                    return
            return

        locked, _ = is_group_locked(chat_id)
        if locked:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except Exception:
                pass
            return

        chat_mutes = bot_data.get("mute_list", {}).get(chat_id, {})
        if sender_id in chat_mutes and time.time() < chat_mutes[sender_id]:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except Exception:
                pass
            return

        if settings.get("profanity", True) and contains_profanity(new_text):
            await _delete_edit("فحش (ویرایش)")
            return
        if settings.get("filter", True):
            _filtered = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if contains_filtered_word(new_text, _filtered):
                await _delete_edit("کلمه فیلترشده (ویرایش)")
                return
        if settings.get("link", False) and contains_link(new_text):
            await _delete_edit("لینک (ویرایش)")
            return
        if settings.get("hyperlink", False) and contains_hyperlink(new_text):
            await _delete_edit("هایپرلینک (ویرایش)")
            return
        if settings.get("id", False) and contains_id(new_text):
            await _delete_edit("آیدی (ویرایش)")
            return
        if settings.get("forward", False) and is_forwarded(message):
            await _delete_edit("فوروارد (ویرایش)")
            return
        if settings.get("gif", False) and is_gif(message):
            await _delete_edit("گیف (ویرایش)")
            return
        if settings.get("emoji", False) and contains_emoji(new_text):
            await _delete_edit("ارسال ایموجی (ویرایش)", "EMOJI")
            return
        if settings.get("sticker", False) and is_sticker(message):
            await _delete_edit("ارسال استیکر (ویرایش)", "STICKER")
            return
        if settings.get("number", False) and is_only_number(new_text):
            await _delete_edit("ارسال عدد (ویرایش)", "NUMBER")
            return
        if settings.get("english", False) and is_english_text(new_text):
            await _delete_edit("ارسال متن انگلیسی (ویرایش)", "ENGLISH")
            return
        if settings.get("forbidden_words", False) and contains_forbidden_bio(new_text):
            await _delete_edit("کلمات غیرمجاز (ویرایش)", "BIO")
            return
    except Exception as _err:
        print(f"❌ process_edited_message: {_err}", flush=True)


# ================== MAIN HANDLER ==================
@bot.on_message()
async def handle_message(bot, message):
    global bot_is_active, message_cache, bot_data, settings

    try:
        try:
            msg_id_raw = getattr(message, "message_id", None)
            msg_id = str(msg_id_raw) if msg_id_raw is not None else ""
            msg_id = msg_id.strip()
        except:
            msg_id = ""

        chat_id = str(message.chat_id) if message.chat_id else ""
        sender_id = str(message.sender_id) if message.sender_id else ""

        # ✅ کپشن هم چک می‌شه، نه فقط text
        raw_text = ""
        try:
            t = getattr(message, "text", None)
            if t:
                raw_text = t.strip()
            else:
                cap = (getattr(message, "caption", None) or
                       getattr(message, "text_caption", None) or "")
                if cap:
                    raw_text = str(cap).strip()
        except:
            raw_text = ""
        clean_text = clean_message(raw_text)

        is_valid_mid = _is_valid_id(msg_id)

        bot_id_cached = BOT_ID_CACHE.get("id")
        if bot_id_cached and str(sender_id) == str(bot_id_cached):
            return

        if is_valid_mid:
            pm_key = f"{chat_id}:{msg_id}"
            prev_text = processed_messages.get(pm_key)
            if prev_text is not None:
                if prev_text != raw_text:
                    processed_messages[pm_key] = raw_text
                    print(f"✏️ [edit] {pm_key}", flush=True)
                    await process_edited_message(message, chat_id, sender_id, prev_text, raw_text)
                    return
                else:
                    return
            processed_messages[pm_key] = raw_text

        button_id = extract_button_id(message)

        if sender_id: register_user(sender_id)
        if is_group_chat(chat_id): register_group(chat_id)

        if chat_id and is_valid_mid and sender_id:
            if chat_id not in message_cache: message_cache[chat_id] = {}
            message_cache[chat_id][msg_id] = sender_id
            try:
                rinfo = extract_reply_info(message)
                if rinfo["reply_id"] and rinfo["sender_id"]:
                    message_cache[chat_id][str(rinfo["reply_id"])] = str(rinfo["sender_id"])
            except Exception as e:
                print(f"⚠️ reply cache: {e}", flush=True)
            if len(message_cache[chat_id]) > 1000:
                keys = list(message_cache[chat_id].keys())
                for k in keys[:-1000]: del message_cache[chat_id][k]
            save_cache(message_cache)

        ct = time.time()
        is_owner_check = (str(sender_id) == OWNER_ID)

        print(f"📩 {chat_id} | {sender_id} | {raw_text!r}", flush=True)

        # While disabled, silence all group activity before any feature (including
        # broadcast handling) can reply. The group-role check below authorizes activation.
        if is_group_chat(chat_id) and not bot_is_active and clean_text not in ("فعال", "فاعل"):
            return

        # ============ 📢 ارسال پیام همگانی ============
        broadcast_match = re.match(r"^ارسال\s+پیام\s+همگانی\s+گروه\s+([\s\S]+)$", raw_text.strip())
        if broadcast_match:
            if not is_owner_check: return
            broadcast_text = broadcast_match.group(1).strip()
            if not broadcast_text:
                try:
                    await bot.send_message(chat_id=chat_id, text="⚠️ متن پیام رو وارد کن.")
                except: pass
                return
            groups = ensure_list(bot_data.get("known_groups", []))
            if not groups:
                try:
                    await bot.send_message(chat_id=chat_id, text="📭 ربات توی هیچ گروهی عضو نیست.")
                except: pass
                return
            status_msg = None
            try:
                status_msg = await bot.send_message(chat_id=chat_id, text=f"📢 در حال ارسال به {len(groups)} گروه...")
            except: pass
            sent = 0
            failed = 0
            failed_details = []
            dead_groups = []
            for gid in groups:
                try:
                    await bot.send_message(chat_id=gid, text=broadcast_text)
                    sent += 1
                    await asyncio.sleep(1.5)
                except Exception as e:
                    failed += 1
                    err_str = str(e)
                    is_alive, val_err = await validate_group(gid)
                    if not is_alive:
                        dead_groups.append(gid)
                        failed_details.append((gid, err_str, True, val_err))
                    else:
                        failed_details.append((gid, err_str, False, val_err))
                    await asyncio.sleep(0.5)
            if dead_groups:
                current = ensure_list(bot_data.get("known_groups", []))
                bot_data["known_groups"] = [g for g in current if g not in dead_groups]
                save_data(bot_data, force=True)
                for gid in dead_groups:
                    group_info_cache.pop(gid, None)
                    group_info_cache_ttl.pop(gid, None)
            try:
                if status_msg:
                    mid = extract_msg_id(status_msg)
                    if mid: await bot.delete_message(chat_id=chat_id, message_id=mid)
            except: pass
            report = (
                f"✅ **ارسال همگانی انجام شد!**\n\n"
                f"📤 موفق: **{sent}**\n"
                f"❌ ناموفق: **{failed}**\n"
                f"📊 کل گروه‌ها: **{len(groups)}**\n"
            )
            if dead_groups:
                report += f"🗑️ حذف‌شده (مرده): **{len(dead_groups)}**\n"
            report += f"\n⚡ **FLUXBOT**"
            try:
                await send_long_message(chat_id, report)
            except: pass
            return

        # ============ پیوی ============
        if is_private_chat(chat_id):
            if is_owner_check and clean_text in ("لیست گروه ها", "لیست گروه‌ها", "گروه ها", "گروه‌ها", "لیست گروها"):
                msg = await bot.send_message(chat_id=chat_id, text="⏳ در حال بررسی گروه‌ها...")
                groups_text = await get_group_list_text()
                try:
                    mid = extract_msg_id(msg)
                    if mid: await bot.delete_message(chat_id=chat_id, message_id=mid)
                except: pass
                await send_long_message(chat_id, groups_text)
                return
            if button_id == "btn_channel" or raw_text == BTN_CHANNEL:
                await bot.send_message(chat_id=chat_id, text=get_channel_text()); return
            if button_id == "btn_help" or raw_text == BTN_HELP:
                await send_long_message(chat_id, get_education_text()); return
            if button_id == "btn_users" or raw_text == BTN_USERS:
                await bot.send_message(chat_id=chat_id, text=get_users_text()); return
            if button_id == "btn_groups" or raw_text == BTN_GROUPS:
                text = await get_groups_text()
                await bot.send_message(chat_id=chat_id, text=text); return
            if button_id == "btn_dev" or raw_text == BTN_DEV:
                await bot.send_message(chat_id=chat_id, text=get_dev_text()); return
            if button_id == "btn_invite_enter" or raw_text == BTN_INVITE_ENTER:
                waiting_for_code[sender_id] = ct
                await bot.send_message(chat_id=chat_id, text=(
                    "🎟️ **زدن کد دعوت**\n\nکد ۶ رقمی خود را ارسال کنید.\n\n"
                    "💡 برای لغو: «انصراف»\n\n⏱️ ۲ دقیقه فعال است.\n⚡ **FLUXBOT**"))
                return
            if button_id == "btn_invite_show" or raw_text == BTN_INVITE_SHOW:
                code = get_or_create_code(sender_id)
                await bot.send_message(chat_id=chat_id, text=(
                    f"🎫 **کد دعوت شما**\n\nکد:\n`{code}`\n\n"
                    f"📌 به دوستانتان بدهید.\n"
                    f"💎 هر کسی وارد کند، هر دو **۱ امتیاز** می‌گیرید.\n\n"
                    f"⭐ **امتیاز فعلی:** {get_points(sender_id)}\n\n⚡ **FLUXBOT**"))
                return
            if button_id == "btn_points" or raw_text == BTN_POINTS:
                pts = get_points(sender_id)
                code = get_or_create_code(sender_id)
                invited = sum(1 for v in bot_data.get("invited_users", {}).values() if v == sender_id)
                await bot.send_message(chat_id=chat_id, text=(
                    f"⭐ **امتیاز من**\n━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💎 **امتیاز:** `{pts}`\n👥 **دعوت‌شده:** `{invited}`\n🎫 **کد:** `{code}`\n\n⚡ **FLUXBOT**"))
                return
            if button_id == "btn_features" or raw_text == BTN_FEATURES or clean_text in ("قابلیت ها", "قابلیت‌ها", "قابلیت های ربات"):
                await send_long_message(chat_id, get_features_text())
                return
            if button_id == "btn_top_inviters" or raw_text == BTN_TOP_INVITERS:
                text = await get_top_inviters_text()
                await send_long_message(chat_id, text)
                return
            if clean_text in ("لیست بازی", "لیست بازی ها", "لیست بازی‌ها", "بازی ها", "بازی‌ها", "بازی"):
                await bot.send_message(chat_id=chat_id, text=get_games_list_text())
                return
            wait_ts = waiting_for_code.get(sender_id, 0)
            if wait_ts and ct - wait_ts < 120:
                if raw_text in ("انصراف", "لغو", "/cancel"):
                    del waiting_for_code[sender_id]
                    await bot.send_message(chat_id=chat_id, text="✅ لغو شد.")
                    return
                code_match = re.match(r'^\s*(\d{6})\s*$', raw_text)
                if code_match:
                    del waiting_for_code[sender_id]
                    result_text = await process_invite_code(chat_id, sender_id, code_match.group(1))
                    await bot.send_message(chat_id=chat_id, text=result_text)
                    return
                del waiting_for_code[sender_id]
                await bot.send_message(chat_id=chat_id, text="❌ **کد نامعتبر!** باید ۶ رقم باشد.")
                return
            if is_command(clean_text, "start", "شروع", "منو"):
                text = (
                    "╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   🌊 جریان قدرت 🌊\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                    "🌟 **خوش آمدید!**\n\n👇 **از منوی پایین انتخاب کنید:**"
                )
                kp = build_keypad()
                if kp:
                    try:
                        await bot.send_message(chat_id=chat_id, text=text, chat_keypad=kp, chat_keypad_type="New")
                    except Exception as e:
                        print(f"⚠️ keypad send: {e}", flush=True)
                        await bot.send_message(chat_id=chat_id, text=text)
                else:
                    await bot.send_message(chat_id=chat_id, text=text)
                return
            return

        # ============ گروه ============
        if not is_group_chat(chat_id): return

        ui = await get_user_info(chat_id, sender_id)
        role = ui["role"]
        disp = format_user_display(ui, sender_id)
        is_owner_group = (role == "مالک")
        is_special = bot_data.get("special_users", {}).get(chat_id, {}).get(sender_id, False)
        can_manage = is_owner_group or is_special

        # When the bot is disabled, do not answer anyone in groups. Only an
        # authorized owner/special user can wake it up with the exact command "فعال".
        if not bot_is_active:
            if can_manage and is_command(clean_text, "فعال", "فاعل"):
                bot_is_active = True
                bot_data["bot_is_active"] = True
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, text="✅ فعال شد.", reply_to_message_id=message.message_id)
            return

        # Keep lock-control commands usable for owners/special users even when
        # one of the content locks is enabled.
        _filter_control_words = (
            "لینک", "آیدی", "اسپم", "هایپرلینک", "فحش", "فوروارد", "هدایت",
            "گیف", "ایموجی", "استیکر", "عدد", "انگلیسی", "کلمات غیرمجاز",
            "کلمات غیر مجاز", "کلمه غیرمجاز", "کلمه غیر مجاز", "بیو", "بایو",
            "بیوچک", "بایوچک", "بیو چک", "بایو چک", "ویرایش",
        )
        _is_filter_control_command = can_manage and any(
            match_two_word_cmd(clean_text, _lock_word, FILTER_ON, FILTER_OFF) is not None
            for _lock_word in _filter_control_words
        )
        locked, _ = is_group_locked(chat_id)
        if locked and not can_manage:
            try: await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except Exception as e:
                print(f"⚠️ delete locked: {e}", flush=True)
            return

        now = time.time()
        chat_mutes = bot_data.get("mute_list", {}).get(chat_id, {})
        if sender_id in chat_mutes:
            if now < chat_mutes[sender_id]:
                try: await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                except Exception as e:
                    print(f"⚠️ delete muted: {e}", flush=True)
                return
            else:
                del chat_mutes[sender_id]
                if "mute_list" not in bot_data: bot_data["mute_list"] = {}
                bot_data["mute_list"][chat_id] = chat_mutes
                save_data(bot_data, force=True)

        if not can_manage:
            slow_sec = bot_data.get("slow_mode", {}).get(chat_id)
            if slow_sec:
                if await handle_slow_mode(chat_id, sender_id, slow_sec, ui):
                    try: await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    except Exception as e:
                        print(f"⚠️ slow delete: {e}", flush=True)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "ارسال سریع در حالت آهسته", user_info=ui)
                    return

        if not can_manage and is_valid_mid:
            ar_limit = bot_data.get("anti_repeat", {}).get(chat_id)
            if ar_limit and raw_text:
                if await handle_repeat_check(chat_id, sender_id, msg_id, raw_text, ar_limit, ui):
                    return

        if settings["spam"] and not can_manage and is_valid_mid:
            if await handle_spam_check(chat_id, sender_id, msg_id, ui):
                return

        if can_manage and not _is_filter_control_command:
            # Apply the new content locks to managers too, without changing
            # the existing moderation order for ordinary members.
            if settings.get("emoji", False) and contains_emoji(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "ارسال ایموجی", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete emoji failed: {e}", flush=True)
                return
            if settings.get("sticker", False) and is_sticker(message):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "ارسال استیکر", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete sticker failed: {e}", flush=True)
                return
            if settings.get("number", False) and is_only_number(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "ارسال عدد", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete number failed: {e}", flush=True)
                return
            if settings.get("english", False) and is_english_text(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "ارسال متن انگلیسی", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete english failed: {e}", flush=True)
                return
            if settings.get("forbidden_words", False) and contains_forbidden_bio(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "کلمات غیرمجاز", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete bio failed: {e}", flush=True)
                return

        # ═══════ فیلترهای محتوا — اینجا ID اول از همه ═══════
        if bot_is_active and not can_manage:
            # 🆔 آیدی — اول چک می‌شه
            if settings.get("id", False) and contains_id(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "ارسال آیدی", user_info=ui)
                    print(f"🗑️ [ID] پاک شد | {chat_id} | {raw_text[:40]}", flush=True)
                except Exception as e:
                    print(f"⚠️ delete ID failed: {e}", flush=True)
                return
            # 🔗 لینک
            if settings.get("link", False) and contains_link(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "لینک", user_info=ui)
                    print(f"🗑️ [LINK] پاک شد | {chat_id}", flush=True)
                except Exception as e:
                    print(f"⚠️ delete link failed: {e}", flush=True)
                return
            # 🔗 هایپرلینک
            if settings.get("hyperlink", False) and contains_hyperlink(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "هایپرلینک", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete hyperlink failed: {e}", flush=True)
                return
            # 🤬 فحش
            if settings.get("profanity", True) and contains_profanity(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "فحش", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete profanity failed: {e}", flush=True)
                return
            # 🚫 کلمه فیلترشده
            if settings.get("filter", True):
                fl = ensure_list_dict(bot_data, "filtered_words", chat_id)
                if contains_filtered_word(raw_text, fl):
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                        if settings.get("warning"):
                            await add_warning(chat_id, sender_id, "کلمه فیلترشده", user_info=ui)
                    except Exception as e:
                        print(f"⚠️ delete filter failed: {e}", flush=True)
                    return
            # 📨 فوروارد
            if settings.get("forward", False) and is_forwarded(message):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "فوروارد", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete forward failed: {e}", flush=True)
                return
            # 🎞️ گیف
            if settings.get("gif", False) and is_gif(message):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "گیف", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete gif failed: {e}", flush=True)
                return
            # 😀 ایموجی
            if settings.get("emoji", False) and contains_emoji(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "ارسال ایموجی", user_info=ui)
                    print(f"🗑️ [EMOJI] پاک شد | {chat_id}", flush=True)
                except Exception as e:
                    print(f"⚠️ delete emoji failed: {e}", flush=True)
                return
            # 🩹 استیکر
            if settings.get("sticker", False) and is_sticker(message):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "ارسال استیکر", user_info=ui)
                    print(f"🗑️ [STICKER] پاک شد | {chat_id}", flush=True)
                except Exception as e:
                    print(f"⚠️ delete sticker failed: {e}", flush=True)
                return
            # 🔢 عدد
            if settings.get("number", False) and is_only_number(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "ارسال عدد", user_info=ui)
                    print(f"🗑️ [NUMBER] پاک شد | {chat_id}", flush=True)
                except Exception as e:
                    print(f"⚠️ delete number failed: {e}", flush=True)
                return
            # 🔤 انگلیسی
            if settings.get("english", False) and is_english_text(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "ارسال متن انگلیسی", user_info=ui)
                    print(f"🗑️ [ENGLISH] پاک شد | {chat_id}", flush=True)
                except Exception as e:
                    print(f"⚠️ delete english failed: {e}", flush=True)
                return
            # 🚫 کلمات غیرمجاز بیوگرافی
            if settings.get("forbidden_words", False) and contains_forbidden_bio(raw_text):
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings.get("warning"):
                        await add_warning(chat_id, sender_id, "کلمات غیرمجاز", user_info=ui)
                    print(f"🗑️ [BIO] پاک شد | {chat_id}", flush=True)
                except Exception as e:
                    print(f"⚠️ delete bio failed: {e}", flush=True)
                return

        if not bot_is_active and not can_manage:
            return

        if settings.get("welcome", True) and bot_is_active and not can_manage:
            welcomed = bot_data.get("welcomed_users", {}).get(chat_id, {})
            if sender_id not in welcomed:
                cn = await get_chat_name(chat_id)
                welcome_msg = get_welcome_text(chat_id, cn, disp)
                welcome_sent = False
                try:
                    result = await bot.send_message(
                        chat_id=chat_id,
                        reply_to_message_id=message.message_id,
                        text=welcome_msg,
                    )
                    welcome_sent = api_result_ok(result)
                except Exception as e:
                    print(f"⚠️ welcome: {e}", flush=True)
                if welcome_sent:
                    if chat_id not in bot_data["welcomed_users"]:
                        bot_data["welcomed_users"][chat_id] = {}
                    bot_data["welcomed_users"][chat_id][sender_id] = True
                    save_data(bot_data)

        today = get_local_now().strftime("%Y-%m-%d")
        if chat_id not in bot_data["message_counts"]: bot_data["message_counts"][chat_id] = {}
        if sender_id not in bot_data["message_counts"][chat_id]:
            bot_data["message_counts"][chat_id][sender_id] = {"today": 0, "date": today}
        elif bot_data["message_counts"][chat_id][sender_id]["date"] != today:
            bot_data["message_counts"][chat_id][sender_id] = {"today": 0, "date": today}
        bot_data["message_counts"][chat_id][sender_id]["today"] += 1
        save_data(bot_data)

        # 🎯 چالش
        if is_command(clean_text, "چالش"):
            try:
                challenge_msg = build_challenge_message()
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=challenge_msg)
            except Exception as e:
                print(f"❌ challenge: {e}", flush=True)
            return

        # 🎨 فونت
        font_match = re.match(r"^(?:فونت|فوت)\s+([\s\S]+)$", raw_text.strip())
        if font_match:
            font_text = font_match.group(1).strip()
            if font_text:
                try:
                    font_msg = build_font_message(font_text)
                    if font_msg:
                        try:
                            await bot.send_message(chat_id=chat_id, text=font_msg,
                                                   reply_to_message_id=message.message_id)
                        except Exception as e:
                            print(f"❌ font send: {e}", flush=True)
                            await send_long_message(chat_id, font_msg,
                                                    reply_to_message_id=message.message_id)
                except Exception as e:
                    print(f"❌ font: {e}", flush=True)
            return

        if is_command(clean_text, "فونت", "فوت"):
            try:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id,
                    text=("🎨 **فونت‌ساز**\n\n"
                          "📝 مثال: `فونت king`\n\n"
                          "⚡ **FLUXBOT**"))
            except: pass
            return

        # 💬 سخنگو — دستورها رو قورت نمی‌ده
        _looks_like_cmd = False
        for _w in ("لینک", "آیدی", "اسپم", "هایپرلینک", "فحش",
                   "فوروارد", "هدایت", "گیف", "سخنگو",
                   "خوش‌آمدگویی", "خوشآمدگویی", "خداحافظی", "شرط بندی",
                   "ایموجی", "استیکر", "عدد", "انگلیسی",
                   "کلمات غیرمجاز", "کلمات غیر مجاز", "بیو", "ویرایش"):
            if match_two_word_cmd(clean_text, _w, FILTER_ON, FILTER_OFF) is not None or \
               match_two_word_cmd(clean_text, _w, FEATURE_ON, FEATURE_OFF) is not None:
                _looks_like_cmd = True
                break
        talk_reply = None if _looks_like_cmd else get_talkative_reply(raw_text)
        if talk_reply and is_talkative_enabled(chat_id):
            try:
                reply = random.choice(talk_reply)
                await bot.send_message(chat_id=chat_id, text=reply, reply_to_message_id=message.message_id)
            except Exception as e:
                print(f"⚠️ talkative: {e}", flush=True)
            return

        # 🔄 قفل سخنگو (فیچر)
        res = match_two_word_cmd(clean_text, "سخنگو", FEATURE_ON, FEATURE_OFF)
        if res is not None:
            if not can_manage: return
            set_talkative(chat_id, res)
            if res:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    "✅ **سخنگو فعال شد!**\n\n"
                    "حالا هرکی بگه `فلکس بات`، ربات بهش جواب می‌ده 💬\n\n"
                    "⚡ **FLUXBOT**"))
            else:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    "🔴 **سخنگو غیرفعال شد!**\n\n"
                    "از این به بعد ربات به `فلکس بات` جواب نمی‌ده.\n\n"
                    "⚡ **FLUXBOT**"))
            return

        # 🔄 قفل شرط بندی (فیچر)
        bet_res = match_two_word_cmd(clean_text, "شرط بندی", FEATURE_ON, FEATURE_OFF)
        if bet_res is None:
            bet_res = _check_betting_lock(clean_text)
        if bet_res is not None:
            if not can_manage: return
            settings["betting_enabled"] = bet_res
            bot_data["settings"] = settings
            save_data(bot_data, force=True)
            if bet_res:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    "🟢 **شرط بندی فعال شد!**\n\n"
                    "حالا اعضا می‌تونن شرط ببندن.\n\n"
                    "⚡ **FLUXBOT**"))
            else:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    "🔴 **شرط بندی غیرفعال شد!**\n\n"
                    "از این به بعد ربات به شرط بندی جواب نمی‌ده.\n\n"
                    "⚡ **FLUXBOT**"))
            return

        # 🔄 قفل‌های فیلتر
        filter_locks = {
            "لینک": "link", "آیدی": "id", "اسپم": "spam", "هایپرلینک": "hyperlink",
            "فحش": "profanity", "فوروارد": "forward", "هدایت": "forward", "گیف": "gif",
            "ایموجی": "emoji", "استیکر": "sticker", "عدد": "number",
            "انگلیسی": "english", "کلمات غیرمجاز": "forbidden_words",
            "کلمات غیر مجاز": "forbidden_words", "بیو": "forbidden_words",
            "ویرایش": "edit",
            "کلمه غیرمجاز": "forbidden_words",
            "کلمه غیر مجاز": "forbidden_words",
            "بایو": "forbidden_words", "بیوچک": "forbidden_words", "بایوچک": "forbidden_words",
            "بیو چک": "forbidden_words", "بایو چک": "forbidden_words",
        }
        for w, key in filter_locks.items():
            res = match_two_word_cmd(clean_text, w, FILTER_ON, FILTER_OFF)
            if res is not None:
                if not can_manage: return
                settings[key] = res
                bot_data["settings"] = settings
                save_data(bot_data, force=True)
                if res:
                    txt = (f"🔒 **{w} قفل شد!**\n\n"
                           f"✅ حالا پیام‌های حاوی {w} پاک می‌شن.\n\n"
                           f"🔓 برای باز کردن: `{w} باز`\n\n⚡ **FLUXBOT**")
                else:
                    txt = (f"🔓 **{w} باز شد!**\n\n"
                           f"❌ دیگه پیام‌های حاوی {w} پاک نمی‌شن.\n\n"
                           f"🔒 برای قفل کردن: `{w} قفل`\n\n⚡ **FLUXBOT**")
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=txt)
                return

        # 🔄 قفل‌های فیچر
        feature_locks = {
            "خوش‌آمدگویی": "welcome", "خوشآمدگویی": "welcome", "خداحافظی": "goodbye",
        }
        for w, key in feature_locks.items():
            res = match_two_word_cmd(clean_text, w, FEATURE_ON, FEATURE_OFF)
            if res is not None:
                if not can_manage: return
                settings[key] = res
                bot_data["settings"] = settings
                save_data(bot_data, force=True)
                status = "🟢 فعال" if res else "🔴 غیرفعال"
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id,
                                       text=f"✅ **{w}** {status} شد.\n\n⚡ **FLUXBOT**")
                return

        # ═══════ بازی‌های ماژولار ═══════
        for _game in MODULAR_GAMES:
            try:
                _ctx = {
                    "bot": bot, "chat_id": chat_id, "sender_id": sender_id,
                    "msg_id": msg_id, "raw_text": raw_text, "clean_text": clean_text,
                    "sender_display": disp, "can_manage": can_manage,
                    "message": message,
                    "points_getter": get_points,
                    "points_setter": lambda uid, val: bot_data.get("points", {}).__setitem__(str(uid), val) or save_data(bot_data, force=True),
                    "settings": settings, "bot_data": bot_data, "save_data": save_data,
                }
                if await _game.handle(_ctx):
                    return
            except Exception as e:
                print(f"❌ {_game.__name__}: {e}", flush=True)

        games = get_games()

        if chat_id in coin_flip_games:
            cf = coin_flip_games[chat_id]
            if str(sender_id) == cf["player"] and raw_text in ("شیر", "خط"):
                choice = raw_text
                del coin_flip_games[chat_id]
                result = random.choice(["شیر", "خط"])
                won = (choice == result)
                if won:
                    text = (f"🪙 **نتیجه:** {result}\n\n"
                        f"🎉 **{disp} برنده شد!** 🎉\n\n"
                        f"━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT**")
                else:
                    text = (f"🪙 **نتیجه:** {result}\n\n"
                        f"😢 **{disp} باخت!**\n\n"
                        f"━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT**")
                await bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=message.message_id)
                return

        if clean_text in ("لیست بازی", "لیست بازی ها", "لیست بازی‌ها", "بازی ها", "بازی‌ها"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=get_games_list_text())
            return

        if clean_text == "قوانین":
            rules = bot_data.get("rules", {}).get(chat_id)
            if rules:
                rules_text = ("📜 **قوانین گروه**\n━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{rules}\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT**")
                if len(rules_text) > 800:
                    await send_long_message(chat_id, rules_text, reply_to_message_id=message.message_id)
                else:
                    await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=rules_text)
            else:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    "ℹ️ **هنوز قوانینی تنظیم نشده!**\n\n"
                    "مالک باید با دستور زیر تنظیم کنه:\n"
                    "`تنظیم قوانین [متن]`"))
            return

        rtm = re.match(r"^تنظیم\s+قوانین\s+([\s\S]+)$", raw_text.strip())
        if rtm:
            if not is_owner_group: return
            rules_text = rtm.group(1).strip()
            if not rules_text: return
            if "rules" not in bot_data: bot_data["rules"] = {}
            bot_data["rules"][chat_id] = rules_text
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                "✅ **قوانین گروه ثبت شد!**\n\n📌 برای نمایش: `قوانین`\n\n⚡ **FLUXBOT**"))
            return

        if is_command(clean_text, "حذف قوانین", "پاک قوانین"):
            if not is_owner_group: return
            if "rules" not in bot_data: bot_data["rules"] = {}
            if chat_id in bot_data["rules"]:
                del bot_data["rules"][chat_id]
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, text="✅ **قوانین گروه حذف شد.**", reply_to_message_id=message.message_id)
            else:
                await bot.send_message(chat_id=chat_id, text="ℹ️ قوانینی تنظیم نشده.", reply_to_message_id=message.message_id)
            return

        cwm = re.match(r"^تنظیم\s+پیام\s+خوش\s*آمدگویی\s+([\s\S]+)$", raw_text.strip())
        if cwm:
            if not is_owner_group: return
            welcome_text = cwm.group(1).strip()
            if not welcome_text: return
            if "custom_welcome" not in bot_data: bot_data["custom_welcome"] = {}
            bot_data["custom_welcome"][chat_id] = welcome_text
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                "✅ **پیام خوش‌آمدگویی تنظیم شد!**\n\n"
                "💡 متغیرها: `{name}` / `{group}` / `{time}`\n\n⚡ **FLUXBOT**"))
            return

        if is_command(clean_text, "حذف پیام خوش آمدگویی", "حذف پیام خوش‌آمدگویی"):
            if not is_owner_group: return
            if "custom_welcome" not in bot_data: bot_data["custom_welcome"] = {}
            if chat_id in bot_data["custom_welcome"]:
                del bot_data["custom_welcome"][chat_id]
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, text="✅ **پیام خوش‌آمدگویی حذف شد.**", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "نمایش پیام خوش آمدگویی", "نمایش پیام خوش‌آمدگویی"):
            if not can_manage: return
            custom = bot_data.get("custom_welcome", {}).get(chat_id)
            if custom:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    "📋 **پیام خوش‌آمدگویی فعلی:**\n\n" + custom))
            else:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="ℹ️ پیام پیش‌فرض فعاله.")
            return

        arm = re.match(r"^تنظیم\s+ضد\s+تکرار\s+(\d+)$", clean_text)
        if arm:
            if not is_owner_group: return
            limit = int(arm.group(1))
            if limit < 2 or limit > 10: return
            if "anti_repeat" not in bot_data: bot_data["anti_repeat"] = {}
            bot_data["anti_repeat"][chat_id] = limit
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                f"✅ **ضد تکرار فعال شد!**\n\n📊 **حد:** {limit} پیام یکسان\n\n⚡ **FLUXBOT**"))
            return

        if is_command(clean_text, "ضد تکرار بسته", "غیرفعال ضد تکرار"):
            if not is_owner_group: return
            if "anti_repeat" not in bot_data: bot_data["anti_repeat"] = {}
            if chat_id in bot_data["anti_repeat"]:
                del bot_data["anti_repeat"][chat_id]
                save_data(bot_data, force=True)
            if chat_id in repeat_tracker: del repeat_tracker[chat_id]
            await bot.send_message(chat_id=chat_id, text="✅ **ضد تکرار غیرفعال شد.**", reply_to_message_id=message.message_id)
            return

        smm = re.match(r"^تنظیم\s+حالت\s+آهسته\s+(.+)$", clean_text)
        if smm:
            if not is_owner_group: return
            sec = parse_slow_duration(smm.group(1).strip())
            if sec is None:
                await bot.send_message(chat_id=chat_id, text=(
                    "⚠️ **فرمت اشتباه!**\n\nمثال‌ها:\n"
                    "├ `تنظیم حالت آهسته 5 ثانیه`\n"
                    "├ `تنظیم حالت آهسته 1 دقیقه`\n"
                    "├ `تنظیم حالت آهسته 1 ساعت`\n"
                    "└ `تنظیم حالت آهسته 1 روز`"), reply_to_message_id=message.message_id)
                return
            if "slow_mode" not in bot_data: bot_data["slow_mode"] = {}
            bot_data["slow_mode"][chat_id] = sec
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                f"✅ **حالت آهسته فعال شد!**\n\n⏱️ **مدت:** {format_duration(sec)}\n\n⚡ **FLUXBOT**"))
            return

        if is_command(clean_text, "حالت آهسته بسته", "غیرفعال حالت آهسته"):
            if not is_owner_group: return
            if "slow_mode" not in bot_data: bot_data["slow_mode"] = {}
            if chat_id in bot_data["slow_mode"]:
                del bot_data["slow_mode"][chat_id]
                save_data(bot_data, force=True)
            if chat_id in slow_tracker: del slow_tracker[chat_id]
            await bot.send_message(chat_id=chat_id, text="✅ **حالت آهسته غیرفعال شد.**", reply_to_message_id=message.message_id)
            return

        bcm = re.match(r"^پاکسازی\s+(\d+)$", clean_text)
        if bcm:
            if not can_manage: return
            limit = int(bcm.group(1))
            if limit < 1 or limit > 500: return
            msg = await bot.send_message(chat_id=chat_id, text=f"🧹 در حال پاکسازی {limit} پیام...")
            deleted, failed = await bulk_cleanup(chat_id, sender_id, limit)
            try:
                mid = extract_msg_id(msg)
                if mid: await bot.delete_message(chat_id=chat_id, message_id=mid)
            except: pass
            await bot.send_message(chat_id=chat_id, text=(
                f"🧹 **پاکسازی انجام شد!**\n\n✅ حذف شده: **{deleted}**\n❌ ناموفق: **{failed}**\n\n⚡ **FLUXBOT**"),
                reply_to_message_id=message.message_id)
            return

        game_start_match = re.match(r"^(دوز|بازی دوز)\s*(قرمز|زرد)?$", clean_text)
        if game_start_match:
            if chat_id in games and games[chat_id].get("status") in ("waiting", "playing"):
                g = games[chat_id]
                started = g.get("started_at", 0)
                if time.time() - started > (GAME_TIMEOUT * 3):
                    del games[chat_id]
                    save_data(bot_data, force=True)
                else:
                    if g["status"] == "waiting":
                        await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                            f"⏳ **بازی در انتظار حریف!**\n\n👤 **سازنده:** {g['player1_name']}\n📌 برای پیوستن: `شرکت`"))
                    else:
                        await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="⚠️ **یک بازی در حال اجراست!**")
                    return
            color_choice = game_start_match.group(2) or "قرمز"
            game = await start_game(chat_id, sender_id, disp, color_choice)
            if game is None:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id,
                                       text="⚠️ **یک بازی در حال اجراست!**")
                return
            color_emoji = RED if game["color1"] == "R" else YELLOW
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                f"🎮 **بازی دوز شروع شد!**\n\n👤 **سازنده:** {disp}\n🎨 **رنگ:** {color_emoji}\n\n"
                f"⏳ **منتظر حریف...**\n\n📌 برای پیوستن: `شرکت`\n"
                f"⏱️ اگه ۲ دقیقه کسی نیاد، خودکار لغو می‌شه.\n\n⚡ **FLUXBOT**"))
            return

        if clean_text in ("بازی شیر یا خط", "شیر یا خط", "شیریا خط"):
            if chat_id in coin_flip_games:
                cf = coin_flip_games[chat_id]
                started = cf.get("started_at", 0)
                if time.time() - started > (GAME_TIMEOUT * 3):
                    del coin_flip_games[chat_id]
                else:
                    await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id,
                                           text="⚠️ **یک بازی شیر یا خط در جریانه!**")
                    return
            if chat_id in games and games[chat_id].get("status") in ("waiting", "playing"):
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="⚠️ **یه بازی دیگه در جریانه!**")
                return
            started_at = time.time()
            coin_flip_games[chat_id] = {"player": str(sender_id), "started_at": started_at}
            try: asyncio.create_task(game_timeout_check(chat_id, "coinflip", started_at))
            except: pass
            await bot.send_message(chat_id=chat_id, text=(
                f"🪙 **بازی شیر یا خط شروع شد!**\n\n"
                f"👤 **بازیکن:** {disp}\n\n"
                f"🎯 **شیر یا خط؟** (بنویس `شیر` یا `خط`)\n\n"
                f"⏱️ ۲ دقیقه فرصت داری.\n\n⚡ **FLUXBOT**"))
            return

        if is_command(clean_text, "شرکت", "join"):
            if chat_id not in games:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="⚠️ **بازی فعالی نیست.**\n\nبرای شروع: `دوز`")
                return
            g, status = await join_game(chat_id, sender_id, disp)
            if status == "no_game":
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="⚠️ **بازی فعالی نیست.**")
                return
            if status == "already_started":
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="⚠️ **قبلاً شروع شده.**")
                return
            if status == "self_join":
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="⚠️ **نمی‌توانید به بازی خودتان بپیوندید!**")
                return
            board_txt = render_board(g["board"])
            c1 = RED if g["color1"] == "R" else YELLOW
            c2 = RED if g["color2"] == "R" else YELLOW
            await bot.send_message(chat_id=chat_id, text=(
                f"🎮 **بازی شروع شد!**\n\n"
                f"{c1} **{g['player1_name']}**  vs  {c2} **{g['player2_name']}**\n\n"
                f"```\n{board_txt}\n```\n\n"
                f"🎯 **نوبت:** {g['player1_name']} ({c1})\n\n📌 عدد 1 تا 7 بفرست.\n\n⚡ **FLUXBOT**"))
            return

        if is_command(clean_text, "انصراف"):
            if chat_id in coin_flip_games:
                cf = coin_flip_games[chat_id]
                if str(sender_id) == cf["player"]:
                    del coin_flip_games[chat_id]
                    await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="🚫 **بازی شیر یا خط لغو شد.**")
                    return
            g, status = await cancel_game(chat_id, sender_id)
            if status == "no_game": return
            if status == "not_player":
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="⚠️ **شما در این بازی نیستید.**")
                return
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="🚫 **بازی لغو شد.**")
            return

        if chat_id in games and games[chat_id].get("status") == "playing":
            g = games[chat_id]
            if str(sender_id) in (g["player1"], g["player2"]):
                col_match = re.match(r"^\s*([1-7])\s*$", raw_text)
                if col_match:
                    if str(sender_id) != g["turn"]:
                        cn = g["player1_name"] if g["turn"] == g["player1"] else g["player2_name"]
                        await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"⚠️ **نوبت شما نیست!**\n\n🎯 نوبت: **{cn}**")
                        return
                    col = int(col_match.group(1)) - 1
                    if str(sender_id) == g["player1"]:
                        color = g["color1"]; player_name = g["player1_name"]
                    else:
                        color = g["color2"]; player_name = g["player2_name"]
                    ok, row, c = drop_piece(g["board"], col, color)
                    if not ok:
                        await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="⚠️ **این ستون پر است!**")
                        return
                    color_emoji = RED if color == "R" else YELLOW
                    if check_win(g["board"], row, c, color):
                        board_txt = render_board(g["board"])
                        del games[chat_id]
                        save_data(bot_data, force=True)
                        await bot.send_message(chat_id=chat_id, text=(
                            f"🏆 **برنده!** 🏆\n\n{color_emoji} **{player_name}** برنده شد!\n\n```\n{board_txt}\n```\n\n⚡ **FLUXBOT**"))
                        return
                    if is_board_full(g["board"]):
                        board_txt = render_board(g["board"])
                        del games[chat_id]
                        save_data(bot_data, force=True)
                        await bot.send_message(chat_id=chat_id, text=f"🤝 **مساوی!**\n\n```\n{board_txt}\n```\n\n⚡ **FLUXBOT**")
                        return
                    if g["turn"] == g["player1"]: g["turn"] = g["player2"]
                    else: g["turn"] = g["player1"]
                    save_data(bot_data, force=True)
                    board_txt = render_board(g["board"])
                    next_name = g["player1_name"] if g["turn"] == g["player1"] else g["player2_name"]
                    next_color = RED if (g["turn"] == g["player1"] and g["color1"] == "R") or (g["turn"] == g["player2"] and g["color2"] == "R") else YELLOW
                    await bot.send_message(chat_id=chat_id, text=(
                        f"{color_emoji} **{player_name}** ستون {col+1}.\n\n```\n{board_txt}\n```\n\n"
                        f"🎯 **نوبت:** {next_name} ({next_color})"))
                    return

        if is_command(clean_text, "راهنما", "help", "دستورات", "دستور", "commands"):
            await send_long_message(chat_id, get_help_text(), reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "قابلیت ها", "قابلیت‌ها", "قابلیت های ربات", "قابلیت"):
            await send_long_message(chat_id, get_features_text(), reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "ساعت", "زمان"):
            now_dt = get_local_now()
            days = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
            wd = days[now_dt.weekday()]
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                f"⏰ **ساعت فعلی**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🕐 `{now_dt.strftime('%H:%M:%S')}`\n📅 `{now_dt.strftime('%Y/%m/%d')}`\n📆 {wd}\n\n⚡ **FLUXBOT**"))
            return

        if is_command(clean_text, "مقام", "رتبه", "مقامم", "رتبه‌م", "رتبم"):
            try:
                ui_fresh = await get_user_info(chat_id, sender_id, force=True)
                role_fresh = ui_fresh.get("role", "عضو")
                disp_fresh = format_user_display(ui_fresh, sender_id)
                role_emoji = {"مالک": "👑", "ادمین": "⚡", "عضو": "👤"}.get(role_fresh, "👤")
                role_desc = {
                    "مالک": "صاحب و مالک این گروه",
                    "ادمین": "مدیر این گروه",
                    "عضو": "عضو عادی گروه",
                }.get(role_fresh, "عضو گروه")
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    f"╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                    f"   🎖️ **مقام شما** 🎖️\n"
                    f"╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                    f"👤 **نام:** {disp_fresh}\n"
                    f"{role_emoji} **مقام:** {role_fresh}\n"
                    f"📌 **توضیح:** {role_desc}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ **FLUXBOT**"))
            except Exception as e:
                print(f"❌ role cmd: {e}", flush=True)
                try:
                    await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id,
                                           text="⚠️ خطا در دریافت مقام.")
                except: pass
            return

        if is_command(clean_text, "حذف ویژه", "لغو ویژه", "حذف ادمین"):
            if not is_owner_group: return
            tgt = await find_reply_target(message, chat_id)
            if tgt == "BOT_SELF": return
            if not tgt:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            if chat_id in bot_data["special_users"] and tgt in bot_data["special_users"][chat_id]:
                del bot_data["special_users"][chat_id][tgt]
                save_data(bot_data, force=True)
                await send_user_mention_message(
                    chat_id, tgt, f"✅ {USER_MENTION_TOKEN} از ویژه حذف شد.",
                    reply_to_message_id=message.message_id, bot_client=bot,
                )
            else:
                await send_user_mention_message(
                    chat_id, tgt, f"ℹ️ {USER_MENTION_TOKEN} ویژه نیست.",
                    reply_to_message_id=message.message_id, bot_client=bot,
                )
            return

        if is_command(clean_text, "ویژه", "ادمین"):
            if not is_owner_group: return
            tgt = await find_reply_target(message, chat_id)
            if tgt == "BOT_SELF": return
            if not tgt:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            if chat_id not in bot_data["special_users"]: bot_data["special_users"][chat_id] = {}
            if bot_data["special_users"][chat_id].get(tgt, False):
                await send_user_mention_message(
                    chat_id, tgt, f"ℹ️ {USER_MENTION_TOKEN} از قبل ویژه است.",
                    reply_to_message_id=message.message_id, bot_client=bot,
                )
                return
            bot_data["special_users"][chat_id][tgt] = True
            save_data(bot_data, force=True)
            await send_user_mention_message(
                chat_id, tgt, f"⭐ {USER_MENTION_TOKEN} ویژه شد!",
                reply_to_message_id=message.message_id, bot_client=bot,
            )
            return

        wam = re.match(r"^حذف\s+اخطار(?:\s+(\d+))?$", clean_text)
        if wam:
            if not can_manage: return
            target_uid = await find_reply_target(message, chat_id)
            if target_uid == "BOT_SELF": return
            if not target_uid:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            amount_str = wam.group(1)
            if "warnings" not in bot_data: bot_data["warnings"] = {}
            if chat_id not in bot_data["warnings"]: bot_data["warnings"][chat_id] = {}
            current = bot_data["warnings"][chat_id].get(target_uid, 0)
            if current == 0:
                await send_user_mention_message(
                    chat_id, target_uid, f"ℹ️ برای {USER_MENTION_TOKEN} اخطاری ثبت نشده است.",
                    reply_to_message_id=message.message_id, bot_client=bot,
                )
                return
            if amount_str:
                amount = int(amount_str)
                if amount <= 0: return
                removed = min(amount, current)
                bot_data["warnings"][chat_id][target_uid] = current - removed
                save_data(bot_data, force=True)
                await send_user_mention_message(
                    chat_id, target_uid,
                    f"✅ {removed} اخطار از {USER_MENTION_TOKEN} حذف شد.\n\n"
                    f"📊 باقی‌مانده: {current - removed} از {bot_data['warn_limit'].get(chat_id, 3)}",
                    reply_to_message_id=message.message_id, bot_client=bot,
                )
            else:
                bot_data["warnings"][chat_id][target_uid] = 0
                save_data(bot_data, force=True)
                await send_user_mention_message(
                    chat_id, target_uid, f"✅ تمام اخطارهای {USER_MENTION_TOKEN} پاک شد.",
                    reply_to_message_id=message.message_id, bot_client=bot,
                )
            return

        dtm = re.match(r"^حذف\s+(\d+)$", clean_text)
        if dtm:
            if not can_manage: return
            mins = int(dtm.group(1))
            if mins <= 0 or mins > 10080: return
            rid = extract_reply_info(message)["reply_id"]
            if not rid:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام ریپلای کنید.", reply_to_message_id=message.message_id); return
            await schedule_delete(chat_id, rid, mins * 60)
            if mins >= 60:
                h, m = mins // 60, mins % 60
                ts = f"{h} ساعت" + (f" و {m} دقیقه" if m > 0 else "")
            else: ts = f"{mins} دقیقه"
            await bot.send_message(chat_id=chat_id, text=f"⏱️ پیام پس از **{ts}** پاک می‌شه.", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "حذف", "پاک"):
            if not can_manage: return
            rid = extract_reply_info(message)["reply_id"]
            if not rid:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام ریپلای کنید.", reply_to_message_id=message.message_id); return
            try:
                await bot.delete_message(chat_id=chat_id, message_id=rid)
                await bot.send_message(chat_id=chat_id, text="🗑️ **حذف شد.**", reply_to_message_id=message.message_id)
            except Exception as e:
                print(f"⚠️ delete: {e}", flush=True)
            return

        if is_command(clean_text, "باز", "بازکردن"):
            if not can_manage: return
            had = False
            if bot_data.get("group_locks", {}).get(chat_id, False):
                bot_data["group_locks"][chat_id] = False
                had = True
            if chat_id in bot_data.get("temp_locks", {}):
                del bot_data["temp_locks"][chat_id]
                had = True
            if had: save_data(bot_data, force=True)
            msg = "🔓 **گروه باز شد!**" if had else "ℹ️ از قبل باز بود."
            await bot.send_message(chat_id=chat_id, text=msg, reply_to_message_id=message.message_id)
            return

        # قفل گروه (با هر فرمت)
        if _strip_zwnj(clean_text) in ("قفلگروه", "قفلگرو"):
            if not can_manage: return
            if "group_locks" not in bot_data: bot_data["group_locks"] = {}
            bot_data["group_locks"][chat_id] = True
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="🔒 **گروه قفل شد!**\n\nباز: `باز`")
            return

        tm = re.match(r"^قفل\s+(\d+)$", clean_text)
        if tm:
            if not can_manage: return
            h = int(tm.group(1))
            if h <= 0 or h > 168: return
            et = time.time() + h * 3600
            if "temp_locks" not in bot_data: bot_data["temp_locks"] = {}
            if "group_locks" not in bot_data: bot_data["group_locks"] = {}
            bot_data["temp_locks"][chat_id] = et
            bot_data["group_locks"][chat_id] = False
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                f"🔒 **قفل موقت: {h} ساعت**\n🕐 پایان: {datetime.fromtimestamp(et, tz=IRAN_TZ).strftime('%H:%M - %Y/%m/%d')}"))
            return

        sm = re.match(r"^قفل\s+(\d{1,2}):(\d{2})\s+(?:تا\s+)?(\d{1,2}):(\d{2})$", clean_text)
        if sm:
            if not can_manage: return
            sh, sm2, eh, em = map(int, sm.groups())
            if not (0 <= sh <= 23 and 0 <= sm2 <= 59 and 0 <= eh <= 23 and 0 <= em <= 59): return
            if "scheduled_locks" not in bot_data: bot_data["scheduled_locks"] = {}
            if chat_id not in bot_data["scheduled_locks"]: bot_data["scheduled_locks"][chat_id] = []
            bot_data["scheduled_locks"][chat_id].append((sh, sm2, eh, em))
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"🔒 **قفل: {sh:02d}:{sm2:02d} تا {eh:02d}:{em:02d}**")
            return

        if is_command(clean_text, "حذف قفل زمان‌بندی"):
            if not can_manage: return
            if "scheduled_locks" not in bot_data: bot_data["scheduled_locks"] = {}
            bot_data["scheduled_locks"][chat_id] = []
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, text="✅ حذف شد.", reply_to_message_id=message.message_id)
            return

        if _strip_zwnj(clean_text) in ("لیستقفلگروه", "لیستقفلگرو"):
            if not can_manage: return
            s = []
            gl = bot_data.get("group_locks", {}).get(chat_id, False)
            tl = bot_data.get("temp_locks", {}).get(chat_id)
            sl_list = bot_data.get("scheduled_locks", {}).get(chat_id, [])
            current_locked, current_reason = is_group_locked(chat_id)
            s.append("🔴 قفل دستی: بسته" if gl else "🟢 قفل دستی: باز")
            try:
                temp_active = bool(tl) and float(tl) > time.time()
            except (TypeError, ValueError):
                temp_active = False
            if temp_active:
                s.append(f"🔴 قفل موقت: بسته ({get_remaining_time(float(tl))})")
            else:
                s.append("🟢 قفل موقت: باز")
            if sl_list:
                sl = []
                for interval in sl_list:
                    try:
                        sh, sm, eh, em = map(int, interval)
                        if not (0 <= sh <= 23 and 0 <= sm <= 59 and
                                0 <= eh <= 23 and 0 <= em <= 59):
                            continue
                        sl.append(f"  • {sh:02d}:{sm:02d} تا {eh:02d}:{em:02d}")
                    except (TypeError, ValueError):
                        continue
                schedule_state = (
                    "🔴 بسته" if current_locked and "زمان‌بندی" in current_reason
                    else "🟢 باز"
                )
                schedule_text = "\n".join(sl) if sl else "مورد معتبری ثبت نشده است."
                s.append(f"⏰ زمان‌بندی: {schedule_state}\n{schedule_text}")
            else:
                s.append("⏰ زمان‌بندی: 🟢 باز")
            s.append(f"🔒 وضعیت فعلی گروه: {'🔴 بسته' if current_locked else '🟢 باز'}")
            ar = bot_data.get("anti_repeat", {}).get(chat_id)
            s.append(f"🔁 ضد تکرار: {'🔴 ' + str(ar) + ' پیام یکسان' if ar else '🟢 غیرفعال'}")
            slow = bot_data.get("slow_mode", {}).get(chat_id)
            s.append(f"🐌 حالت آهسته: {'🔴 ' + format_duration(slow) if slow else '🟢 غیرفعال'}")
            tk = "🟢 فعال" if is_talkative_enabled(chat_id) else "🔴 غیرفعال"
            s.append(f"💬 سخنگو: {tk}")
            s.append(f"🎰 شرط بندی: {'🟢 فعال' if settings.get('betting_enabled', True) else '🔴 غیرفعال'}")
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                "🔒 **قفل گروه**\n━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(s) + "\n\n⚡ **FLUXBOT**"))
            return

        if chat_id not in bot_data["group_message_count"]: bot_data["group_message_count"][chat_id] = 0
        bot_data["group_message_count"][chat_id] += 1
        save_data(bot_data)

        if is_command(clean_text, "فعال", "فاعل"):
            if not can_manage: return
            msg = "✅ از قبل فعال." if bot_is_active else "✅ فعال شد."
            bot_is_active = True
            bot_data["bot_is_active"] = True
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, text=msg, reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "غیرفعال"):
            if not can_manage: return
            msg = "⛔ از قبل غیرفعال." if not bot_is_active else "🛑 غیرفعال شد."
            bot_is_active = False
            bot_data["bot_is_active"] = False
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, text=msg, reply_to_message_id=message.message_id)
            return

        wdm = re.match(r"^حذف\s+پیام\s+اخطار\s+(\d+)$", clean_text)
        if wdm:
            if not is_owner_group: return
            sec = int(wdm.group(1))
            if sec < 0 or sec > 3600: return
            if "warn_delete_after" not in bot_data: bot_data["warn_delete_after"] = {}
            if sec == 0:
                bot_data["warn_delete_after"][chat_id] = 0
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, text="✅ **غیرفعال شد.**", reply_to_message_id=message.message_id)
            else:
                bot_data["warn_delete_after"][chat_id] = sec
                save_data(bot_data, force=True)
                m, s = sec // 60, sec % 60
                ts = f"{m} دقیقه" + (f" و {s} ثانیه" if s > 0 else "") if m > 0 else f"{sec} ثانیه"
                await bot.send_message(chat_id=chat_id, text=f"✅ **فعال شد ({ts}).**", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "بن", "سیک", "اخراج"):
            if not can_manage: return
            tgt = await find_reply_target(message, chat_id)
            if tgt == "BOT_SELF": return
            if not tgt:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            if tgt == OWNER_ID: return
            try:
                await bot.ban_member_chat(chat_id, tgt)
                if chat_id not in bot_data["banned_users"]: bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][tgt] = time.time()
                save_data(bot_data, force=True)
                await send_user_mention_message(
                    chat_id, tgt, f"🚫 {USER_MENTION_TOKEN} از گروه اخراج شد.",
                    reply_to_message_id=message.message_id, bot_client=bot,
                )
            except Exception as e:
                print(f"⚠️ ban: {e}", flush=True)
            return

        if is_command(clean_text, "انبن", "آنبن"):
            if not can_manage: return
            tgt = await find_reply_target(message, chat_id)
            if tgt == "BOT_SELF": return
            if not tgt:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            try:
                await bot.unban_member_chat(chat_id, tgt)
                if chat_id in bot_data["banned_users"] and tgt in bot_data["banned_users"][chat_id]:
                    del bot_data["banned_users"][chat_id][tgt]
                    save_data(bot_data, force=True)
                await send_user_mention_message(
                    chat_id, tgt, f"✅ مسدودیت {USER_MENTION_TOKEN} برداشته شد.",
                    reply_to_message_id=message.message_id, bot_client=bot,
                )
            except Exception as e:
                print(f"⚠️ unban: {e}", flush=True)
            return

        fm = re.match(r"^فیلتر\s+(.+)$", clean_text)
        if fm:
            if not is_owner_group: return
            w = fm.group(1).strip()
            if not w: return
            fl = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if w in fl:
                await bot.send_message(chat_id=chat_id, text="⚠️ از قبل فیلتر شده.", reply_to_message_id=message.message_id); return
            if len(fl) >= MAX_FILTER_WORDS:
                await bot.send_message(chat_id=chat_id, text=f"⚠️ حداکثر {MAX_FILTER_WORDS}", reply_to_message_id=message.message_id); return
            fl.append(w); save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"✅ **«{w}» فیلتر شد** ({len(fl)}/{MAX_FILTER_WORDS})")
            return

        ufm = re.match(r"^حذف\s+فیلتر\s+(.+)$", clean_text)
        if ufm:
            if not is_owner_group: return
            w = ufm.group(1).strip()
            fl = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if w in fl:
                fl.remove(w); save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, text=f"✅ «{w}» حذف شد.", reply_to_message_id=message.message_id)
            else: await bot.send_message(chat_id=chat_id, text="⚠️ نبود.", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "لیست فیلتر"):
            if not can_manage: return
            w = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if not w: t = "📋 خالی"
            else: t = f"📋 ({len(w)}/{MAX_FILTER_WORDS}):\n\n" + "\n".join([f"├ 🚫 {x}" for x in w])
            await bot.send_message(chat_id=chat_id, text=t, reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "جک", "جوک"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"😂 {random.choice(JOKES)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "ضرب المثل", "ضرب‌المثل"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"📜 {random.choice(PROVERBS)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "دانستی", "دانستنی"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"💡 {random.choice(TRIVIA)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "فکت"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"🧠 {random.choice(FACTS)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "پ ن پ", "پنپ"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"💚 {random.choice(PNP)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "شعر"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"📝 {random.choice(POEMS)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "فال"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"{random.choice(FAL)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "شانس"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"{random.choice(LUCK)}\n\n⚡ **FLUXBOT**"); return

        if is_command(clean_text, "آمار گروه", "تاپ", "برترین‌ها"):
            today = get_local_now().strftime("%Y-%m-%d")
            counts = bot_data["message_counts"].get(chat_id, {})
            tc = [(u, d["today"]) for u, d in counts.items() if d.get("date") == today and d.get("today", 0) > 0]
            tc.sort(key=lambda x: x[1], reverse=True)
            top = tc[:10]
            if not top:
                await bot.send_message(chat_id=chat_id, text="📊 امروز پیامی نبود.", reply_to_message_id=message.message_id); return
            medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
            lines = []
            for i, (u, c) in enumerate(top):
                uinfo = await get_user_info(chat_id, u)
                lines.append(f"{medals[i]} {format_user_display(uinfo, u)} — `{c}`")
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"🏆 **برترین‌ها:**\n\n" + "\n".join(lines) + "\n\n⚡ **FLUXBOT**")
            return

        mm = re.match(r"^سکوت\s+(\d+)$", clean_text)
        if mm:
            if not can_manage: return
            mins = int(mm.group(1))
            if mins <= 0: return
            tgt = await find_reply_target(message, chat_id)
            if tgt == "BOT_SELF": return
            if not tgt: tgt = sender_id
            if tgt == OWNER_ID: return
            et = time.time() + mins * 60
            if "mute_list" not in bot_data: bot_data["mute_list"] = {}
            if chat_id not in bot_data["mute_list"]: bot_data["mute_list"][chat_id] = {}
            bot_data["mute_list"][chat_id][tgt] = et
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"🔇 سکوت {mins} دقیقه (پایان: {datetime.fromtimestamp(et, tz=IRAN_TZ).strftime('%H:%M')})")
            return

        wsm = re.match(r"^تنظیم\s+اخطار\s+(\d+)$", clean_text)
        if wsm:
            if not is_owner_group: return
            lim = int(wsm.group(1))
            if lim <= 0 or lim > 500: return
            bot_data["warn_limit"][chat_id] = lim
            settings["warning"] = True
            bot_data["settings"] = settings
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, text=f"✅ حد اخطار: {lim}", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "اخطار"):
            if not is_owner_group: return
            tgt = await find_reply_target(message, chat_id)
            if tgt == "BOT_SELF": return
            if not tgt:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            await add_warning(chat_id, tgt, "اخطار دستی مالک")
            return

        if is_command(clean_text, "لیست قفل"):
            if not can_manage: return

            def _lock_stat(v):
                return "🔴 بسته" if v else "🟢 باز"

            def _feature_stat(v):
                return "🟢 فعال" if v else "🔴 غیرفعال"

            wl = bot_data["warn_limit"].get(chat_id, 3)
            fc = len(ensure_list_dict(bot_data, "filtered_words", chat_id))
            gl, gr = is_group_locked(chat_id)
            gs = f"🔴 بسته ({gr})" if gl else "🟢 باز"
            wda = get_warn_delete_after(chat_id)
            if wda > 0:
                m, s = wda // 60, wda % 60
                wds = f"🟢 فعال ({m}د {s}ث)" if m > 0 else f"🟢 فعال ({wda}ث)"
            else:
                wds = "🔴 غیرفعال"
            ar = bot_data.get("anti_repeat", {}).get(chat_id)
            ars = f"🟢 فعال ({ar} پیام یکسان)" if ar else "🔴 غیرفعال"
            slow = bot_data.get("slow_mode", {}).get(chat_id)
            slows = f"🟢 فعال ({format_duration(slow)})" if slow else "🔴 غیرفعال"
            rl = bot_data.get("rules", {}).get(chat_id)
            rs = "🟢 تنظیم شده" if rl else "🔴 تنظیم نشده"
            tk = _feature_stat(is_talkative_enabled(chat_id))
            bets = _feature_stat(settings.get("betting_enabled", True))

            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                "📋 **قفل‌ها**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 لینک: {_lock_stat(settings['link'])}\n"
                f"🆔 آیدی: {_lock_stat(settings['id'])}\n"
                f"📢 اسپم: {_lock_stat(settings['spam'])}\n"
                f"🔗 هایپرلینک: {_lock_stat(settings['hyperlink'])}\n"
                f"👋 خوش‌آمد: {_feature_stat(settings.get('welcome', True))}\n"
                f"🤬 فحش: {_lock_stat(settings.get('profanity', True))}\n"
                f"📨 فوروارد: {_lock_stat(settings.get('forward', False))}\n"
                f"🎞️ گیف: {_lock_stat(settings.get('gif', False))}\n"
                f"😀 ایموجی: {_lock_stat(settings.get('emoji', False))}\n"
                f"🩹 استیکر: {_lock_stat(settings.get('sticker', False))}\n"
                f"🔢 عدد: {_lock_stat(settings.get('number', False))}\n"
                f"🔤 انگلیسی: {_lock_stat(settings.get('english', False))}\n"
                f"🚫 کلمات غیرمجاز: {_lock_stat(settings.get('forbidden_words', False))}\n"
                f"✏️ ویرایش: {_lock_stat(settings.get('edit', False))}\n"
                f"🔒 قفل گروه: {gs}\n"
                f"⚠️ اخطار: {_feature_stat(settings['warning'])} ({wl})\n"
                f"⏱️ حذف اخطار: {wds}\n"
                f"🚫 فیلتر: {fc}/{MAX_FILTER_WORDS}\n"
                f"🔁 ضد تکرار: {ars}\n"
                f"🐌 حالت آهسته: {slows}\n"
                f"📜 قوانین: {rs}\n"
                f"💬 سخنگو: {tk}\n"
                f"🎰 شرط بندی: {bets}\n\n"
                "⚡ **FLUXBOT**"))
            return

        am = re.match(r"^تنظیم\s+اصل\s+(.+)$", clean_text)
        if am:
            av = am.group(1).strip()
            if not av: return
            tl = ensure_list_dict(bot_data, "taken_asl", chat_id)
            ca = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("asl")
            if av in tl and av != ca:
                await bot.send_message(chat_id=chat_id, text="❌ تکراری", reply_to_message_id=message.message_id); return
            if chat_id not in bot_data["user_titles"]: bot_data["user_titles"][chat_id] = {}
            if sender_id not in bot_data["user_titles"][chat_id]: bot_data["user_titles"][chat_id][sender_id] = {}
            if ca and ca in tl: tl.remove(ca)
            bot_data["user_titles"][chat_id][sender_id]["asl"] = av
            if av not in tl: tl.append(av)
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, text=f"✅ اصل: `{av}`", reply_to_message_id=message.message_id)
            return

        lm = re.match(r"^تنظیم\s+لقب\s+(.+)$", clean_text)
        if lm:
            lv = lm.group(1).strip()
            if not lv: return
            tl = ensure_list_dict(bot_data, "taken_laghab", chat_id)
            cl = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("laghab")
            if lv in tl and lv != cl:
                await bot.send_message(chat_id=chat_id, text="❌ تکراری", reply_to_message_id=message.message_id); return
            if chat_id not in bot_data["user_titles"]: bot_data["user_titles"][chat_id] = {}
            if sender_id not in bot_data["user_titles"][chat_id]: bot_data["user_titles"][chat_id][sender_id] = {}
            if cl and cl in tl: tl.remove(cl)
            bot_data["user_titles"][chat_id][sender_id]["laghab"] = lv
            if lv not in tl: tl.append(lv)
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, text=f"✅ لقب: `{lv}`", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "پروفایل", "آمار", "امار", "آمارم", "امارم"):
            ut = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {})
            asl = ut.get("asl", "ثبت نشده")
            lgh = ut.get("laghab", "ثبت نشده")
            today = get_local_now().strftime("%Y-%m-%d")
            cn = bot_data["message_counts"].get(chat_id, {}).get(sender_id, {})
            tc = cn.get("today", 0) if cn.get("date") == today else 0
            if chat_id not in bot_data["join_dates"]: bot_data["join_dates"][chat_id] = {}
            if sender_id not in bot_data["join_dates"][chat_id]:
                bot_data["join_dates"][chat_id][sender_id] = get_now_time()
                save_data(bot_data)
            jd = bot_data["join_dates"][chat_id][sender_id]
            ss = "⭐ ویژه" if is_special else "عادی"
            wc = bot_data["warnings"].get(chat_id, {}).get(sender_id, 0)
            wl = bot_data["warn_limit"].get(chat_id, 3)
            pts = get_points(sender_id)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                f"📊 **پروفایل {disp}**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🐺 اصل: `{asl}`\n🎭 لقب: `{lgh}`\n👑 مقام: {role}\n"
                f"⭐ وضعیت: {ss}\n💎 امتیاز: `{pts}`\n⚠️ اخطار: [{wc}/{wl}]\n"
                f"📅 پیوست: {jd}\n💬 پیام امروز: {tc}\n\n⚡ **FLUXBOT**"))
            return

    except Exception as e:
        print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)
        try:
            traceback.print_exc()
        except: pass


async def main():
    print("🤖 FLUXBOT STARTING...", flush=True)
    print(f"👑 OWNER: {OWNER_ID}", flush=True)
    print(f"💬 KEYWORDS: {len(TALKATIVE_MAP)} | JOKES: {len(JOKES)} | BOT_ACTIVE: {bot_is_active}", flush=True)
    print(f"🎮 MODULAR GAMES: {len(MODULAR_GAMES)}", flush=True)
    try: asyncio.create_task(cleanup_task())
    except: pass
    try: asyncio.create_task(group_cleanup_task())
    except: pass
    try: await bot.run()
    except Exception as e: print(f"❌ BOT RUN: {type(e).__name__}: {e}", flush=True)


# محفوظ از نسخهٔ تکراری/خراب: if __name__ == "__main__":
# محفوظ از نسخهٔ تکراری/خراب:     asyncio.run(main())          await bot.send_message(chat_id=chat_id, text=msg, reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         # قفل گروه (با هر فرمت)
# محفوظ از نسخهٔ تکراری/خراب:         if _strip_zwnj(clean_text) in ("قفلگروه", "قفلگرو"):
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             if "group_locks" not in bot_data: bot_data["group_locks"] = {}
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["group_locks"][chat_id] = True
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="🔒 **گروه قفل شد!**\n\nباز: `باز`")
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         tm = re.match(r"^قفل\s+(\d+)$", clean_text)
# محفوظ از نسخهٔ تکراری/خراب:         if tm:
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             h = int(tm.group(1))
# محفوظ از نسخهٔ تکراری/خراب:             if h <= 0 or h > 168: return
# محفوظ از نسخهٔ تکراری/خراب:             et = time.time() + h * 3600
# محفوظ از نسخهٔ تکراری/خراب:             if "temp_locks" not in bot_data: bot_data["temp_locks"] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if "group_locks" not in bot_data: bot_data["group_locks"] = {}
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["temp_locks"][chat_id] = et
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["group_locks"][chat_id] = False
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
# محفوظ از نسخهٔ تکراری/خراب:                 f"🔒 **قفل موقت: {h} ساعت**\n🕐 پایان: {datetime.fromtimestamp(et, tz=IRAN_TZ).strftime('%H:%M - %Y/%m/%d')}"))
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         sm = re.match(r"^قفل\s+(\d{1,2}):(\d{2})\s+(?:تا\s+)?(\d{1,2}):(\d{2})$", clean_text)
# محفوظ از نسخهٔ تکراری/خراب:         if sm:
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             sh, sm2, eh, em = map(int, sm.groups())
# محفوظ از نسخهٔ تکراری/خراب:             if not (0 <= sh <= 23 and 0 <= sm2 <= 59 and 0 <= eh <= 23 and 0 <= em <= 59): return
# محفوظ از نسخهٔ تکراری/خراب:             if "scheduled_locks" not in bot_data: bot_data["scheduled_locks"] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if chat_id not in bot_data["scheduled_locks"]: bot_data["scheduled_locks"][chat_id] = []
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["scheduled_locks"][chat_id].append((sh, sm2, eh, em))
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"🔒 **قفل: {sh:02d}:{sm2:02d} تا {eh:02d}:{em:02d}**")
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "حذف قفل زمان‌بندی"):
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             if "scheduled_locks" not in bot_data: bot_data["scheduled_locks"] = {}
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["scheduled_locks"][chat_id] = []
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, text="✅ حذف شد.", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if _strip_zwnj(clean_text) in ("لیستقفلگروه", "لیستقفلگرو"):
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             s = []
# محفوظ از نسخهٔ تکراری/خراب:             gl = bot_data.get("group_locks", {}).get(chat_id, False)
# محفوظ از نسخهٔ تکراری/خراب:             tl = bot_data.get("temp_locks", {}).get(chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             sl_list = bot_data.get("scheduled_locks", {}).get(chat_id, [])
# محفوظ از نسخهٔ تکراری/خراب:             current_locked, current_reason = is_group_locked(chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             s.append("🔴 قفل دستی: بسته" if gl else "🟢 قفل دستی: باز")
# محفوظ از نسخهٔ تکراری/خراب:             try:
# محفوظ از نسخهٔ تکراری/خراب:                 temp_active = bool(tl) and float(tl) > time.time()
# محفوظ از نسخهٔ تکراری/خراب:             except (TypeError, ValueError):
# محفوظ از نسخهٔ تکراری/خراب:                 temp_active = False
# محفوظ از نسخهٔ تکراری/خراب:             if temp_active:
# محفوظ از نسخهٔ تکراری/خراب:                 s.append(f"🔴 قفل موقت: بسته ({get_remaining_time(float(tl))})")
# محفوظ از نسخهٔ تکراری/خراب:             else:
# محفوظ از نسخهٔ تکراری/خراب:                 s.append("🟢 قفل موقت: باز")
# محفوظ از نسخهٔ تکراری/خراب:             if sl_list:
# محفوظ از نسخهٔ تکراری/خراب:                 sl = []
# محفوظ از نسخهٔ تکراری/خراب:                 for interval in sl_list:
# محفوظ از نسخهٔ تکراری/خراب:                     try:
# محفوظ از نسخهٔ تکراری/خراب:                         sh, sm, eh, em = map(int, interval)
# محفوظ از نسخهٔ تکراری/خراب:                         if not (0 <= sh <= 23 and 0 <= sm <= 59 and
# محفوظ از نسخهٔ تکراری/خراب:                                 0 <= eh <= 23 and 0 <= em <= 59):
# محفوظ از نسخهٔ تکراری/خراب:                             continue
# محفوظ از نسخهٔ تکراری/خراب:                         sl.append(f"  • {sh:02d}:{sm:02d} تا {eh:02d}:{em:02d}")
# محفوظ از نسخهٔ تکراری/خراب:                     except (TypeError, ValueError):
# محفوظ از نسخهٔ تکراری/خراب:                         continue
# محفوظ از نسخهٔ تکراری/خراب:                 schedule_state = (
# محفوظ از نسخهٔ تکراری/خراب:                     "🔴 بسته" if current_locked and "زمان‌بندی" in current_reason
# محفوظ از نسخهٔ تکراری/خراب:                     else "🟢 باز"
# محفوظ از نسخهٔ تکراری/خراب:                 )
# محفوظ از نسخهٔ تکراری/خراب:                 schedule_text = "\n".join(sl) if sl else "مورد معتبری ثبت نشده است."
# محفوظ از نسخهٔ تکراری/خراب:                 s.append(f"⏰ زمان‌بندی: {schedule_state}\n{schedule_text}")
# محفوظ از نسخهٔ تکراری/خراب:             else:
# محفوظ از نسخهٔ تکراری/خراب:                 s.append("⏰ زمان‌بندی: 🟢 باز")
# محفوظ از نسخهٔ تکراری/خراب:             s.append(f"🔒 وضعیت فعلی گروه: {'🔴 بسته' if current_locked else '🟢 باز'}")
# محفوظ از نسخهٔ تکراری/خراب:             ar = bot_data.get("anti_repeat", {}).get(chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             s.append(f"🔁 ضد تکرار: {'🔴 ' + str(ar) + ' پیام یکسان' if ar else '🟢 غیرفعال'}")
# محفوظ از نسخهٔ تکراری/خراب:             slow = bot_data.get("slow_mode", {}).get(chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             s.append(f"🐌 حالت آهسته: {'🔴 ' + format_duration(slow) if slow else '🟢 غیرفعال'}")
# محفوظ از نسخهٔ تکراری/خراب:             tk = "🟢 فعال" if is_talkative_enabled(chat_id) else "🔴 غیرفعال"
# محفوظ از نسخهٔ تکراری/خراب:             s.append(f"💬 سخنگو: {tk}")
# محفوظ از نسخهٔ تکراری/خراب:             s.append(f"🎰 شرط بندی: {'🟢 فعال' if settings.get('betting_enabled', True) else '🔴 غیرفعال'}")
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
# محفوظ از نسخهٔ تکراری/خراب:                 "🔒 **قفل گروه**\n━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(s) + "\n\n⚡ **FLUXBOT**"))
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if chat_id not in bot_data["group_message_count"]: bot_data["group_message_count"][chat_id] = 0
# محفوظ از نسخهٔ تکراری/خراب:         bot_data["group_message_count"][chat_id] += 1
# محفوظ از نسخهٔ تکراری/خراب:         save_data(bot_data)
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "فعال", "فاعل"):
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             msg = "✅ از قبل فعال." if bot_is_active else "✅ فعال شد."
# محفوظ از نسخهٔ تکراری/خراب:             bot_is_active = True
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["bot_is_active"] = True
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, text=msg, reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "غیرفعال"):
# محفوظ از نسخهٔ تکراری/خراب:             if not is_owner_group: return
# محفوظ از نسخهٔ تکراری/خراب:             msg = "⛔ از قبل غیرفعال." if not bot_is_active else "🛑 غیرفعال شد."
# محفوظ از نسخهٔ تکراری/خراب:             bot_is_active = False
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["bot_is_active"] = False
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, text=msg, reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         wdm = re.match(r"^حذف\s+پیام\s+اخطار\s+(\d+)$", clean_text)
# محفوظ از نسخهٔ تکراری/خراب:         if wdm:
# محفوظ از نسخهٔ تکراری/خراب:             if not is_owner_group: return
# محفوظ از نسخهٔ تکراری/خراب:             sec = int(wdm.group(1))
# محفوظ از نسخهٔ تکراری/خراب:             if sec < 0 or sec > 3600: return
# محفوظ از نسخهٔ تکراری/خراب:             if "warn_delete_after" not in bot_data: bot_data["warn_delete_after"] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if sec == 0:
# محفوظ از نسخهٔ تکراری/خراب:                 bot_data["warn_delete_after"][chat_id] = 0
# محفوظ از نسخهٔ تکراری/خراب:                 save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="✅ **غیرفعال شد.**", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             else:
# محفوظ از نسخهٔ تکراری/خراب:                 bot_data["warn_delete_after"][chat_id] = sec
# محفوظ از نسخهٔ تکراری/خراب:                 save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:                 m, s = sec // 60, sec % 60
# محفوظ از نسخهٔ تکراری/خراب:                 ts = f"{m} دقیقه" + (f" و {s} ثانیه" if s > 0 else "") if m > 0 else f"{sec} ثانیه"
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text=f"✅ **فعال شد ({ts}).**", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "بن", "سیک", "اخراج"):
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             tgt = await find_reply_target(message, chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             if tgt == "BOT_SELF": return
# محفوظ از نسخهٔ تکراری/خراب:             if not tgt:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:                 return
# محفوظ از نسخهٔ تکراری/خراب:             if tgt == OWNER_ID: return
# محفوظ از نسخهٔ تکراری/خراب:             try:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.ban_member_chat(chat_id, tgt)
# محفوظ از نسخهٔ تکراری/خراب:                 if chat_id not in bot_data["banned_users"]: bot_data["banned_users"][chat_id] = {}
# محفوظ از نسخهٔ تکراری/خراب:                 bot_data["banned_users"][chat_id][tgt] = time.time()
# محفوظ از نسخهٔ تکراری/خراب:                 save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:                 await send_user_mention_message(
# محفوظ از نسخهٔ تکراری/خراب:                     chat_id, tgt, f"🚫 {USER_MENTION_TOKEN} از گروه اخراج شد.",
# محفوظ از نسخهٔ تکراری/خراب:                     reply_to_message_id=message.message_id, bot_client=bot,
# محفوظ از نسخهٔ تکراری/خراب:                 )
# محفوظ از نسخهٔ تکراری/خراب:             except Exception as e:
# محفوظ از نسخهٔ تکراری/خراب:                 print(f"⚠️ ban: {e}", flush=True)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "انبن", "آنبن"):
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             tgt = await find_reply_target(message, chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             if tgt == "BOT_SELF": return
# محفوظ از نسخهٔ تکراری/خراب:             if not tgt:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:                 return
# محفوظ از نسخهٔ تکراری/خراب:             try:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.unban_member_chat(chat_id, tgt)
# محفوظ از نسخهٔ تکراری/خراب:                 if chat_id in bot_data["banned_users"] and tgt in bot_data["banned_users"][chat_id]:
# محفوظ از نسخهٔ تکراری/خراب:                     del bot_data["banned_users"][chat_id][tgt]
# محفوظ از نسخهٔ تکراری/خراب:                     save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:                 await send_user_mention_message(
# محفوظ از نسخهٔ تکراری/خراب:                     chat_id, tgt, f"✅ مسدودیت {USER_MENTION_TOKEN} برداشته شد.",
# محفوظ از نسخهٔ تکراری/خراب:                     reply_to_message_id=message.message_id, bot_client=bot,
# محفوظ از نسخهٔ تکراری/خراب:                 )
# محفوظ از نسخهٔ تکراری/خراب:             except Exception as e:
# محفوظ از نسخهٔ تکراری/خراب:                 print(f"⚠️ unban: {e}", flush=True)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         fm = re.match(r"^فیلتر\s+(.+)$", clean_text)
# محفوظ از نسخهٔ تکراری/خراب:         if fm:
# محفوظ از نسخهٔ تکراری/خراب:             if not is_owner_group: return
# محفوظ از نسخهٔ تکراری/خراب:             w = fm.group(1).strip()
# محفوظ از نسخهٔ تکراری/خراب:             if not w: return
# محفوظ از نسخهٔ تکراری/خراب:             fl = ensure_list_dict(bot_data, "filtered_words", chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             if w in fl:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="⚠️ از قبل فیلتر شده.", reply_to_message_id=message.message_id); return
# محفوظ از نسخهٔ تکراری/خراب:             if len(fl) >= MAX_FILTER_WORDS:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text=f"⚠️ حداکثر {MAX_FILTER_WORDS}", reply_to_message_id=message.message_id); return
# محفوظ از نسخهٔ تکراری/خراب:             fl.append(w); save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"✅ **«{w}» فیلتر شد** ({len(fl)}/{MAX_FILTER_WORDS})")
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         ufm = re.match(r"^حذف\s+فیلتر\s+(.+)$", clean_text)
# محفوظ از نسخهٔ تکراری/خراب:         if ufm:
# محفوظ از نسخهٔ تکراری/خراب:             if not is_owner_group: return
# محفوظ از نسخهٔ تکراری/خراب:             w = ufm.group(1).strip()
# محفوظ از نسخهٔ تکراری/خراب:             fl = ensure_list_dict(bot_data, "filtered_words", chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             if w in fl:
# محفوظ از نسخهٔ تکراری/خراب:                 fl.remove(w); save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text=f"✅ «{w}» حذف شد.", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             else: await bot.send_message(chat_id=chat_id, text="⚠️ نبود.", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "لیست فیلتر"):
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             w = ensure_list_dict(bot_data, "filtered_words", chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             if not w: t = "📋 خالی"
# محفوظ از نسخهٔ تکراری/خراب:             else: t = f"📋 ({len(w)}/{MAX_FILTER_WORDS}):\n\n" + "\n".join([f"├ 🚫 {x}" for x in w])
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, text=t, reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "جک", "جوک"):
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"😂 {random.choice(JOKES)}\n\n⚡ **FLUXBOT**"); return
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "ضرب المثل", "ضرب‌المثل"):
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"📜 {random.choice(PROVERBS)}\n\n⚡ **FLUXBOT**"); return
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "دانستی", "دانستنی"):
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"💡 {random.choice(TRIVIA)}\n\n⚡ **FLUXBOT**"); return
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "فکت"):
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"🧠 {random.choice(FACTS)}\n\n⚡ **FLUXBOT**"); return
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "پ ن پ", "پنپ"):
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"💚 {random.choice(PNP)}\n\n⚡ **FLUXBOT**"); return
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "شعر"):
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"📝 {random.choice(POEMS)}\n\n⚡ **FLUXBOT**"); return
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "فال"):
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"{random.choice(FAL)}\n\n⚡ **FLUXBOT**"); return
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "شانس"):
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"{random.choice(LUCK)}\n\n⚡ **FLUXBOT**"); return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "آمار گروه", "تاپ", "برترین‌ها"):
# محفوظ از نسخهٔ تکراری/خراب:             today = get_local_now().strftime("%Y-%m-%d")
# محفوظ از نسخهٔ تکراری/خراب:             counts = bot_data["message_counts"].get(chat_id, {})
# محفوظ از نسخهٔ تکراری/خراب:             tc = [(u, d["today"]) for u, d in counts.items() if d.get("date") == today and d.get("today", 0) > 0]
# محفوظ از نسخهٔ تکراری/خراب:             tc.sort(key=lambda x: x[1], reverse=True)
# محفوظ از نسخهٔ تکراری/خراب:             top = tc[:10]
# محفوظ از نسخهٔ تکراری/خراب:             if not top:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="📊 امروز پیامی نبود.", reply_to_message_id=message.message_id); return
# محفوظ از نسخهٔ تکراری/خراب:             medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
# محفوظ از نسخهٔ تکراری/خراب:             lines = []
# محفوظ از نسخهٔ تکراری/خراب:             for i, (u, c) in enumerate(top):
# محفوظ از نسخهٔ تکراری/خراب:                 uinfo = await get_user_info(chat_id, u)
# محفوظ از نسخهٔ تکراری/خراب:                 lines.append(f"{medals[i]} {format_user_display(uinfo, u)} — `{c}`")
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"🏆 **برترین‌ها:**\n\n" + "\n".join(lines) + "\n\n⚡ **FLUXBOT**")
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "سکوت"):
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             tgt = await find_reply_target(message, chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             if tgt == "BOT_SELF": return
# محفوظ از نسخهٔ تکراری/خراب:             if not tgt:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:                 return
# محفوظ از نسخهٔ تکراری/خراب:             if tgt == OWNER_ID: return
# محفوظ از نسخهٔ تکراری/خراب:             if "mute_list" not in bot_data: bot_data["mute_list"] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if chat_id not in bot_data["mute_list"]: bot_data["mute_list"][chat_id] = {}
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["mute_list"][chat_id][tgt] = 9999999999
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             try:
# محفوظ از نسخهٔ تکراری/خراب:                 await send_user_mention_message(
# محفوظ از نسخهٔ تکراری/خراب:                     chat_id, tgt,
# محفوظ از نسخهٔ تکراری/خراب:                     f"🔇 {USER_MENTION_TOKEN} برای همیشه سکوت شد!\n\n"
# محفوظ از نسخهٔ تکراری/خراب:                     f"💡 برای آزادسازی: `رفع سکوت` (ریپلای)\n\n"
# محفوظ از نسخهٔ تکراری/خراب:                     f"⚡ **FLUXBOT**",
# محفوظ از نسخهٔ تکراری/خراب:                     reply_to_message_id=message.message_id, bot_client=bot,
# محفوظ از نسخهٔ تکراری/خراب:                 )
# محفوظ از نسخهٔ تکراری/خراب:             except Exception as e:
# محفوظ از نسخهٔ تکراری/خراب:                 print(f"⚠️ mute forever: {e}", flush=True)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         mm = re.match(r"^سکوت\s+(\d+)$", clean_text)
# محفوظ از نسخهٔ تکراری/خراب:         if mm:
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             mins = int(mm.group(1))
# محفوظ از نسخهٔ تکراری/خراب:             if mins <= 0: return
# محفوظ از نسخهٔ تکراری/خراب:             tgt = await find_reply_target(message, chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             if tgt == "BOT_SELF": return
# محفوظ از نسخهٔ تکراری/خراب:             if not tgt: tgt = sender_id
# محفوظ از نسخهٔ تکراری/خراب:             if tgt == OWNER_ID: return
# محفوظ از نسخهٔ تکراری/خراب:             et = time.time() + mins * 60
# محفوظ از نسخهٔ تکراری/خراب:             if "mute_list" not in bot_data: bot_data["mute_list"] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if chat_id not in bot_data["mute_list"]: bot_data["mute_list"][chat_id] = {}
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["mute_list"][chat_id][tgt] = et
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"🔇 سکوت {mins} دقیقه (پایان: {datetime.fromtimestamp(et, tz=IRAN_TZ).strftime('%H:%M')})")
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "رفع سکوت", "حذف سکوت", "آزاد", "آنمیوت", "انمیوت"):
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب:             tgt = await find_reply_target(message, chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             if tgt == "BOT_SELF": return
# محفوظ از نسخهٔ تکراری/خراب:             if not tgt:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:                 return
# محفوظ از نسخهٔ تکراری/خراب:             if "mute_list" not in bot_data: bot_data["mute_list"] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if chat_id not in bot_data["mute_list"]: bot_data["mute_list"][chat_id] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if tgt in bot_data["mute_list"][chat_id]:
# محفوظ از نسخهٔ تکراری/خراب:                 del bot_data["mute_list"][chat_id][tgt]
# محفوظ از نسخهٔ تکراری/خراب:                 save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:                 try:
# محفوظ از نسخهٔ تکراری/خراب:                     await send_user_mention_message(
# محفوظ از نسخهٔ تکراری/خراب:                         chat_id, tgt,
# محفوظ از نسخهٔ تکراری/خراب:                         f"🔊 {USER_MENTION_TOKEN} از سکوت خارج شد!\n\n"
# محفوظ از نسخهٔ تکراری/خراب:                         f"✅ حالا می‌تونه آزادانه پیام بفرسته.\n\n"
# محفوظ از نسخهٔ تکراری/خراب:                         f"⚡ **FLUXBOT**",
# محفوظ از نسخهٔ تکراری/خراب:                         reply_to_message_id=message.message_id, bot_client=bot,
# محفوظ از نسخهٔ تکراری/خراب:                     )
# محفوظ از نسخهٔ تکراری/خراب:                 except Exception as e:
# محفوظ از نسخهٔ تکراری/خراب:                     print(f"⚠️ unmute: {e}", flush=True)
# محفوظ از نسخهٔ تکراری/خراب:             else:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="ℹ️ این کاربر در حال سکوت نیست.", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         wsm = re.match(r"^تنظیم\s+اخطار\s+(\d+)$", clean_text)
# محفوظ از نسخهٔ تکراری/خراب:         if wsm:
# محفوظ از نسخهٔ تکراری/خراب:             if not is_owner_group: return
# محفوظ از نسخهٔ تکراری/خراب:             lim = int(wsm.group(1))
# محفوظ از نسخهٔ تکراری/خراب:             if lim <= 0 or lim > 500: return
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["warn_limit"][chat_id] = lim
# محفوظ از نسخهٔ تکراری/خراب:             settings["warning"] = True
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["settings"] = settings
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, text=f"✅ حد اخطار: {lim}", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "اخطار"):
# محفوظ از نسخهٔ تکراری/خراب:             if not is_owner_group: return
# محفوظ از نسخهٔ تکراری/خراب:             tgt = await find_reply_target(message, chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             if tgt == "BOT_SELF": return
# محفوظ از نسخهٔ تکراری/خراب:             if not tgt:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:                 return
# محفوظ از نسخهٔ تکراری/خراب:             await add_warning(chat_id, tgt, "اخطار دستی مالک")
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "لیست قفل"):
# محفوظ از نسخهٔ تکراری/خراب:             if not can_manage: return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:             def _lock_stat(v):
# محفوظ از نسخهٔ تکراری/خراب:                 return "🔴 بسته" if v else "🟢 باز"
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:             def _feature_stat(v):
# محفوظ از نسخهٔ تکراری/خراب:                 return "🟢 فعال" if v else "🔴 غیرفعال"
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:             wl = bot_data["warn_limit"].get(chat_id, 3)
# محفوظ از نسخهٔ تکراری/خراب:             fc = len(ensure_list_dict(bot_data, "filtered_words", chat_id))
# محفوظ از نسخهٔ تکراری/خراب:             gl, gr = is_group_locked(chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             gs = f"🔴 بسته ({gr})" if gl else "🟢 باز"
# محفوظ از نسخهٔ تکراری/خراب:             wda = get_warn_delete_after(chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             if wda > 0:
# محفوظ از نسخهٔ تکراری/خراب:                 m, s = wda // 60, wda % 60
# محفوظ از نسخهٔ تکراری/خراب:                 wds = f"🟢 فعال ({m}د {s}ث)" if m > 0 else f"🟢 فعال ({wda}ث)"
# محفوظ از نسخهٔ تکراری/خراب:             else:
# محفوظ از نسخهٔ تکراری/خراب:                 wds = "🔴 غیرفعال"
# محفوظ از نسخهٔ تکراری/خراب:             ar = bot_data.get("anti_repeat", {}).get(chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             ars = f"🟢 فعال ({ar} پیام یکسان)" if ar else "🔴 غیرفعال"
# محفوظ از نسخهٔ تکراری/خراب:             slow = bot_data.get("slow_mode", {}).get(chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             slows = f"🟢 فعال ({format_duration(slow)})" if slow else "🔴 غیرفعال"
# محفوظ از نسخهٔ تکراری/خراب:             rl = bot_data.get("rules", {}).get(chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             rs = "🟢 تنظیم شده" if rl else "🔴 تنظیم نشده"
# محفوظ از نسخهٔ تکراری/خراب:             tk = _feature_stat(is_talkative_enabled(chat_id))
# محفوظ از نسخهٔ تکراری/خراب:             bets = _feature_stat(settings.get("betting_enabled", True))
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
# محفوظ از نسخهٔ تکراری/خراب:                 "📋 **قفل‌ها**\n━━━━━━━━━━━━━━━━━━━\n\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🔗 لینک: {_lock_stat(settings['link'])}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🆔 آیدی: {_lock_stat(settings['id'])}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"📢 اسپم: {_lock_stat(settings['spam'])}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🔗 هایپرلینک: {_lock_stat(settings['hyperlink'])}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"👋 خوش‌آمد: {_feature_stat(settings.get('welcome', True))}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🤬 فحش: {_lock_stat(settings.get('profanity', True))}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"📨 فوروارد: {_lock_stat(settings.get('forward', False))}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🎞️ گیف: {_lock_stat(settings.get('gif', False))}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🔒 قفل گروه: {gs}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"⚠️ اخطار: {_feature_stat(settings['warning'])} ({wl})\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"⏱️ حذف اخطار: {wds}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🚫 فیلتر: {fc}/{MAX_FILTER_WORDS}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🔁 ضد تکرار: {ars}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🐌 حالت آهسته: {slows}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"📜 قوانین: {rs}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"💬 سخنگو: {tk}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🎰 شرط بندی: {bets}\n\n"
# محفوظ از نسخهٔ تکراری/خراب:                 "⚡ **FLUXBOT**"))
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         am = re.match(r"^تنظیم\s+اصل\s+(.+)$", clean_text)
# محفوظ از نسخهٔ تکراری/خراب:         if am:
# محفوظ از نسخهٔ تکراری/خراب:             av = am.group(1).strip()
# محفوظ از نسخهٔ تکراری/خراب:             if not av: return
# محفوظ از نسخهٔ تکراری/خراب:             tl = ensure_list_dict(bot_data, "taken_asl", chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             ca = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("asl")
# محفوظ از نسخهٔ تکراری/خراب:             if av in tl and av != ca:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="❌ تکراری", reply_to_message_id=message.message_id); return
# محفوظ از نسخهٔ تکراری/خراب:             if chat_id not in bot_data["user_titles"]: bot_data["user_titles"][chat_id] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if sender_id not in bot_data["user_titles"][chat_id]: bot_data["user_titles"][chat_id][sender_id] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if ca and ca in tl: tl.remove(ca)
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["user_titles"][chat_id][sender_id]["asl"] = av
# محفوظ از نسخهٔ تکراری/خراب:             if av not in tl: tl.append(av)
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, text=f"✅ اصل: `{av}`", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         lm = re.match(r"^تنظیم\s+لقب\s+(.+)$", clean_text)
# محفوظ از نسخهٔ تکراری/خراب:         if lm:
# محفوظ از نسخهٔ تکراری/خراب:             lv = lm.group(1).strip()
# محفوظ از نسخهٔ تکراری/خراب:             if not lv: return
# محفوظ از نسخهٔ تکراری/خراب:             tl = ensure_list_dict(bot_data, "taken_laghab", chat_id)
# محفوظ از نسخهٔ تکراری/خراب:             cl = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("laghab")
# محفوظ از نسخهٔ تکراری/خراب:             if lv in tl and lv != cl:
# محفوظ از نسخهٔ تکراری/خراب:                 await bot.send_message(chat_id=chat_id, text="❌ تکراری", reply_to_message_id=message.message_id); return
# محفوظ از نسخهٔ تکراری/خراب:             if chat_id not in bot_data["user_titles"]: bot_data["user_titles"][chat_id] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if sender_id not in bot_data["user_titles"][chat_id]: bot_data["user_titles"][chat_id][sender_id] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if cl and cl in tl: tl.remove(cl)
# محفوظ از نسخهٔ تکراری/خراب:             bot_data["user_titles"][chat_id][sender_id]["laghab"] = lv
# محفوظ از نسخهٔ تکراری/خراب:             if lv not in tl: tl.append(lv)
# محفوظ از نسخهٔ تکراری/خراب:             save_data(bot_data, force=True)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, text=f"✅ لقب: `{lv}`", reply_to_message_id=message.message_id)
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:         if is_command(clean_text, "پروفایل", "آمار", "امار", "آمارم", "امارم"):
# محفوظ از نسخهٔ تکراری/خراب:             ut = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {})
# محفوظ از نسخهٔ تکراری/خراب:             asl = ut.get("asl", "ثبت نشده")
# محفوظ از نسخهٔ تکراری/خراب:             lgh = ut.get("laghab", "ثبت نشده")
# محفوظ از نسخهٔ تکراری/خراب:             today = get_local_now().strftime("%Y-%m-%d")
# محفوظ از نسخهٔ تکراری/خراب:             cn = bot_data["message_counts"].get(chat_id, {}).get(sender_id, {})
# محفوظ از نسخهٔ تکراری/خراب:             tc = cn.get("today", 0) if cn.get("date") == today else 0
# محفوظ از نسخهٔ تکراری/خراب:             if chat_id not in bot_data["join_dates"]: bot_data["join_dates"][chat_id] = {}
# محفوظ از نسخهٔ تکراری/خراب:             if sender_id not in bot_data["join_dates"][chat_id]:
# محفوظ از نسخهٔ تکراری/خراب:                 bot_data["join_dates"][chat_id][sender_id] = get_now_time()
# محفوظ از نسخهٔ تکراری/خراب:                 save_data(bot_data)
# محفوظ از نسخهٔ تکراری/خراب:             jd = bot_data["join_dates"][chat_id][sender_id]
# محفوظ از نسخهٔ تکراری/خراب:             ss = "⭐ ویژه" if is_special else "عادی"
# محفوظ از نسخهٔ تکراری/خراب:             wc = bot_data["warnings"].get(chat_id, {}).get(sender_id, 0)
# محفوظ از نسخهٔ تکراری/خراب:             wl = bot_data["warn_limit"].get(chat_id, 3)
# محفوظ از نسخهٔ تکراری/خراب:             pts = get_points(sender_id)
# محفوظ از نسخهٔ تکراری/خراب:             await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
# محفوظ از نسخهٔ تکراری/خراب:                 f"📊 **پروفایل {disp}**\n━━━━━━━━━━━━━━━━━━━\n\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"🐺 اصل: `{asl}`\n🎭 لقب: `{lgh}`\n👑 مقام: {role}\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"⭐ وضعیت: {ss}\n💎 امتیاز: `{pts}`\n⚠️ اخطار: [{wc}/{wl}]\n"
# محفوظ از نسخهٔ تکراری/خراب:                 f"📅 پیوست: {jd}\n💬 پیام امروز: {tc}\n\n⚡ **FLUXBOT**"))
# محفوظ از نسخهٔ تکراری/خراب:             return
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب:     except Exception as e:
# محفوظ از نسخهٔ تکراری/خراب:         print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)
# محفوظ از نسخهٔ تکراری/خراب:         try:
# محفوظ از نسخهٔ تکراری/خراب:             traceback.print_exc()
# محفوظ از نسخهٔ تکراری/خراب:         except: pass
# محفوظ از نسخهٔ تکراری/خراب: 
# محفوظ از نسخهٔ تکراری/خراب: 
async def main():
    print("🤖 FLUXBOT STARTING...", flush=True)
    print(f"👑 OWNER: {OWNER_ID}", flush=True)
    print(f"💬 KEYWORDS: {len(TALKATIVE_MAP)} | JOKES: {len(JOKES)} | BOT_ACTIVE: {bot_is_active}", flush=True)
    print(f"🎮 MODULAR GAMES: {len(MODULAR_GAMES)}", flush=True)
    try: asyncio.create_task(cleanup_task())
    except: pass
    try: asyncio.create_task(group_cleanup_task())
    except: pass
    try: await bot.run()
    except Exception as e: print(f"❌ BOT RUN: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
