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

username_cache = {}
username_cache_ttl = {}
spam_tracker = {}
processed_messages = {}
text_dedup = {}
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


# ================== 🔄 Two-Word Flexible Command Matcher ==================
ON_WORDS = {"باز", "روشن", "فعال", "بازکردن", "بازکن", "on", "enable", "روشن‌کن", "بازش"}
OFF_WORDS = {"بسته", "خاموش", "غیرفعال", "قفل", "بستن", "ببند", "off", "disable", "خاموش‌کن", "قفلش"}


def match_two_word_cmd(text, word):
    """چک می‌کنه 'کلمه + فعل' یا 'فعل + کلمه' - برمی‌گردونه True (روشن) / False (خاموش) / None"""
    if not text:
        return None
    parts = text.strip().split()
    if len(parts) != 2:
        return None
    a, b = parts[0].strip(), parts[1].strip()
    if a == word:
        if b in ON_WORDS: return True
        if b in OFF_WORDS: return False
    if b == word:
        if a in ON_WORDS: return True
        if a in OFF_WORDS: return False
    return None


# ================== 🎨 FONT SYSTEM ==================
def _has_persian(text):
    return bool(re.search(r'[\u0600-\u06FF]', text or ""))


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
    text = text.strip()
    if not text: return None
    if len(text) > 30: text = text[:30] + "…"
    has_en = _has_latin(text)
    sections = []
    if has_en:
        sections.append(("🇬🇧 **استایل‌های انگلیسی:**", [
            ("1️⃣ بولد", font_bold(text)),
            ("2️⃣ ایتالیک", font_italic(text)),
            ("3️⃣ بولد ایتالیک", font_bold_italic(text)),
            ("4️⃣ اسکریپت", font_bold_script(text)),
            ("5️⃣ گوتیک", font_bold_fraktur(text)),
            ("6️⃣ ساده", font_sans(text)),
            ("7️⃣ ساده بولد", font_sans_bold(text)),
            ("8️⃣ مونو", font_mono(text)),
            ("9️⃣ پهن", font_fullwidth(text)),
            ("🔟 کوچک", font_small_caps(text)),
        ]))
    sections.append(("✨ **استایل‌های تزئینی:**", [
        ("✏️ خط‌خورده", deco_strike(text)),
        ("✏️ زیرخط", deco_underline(text)),
        ("✏️ بالای خط", deco_overline(text)),
        ("✏️ دو زیرخط", deco_double_under(text)),
        ("✏️ خط‌دار", deco_slash(text)),
        ("✏️ نقطه‌دار", deco_dot_above(text)),
        ("✿ گل‌دار", f"✿ {text} ✿"),
        ("❁ برگ‌دار", f"❁ {text} ❁"),
        ("【 قاب مربع 】", f"【 {text} 】"),
        ("「 قاب گوشه 」", f"「 {text} 」"),
        ("★彡 ستاره‌ای 彡★", f"★彡 {text} 彡★"),
        ("༺ تیبت ༻", f"༺ {text} ༻"),
        ("•° کلاسیک °•", f"•°¯`•• {text} ••´¯°•"),
        ("▁▂▃ خط پایین ▃▂▁", f"▁▂▃ {text} ▃▂▁"),
    ]))
    lines = [
        "╭─━━━━━━━━━━━━━━━━━━━─╮",
        "   🎨 **فونت‌ساز FLUXBOT** 🎨",
        "╰─━━━━━━━━━━━━━━━━━━━─╯",
        "",
        f"📝 **متن شما:** `{text}`",
        "━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for title, items in sections:
        lines.append(title)
        lines.append("")
        for name, styled in items:
            lines.append(f"**{name}:**")
            lines.append(styled)
            lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
    lines.append("💡 **روی هر خط، نگه دار و کپی کن!**")
    lines.append("")
    lines.append("⚡ **FLUXBOT**")
    return "\n".join(lines)


# ================== 🎯 CHALLENGES ==================
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


# ================== 💬 TALKATIVE (سخنگو) ==================
TALKATIVE_PHRASES = [
    "جونم؟ 🥰", "جانم؟ 💖", "جانم عزیزم 💕", "جانم به قربانت 🌹", "جانان 💝",
    "قربونت 🌷", "فدات 💗", "عزیزم 🌸", "گلم 🌺", "نازنینم 💞",
    "عشقم 💖", "قلبم 💓", "جیگرم 🔥", "دلم 💗", "دلبرم 💐",
    "نفسم 😍", "روحم 🕊️", "زندگیم 💫", "همه چیزم 💖", "قشنگم 🌟",
    "خوشگلم 💕", "زیبای من 🌹", "ماه من 🌙", "خورشیدم ☀️", "ستاره‌م ⭐",
    "قمر 🌸", "پری 🌺", "فرشته 💫", "بوس بفرست 😘", "بوست کنم 🤗",
    "بله؟ 🤗", "چی شد؟ 😊", "چیه؟ 😁", "ها؟ 😅", "چی شده؟ 🤔",
    "چی میگی؟ 😊", "چی می‌خوای؟ 😄", "چی می‌خواستی؟ 🤗", "چی کارم داری؟ 😄", "چی به چیه؟ 🤨",
    "چیشده؟ 😯", "خب بگو 🤔", "بگو ببینم 👀", "بگو دیگه 😊", "چیه دیگه؟ 😜",
    "آره؟ 😐", "جدی؟ 😲", "راست میگی؟ 😳", "واقعا؟ 😮", "اینطور؟ 🤔",
    "در خدمتم 🌹", "درخدمتم 💐", "بفرمایید 🌸", "امر بفرمایید 🙋", "امر کن 🎩",
    "به روی چشم 👁️", "چشم 🫡", "دستور بده 👑", "دستورت چیه؟ ⚡", "در خدمتیم 🌟",
    "چاکرم 💫", "سراپا گوش 🎧", "حاضرم 🎯", "منتظرم ✨", "خدمت شما 📞",
    "بفرما 🌺", "بفرمایید بگید 🌹", "بگو جانم 💐", "بله جانم 🌷", "بله بفرمایید 🌺",
    "بله عزیزم 💕", "با من کاری داشتی؟ 🤗", "بگو 😌", "من اینجام 💫", "غلام شما 🙇",
    "گوش می‌دم 👂", "خب؟ 😏", "بعد؟ 🤨", "دیگه چی؟ 😆", "هستی؟ 🤔",
    "بازم؟ 😄", "ادامه بده 🎬", "برو جلو 🚀", "چشام به دهنت 😯", "گوش گوش 🎧",
    "چی میگی تو؟ 😂", "داری چرت میگی؟ 🤪", "حوصله داری؟ 😴", "برو بابا 😂", "خب که چی؟ 🙄",
    "به من چه؟ 🤷", "نکن اینکارو 🙅", "بیخیال 🚶", "بسه دیگه ✋", "جانم بگو 🌹",
    "بگو ببینم چخبر؟ 📰", "چه خبر؟ 📢", "خبری هست؟ 📰", "بله بله؟ 🤭", "ها چی شده؟ 😯",
    "چی شده یهو؟ 😱", "چیه، ترسیدم 🫣", "بگو تا کی منتظر باشم؟ ⏰", "شرمنده نکن منو 🙈", "چیزی گفتید؟ 👂",
    "منو صدا زدی؟ 📢", "بله؟ بنده؟ 🙋", "قربان؟ 🎩", "بله قربان 🎖️", "اینجام 🙋",
    "سلام؟ 👋", "چیه سلام کردی؟ 😊", "چی میگی عزیز؟ 💐", "بگو ببینم چی داری؟ 🎁", "دستت درد نکنه، بگو 🌹",
    "من خدام 🫡", "به من میگی؟ 🤗", "بله چیه بفرمایید؟ 🌸", "من چاکرتم 💫", "چیزی لازم داری؟ 🤝",
    "کمک بخوای؟ 🆘", "کمکی هست؟ 💪", "چیکار می‌کنی؟ 🎬", "چطوری؟ 😊", "خوبی؟ 💚",
    "سلامتی؟ 🌿", "چیه مگه؟ 🤨", "کی بودی؟ 🕵️", "چی میخواستی آخه؟ 🤔", "جانم عزیز دل 💖",
    "بیا جلو ببینم 👀", "بگو ببینم چی شد؟ 📝", "چی خبر؟ 📻", "چیه یهو یادم افتادی؟ 💭", "بگو بشنوم 🎧",
    "یه لحظه؟ ⏳", "بله، چیزی شده؟ ❓", "بگو دیگه، زود باش ⚡", "چیه یادت افتاد؟ 💡", "صدات کردم که؟ 📞",
    "چیه به چه کارم داری؟ 😄", "چیکارم داری؟ 🤨", "چی میخوای از جونم؟ 😂", "بگو ببینم چیکارم داری؟ 🤗", "درود بر تو 🌟",
    "سلام بر تو 🌸", "علیک سلام 🌹", "چیه سلام منو خوردی؟ 😄", "من گوش میدم، تو بگو 👂", "با ادب حرف بزن 😌",
    "چی گفتی؟ 🤔", "نشنیدم، دوباره بگو 👂", "بلندتر بگو 📢", "چیزی گفتی؟ 🎤", "در خدمت شما 🌷",
    "من اینجام خدمتت 🌹", "چشم و دل 🫀", "دست به کارم 🤝", "بیا اینجا ببینم 🚶", "بگو کی هستی؟ 🕵️",
    "چیه بگو؟ 😊", "چی میگی تو؟ 😅", "جانم؟ بگو 🌹", "چیه مثل برق اومدی؟ ⚡", "چیزی هست؟ 🤔",
    "بگید ببینم 👂", "من آماده‌ام ✅", "چشم، حالا بگو ✨", "بفرمایید سرکار 🌺", "بنده در خدمتم 🙋",
    "چی میخوای؟ بگو دیگه 😊", "بگو ببینم چیشده؟ 🤔", "چیه داری بهم نگاه می‌کنی؟ 👀", "بگو چیت هست؟ 📝", "بفرمایید، بنده گوشم 👂",
    "چیه صدایم زدی؟ 📢", "چیشد یهو؟ ⏰", "بگو من اینجام 🌹", "قربونت برم، چی میگی؟ 💕", "بیا حرف بزنیم 🗣️",
    "چیه میخوای بگی؟ 💬", "بگو ببینم چه مرگت شده؟ 😂", "بیا تو بگو ✨", "چی میخوای بگی؟ 🤔", "بگو دیگه خب 😊",
    "بله بله، بگو 😄", "تو بگو من گوشم 🎧", "چی داری؟ بریز وسط 🎤", "بیا وسط میدون 🏟️", "چی گفتی؟ چاکرم 🫡",
    "بله سرورم 🎖️", "دستور شما اجرا میشه ✅", "چشم ارباب 👑", "درخدمتم قربان 🫡", "بگو ببینم چیکار داری؟ 🤔",
    "ای جانم 💕", "ای دل غافل 🥰", "چی شده رفیق؟ 🤝", "بگو بشینم گوش بدم 🪑", "چی میگی همشهری؟ 🏘️",
    "بیا پایین ببینم 🤔", "چی شده داداش؟ 😎", "چی میگی رفیق؟ 🤜", "بگو ببینم قضیه چیه؟ 🔍", "چیه یکم آروم باش 😌",
    "عسل 🍯", "شکلات 🍫", "قند 🍬", "شکرم 🍬", "قند و نبات 🍭",
    "یه لحظه نگاه کن 😊", "چشم‌های قشنگت رو ببینم 😍", "صدات گرم 🌟", "ای جان 😍", "وای چقدر قشنگ 💕",
    "جونم؟ باز چی میخوای؟ 😏", "باز تو؟ 😄", "چیه دست از سر من برنمی‌داری؟ 😂", "بگو ببینم چیکار داری باز؟ 🤪", "چیشده اینبار؟ 😆",
    "هزار بار گفتم، بگو 😤", "بازم؟ جدی؟ 😵", "نه بابا تو دیگه کی هستی؟ 😂", "شرمنده نکن 😅", "خب دیگه چیه؟ 🙄",
    "فلکس بات در خدمته 💫", "به به چه عجب 🤗", "بله بنده؟ 🙋", "چی می‌خوای از این زبون بسته؟ 🥺", "بگو، مگه دست خودمه؟ 😂",
    "من یه رباتم، تو یه انسان، ولی باز دوستیم 💚", "چیه باز تنهام گذاشتی؟ 🥺", "بگو ببینم چی توی دلت هست 💭", "هی، سلام 😊", "چی شده عزیز؟ 💐",
    "بله چیه؟ 🤔", "چه کردی؟ 🤨", "چی میگی رفیق؟ 😊", "چی می‌خواستی؟ 🤗", "چطور می‌تونم کمکت کنم؟ 💪",
    "چی میخوای عزیز؟ 🌸", "چی لازم داری؟ 🎁", "چی میگی گلم؟ 🌹", "چی میگی جانم؟ 💖", "چی میگی عشقم؟ 💕",
    "بیا بغل 🤗", "بوست کنم 🥰", "دوستت دارم 💖", "عاشقتم 💕", "قلبم برات میزنه 💓",
    "یه بوس چسبیده 😘", "بغلم کن 🤗", "بوس بفرست 🌹", "بغل به بغل 💐", "قربونت برم 💗",
    "ای بابا باز تو؟ 😂", "نه بابا، باز تو اومدی؟ 🤪", "چیه یهو؟ 😯", "بازم شروع شد؟ 🤦", "خب دیگه چی؟ 😅",
    "اه اومدی؟ 😏", "چیه اینبار؟ 🙄", "باز چی شده آخه؟ 😩", "بگو ببینم چخبر؟ 📰", "خب؟ ادامه بده 🎬",
    "خبری هست؟ 📻", "چی خبر؟ 📰", "شنیدم صدات کردم 📞", "چی شده دوباره؟ 😅", "بازم دردسر؟ 😂",
    "بله بنده در خدمتم 🌟", "بگو تا خسته شم 😊", "بگو من چاکرم 🤝", "بگو حرف بزن 🎤", "بگو بشینم گوش کنم 🪑",
    "تو چطوری؟ 😊", "خوبی تو؟ 💚", "چخبر از خودت؟ 📰", "چی کار می‌کنی؟ 🎬", "سلامتی تو؟ 🌿",
    "بله مدیر؟ 🎩", "بله رئیس؟ 👔", "بله سرکار؟ 🌺", "بله بانو؟ 🌹", "بله آقا؟ 🎩",
    "صدای قشنگت 🌟", "کلامت زیبا 💕", "حرفت متین 🌹", "بیانت عالیه ✨", "چقدر قشنگ حرف می‌زنی 💐",
    "چی به من میگی؟ 😏", "باز چی میخوای از این بیچاره؟ 😂", "نه بابا اینم شد کار؟ 🤣", "بنده چاکرم فقط 😌", "چشم تا خود صبح 🫡",
    "چی؟ 🤔", "بله؟ 🤗", "خب؟ 😏", "بعد؟ 🤨", "بازم؟ 😄", "چیه؟ 😊", "چشه؟ 🤔", "ها؟ 😅",
    "بفرمایید 🌺", "بفرما 🌹", "درخدمتم 💫", "چاکرم 🎩", "غلام شما 🙇", "خدمتگزار شما 💐", "بنده حقیر 🫡",
]


TALKATIVE_TRIGGERS_RE = re.compile(
    r"^(?:فلاکس|فلکس|فلوکس|فلکسی)\s*بات|^flux\s*bot",
    re.IGNORECASE
)


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
    if "games" not in bot_data: bot_data["games"] = {}
    return bot_data["games"]


async def game_timeout_check(chat_id, game_type):
    try:
        await asyncio.sleep(GAME_TIMEOUT)
        if game_type == "connect4":
            games = get_games()
            if chat_id in games and games[chat_id].get("status") == "waiting":
                del games[chat_id]
                save_data(bot_data, force=True)
                try:
                    await bot.send_message(chat_id=chat_id, text=(
                        "⏱️ **زمان بازی به پایان رسید!**\n\n"
                        "هیچ‌کس شرکت نکرد و بازی لغو شد.\n\n⚡ **FLUXBOT**"))
                except: pass
        elif game_type == "coinflip":
            if chat_id in coin_flip_games:
                del coin_flip_games[chat_id]
                try:
                    await bot.send_message(chat_id=chat_id, text=(
                        "⏱️ **زمان انتخاب به پایان رسید!**\n\n"
                        "بازی شیر یا خط لغو شد.\n\n⚡ **FLUXBOT**"))
                except: pass
    except Exception as e:
        print(f"⚠️ game_timeout: {e}", flush=True)


async def start_game(chat_id, sender_id, sender_display, color_choice):
    games = get_games()
    if chat_id in games:
        g = games[chat_id]
        if g.get("status") in ("waiting", "playing"): return None
    color1 = "R" if color_choice == "قرمز" else "Y" if color_choice == "زرد" else "R"
    color2 = "Y" if color1 == "R" else "R"
    games[chat_id] = {
        "player1": str(sender_id), "player1_name": sender_display,
        "player2": None, "player2_name": None,
        "color1": color1, "color2": color2,
        "board": [[None]*7 for _ in range(6)],
        "turn": str(sender_id), "status": "waiting",
        "started_at": time.time(),
    }
    save_data(bot_data, force=True)
    try: asyncio.create_task(game_timeout_check(chat_id, "connect4"))
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
    if key not in d:
        d[key] = []
        return d[key]
    if sub_key is not None:
        if not isinstance(d[key], dict): d[key] = {}
        if sub_key not in d[key]: d[key][sub_key] = []
        d[key][sub_key] = ensure_list(d[key][sub_key])
        return d[key][sub_key]
    d[key] = ensure_list(d[key])
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
            data = mi.get("data", mi) if isinstance(mi, dict) else mi
            cm = {}
            if isinstance(data, dict):
                cm = data.get("chat_member") or data.get("member") or data
            if not isinstance(cm, dict):
                cm = {}

            info["name"] = (
                cm.get("first_name") or cm.get("firstName") or
                cm.get("name") or cm.get("title") or
                cm.get("display_name")
            )
            un = cm.get("username") or cm.get("user_name") or cm.get("userName")
            if un: info["username"] = str(un).lstrip("@")

            status_raw = (
                cm.get("status") or cm.get("member_type") or cm.get("memberType") or
                cm.get("role") or cm.get("type") or cm.get("chat_member_type") or
                cm.get("membership") or ""
            )
            if not status_raw and isinstance(data, dict):
                status_raw = data.get("status") or data.get("member_type") or ""

            st = str(status_raw or "").strip().lower().replace("_", "").replace("-", "").replace(" ", "")

            role = "عضو"
            if st in ("creator", "owner", "admincreator", "ownercreator", "superadmin", "chatcreator"):
                role = "مالک"
            elif st in ("admin", "administrator", "moderator", "mod", "chatadmin", "channeladmin"):
                role = "ادمین"
            elif st in ("member", "user", "participant", "regular", "normal", "ordinary"):
                role = "عضو"

            if role == "عضو":
                if cm.get("is_creator") or cm.get("isCreator") or cm.get("is_owner") or cm.get("isOwner"):
                    role = "مالک"
                elif cm.get("is_admin") or cm.get("isAdmin") or cm.get("is_administrator") or cm.get("isAdministrator"):
                    role = "ادمین"

            perms = cm.get("permissions") or cm.get("rights") or {}
            if isinstance(perms, dict) and role == "عضو":
                if perms.get("is_creator") or perms.get("is_owner"):
                    role = "مالک"
                elif perms.get("is_admin"):
                    role = "ادمین"

            info["role"] = role

            username_cache[key] = info
            username_cache_ttl[key] = now + 600
            save_known_user(user_id, info.get("name"), info.get("username"))
            save_data(bot_data)
    except Exception as e:
        print(f"⚠️ get_user_info: {e}", flush=True)
    return info


def save_known_user(user_id, name=None, username=None):
    if "known_users" not in bot_data: bot_data["known_users"] = {}
    uid = str(user_id)
    if uid not in bot_data["known_users"]: bot_data["known_users"][uid] = {}
    if name: bot_data["known_users"][uid]["name"] = name
    if username: bot_data["known_users"][uid]["username"] = username
    bot_data["known_users"][uid]["last_seen"] = time.time()


def get_display_for_user(user_id):
    uid = str(user_id)
    now = time.time()
    for k, v in username_cache.items():
        ttl = username_cache_ttl.get(k, 0)
        if now < ttl and k.endswith(f":{uid}"):
            if v.get("username"): return f"@{v['username']}"
            if v.get("name"): return v["name"]
    ku = bot_data.get("known_users", {}).get(uid, {})
    if ku.get("username"): return f"@{ku['username']}"
    if ku.get("name"): return ku["name"]
    short = uid[1:] if uid.startswith(("u", "b")) else uid
    return f"کاربر `{short[:10]}`"


def format_user_display(ui, uid):
    if ui.get("username"): return f"@{ui['username']}"
    if ui.get("name"): return ui["name"]
    return get_display_for_user(uid)


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
            if hasattr(rt, 'message_id'): result["reply_id"] = str(rt.message_id)
            elif hasattr(rt, 'id'): result["reply_id"] = str(rt.id)
            elif isinstance(rt, dict):
                mid = rt.get('message_id') or rt.get('id')
                if mid: result["reply_id"] = str(mid)
            if hasattr(rt, 'sender_id'): result["sender_id"] = str(rt.sender_id)
            elif hasattr(rt, 'user_id'): result["sender_id"] = str(rt.user_id)
            elif hasattr(rt, 'from_id'): result["sender_id"] = str(rt.from_id)
            elif hasattr(rt, 'sender'):
                s = rt.sender
                if hasattr(s, 'id'): result["sender_id"] = str(s.id)
                elif isinstance(s, dict):
                    sid = s.get('id') or s.get('user_id')
                    if sid: result["sender_id"] = str(sid)
            elif isinstance(rt, dict):
                sid = rt.get('sender_id') or rt.get('user_id') or rt.get('from_id')
                if sid: result["sender_id"] = str(sid)
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


async def find_reply_target(message, chat_id):
    info = extract_reply_info(message)
    rid = info["reply_id"]
    sid_direct = info["sender_id"]
    if sid_direct:
        bot_id = await get_bot_id()
        if bot_id and sid_direct == bot_id: return "BOT_SELF"
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
            bot_id = await get_bot_id()
            if bot_id and sid == bot_id: return "BOT_SELF"
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
            if sid:
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
                await asyncio.sleep(0.4)
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

JOKES = [
    "به یارو میگن چرا زنتو میزنی؟ میگه چون عاشقشم! 😂",
    "رفتم دکتر گفتم آدم‌ها رو دوست ندارم! گفت پس چرا اومدی؟ گفتم تو که آدم نیستی! 😅",
    "به یارو میگن شغلت چیه؟ میگه بیکارم! میگن پس چطوری خرج می‌کنی؟ میگه آبروم رو می‌فروشم! 😂",
    "از یارو پرسیدن چرا زیر بارون وایسادی؟ گفت منتظرم یه قطره بیفته تا لیوانم پر شه! 🌧️",
]

PROVERBS = [
    "آب که از سر گذشت، چه یک وجب چه صد وجب. 🌊",
    "از این ستون به آن ستون فرج است. 🕌",
    "از تو حرکت، از خدا برکت. 🙏",
    "اسب را که بردی، لگامش را هم ببر. 🐴",
]

TRIVIA = [
    "🐙 اختاپوس‌ها سه قلب دارند و خونشان آبی است.",
    "🍯 عسل هرگز فاسد نمی‌شود.",
    "🐘 فیل‌ها تنها پستانداری هستند که نمی‌توانند بپرند.",
    "🌙 ماه هر سال حدود ۳.۸ سانتی‌متر از زمین دور می‌شود.",
]

FACTS = [
    "🧠 مغز انسان ۲٪ وزن بدن را دارد اما ۲۰٪ انرژی مصرف می‌کند!",
    "🦷 مینای دندان سخت‌ترین ماده در بدن انسان است.",
    "👁️ چشم انسان می‌تواند حدود ۱۰ میلیون رنگ را تشخیص دهد.",
    "💤 انسان در طول عمرش حدود ۲۵ سال می‌خوابد!",
]

PNP = [
    "پند: با دلِ خودت روراست باش. 💚",
    "پند: هرگز قضاوت نکن تا خودت در اون موقعیت قرار نگیری. ⚖️",
    "پند: موفقیت یعنی بلند شدن بعد از هر زمین خوردن. 💪",
]

POEMS = [
    "دوش دیدم که ملائک در میخانه زدند / گل آدم بسرشتند و به پیمانه زدند. 🍷",
    "بنی آدم اعضای یک پیکرند / که در آفرینش ز یک گوهرند. 🤝",
    "توانا بود هر که دانا بود / ز دانش دل پیر برنا بود. 📚",
]

FAL = [
    "🔮 **فال امروز:** روز خوبی در انتظارته! 🍀",
    "🔮 **فال امروز:** مراقب باش، یه نفر داره پشت سرت حرف می‌زنه. 🤫",
    "🔮 **فال امروز:** پول به دستت می‌رسه، ولی خرجش نکن! 💰",
]

LUCK = [
    "🍀 **شانس امروز:** ۱۰ از ۱۰! فوق‌العاده‌ست!",
    "🍀 **شانس امروز:** ۹ از ۱۰! عالیه!",
    "🍀 **شانس امروز:** ۸ از ۱۰! خوبه!",
    "🍀 **شانس امروز:** ۷ از ۱۰! معمولیه.",
    "🍀 **شانس امروز:** ۵ از ۱۰! یه ذره ضعیفه.",
]


def clean_message(text):
    if not text: return ""
    text = re.sub(r"@\S+", "", text)
    text = re.sub(r"/(\w+)", r"\1", text)
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


async def get_chat_name(chat_id):
    try:
        info = await bot.get_chat_info(chat_id)
        if isinstance(info, dict):
            data = info.get("data", info)
            if isinstance(data, dict):
                chat = data.get("chat", data)
                if isinstance(chat, dict):
                    return chat.get("title") or chat.get("name") or "گروه"
        return "گروه"
    except Exception as e:
        print(f"⚠️ get_chat_name: {e}", flush=True)
        return "گروه"


async def get_chat_join_link(chat_id):
    try:
        info = await bot.get_chat_info(chat_id)
        if isinstance(info, dict):
            data = info.get("data", info)
            if isinstance(data, dict):
                chat = data.get("chat", data)
                if isinstance(chat, dict):
                    link = (chat.get("join_link") or chat.get("invite_link") or
                           chat.get("link") or chat.get("join_url") or chat.get("invite_url"))
                    if link: return str(link)
                    un = chat.get("username")
                    if un: return f"https://rubika.ir/{un}"
        return None
    except Exception as e:
        print(f"⚠️ get_chat_link: {e}", flush=True)
        return None


async def get_group_list_text():
    groups = ensure_list(bot_data.get("known_groups", []))
    if not groups:
        return "📋 **لیست گروه‌ها**\n\n📭 ربات هنوز توی هیچ گروهی نیست.\n\n⚡ **FLUXBOT**"
    live_groups = []
    dead_groups = []
    now = time.time()
    for gid in groups:
        cached = group_info_cache.get(gid)
        ttl = group_info_cache_ttl.get(gid, 0)
        if cached and now < ttl:
            live_groups.append(gid)
            continue
        is_alive, _err = await validate_group(gid)
        if is_alive:
            live_groups.append(gid)
        else:
            dead_groups.append(gid)
            print(f"🗑️ گروه مرده حذف شد: {gid} | {_err}", flush=True)
        await asyncio.sleep(0.15)
    if dead_groups:
        bot_data["known_groups"] = live_groups
        save_data(bot_data, force=True)
        for gid in dead_groups:
            group_info_cache.pop(gid, None)
            group_info_cache_ttl.pop(gid, None)
    if not live_groups:
        return "📋 **لیست گروه‌ها**\n\n📭 هیچ گروه فعالی وجود نداره.\n\n⚡ **FLUXBOT**"
    text = (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
        "   ⚡ **FLUXBOT** ⚡\n"
        f"   📋 لیست گروه‌ها ({len(live_groups)})\n"
        "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
    )
    now = time.time()
    for i, gid in enumerate(live_groups, 1):
        cached = group_info_cache.get(gid)
        ttl = group_info_cache_ttl.get(gid, 0)
        if cached and now < ttl:
            name = cached.get("name", "گروه")
            link = cached.get("link")
        else:
            try:
                name = await get_chat_name(gid)
                link = await get_chat_join_link(gid)
                group_info_cache[gid] = {"name": name, "link": link}
                group_info_cache_ttl[gid] = now + 1800
            except Exception as e:
                print(f"⚠️ group info {gid}: {e}", flush=True)
                name = f"گروه #{i}"
                link = None
            await asyncio.sleep(0.1)
        text += f"{i}. 🏠 **{name}**\n"
        if link: text += f"   🔗 {link}\n"
        else: text += f"   🔗 بدون لینک\n"
        text += "\n"
    text += "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"
    return text


def get_games_list_text():
    return (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
        "   ⚡ **FLUXBOT** ⚡\n"
        "   🎮 لیست بازی‌ها 🎮\n"
        "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        "🎲 **بازی دوز چهارتایی**\n"
        "├ 📌 شروع: `دوز`\n"
        "├ 🎨 رنگ: `دوز قرمز` یا `دوز زرد`\n"
        "├ 👥 پیوستن: `شرکت`\n"
        "├ 🎯 انداختن: عدد `1` تا `7`\n"
        "└ 🚫 لغو: `انصراف`\n\n"
        "🪙 **بازی شیر یا خط**\n"
        "├ 📌 شروع: `بازی شیر یا خط`\n"
        "├ 🎯 انتخاب: `شیر` یا `خط`\n"
        "└ 🎲 نتیجه تصادفی\n\n"
        "⏱️ **نکته:** اگه بعد ۲ دقیقه کسی بازی نکنه، خودکار لغو می‌شه.\n\n"
        "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"
    )


def get_features_text():
    return (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
        "   ⚡ **FLUXBOT** ⚡\n"
        "   🌊 جریان قدرت 🌊\n"
        "   📖 قابلیت‌های کامل\n"
        "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💬 **سخنگو**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 📌 `فلکس بات` → جواب رندوم\n"
        "├ 🌟 پیش‌فرض: فعال\n"
        "├ 🟢 `سخنگو باز` / `باز سخنگو`\n"
        "├ 🔴 `سخنگو بسته` / `بسته سخنگو`\n"
        "└ 💡 فقط در گروه\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎨 **فونت‌ساز**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 📝 `فونت [متن]` یا `فوت [متن]`\n"
        "├ 🌍 فارسی و انگلیسی\n"
        "└ 💡 فقط در گروه\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎯 **چالش روزانه**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 📌 `چالش`\n"
        "├ 🎲 چالش تصادفی (متنی/نظرسنجی)\n"
        "└ 💡 فقط در گروه\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🛡️ **قفل‌ها (هر دو ترتیب کار می‌کنه!)**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🔗 لینک (باز/بسته)\n"
        "├ 🆔 آیدی (باز/بسته)\n"
        "├ 📢 اسپم (باز/بسته)\n"
        "├ 🔗 هایپرلینک (باز/بسته)\n"
        "├ 🤬 فحش (باز/بسته)\n"
        "├ 📨 فوروارد (باز/بسته)\n"
        "├ 🎞️ گیف (باز/بسته)\n"
        "├ 👋 خوش‌آمدگویی (باز/بسته)\n"
        "└ 💬 سخنگو (باز/بسته)\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🔒 **قفل گروه**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ `قفل گروه` / `باز`\n"
        "├ `قفل [ساعت]` → موقت\n"
        "├ `قفل 08:00 22:00` → زمان‌بندی\n"
        "└ `لیست قفل گروه`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ **سیستم اخطار**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ `اخطار` (ریپلای)\n"
        "├ `تنظیم اخطار [عدد]`\n"
        "├ `حذف اخطار` / `حذف اخطار [عدد]`\n"
        "└ `حذف پیام اخطار [ثانیه]`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "👑 **مدیریت کاربران**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ `بن` / `سیک` / `اخراج` (ریپلای)\n"
        "├ `انبن` (ریپلای)\n"
        "├ `سکوت [دقیقه]` (ریپلای)\n"
        "├ `ویژه` / `حذف ویژه` (ریپلای)\n"
        "└ `مقام`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📜 **قوانین گروه**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ `تنظیم قوانین [متن]`\n"
        "├ `قوانین` → نمایش\n"
        "└ `حذف قوانین`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🔁 **ضد تکرار و آهسته**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ `تنظیم ضد تکرار [۲-۱۰]`\n"
        "├ `ضد تکرار بسته`\n"
        "├ `تنظیم حالت آهسته [زمان]`\n"
        "└ `حالت آهسته بسته`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎮 **بازی و سرگرمی**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🎲 `دوز` / `دوز قرمز` / `دوز زرد`\n"
        "├ 🪙 `بازی شیر یا خط`\n"
        "├ 🎯 `چالش`\n"
        "├ 😂 `جک` / 📜 `ضرب المثل`\n"
        "├ 💡 `دانستی` / 🧠 `فکت`\n"
        "├ 💚 `پ ن پ` / 📝 `شعر`\n"
        "└ 🔮 `فال` / 🍀 `شانس`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📊 **پروفایل و آمار**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 📊 `پروفایل`\n"
        "├ 🏆 `تاپ`\n"
        "├ ⏰ `ساعت`\n"
        "├ 🐺 `تنظیم اصل [نام]`\n"
        "└ 🎭 `تنظیم لقب [نام]`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎟️ **دعوت دوستان**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🎫 کد دعوت ۶ رقمی\n"
        "├ ⭐ امتیاز دو طرف\n"
        "└ 🏆 لیست برتر\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ **ابزارهای مدیریتی**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🗑️ `حذف` / `حذف [دقیقه]`\n"
        "├ 🧹 `پاکسازی [عدد]`\n"
        "├ 🚫 `فیلتر [کلمه]`\n"
        "├ 📋 `لیست فیلتر`\n"
        "└ 📚 `راهنما`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "👑 **فقط مالک ربات**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 📢 `ارسال پیام همگانی گروه [متن]`\n"
        "└ 📋 `لیست گروه ها`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🔗 **@Flux1bot**\n"
        "📢 **@RPCITY_PHANTOM**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ **FLUXBOT** | 🌊 **جریان قدرت**"
    )


def load_cache():
    for path in CACHE_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    print(f"✅ CACHE: {path}", flush=True)
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ load_cache {path}: {e}", flush=True)
    return {}


def save_cache(cache, force=False):
    save_counter["cache"] += 1
    if not force and save_counter["cache"] % 3 != 0: return
    total = sum(len(v) if isinstance(v, dict) else 0 for v in cache.values())
    if total > 5000:
        print(f"⚠️ Cache too big ({total}), trimming...", flush=True)
        for k in list(cache.keys()):
            if isinstance(cache[k], dict) and len(cache[k]) > 500:
                items = list(cache[k].items())
                cache[k] = dict(items[-500:])
    for path in CACHE_PATHS:
        try:
            dn = os.path.dirname(path)
            if dn and not os.path.exists(dn): os.makedirs(dn, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ save_cache: {e}", flush=True)


def load_data():
    defaults = {
        "welcomed_users": {}, "user_titles": {}, "taken_asl": {}, "taken_laghab": {},
        "message_counts": {}, "join_dates": {}, "special_users": {}, "warnings": {},
        "warn_limit": {}, "warn_delete_after": {}, "started_users": [], "known_groups": [],
        "group_message_count": {}, "filtered_words": {}, "banned_users": {},
        "invite_codes": {}, "code_to_user": {}, "points": {}, "invited_users": {},
        "known_users": {}, "games": {},
        "group_locks": {}, "temp_locks": {}, "scheduled_locks": {}, "mute_list": {},
        "custom_welcome": {},
        "rules": {},
        "anti_repeat": {},
        "slow_mode": {},
        "talkative_disabled": [],
        "settings": {
            "link": False, "id": False, "spam": False, "hyperlink": False,
            "welcome": True, "warning": False, "filter": True, "auto_ban": True,
            "profanity": True, "forward": False, "gif": False, "goodbye": False,
        },
    }
    for path in DATA_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for lk in ["started_users", "known_groups", "talkative_disabled"]:
                        if lk in loaded: loaded[lk] = ensure_list(loaded[lk])
                    for k, v in defaults.items():
                        if k not in loaded: loaded[k] = v
                    if "settings" in loaded:
                        for sk, sv in defaults["settings"].items():
                            if sk not in loaded["settings"]:
                                loaded["settings"][sk] = sv
                    print(f"✅ DATA: {path}", flush=True)
                    return loaded
        except Exception as e:
            print(f"⚠️ load_data {path}: {e}", flush=True)
    return defaults


def save_data(data, force=False):
    save_counter["data"] += 1
    if not force and save_counter["data"] % 3 != 0: return
    for path in DATA_PATHS:
        try:
            dn = os.path.dirname(path)
            if dn and not os.path.exists(dn): os.makedirs(dn, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ save_data: {e}", flush=True)


bot_is_active = True
bot_data = load_data()
settings = bot_data.get("settings", {})
for sk in ["link", "id", "spam", "hyperlink", "warning", "filter", "auto_ban",
           "profanity", "forward", "gif", "goodbye"]:
    if sk not in settings: settings[sk] = False
if "welcome" not in settings: settings["welcome"] = True
message_cache = load_cache()

group_locks = bot_data.get("group_locks", {})
temp_locks = bot_data.get("temp_locks", {})
scheduled_locks = bot_data.get("scheduled_locks", {})
mute_list = bot_data.get("mute_list", {})


async def cleanup_task():
    while True:
        try:
            await asyncio.sleep(300)
            now = time.time()
            expired = [k for k, v in waiting_for_code.items() if now - v > 300]
            for k in expired: del waiting_for_code[k]
            cutoff = now - 30
            keys = [k for k, v in text_dedup.items() if v < cutoff]
            for k in keys:
                if k in text_dedup: del text_dedup[k]
            # رفرش کش نقش‌ها هر ۵ دقیقه برای دقت
            role_refresh_counter = bot_data.get("_role_refresh", 0)
            if now - role_refresh_counter > 300:
                username_cache.clear()
                username_cache_ttl.clear()
                bot_data["_role_refresh"] = now
            expired = [k for k, v in username_cache_ttl.items() if now > v]
            for k in expired:
                if k in username_cache: del username_cache[k]
                if k in username_cache_ttl: del username_cache_ttl[k]
            if len(processed_messages) > 1000:
                items = sorted(processed_messages.items(), key=lambda x: x[1])
                keep = dict(items[-500:])
                processed_messages.clear()
                processed_messages.update(keep)
            print(f"🧹 Cleanup done", flush=True)
        except Exception as e:
            print(f"⚠️ cleanup: {e}", flush=True)


async def group_cleanup_task():
    await asyncio.sleep(600)
    while True:
        try:
            groups = ensure_list(bot_data.get("known_groups", []))
            if not groups:
                await asyncio.sleep(3600)
                continue
            live = []
            dead = []
            for gid in groups:
                try:
                    is_alive, err = await validate_group(gid)
                    if is_alive:
                        live.append(gid)
                    else:
                        dead.append((gid, err))
                        print(f"🗑️ [auto-clean] گروه مرده: {gid} | {err}", flush=True)
                    await asyncio.sleep(0.2)
                except Exception as e:
                    print(f"⚠️ validate_group {gid}: {e}", flush=True)
                    live.append(gid)
            if dead:
                bot_data["known_groups"] = live
                save_data(bot_data, force=True)
                for gid, _ in dead:
                    group_info_cache.pop(gid, None)
                    group_info_cache_ttl.pop(gid, None)
                print(f"🧹 [auto-clean] {len(dead)} گروه مرده حذف شد. باقی‌مانده: {len(live)}", flush=True)
            await asyncio.sleep(3600)
        except Exception as e:
            print(f"⚠️ group_cleanup: {e}", flush=True)
            await asyncio.sleep(600)


def contains_link(text):
    if not text: return False
    pats = [r'https?://\S+', r'www\.\S+', r't\.me/\S+', r'rubika\.ir/\S+',
            r'telegram\.me/\S+', r'\.ir/\S+', r'\.com/\S+', r'\.org/\S+', r'\.net/\S+', r'\.me/\S+']
    return any(re.search(p, text, re.IGNORECASE) for p in pats)


def contains_hyperlink(text):
    if not text: return False
    return bool(re.search(r'\[.+?\]\(.+?\)', text) or re.search(r'<a\s+href=', text, re.IGNORECASE))


def contains_id(text):
    if not text: return False
    return bool(re.search(r'@\w+', text))


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
    if not text: return None
    n = normalize_text(text)
    if not n: return None
    for w in PROFANITY_LIST:
        nw = normalize_text(w)
        if nw and nw in n: return w
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
    if bot_data.get("group_locks", {}).get(chat_id, False): return True, "قفل دستی"
    temp_locks_now = bot_data.get("temp_locks", {})
    if chat_id in temp_locks_now:
        et = temp_locks_now[chat_id]
        if time.time() < et:
            return True, f"قفل موقت (پایان: {datetime.fromtimestamp(et).strftime('%H:%M')})"
        else:
            del temp_locks_now[chat_id]
            save_data(bot_data)
    scheduled = bot_data.get("scheduled_locks", {})
    if chat_id in scheduled and scheduled[chat_id]:
        now = get_local_now()
        cm = now.hour * 60 + now.minute
        for sh, sm, eh, em in scheduled[chat_id]:
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
        if chat_id not in bot_data["warnings"]: bot_data["warnings"][chat_id] = {}
        if user_id not in bot_data["warnings"][chat_id]: bot_data["warnings"][chat_id][user_id] = 0
        bot_data["warnings"][chat_id][user_id] += 1
        count = bot_data["warnings"][chat_id][user_id]
        limit = bot_data["warn_limit"].get(chat_id, 3)
        save_data(bot_data, force=True)
        if user_info is None: user_info = await get_user_info(chat_id, user_id)
        display = format_user_display(user_info, user_id)
        del_after = get_warn_delete_after(chat_id)
        wt = (
            f"⚠️ **اخطار!** ⚠️\n\n"
            f"👤 **کاربر:** {display}\n"
            f"📌 **دلیل:** {reason if reason else 'تخلف از قوانین'}\n"
            f"📊 **اخطار فعلی:** [{count}/{limit}]\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT**"
        )
        try:
            result = await bot.send_message(chat_id=chat_id, text=wt)
            if del_after > 0:
                mid = extract_msg_id(result)
                if mid: await schedule_delete(chat_id, mid, del_after)
        except Exception as e:
            print(f"⚠️ warn send: {e}", flush=True)
        if count >= limit and settings.get("auto_ban", True):
            try:
                await bot.ban_member_chat(chat_id, user_id)
                if chat_id not in bot_data["banned_users"]: bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][user_id] = time.time()
                save_data(bot_data, force=True)
                bm = f"🚫 **کاربر اخراج شد!**\n\n👤 {display}\n📊 تعداد اخطار: [{count}/{limit}]"
                try:
                    result = await bot.send_message(chat_id=chat_id, text=bm)
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
        b.row(b1, b2)
        b.row(b3, b4)
        b.row(b5)
        b.row(b6, b7)
        b.row(b8, b9)
        b.row(b10)
        return b.build()
    except Exception as e:
        print(f"❌ KEYPAD: {e}", flush=True)
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
        "├ 👑 `مقام`\n├ 📊 `پروفایل`\n├ 🏆 `آمار گروه`\n├ ⏰ `ساعت`\n"
        "├ 📜 `قوانین`\n"
        "├ 🐺 `تنظیم اصل [نام]`\n├ 🎭 `تنظیم لقب [نام]`\n"
        "├ 🎨 `فونت [متن]` → فونت‌ساز\n"
        "├ 🎯 `چالش` → چالش روزانه\n"
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
        "├ 🪙 `بازی شیر یا خط` → بازی شانسی\n"
        "└ 🚫 `انصراف` → لغو\n\n"
        "🔓 **قفل‌ها (هر دو ترتیب کار می‌کنه):**\n"
        "├ `لینک باز` / `باز لینک`\n"
        "├ `آیدی بسته` / `بسته آیدی`\n"
        "├ `اسپم فعال` / `فعال اسپم`\n"
        "├ `فحش خاموش` / `خاموش فحش`\n"
        "├ `فوروارد قفل` / `قفل فوروارد`\n"
        "├ `گیف روشن` / `روشن گیف`\n"
        "├ `سخنگو بسته` / `بسته سخنگو`\n"
        "└ `هایپرلینک باز` / `باز هایپرلینک`\n\n"
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
        "├ 🧹 `پاکسازی [عدد]` → پاکسازی انبوه\n"
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
            await asyncio.sleep(0.25)
        except Exception as e:
            failed += 1
            print(f"⚠️ bulk delete {mid}: {e}", flush=True)
    return deleted, failed


async def handle_repeat_check(chat_id, user_id, msg_id, text, limit, user_info):
    if not text: return False
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
                    await asyncio.sleep(0.2)
                except Exception as e:
                    print(f"⚠️ repeat delete {mid}: {e}", flush=True)
            try:
                display = format_user_display(user_info, user_id)
                if settings.get("warning"):
                    await add_warning(chat_id, user_id, f"ارسال {limit} پیام یکسان پشت سر هم", user_info=user_info)
                else:
                    await bot.send_message(chat_id=chat_id, text=(
                        f"🔁 **ضد تکرار فعال است!**\n\n"
                        f"👤 {display}\n"
                        f"📌 {limit} پیام یکسان شما پاک شد.\n\n⚡ **FLUXBOT**"))
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


# ================== MAIN HANDLER ==================
@bot.on_message()
async def handle_message(bot, message):
    global bot_is_active, message_cache, bot_data, settings, text_dedup

    try:
        msg_id = str(message.message_id)
        chat_id = str(message.chat_id) if message.chat_id else ""
        sender_id = str(message.sender_id) if message.sender_id else ""
        raw_text = (message.text or "").strip()
        clean_text = clean_message(raw_text)

        aux = getattr(message, 'aux_data', None) or getattr(message, 'auxData', None)
        button_id = None
        if aux and isinstance(aux, dict):
            button_id = aux.get('button_id') or aux.get('id')

        if sender_id: register_user(sender_id)
        if is_group_chat(chat_id): register_group(chat_id)

        if chat_id and msg_id and sender_id:
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
        if len(processed_messages) > 1000:
            items = sorted(processed_messages.items(), key=lambda x: x[1])
            keep = dict(items[-500:])
            processed_messages.clear()
            processed_messages.update(keep)
        if msg_id in processed_messages: return
        processed_messages[msg_id] = ct

        is_owner_check = (str(sender_id) == OWNER_ID)
        if not is_owner_check:
            dedup_key = f"{chat_id}:{sender_id}:{raw_text}"
            last_seen = text_dedup.get(dedup_key, 0)
            if ct - last_seen < 1.5: return
            text_dedup[dedup_key] = ct

        print(f"📩 {chat_id} | {sender_id} | {raw_text!r}", flush=True)

        # ============ 📢 ارسال پیام همگانی (فقط مالک) ============
        broadcast_match = re.match(r"^ارسال\s+پیام\s+همگانی\s+گروه\s+([\s\S]+)$", raw_text.strip())
        if broadcast_match:
            if not is_owner_check: return
            broadcast_text = broadcast_match.group(1).strip()
            if not broadcast_text:
                try:
                    await bot.send_message(chat_id=chat_id, text="⚠️ متن پیام رو وارد کن.\n\nمثال:\n`ارسال پیام همگانی گروه سلام به همه`")
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
                        print(f"🗑️ [broadcast] گروه مرده: {gid} | send_err={err_str} | val_err={val_err}", flush=True)
                    else:
                        failed_details.append((gid, err_str, False, val_err))
                        print(f"⚠️ [broadcast] خطای ارسال: {gid} | {err_str}", flush=True)
                    await asyncio.sleep(0.5)
            if dead_groups:
                current = ensure_list(bot_data.get("known_groups", []))
                bot_data["known_groups"] = [g for g in current if g not in dead_groups]
                save_data(bot_data, force=True)
                for gid in dead_groups:
                    group_info_cache.pop(gid, None)
                    group_info_cache_ttl.pop(gid, None)
                print(f"🧹 [broadcast] {len(dead_groups)} گروه مرده حذف شد", flush=True)
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
            if failed_details:
                details_text = "\n\n🔍 **جزئیات خطاها:**\n"
                for gid, err_str, is_dead, val_err in failed_details[:20]:
                    short_gid = gid[-8:] if len(gid) > 8 else gid
                    err_display = (val_err or err_str)[:120].replace("\n", " ")
                    tag = "🗑️ حذف شد" if is_dead else "⚠️ باقی ماند"
                    details_text += f"\n├ `...{short_gid}` → {tag}\n│    {err_display}\n"
                if len(failed_details) > 20:
                    details_text += f"\n... و {len(failed_details) - 20} خطای دیگر"
                report += details_text
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
                except Exception as e:
                    print(f"⚠️ delete loading msg: {e}", flush=True)
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

        # 🎨 دستور فونت / فوت
        font_match = re.match(r"^(?:فونت|فوت)\s+([\s\S]+)$", raw_text.strip())
        if font_match:
            font_text = font_match.group(1).strip()
            if not font_text:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        reply_to_message_id=message.message_id,
                        text="⚠️ **متن رو وارد کن!**\n\n📝 مثال:\n`فونت سلام`\n`فوت Hello`"
                    )
                except: pass
                return
            try:
                font_msg = build_font_message(font_text)
                if font_msg:
                    await send_long_message(chat_id, font_msg, reply_to_message_id=message.message_id)
            except Exception as e:
                print(f"❌ font: {e}", flush=True)
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        reply_to_message_id=message.message_id,
                        text="⚠️ خطا در ساخت فونت. متن ساده‌تری امتحان کن."
                    )
                except: pass
            return

        # 🎨 راهنمای فونت
        if is_command(clean_text, "فونت", "فوت"):
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=message.message_id,
                    text=(
                        "🎨 **فونت‌ساز FLUXBOT**\n\n"
                        "📝 **روش استفاده:**\n"
                        "├ `فونت [متن]`\n"
                        "└ `فوت [متن]`\n\n"
                        "💡 **مثال:**\n"
                        "├ `فونت سلام`\n"
                        "├ `فوت Hello`\n"
                        "└ `فونت Python 2024`\n\n"
                        "🌟 بالای ۲۰ استایل (فارسی + انگلیسی)\n\n"
                        "⚡ **FLUXBOT**"
                    )
                )
            except: pass
            return

        # 🎯 دستور چالش
        if is_command(clean_text, "چالش"):
            try:
                challenge_msg = build_challenge_message()
                await bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=message.message_id,
                    text=challenge_msg
                )
            except Exception as e:
                print(f"❌ challenge: {e}", flush=True)
            return

        # 💬 سخنگو - پاسخ خودکار
        if TALKATIVE_TRIGGERS_RE.match(raw_text.strip()):
            if is_talkative_enabled(chat_id):
                try:
                    reply = get_random_talkative()
                    await bot.send_message(
                        chat_id=chat_id,
                        text=reply,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    print(f"⚠️ talkative: {e}", flush=True)
            return

        # 🔄 قفل‌های دوکلمه‌ای - سخنگو
        res = match_two_word_cmd(clean_text, "سخنگو")
        if res is not None:
            ui_temp = await get_user_info(chat_id, sender_id)
            role_temp = ui_temp["role"]
            is_owner_g = (role_temp == "مالک")
            is_spec = bot_data.get("special_users", {}).get(chat_id, {}).get(sender_id, False)
            if not (is_owner_g or is_spec):
                return
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

        # 🔄 قفل‌های دوکلمه‌ای - بقیه
        lock_words_map = {
            "لینک": "link", "آیدی": "id", "اسپم": "spam", "هایپرلینک": "hyperlink",
            "خوش‌آمدگویی": "welcome", "خوشآمدگویی": "welcome",
            "فحش": "profanity", "فوروارد": "forward", "هدایت": "forward",
            "گیف": "gif", "خداحافظی": "goodbye",
        }
        for w, key in lock_words_map.items():
            res = match_two_word_cmd(clean_text, w)
            if res is not None:
                ui_temp = await get_user_info(chat_id, sender_id)
                role_temp = ui_temp["role"]
                is_owner_g = (role_temp == "مالک")
                is_spec = bot_data.get("special_users", {}).get(chat_id, {}).get(sender_id, False)
                if not (is_owner_g or is_spec):
                    return
                settings[key] = res
                bot_data["settings"] = settings
                save_data(bot_data, force=True)
                status = "🟢 باز" if res else "🔴 بسته"
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id,
                                       text=f"✅ **{w}** {status} شد.\n\n⚡ **FLUXBOT**")
                return

        ui = await get_user_info(chat_id, sender_id)
        role = ui["role"]
        disp = format_user_display(ui, sender_id)
        is_owner_group = (role == "مالک")
        is_special = bot_data.get("special_users", {}).get(chat_id, {}).get(sender_id, False)
        can_manage = is_owner_group or is_special

        locked, reason = is_group_locked(chat_id)
        if locked and not can_manage:
            try: await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except Exception as e:
                print(f"⚠️ delete locked: {e}", flush=True)
            return

        games = get_games()

        if chat_id in coin_flip_games:
            cf = coin_flip_games[chat_id]
            if str(sender_id) == cf["player"] and raw_text in ("شیر", "خط"):
                choice = raw_text
                del coin_flip_games[chat_id]
                result = random.choice(["شیر", "خط"])
                won = (choice == result)
                if won:
                    text = (
                        f"🪙 **نتیجه:** {result}\n\n"
                        f"🎉 **{disp} برنده شد!** 🎉\n\n"
                        f"━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT**"
                    )
                else:
                    text = (
                        f"🪙 **نتیجه:** {result}\n\n"
                        f"😢 **{disp} باخت!**\n\n"
                        f"━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT**"
                    )
                await bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=message.message_id)
                return

        if clean_text in ("لیست بازی", "لیست بازی ها", "لیست بازی‌ها", "بازی ها", "بازی‌ها"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=get_games_list_text())
            return

        if clean_text == "قوانین":
            rules = bot_data.get("rules", {}).get(chat_id)
            if rules:
                rules_text = (
                    "📜 **قوانین گروه**\n"
                    "━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{rules}\n\n"
                    "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT**"
                )
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
            if not rules_text:
                await bot.send_message(chat_id=chat_id, text="⚠️ متن قوانین رو وارد کنید.", reply_to_message_id=message.message_id)
                return
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
            if not welcome_text:
                await bot.send_message(chat_id=chat_id, text="⚠️ متن را وارد کنید.", reply_to_message_id=message.message_id)
                return
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
            if limit < 2 or limit > 10:
                await bot.send_message(chat_id=chat_id, text="⚠️ عدد باید بین ۲ تا ۱۰ باشد.", reply_to_message_id=message.message_id)
                return
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
            dur_text = smm.group(1).strip()
            sec = parse_slow_duration(dur_text)
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
            if limit < 1 or limit > 500:
                await bot.send_message(chat_id=chat_id, text="⚠️ عدد باید بین ۱ تا ۵۰۰ باشد.", reply_to_message_id=message.message_id)
                return
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
                if g["status"] == "waiting":
                    await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                        f"⏳ **بازی در انتظار حریف!**\n\n👤 **سازنده:** {g['player1_name']}\n📌 برای پیوستن: `شرکت`"))
                else:
                    await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="⚠️ **یک بازی در حال اجراست!**")
                return
            color_choice = game_start_match.group(2) or "قرمز"
            game = await start_game(chat_id, sender_id, disp, color_choice)
            color_emoji = RED if game["color1"] == "R" else YELLOW
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                f"🎮 **بازی دوز شروع شد!**\n\n👤 **سازنده:** {disp}\n🎨 **رنگ:** {color_emoji}\n\n"
                f"⏳ **منتظر حریف...**\n\n📌 برای پیوستن: `شرکت`\n\n⚡ **FLUXBOT**"))
            return

        if clean_text in ("بازی شیر یا خط", "شیر یا خط", "شیریا خط"):
            if chat_id in coin_flip_games:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    "⚠️ **یک بازی شیر یا خط در جریانه!**"))
                return
            if chat_id in games and games[chat_id].get("status") in ("waiting", "playing"):
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    "⚠️ **یه بازی دیگه در جریانه!** اول اون تموم شه."))
                return
            coin_flip_games[chat_id] = {"player": str(sender_id), "started_at": time.time()}
            try: asyncio.create_task(game_timeout_check(chat_id, "coinflip"))
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
            now = get_local_now()
            days = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
            wd = days[now.weekday()]
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                f"⏰ **ساعت فعلی**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🕐 `{now.strftime('%H:%M:%S')}`\n📅 `{now.strftime('%Y/%m/%d')}`\n📆 {wd}\n\n⚡ **FLUXBOT**"))
            return

        # 🎖️ دستور مقام (بعد از همه چیز)
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
                    f"⚡ **FLUXBOT**"
                ))
            except Exception as e:
                print(f"❌ role cmd: {e}", flush=True)
                try:
                    await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id,
                                           text="⚠️ خطا در دریافت مقام. لطفاً دوباره تلاش کن.")
                except: pass
            return

        if is_command(clean_text, "حذف ویژه", "لغو ویژه", "حذف ادمین"):
            if not is_owner_group: return
            tgt = await find_reply_target(message, chat_id)
            if tgt == "BOT_SELF":
                await bot.send_message(chat_id=chat_id, text="⚠️ نمی‌توانید ربات را از ویژه حذف کنید.", reply_to_message_id=message.message_id)
                return
            if not tgt:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            ti = await get_user_info(chat_id, tgt)
            td = format_user_display(ti, tgt)
            if chat_id in bot_data["special_users"] and tgt in bot_data["special_users"][chat_id]:
                del bot_data["special_users"][chat_id][tgt]
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, text=f"✅ **{td} از ویژه حذف شد.**", reply_to_message_id=message.message_id)
            else:
                await bot.send_message(chat_id=chat_id, text=f"ℹ️ **{td}** ویژه نیست.", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "ویژه", "ادمین"):
            if not is_owner_group: return
            tgt = await find_reply_target(message, chat_id)
            if tgt == "BOT_SELF":
                await bot.send_message(chat_id=chat_id, text="ℹ️ ربات خودش ویژه است.", reply_to_message_id=message.message_id)
                return
            if not tgt:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            ti = await get_user_info(chat_id, tgt)
            td = format_user_display(ti, tgt)
            if chat_id not in bot_data["special_users"]: bot_data["special_users"][chat_id] = {}
            if bot_data["special_users"][chat_id].get(tgt, False):
                await bot.send_message(chat_id=chat_id, text=f"ℹ️ **{td}** از قبل ویژه است.", reply_to_message_id=message.message_id)
                return
            bot_data["special_users"][chat_id][tgt] = True
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, text=f"⭐ **{td} ویژه شد!**", reply_to_message_id=message.message_id)
            return

        wam = re.match(r"^حذف\s+اخطار(?:\s+(\d+))?$", clean_text)
        if wam:
            if not can_manage: return
            target_uid = await find_reply_target(message, chat_id)
            if target_uid == "BOT_SELF":
                await bot.send_message(chat_id=chat_id, text="⚠️ ربات اخطار ندارد.", reply_to_message_id=message.message_id)
                return
            if not target_uid:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            amount_str = wam.group(1)
            if "warnings" not in bot_data: bot_data["warnings"] = {}
            if chat_id not in bot_data["warnings"]: bot_data["warnings"][chat_id] = {}
            current = bot_data["warnings"][chat_id].get(target_uid, 0)
            target_info = await get_user_info(chat_id, target_uid)
            target_disp = format_user_display(target_info, target_uid)
            if current == 0:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"ℹ️ **{target_disp}** اخطاری ندارد.")
                return
            if amount_str:
                amount = int(amount_str)
                if amount <= 0: return
                removed = min(amount, current)
                bot_data["warnings"][chat_id][target_uid] = current - removed
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    f"✅ **{removed} اخطار از {target_disp} حذف شد.**\n\n📊 باقی‌مانده: [{current - removed}/{bot_data['warn_limit'].get(chat_id, 3)}]"))
            else:
                bot_data["warnings"][chat_id][target_uid] = 0
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"✅ **تمام اخطارهای {target_disp} پاک شد.**")
            return

        dtm = re.match(r"^حذف\s+(\d+)$", clean_text)
        if dtm:
            if not can_manage: return
            mins = int(dtm.group(1))
            if mins <= 0 or mins > 10080:
                await bot.send_message(chat_id=chat_id, text="⚠️ عدد 1 تا 10080", reply_to_message_id=message.message_id); return
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

        if is_command(clean_text, "قفل گروه", "قفلگروه"):
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
            if h <= 0 or h > 168:
                await bot.send_message(chat_id=chat_id, text="⚠️ 1 تا 168 ساعت", reply_to_message_id=message.message_id); return
            et = time.time() + h * 3600
            if "temp_locks" not in bot_data: bot_data["temp_locks"] = {}
            if "group_locks" not in bot_data: bot_data["group_locks"] = {}
            bot_data["temp_locks"][chat_id] = et
            bot_data["group_locks"][chat_id] = False
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                f"🔒 **قفل موقت: {h} ساعت**\n🕐 پایان: {datetime.fromtimestamp(et).strftime('%H:%M - %Y/%m/%d')}"))
            return

        sm = re.match(r"^قفل\s+(\d{1,2}):(\d{2})\s+(?:تا\s+)?(\d{1,2}):(\d{2})$", clean_text)
        if sm:
            if not can_manage: return
            sh, sm2, eh, em = map(int, sm.groups())
            if not (0 <= sh <= 23 and 0 <= sm2 <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
                await bot.send_message(chat_id=chat_id, text="⚠️ ساعت نامعتبر", reply_to_message_id=message.message_id); return
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

        if is_command(clean_text, "لیست قفل گروه"):
            if not can_manage: return
            s = []
            gl = bot_data.get("group_locks", {}).get(chat_id, False)
            tl = bot_data.get("temp_locks", {}).get(chat_id)
            sl_list = bot_data.get("scheduled_locks", {}).get(chat_id, [])
            s.append("🔴 قفل دستی: فعال" if gl else "🟢 قفل دستی: غیرفعال")
            if tl: s.append(f"🟡 موقت: {get_remaining_time(tl)}")
            else: s.append("🟢 موقت: غیرفعال")
            if sl_list:
                sl = "\n".join([f"  • {sh:02d}:{sm:02d} تا {eh:02d}:{em:02d}" for sh, sm, eh, em in sl_list])
                s.append(f"🟡 زمان‌بندی:\n{sl}")
            else: s.append("🟢 زمان‌بندی: غیرفعال")
            ar = bot_data.get("anti_repeat", {}).get(chat_id)
            s.append(f"🔁 ضد تکرار: {'🔴 ' + str(ar) + ' پیام یکسان' if ar else '🟢 غیرفعال'}")
            slow = bot_data.get("slow_mode", {}).get(chat_id)
            s.append(f"🐌 حالت آهسته: {'🔴 ' + format_duration(slow) if slow else '🟢 غیرفعال'}")
            tk = "🟢 فعال" if is_talkative_enabled(chat_id) else "🔴 غیرفعال"
            s.append(f"💬 سخنگو: {tk}")
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                "🔒 **قفل گروه**\n━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(s) + "\n\n⚡ **FLUXBOT**"))
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

        if not can_manage:
            ar_limit = bot_data.get("anti_repeat", {}).get(chat_id)
            if ar_limit and raw_text:
                if await handle_repeat_check(chat_id, sender_id, msg_id, raw_text, ar_limit, ui):
                    return

        if chat_id not in bot_data["group_message_count"]: bot_data["group_message_count"][chat_id] = 0
        bot_data["group_message_count"][chat_id] += 1
        save_data(bot_data)

        if settings.get("welcome", True) and bot_is_active:
            welcomed = bot_data.get("welcomed_users", {}).get(chat_id, {})
            if sender_id not in welcomed:
                cn = await get_chat_name(chat_id)
                welcome_msg = get_welcome_text(chat_id, cn, disp)
                try:
                    await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=welcome_msg)
                except Exception as e:
                    print(f"⚠️ welcome: {e}", flush=True)
                if chat_id not in bot_data["welcomed_users"]: bot_data["welcomed_users"][chat_id] = {}
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

        if is_command(clean_text, "فعال", "فاعل"):
            if not can_manage: return
            msg = "✅ از قبل فعال." if bot_is_active else "✅ فعال شد."
            bot_is_active = True
            await bot.send_message(chat_id=chat_id, text=msg, reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "غیرفعال"):
            if not is_owner_group: return
            msg = "⛔ از قبل غیرفعال." if not bot_is_active else "🛑 غیرفعال شد."
            bot_is_active = False
            await bot.send_message(chat_id=chat_id, text=msg, reply_to_message_id=message.message_id)
            return

        wdm = re.match(r"^حذف\s+پیام\s+اخطار\s+(\d+)$", clean_text)
        if wdm:
            if not is_owner_group: return
            sec = int(wdm.group(1))
            if sec < 0 or sec > 3600:
                await bot.send_message(chat_id=chat_id, text="⚠️ 0 تا 3600", reply_to_message_id=message.message_id); return
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
            if tgt == "BOT_SELF":
                await bot.send_message(chat_id=chat_id, text="⚠️ نمی‌توانید ربات را اخراج کنید!", reply_to_message_id=message.message_id)
                return
            if not tgt:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            if tgt == OWNER_ID:
                await bot.send_message(chat_id=chat_id, text="⚠️ نمی‌توانید مالک ربات را اخراج کنید!", reply_to_message_id=message.message_id)
                return
            try:
                ti = await get_user_info(chat_id, tgt)
                td = format_user_display(ti, tgt)
                await bot.ban_member_chat(chat_id, tgt)
                if chat_id not in bot_data["banned_users"]: bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][tgt] = time.time()
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"🚫 **{td} اخراج شد!**")
            except Exception as e:
                print(f"⚠️ ban: {e}", flush=True)
            return

        if is_command(clean_text, "انبن", "آنبن"):
            if not can_manage: return
            tgt = await find_reply_target(message, chat_id)
            if tgt == "BOT_SELF":
                await bot.send_message(chat_id=chat_id, text="⚠️ ربات بن نبوده.", reply_to_message_id=message.message_id)
                return
            if not tgt:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            try:
                ti = await get_user_info(chat_id, tgt)
                td = format_user_display(ti, tgt)
                await bot.unban_member_chat(chat_id, tgt)
                if chat_id in bot_data["banned_users"] and tgt in bot_data["banned_users"][chat_id]:
                    del bot_data["banned_users"][chat_id][tgt]
                    save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"✅ **{td} آنبن شد!**")
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
            if tgt == "BOT_SELF":
                await bot.send_message(chat_id=chat_id, text="⚠️ نمی‌توانید ربات را سکوت کنید.", reply_to_message_id=message.message_id)
                return
            if not tgt: tgt = sender_id
            if tgt == OWNER_ID:
                await bot.send_message(chat_id=chat_id, text="⚠️ نمی‌توانید مالک ربات را سکوت کنید.", reply_to_message_id=message.message_id)
                return
            et = time.time() + mins * 60
            if "mute_list" not in bot_data: bot_data["mute_list"] = {}
            if chat_id not in bot_data["mute_list"]: bot_data["mute_list"][chat_id] = {}
            bot_data["mute_list"][chat_id][tgt] = et
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=f"🔇 سکوت {mins} دقیقه (پایان: {datetime.fromtimestamp(et).strftime('%H:%M')})")
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
            if tgt == "BOT_SELF":
                await bot.send_message(chat_id=chat_id, text="⚠️ نمی‌توانید به ربات اخطار دهید.", reply_to_message_id=message.message_id)
                return
            if not tgt:
                await bot.send_message(chat_id=chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            ti = await get_user_info(chat_id, tgt)
            await add_warning(chat_id, tgt, "اخطار دستی مالک", user_info=ti)
            return

        if is_command(clean_text, "لیست قفل"):
            if not can_manage: return
            st = lambda v: "🔴" if v else "🟢"
            wl = bot_data["warn_limit"].get(chat_id, 3)
            ws = "🔴" if settings["warning"] else "🟢"
            fc = len(ensure_list_dict(bot_data, "filtered_words", chat_id))
            gl, gr = is_group_locked(chat_id)
            gs = f"🔴 ({gr})" if gl else "🟢"
            wda = get_warn_delete_after(chat_id)
            if wda > 0:
                m, s = wda // 60, wda % 60
                wds = f"🟡 {m}د {s}ث" if m > 0 else f"🟡 {wda}ث"
            else: wds = "🟢"
            ar = bot_data.get("anti_repeat", {}).get(chat_id)
            ars = f"🔴 {ar} پیام یکسان" if ar else "🟢 غیرفعال"
            slow = bot_data.get("slow_mode", {}).get(chat_id)
            slows = f"🔴 {format_duration(slow)}" if slow else "🟢 غیرفعال"
            rl = bot_data.get("rules", {}).get(chat_id)
            rs = "🔴 تنظیم شده" if rl else "🟢 تنظیم نشده"
            tk = "🔴 فعال" if is_talkative_enabled(chat_id) else "🟢 غیرفعال"
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                "📋 **قفل‌ها**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 لینک: {st(settings['link'])}\n🆔 آیدی: {st(settings['id'])}\n"
                f"📢 اسپم: {st(settings['spam'])}\n🔗 هایپرلینک: {st(settings['hyperlink'])}\n"
                f"👋 خوش‌آمد: {st(settings.get('welcome', True))}\n🤬 فحش: {st(settings.get('profanity', True))}\n"
                f"📨 فوروارد: {st(settings.get('forward', False))}\n🎞️ گیف: {st(settings.get('gif', False))}\n"
                f"🔒 قفل گروه: {gs}\n⚠️ اخطار: {ws} ({wl})\n⏱️ حذف اخطار: {wds}\n"
                f"🚫 فیلتر: {fc}/{MAX_FILTER_WORDS}\n"
                f"🔁 ضد تکرار: {ars}\n"
                f"🐌 حالت آهسته: {slows}\n"
                f"📜 قوانین: {rs}\n"
                f"💬 سخنگو: {tk}\n\n⚡ **FLUXBOT**"))
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

        if not bot_is_active: return
        if can_manage: return

        if settings.get("profanity", True):
            bw = contains_profanity(raw_text)
            if bw:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]: await add_warning(chat_id, sender_id, "فحش", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete profanity: {e}", flush=True)
                return

        if settings["filter"]:
            fl = ensure_list_dict(bot_data, "filtered_words", chat_id)
            m = contains_filtered_word(raw_text, fl)
            if m:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]: await add_warning(chat_id, sender_id, "کلمه فیلترشده", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete filter: {e}", flush=True)
                return

        if settings["spam"]:
            if chat_id not in spam_tracker: spam_tracker[chat_id] = {}
            if sender_id not in spam_tracker[chat_id]: spam_tracker[chat_id][sender_id] = []
            spam_tracker[chat_id][sender_id] = [t for t in spam_tracker[chat_id][sender_id] if ct - t < 5]
            spam_tracker[chat_id][sender_id].append(ct)
            if len(spam_tracker[chat_id][sender_id]) >= 5:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]: await add_warning(chat_id, sender_id, "اسپم", user_info=ui)
                except Exception as e:
                    print(f"⚠️ delete spam: {e}", flush=True)
                return

        if settings["link"] and contains_link(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]: await add_warning(chat_id, sender_id, "لینک", user_info=ui)
            except Exception as e:
                print(f"⚠️ delete link: {e}", flush=True)
            return

        if settings["hyperlink"] and contains_hyperlink(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]: await add_warning(chat_id, sender_id, "هایپرلینک", user_info=ui)
            except Exception as e:
                print(f"⚠️ delete hyperlink: {e}", flush=True)
            return

        if settings["id"] and contains_id(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]: await add_warning(chat_id, sender_id, "آیدی", user_info=ui)
            except Exception as e:
                print(f"⚠️ delete id: {e}", flush=True)
            return

        if settings.get("forward", False) and is_forwarded(message):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]: await add_warning(chat_id, sender_id, "فوروارد", user_info=ui)
            except Exception as e:
                print(f"⚠️ delete forward: {e}", flush=True)
            return

        if settings.get("gif", False) and is_gif(message):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]: await add_warning(chat_id, sender_id, "گیف", user_info=ui)
            except Exception as e:
                print(f"⚠️ delete gif: {e}", flush=True)
            return

    except Exception as e:
        print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)
        try:
            traceback.print_exc()
        except: pass


async def main():
    print("🤖 FLUXBOT STARTING...", flush=True)
    print(f"👑 OWNER: {OWNER_ID}", flush=True)
    try: asyncio.create_task(cleanup_task())
    except: pass
    try: asyncio.create_task(group_cleanup_task())
    except: pass
    try: await bot.run()
    except Exception as e: print(f"❌ BOT RUN: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
