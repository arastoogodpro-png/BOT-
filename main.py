import os
import re
import json
import time
import asyncio
import random
from datetime import datetime, timedelta
from rubka import Robot, Message
from rubka.keypad import ChatKeypadBuilder

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

# ================== تایم‌زون ایران ==================
TIMEZONE_OFFSET_HOURS = 3.5

def get_local_now():
    return datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET_HOURS)

# ================== مسیرهای ذخیره‌سازی ==================
DATA_PATHS = [
    "/data/bot_data.json",
    "/app/data/bot_data.json",
    "/app/bot_data.json",
    "/tmp/bot_data.json",
    "./bot_data.json",
]
CACHE_PATHS = [
    "/data/message_cache.json",
    "/app/data/message_cache.json",
    "/app/message_cache.json",
    "/tmp/message_cache.json",
    "./message_cache.json",
]

for _p in ["/data", "/app/data", "/tmp"]:
    try:
        os.makedirs(_p, exist_ok=True)
    except:
        pass

BTN_CHANNEL_TEXT = "📢 کانال رسمی"
BTN_HELP_TEXT = "📚 آموزش فعال‌سازی"
BTN_USERS_TEXT = "👥 کاربران"
BTN_GROUPS_TEXT = "🏠 گروه‌های فعال"
MAX_FILTER_WORDS = 50

# زمان پیش‌فرض برای پاک شدن پیام‌های اطلاع‌رسانی (قفل/سکوت)
NOTICE_DELETE_AFTER = 10  # ثانیه

username_cache = {}
role_cache = {}
lock_cache = {}


# ================== توابع کمکی ==================
def ensure_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.keys()) if value else []
    if isinstance(value, str):
        return [value] if value else []
    return []


def ensure_list_dict(d, key, sub_key=None):
    if key not in d:
        d[key] = []
        return d[key]
    if sub_key is not None:
        if not isinstance(d[key], dict):
            d[key] = {}
        if sub_key not in d[key]:
            d[key][sub_key] = []
        d[key][sub_key] = ensure_list(d[key][sub_key])
        return d[key][sub_key]
    d[key] = ensure_list(d[key])
    return d[key]


# ================== فحش‌ها ==================
PROFANITY_LIST = [
    "کص","کیر","کون","کسکش","کس کش","کصکش","کص کش","خارکصه","خار کصه","خارکسه",
    "بیناموس","بی ناموس","جنده","حرومزاده","حروم زاده","مادرت","مادرتو","مادر خراب",
    "مادر سگ","خواهرت","پدرت","پدر سگ","لاشی","لاشخور","دیوث","دیوثه","بیشعور",
    "احمق","خرفت","کودن","پررو","گاگول","کمه","کمه مغز","خنگ","نفهم","بیسواد",
    "کثافت","گوه","گوه خور","گه","گه خور","شاش","شاشو","جاکش","جا کش","قرمساق",
    "کاسه لیس","پاچه خار","چاپلوس","کونده","کونی","خارکسده","خار کس","سگی",
    "سگ صفت","خری","الاغ","گاوی","گوساله","کرم خور","بی پدر","بیمادر",
    "حرامی","پدرسوخته","مادرسوخته","بی غیرت","عوضی","مزخرف",
    "چرند","کصخل","کسخل","کص خور","کیرخور","کیر کش","پفیوز","چسی","چس خور","تخمی",
    "تخم سگ","مغز کیر","کص مغز","نناموس","بی حیا","لختی","برهنه","کیرمغز",
    "خارکسه","خوارکسده","گوزو","گوزیدن","عنین","پدرسگ","مادرجنده","کیرخوری",
    "کصلیسی","جاکشی","دیوثی","خانجی","ابلهی","نادانی","جاهلی","منافقی","دروغگویی",
    "خیانت","فاحشه","فاحشگی","روسپی","لجنی","کثیفی","پلیدی","خباثت","شرارت","رذالت",
]

# ================== سرگرمی‌ها ==================
JOKES = [
    "به یارو میگن چرا زنتو میزنی؟ میگه چون عاشقشم! 😂",
    "رفتم دکتر گفتم آدم‌ها رو دوست ندارم! گفت پس چرا اومدی؟ گفتم تو که آدم نیستی! 😅",
    "به یارو میگن شغلت چیه؟ میگه بیکارم! میگن پس چطوری خرج می‌کنی؟ میگه آبروم رو می‌فروشم! 😂",
    "از یارو پرسیدن چرا زیر بارون وایسادی؟ گفت منتظرم یه قطره بیفته تا لیوانم پر شه! 🌧️",
    "به یارو میگن چرا کلاهت کجه؟ میگه آفتاب از راست می‌تابه، منم کچلم! ☀️",
    "از یارو پرسیدن چرا دندونات زرده؟ گفت قهوه می‌خورم! گفتن چرا چشات قهوه‌ایه؟ گفت زل می‌زنم به فنجون! ☕",
    "به یارو میگن شب‌ها چیکار می‌کنی؟ میگه می‌خوابم! میگن روزها چی؟ میگه از خواب شبانه استراحت می‌کنم! 😴",
    "از یارو پرسیدن چرا اینقدر لاغری؟ گفت هر شب با فکر کردن لاغر می‌شم! 🧠",
    "به یارو میگن پس فردا امتحان داری؟ گفت نه، پس فردا فرار می‌کنم! 🏃",
    "از یارو پرسیدن چرا همیشه دیر میای؟ گفت چون همیشه میگم یه دقیقه دیگه! ⏰",
    "به یارو میگن چرا با ماشینت تصادف کردی؟ گفت راننده مقابلم هم مثل من فکر می‌کرد! 🚗",
    "از یارو پرسیدن چرا گوشیت شارژ تموم می‌کنه؟ گفت چون همش باهاش حرف می‌زنم! 📱",
]

PROVERBS = [
    "آب که از سر گذشت، چه یک وجب چه صد وجب. 🌊",
    "از این ستون به آن ستون فرج است. 🕌",
    "از تو حرکت، از خدا برکت. 🙏",
    "اسب را که بردی، لگامش را هم ببر. 🐴",
    "اشک تمساح. 🐊",
    "با یک گل بهار نمی‌شود. 🌸",
    "با گرگ باش، با گرگ زوزه بکش. 🐺",
    "بار کج به منزل نمی‌رسد. 🏠",
    "به عمل کار برآید، به سخندانی نیست. 🛠️",
    "به یک دست صدا نمی‌آید. 👏",
    "پول که بیاید، ایمان می‌رود. 💸",
    "تخم‌مرغ دزد، شتر دزد می‌شود. 🥚",
    "چاه مکن که در آن نیفتی. 🕳️",
    "دانه فلفل، سیاه است ولی دل را می‌سوزاند. 🌶️",
    "دو صد گفته چون نیم کردار نیست. 💬",
]

TRIVIA = [
    "🐙 اختاپوس‌ها سه قلب دارند و خونشان آبی است.",
    "🍯 عسل هرگز فاسد نمی‌شود. عسل ۳۰۰۰ ساله مصری هنوز خوراکی است.",
    "🐘 فیل‌ها تنها پستانداری هستند که نمی‌توانند بپرند.",
    "🌙 ماه هر سال حدود ۳.۸ سانتی‌متر از زمین دور می‌شود.",
    "🦒 زرافه‌ها ۷ مهره گردن دارند، درست مثل انسان‌ها.",
    "🐌 حلزون‌ها تا ۳ سال بدون غذا زنده می‌مانند.",
    "💧 بدن انسان حدود ۶۰٪ آب است. مغز ۷۵٪ و خون ۹۲٪ آب است.",
    "🌍 زمین در هر ثانیه حدود ۳۰ کیلومتر به دور خورشید می‌چرخد.",
    "🐝 زنبورها با رقص، به همدیگر محل گل‌ها را نشان می‌دهند.",
    "🦋 پروانه‌ها با پاهایشان مزه می‌کنند!",
]

FACTS = [
    "🧠 مغز انسان ۲٪ وزن بدن را دارد اما ۲۰٪ انرژی مصرف می‌کند!",
    "🦷 مینای دندان سخت‌ترین ماده در بدن انسان است.",
    "👁️ چشم انسان می‌تواند حدود ۱۰ میلیون رنگ را تشخیص دهد.",
    "💤 انسان در طول عمرش حدود ۲۵ سال می‌خوابد!",
    "🫀 قلب انسان روزانه حدود ۱۰۰ هزار بار می‌تپد.",
    "🩸 رگ‌های خونی بدن اگر باز شوند، حدود ۱۰۰ هزار کیلومتر طول دارند!",
    "🫁 ریه‌ها روزانه حدود ۱۱ هزار لیتر هوا تنفس می‌کنند.",
    "🧬 DNA انسان ۹۹.۹٪ با شامپانزه‌ها مشترک است!",
    "🦴 نوزادان با ۳۰۰ استخوان به دنیا می‌آیند، بزرگسالان ۲۰۶ استخوان دارند.",
    "👅 زبان انسان ۱۰ هزار جوانه چشایی دارد.",
]

PNP = [
    "پند: با دلِ خودت روراست باش، حتی اگر به ضررت باشه. 💚",
    "پند: هرگز قضاوت نکن تا خودت در اون موقعیت قرار نگیری. ⚖️",
    "پند: کسی که از تو تعریف می‌کنه، ممکنه پشت سرت بد بگه. 🤐",
    "پند: موفقیت یعنی بلند شدن بعد از هر زمین خوردن. 💪",
    "پند: به کسی که بهت دروغ می‌گه، فرصت دوم نده. 🚫",
    "پند: زخم زبان از زخم شمشیر بدتره. 🗡️",
    "پند: همیشه کسی که بیشترین کمک رو بهت کرد، بیشتر از همه ازت انتظار داره. 🤝",
    "پند: به کسی که پشت سرت حرف می‌زنه، پشت سرش حرف نزن. 🤫",
    "پند: پول همه چیز نیست، ولی نداشتنش خیلی چیزها رو سخت می‌کنه. 💰",
    "پند: احترام به پدر و مادر، کلید خوشبختیه. 🙏",
]

POEMS = [
    "دوش دیدم که ملائک در میخانه زدند / گل آدم بسرشتند و به پیمانه زدند. 🍷",
    "بنی آدم اعضای یک پیکرند / که در آفرینش ز یک گوهرند. 🤝",
    "توانا بود هر که دانا بود / ز دانش دل پیر برنا بود. 📚",
    "هر که را جامه ز عشقی چاک شد / او ز حرص و عیب کلی پاک شد. ❤️",
    "درخت دوستی بنشان که کام دل به بار آرد / نهال دشمنی برکن که رنج بی‌شمار آرد. 🌳",
]

FAL = [
    "🔮 **فال امروز:** روز خوبی در انتظارته. یه خبر خوش بهت می‌رسه! 🍀",
    "🔮 **فال امروز:** مراقب باش، یه نفر داره پشت سرت حرف می‌زنه. 🤫",
    "🔮 **فال امروز:** پول به دستت می‌رسه، ولی خرجش نکن! 💰",
    "🔮 **فال امروز:** یه سفر کوتاه در پیش داری. ✈️",
    "🔮 **فال امروز:** دل به کسی نبند که لیاقتت رو نداره. 💔",
    "🔮 **فال امروز:** امروز روز موفقیته، پس تنبلی نکن! 💪",
]

LUCK = [
    "🍀 **شانس امروز:** ۱۰ از ۱۰! فوق‌العاده‌ست!",
    "🍀 **شانس امروز:** ۹ از ۱۰! عالیه!",
    "🍀 **شانس امروز:** ۸ از ۱۰! خوبه!",
    "🍀 **شانس امروز:** ۷ از ۱۰! معمولیه.",
    "🍀 **شانس امروز:** ۵ از ۱۰! یه ذره ضعیفه.",
    "🍀 **شانس امروز:** ۳ از ۱۰! امروز احتیاط کن!",
    "🍀 **شانس امروز:** ۱ از ۱۰! بهتره خونه بمونی!",
]


# ================== توابع کمکی عمومی ==================
def clean_message(text):
    if not text:
        return ""
    text = re.sub(r"@\S+", "", text)
    text = re.sub(r"/(\w+)", r"\1", text)
    return text.strip()


def normalize_text(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\u0600-\u06FF]', '', text)
    return text


def is_group_chat(chat_id):
    return bool(chat_id) and str(chat_id).lower().startswith("g")


def is_private_chat(chat_id):
    if not chat_id:
        return False
    cid = str(chat_id).lower()
    return cid.startswith("u") or cid.startswith("b")


def get_now_time():
    return get_local_now().strftime("%H:%M - %Y/%m/%d")


def extract_reply_id(message):
    for attr in ['reply_to_message_id', 'reply_to', 'reply_message_id']:
        if hasattr(message, attr):
            val = getattr(message, attr)
            if val:
                if hasattr(val, 'message_id'):
                    return str(val.message_id)
                return str(val)
    return None


def is_forwarded(message):
    for attr in ['forwarded_from', 'forward_from', 'forward', 'is_forwarded', 'fwd_from']:
        if hasattr(message, attr):
            val = getattr(message, attr)
            if val:
                return True
    return False


def is_gif(message):
    for attr in ['is_gif', 'gif', 'animation', 'is_animation']:
        if hasattr(message, attr):
            val = getattr(message, attr)
            if val:
                return True
    msg_type = str(getattr(message, 'type', '') or getattr(message, 'message_type', '')).lower()
    if 'gif' in msg_type or 'animation' in msg_type:
        return True
    return False


async def get_user_info(chat_id, user_id):
    cache_key = f"{chat_id}:{user_id}"
    if cache_key in username_cache:
        cached = username_cache[cache_key]
        if cached.get("username") or cached.get("name"):
            return cached

    info = {"name": None, "username": None, "role": "عضو"}
    try:
        member_info = await bot.get_chat_member(chat_id, user_id)
        if member_info:
            data = member_info.get("data", member_info) if isinstance(member_info, dict) else member_info
            chat_member = data.get("chat_member", data) if isinstance(data, dict) else {}

            info["name"] = (
                chat_member.get("first_name") or
                chat_member.get("name") or
                chat_member.get("title") or
                chat_member.get("display_name") or
                chat_member.get("full_name")
            )

            uname = (
                chat_member.get("username") or
                chat_member.get("user_name") or
                chat_member.get("user_username") or
                chat_member.get("userName")
            )
            if uname:
                info["username"] = str(uname).lstrip("@")

            status = str(chat_member.get("status", "")).strip().lower()
            if status in ("creator", "owner"):
                info["role"] = "مالک"
            elif status in ("admin", "administrator"):
                info["role"] = "ادمین"
            else:
                access = chat_member.get("access_list", [])
                if isinstance(access, list) and access:
                    if "BanMember" in access or "DeleteGlobalAllMessages" in access:
                        info["role"] = "ادمین"

            username_cache[cache_key] = info
    except Exception as e:
        print(f"⚠️ USER INFO ERROR: {e}", flush=True)
    return info


def format_user_display(user_info, user_id):
    if user_info.get("username"):
        return f"@{user_info['username']}"
    if user_info.get("name"):
        return user_info["name"]
    uid = str(user_id)
    if uid.startswith("u") or uid.startswith("b"):
        uid = uid[1:]
    return f"کاربر `{uid[:12]}`"


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
    except:
        return "گروه"


# ================== فایل‌ها ==================
def load_cache():
    for path in CACHE_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    print(f"✅ CACHE LOADED FROM: {path}", flush=True)
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ LOAD CACHE {path}: {e}", flush=True)
    return {}


def save_cache(cache):
    for path in CACHE_PATHS:
        try:
            dn = os.path.dirname(path)
            if dn and not os.path.exists(dn):
                os.makedirs(dn, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ SAVE CACHE {path}: {e}", flush=True)


def load_data():
    default_data = {
        "welcomed_users": {}, "user_titles": {}, "taken_asl": {}, "taken_laghab": {},
        "message_counts": {}, "join_dates": {}, "special_users": {}, "warnings": {},
        "warn_limit": {}, "warn_delete_after": {}, "started_users": [], "known_groups": [],
        "group_message_count": {}, "promo_sent": {}, "filtered_words": {},
        "banned_users": {},
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
                    for list_key in ["started_users", "known_groups"]:
                        if list_key in loaded:
                            loaded[list_key] = ensure_list(loaded[list_key])
                    for k, v in default_data.items():
                        if k not in loaded:
                            loaded[k] = v
                    if "settings" in loaded:
                        for sk, sv in default_data["settings"].items():
                            if sk not in loaded["settings"]:
                                loaded["settings"][sk] = sv
                    print(f"✅ DATA LOADED FROM: {path}", flush=True)
                    return loaded
        except Exception as e:
            print(f"⚠️ LOAD DATA {path}: {e}", flush=True)
    print("ℹ️ NO DATA FILE FOUND - starting fresh", flush=True)
    return default_data


def save_data(data):
    for path in DATA_PATHS:
        try:
            dn = os.path.dirname(path)
            if dn and not os.path.exists(dn):
                os.makedirs(dn, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ SAVE DATA {path}: {e}", flush=True)


# ================== وضعیت‌ها ==================
bot_is_active = True
mute_list = {}
bot_data = load_data()
settings = bot_data.get("settings", {})
for sk in ["link", "id", "spam", "hyperlink", "welcome", "warning", "filter", "auto_ban", "profanity", "forward", "gif", "goodbye"]:
    if sk not in settings:
        settings[sk] = False
message_cache = load_cache()
spam_tracker = {}

group_locks = {}
temp_locks = {}
scheduled_locks = {}


# ================== توابع تشخیص ==================
def contains_link(text):
    if not text:
        return False
    patterns = [r'https?://\S+', r'www\.\S+', r't\.me/\S+', r'rubika\.ir/\S+',
                r'telegram\.me/\S+', r'\.ir/\S+', r'\.com/\S+', r'\.org/\S+', r'\.net/\S+', r'\.me/\S+']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def contains_hyperlink(text):
    if not text:
        return False
    return bool(re.search(r'\[.+?\]\(.+?\)', text) or re.search(r'<a\s+href=', text, re.IGNORECASE))


def contains_id(text):
    if not text:
        return False
    return bool(re.search(r'@\w+', text))


def is_command(text, *commands):
    if not text:
        return False
    t = text.strip()
    return any(t == c for c in commands)


def contains_filtered_word(text, filtered_list):
    if not text or not filtered_list:
        return None
    normalized = normalize_text(text)
    if not normalized:
        return None
    for word in filtered_list:
        nw = normalize_text(word)
        if nw and nw in normalized:
            return word
    return None


def contains_profanity(text):
    if not text:
        return None
    normalized = normalize_text(text)
    if not normalized:
        return None
    for word in PROFANITY_LIST:
        nw = normalize_text(word)
        if nw and nw in normalized:
            return word
    return None


def get_remaining_time(end_time):
    diff = end_time - time.time()
    if diff <= 0:
        return "0 ثانیه"
    hours = int(diff // 3600)
    minutes = int((diff % 3600) // 60)
    seconds = int(diff % 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours} ساعت")
    if minutes > 0:
        parts.append(f"{minutes} دقیقه")
    if seconds > 0 and hours == 0:
        parts.append(f"{seconds} ثانیه")
    return " و ".join(parts) if parts else "0 ثانیه"


def is_group_locked(chat_id):
    if group_locks.get(chat_id, False):
        return True, "قفل دستی"

    if chat_id in temp_locks:
        end_time = temp_locks[chat_id]
        if time.time() < end_time:
            end_str = datetime.fromtimestamp(end_time).strftime("%H:%M")
            return True, f"قفل موقت (پایان: {end_str})"
        else:
            del temp_locks[chat_id]

    if chat_id in scheduled_locks and scheduled_locks[chat_id]:
        now = get_local_now()
        current_minutes = now.hour * 60 + now.minute
        for start_h, start_m, end_h, end_m in scheduled_locks[chat_id]:
            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            time_range_str = f"{start_h:02d}:{start_m:02d} تا {end_h:02d}:{end_m:02d}"
            if start_min <= end_min:
                if start_min <= current_minutes < end_min:
                    return True, f"قفل زمان‌بندی ({time_range_str})"
            else:
                if current_minutes >= start_min or current_minutes < end_min:
                    return True, f"قفل زمان‌بندی ({time_range_str})"

    return False, ""


def get_warn_delete_after(chat_id):
    """دریافت مدت زمان پاک شدن پیام اخطار (0 = غیرفعال)"""
    val = bot_data.get("warn_delete_after", {}).get(chat_id, 0)
    try:
        return int(val)
    except:
        return 0


# ================== اخطار ==================
async def add_warning(chat_id, user_id, reason="", user_info=None):
    try:
        if chat_id not in bot_data["warnings"]:
            bot_data["warnings"][chat_id] = {}
        if user_id not in bot_data["warnings"][chat_id]:
            bot_data["warnings"][chat_id][user_id] = 0
        bot_data["warnings"][chat_id][user_id] += 1
        count = bot_data["warnings"][chat_id][user_id]
        limit = bot_data["warn_limit"].get(chat_id, 3)
        save_data(bot_data)

        if user_info is None:
            user_info = await get_user_info(chat_id, user_id)
        display = format_user_display(user_info, user_id)

        # مدت زمان پاک شدن پیام اخطار
        del_after = get_warn_delete_after(chat_id)
        del_param = del_after if del_after > 0 else None

        warn_text = (
            f"⚠️ **اخطار!** ⚠️\n\n"
            f"👤 **کاربر:** {display}\n"
            f"📌 **دلیل:** {reason if reason else 'تخلف از قوانین'}\n"
            f"📊 **اخطار فعلی:** [{count}/{limit}]\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ **FLUXBOT** | جریان قدرت"
        )
        try:
            kwargs = {"chat_id": chat_id, "text": warn_text}
            if del_param:
                kwargs["delete_after"] = del_param
            await bot.send_message(**kwargs)
        except Exception as e:
            print(f"⚠️ WARN SEND: {e}", flush=True)

        if count >= limit and settings.get("auto_ban", True):
            try:
                await bot.ban_member_chat(chat_id, user_id)
                if chat_id not in bot_data["banned_users"]:
                    bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][user_id] = time.time()
                save_data(bot_data)

                ban_msg = f"🚫 **کاربر اخراج شد!**\n\n👤 {display}\n📊 تعداد اخطار: [{count}/{limit}]"
                kwargs = {"chat_id": chat_id, "text": ban_msg}
                if del_param:
                    kwargs["delete_after"] = del_param
                await bot.send_message(**kwargs)

                bot_data["warnings"][chat_id][user_id] = 0
                save_data(bot_data)
                return True
            except Exception as e:
                print(f"❌ BAN ERROR: {e}", flush=True)
        return False
    except Exception as e:
        print(f"❌ ADD WARNING: {e}", flush=True)
        return False


def register_user(user_id):
    try:
        if not user_id:
            return
        if not isinstance(bot_data.get("started_users"), list):
            bot_data["started_users"] = ensure_list(bot_data.get("started_users"))
        if user_id not in bot_data["started_users"]:
            bot_data["started_users"].append(user_id)
            save_data(bot_data)
    except Exception as e:
        print(f"⚠️ REGISTER USER: {e}", flush=True)


def register_group(chat_id):
    try:
        if not chat_id:
            return
        if not isinstance(bot_data.get("known_groups"), list):
            bot_data["known_groups"] = ensure_list(bot_data.get("known_groups"))
        if chat_id not in bot_data["known_groups"]:
            bot_data["known_groups"].append(chat_id)
            save_data(bot_data)
    except Exception as e:
        print(f"⚠️ REGISTER GROUP: {e}", flush=True)


# ================== کیبورد ==================
def build_chat_keypad():
    try:
        b = ChatKeypadBuilder()
        btn1 = b.button_simple(id="btn_channel", text=BTN_CHANNEL_TEXT)
        btn2 = b.button_simple(id="btn_help", text=BTN_HELP_TEXT)
        btn3 = b.button_simple(id="btn_users", text=BTN_USERS_TEXT)
        btn4 = b.button_simple(id="btn_groups", text=BTN_GROUPS_TEXT)
        b.row(btn1, btn2)
        b.row(btn3, btn4)
        return b.build()
    except Exception as e:
        print(f"❌ KEYPAD: {e}", flush=True)
        return None


# ================== متن‌ها ==================
def get_channel_text():
    return "📢 **کانال رسمی ربات FluxBot**\n\n➣ **@Fluxbot1**\n\n🌟 برای حمایت از ما، دریافت آخرین اخبار، به‌روزرسانی‌ها و آموزش‌های ویژه، لطفاً در کانال رسمی ما عضو شوید. 🙏\n\n💎 **عضویت شما، انگیزه ما برای بهتر شدن است.**\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"


def get_help_text():
    return "📚 **آموزش فعال‌سازی ربات FluxBot**\n\n1️⃣ **ربات را به گروه خود اضافه کنید**\n\n2️⃣ **دسترسی کامل بدهید:**\n   └ ربات را **ادمین** کنید\n   └ دسترسی «حذف پیام» و «مشاهده پیام‌ها» را فعال کنید\n\n3️⃣ **منتظر بمانید:**\n   └ بین ۱ تا ۲ دقیقه صبر کنید\n\n4️⃣ **فعال‌سازی:**\n   └ در گروه بنویسید: `فعال`\n\n💡 گزینه «دریافت همه پیام‌های گروه» را فعال کنید.\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"


def get_users_text():
    count = len(ensure_list(bot_data.get("started_users", [])))
    return f"👥 **آمار کاربران FluxBot**\n\n📊 **تعداد کاربران استارت‌زده:**\n└ **{count}** کاربر\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"


def get_groups_text():
    count = len(ensure_list(bot_data.get("known_groups", [])))
    return f"🏠 **آمار گروه‌های فعال FluxBot**\n\n📊 **تعداد گروه‌های فعال:**\n└ **{count}** گروه\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"


# ================== هندلر پیام‌ها ==================
@bot.on_message()
async def handle_message(bot, message):
    global bot_is_active, message_cache, bot_data, settings

    try:
        msg_id = str(message.message_id)
        chat_id = str(message.chat_id) if message.chat_id else ""
        sender_id = str(message.sender_id) if message.sender_id else ""
        raw_text = (message.text or "").strip()
        clean_text = clean_message(raw_text)

        aux_data = getattr(message, 'aux_data', None) or getattr(message, 'auxData', None)
        button_id = None
        if aux_data and isinstance(aux_data, dict):
            button_id = aux_data.get('button_id') or aux_data.get('id')

        if sender_id:
            register_user(sender_id)
        if is_group_chat(chat_id):
            register_group(chat_id)

        if chat_id and msg_id and sender_id:
            if chat_id not in message_cache:
                message_cache[chat_id] = {}
            message_cache[chat_id][msg_id] = sender_id
            if len(message_cache[chat_id]) > 500:
                keys = list(message_cache[chat_id].keys())
                for k in keys[:-500]:
                    del message_cache[chat_id][k]
            save_cache(message_cache)

        if not hasattr(handle_message, 'processed'):
            handle_message.processed = {}
            handle_message.last_cleanup = time.time()

        ct = time.time()
        if ct - handle_message.last_cleanup > 15:
            handle_message.processed = {k: v for k, v in handle_message.processed.items() if ct - v < 15}
            handle_message.last_cleanup = ct

        if msg_id in handle_message.processed:
            return
        handle_message.processed[msg_id] = ct

        print(f"📩 MESSAGE | chat={chat_id} | sender={sender_id} | raw={raw_text!r}", flush=True)

        # ============ پیوی ============
        if is_private_chat(chat_id):
            if button_id == "btn_channel" or raw_text == BTN_CHANNEL_TEXT:
                await bot.send_message(chat_id=chat_id, text=get_channel_text())
                return
            if button_id == "btn_help" or raw_text == BTN_HELP_TEXT:
                await bot.send_message(chat_id=chat_id, text=get_help_text())
                return
            if button_id == "btn_users" or raw_text == BTN_USERS_TEXT:
                await bot.send_message(chat_id=chat_id, text=get_users_text())
                return
            if button_id == "btn_groups" or raw_text == BTN_GROUPS_TEXT:
                await bot.send_message(chat_id=chat_id, text=get_groups_text())
                return

            if is_command(clean_text, "start", "شروع", "منو"):
                welcome_text = (
                    "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                    "   ⚡ **FLUXBOT** ⚡\n"
                    "   🌊 جریان قدرت 🌊\n"
                    "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                    "🌟 **به ربات مدیریتی FluxBot خوش آمدید!**\n\n"
                    "🤖 من یک ربات مدیریتی حرفه‌ای برای گروه‌های روبیکا هستم.\n\n"
                    "👇 **از منوی پایین، یکی از گزینه‌ها رو انتخاب کنید:**"
                )
                keypad = build_chat_keypad()
                if keypad:
                    try:
                        await bot.send_message(chat_id=chat_id, text=welcome_text, chat_keypad=keypad, chat_keypad_type="New")
                    except:
                        await bot.send_message(chat_id=chat_id, text=welcome_text)
                else:
                    await bot.send_message(chat_id=chat_id, text=welcome_text)
                return
            return

        # ============ گروه ============
        if not is_group_chat(chat_id):
            return

        user_info = await get_user_info(chat_id, sender_id)
        role = user_info["role"]
        display_name = format_user_display(user_info, sender_id)
        is_owner = (role == "مالک")
        is_special = bot_data.get("special_users", {}).get(chat_id, {}).get(sender_id, False)
        can_manage = is_owner or is_special

        # ============ بررسی قفل گروه ============
        locked, lock_reason = is_group_locked(chat_id)

        if locked and not can_manage:
            print(f"🔒 GROUP LOCKED ({lock_reason}) - DELETING MESSAGE FROM {sender_id}", flush=True)
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                print(f"🗑️ DELETED (locked)", flush=True)
            except Exception as e:
                print(f"❌ DELETE LOCKED: {e}", flush=True)

            # اطلاع به کاربر با auto-delete (هر 30 ثانیه یک بار)
            notice_key = f"lock_notice:{chat_id}:{sender_id}"
            last_notice = handle_message.processed.get(notice_key, 0)
            if ct - last_notice > 30:
                handle_message.processed[notice_key] = ct
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"🔒 **گروه قفل است!**\n\n"
                            f"👤 {display_name}\n"
                            f"📌 **دلیل:** {lock_reason}\n\n"
                            f"⏱️ این پیام پس از {NOTICE_DELETE_AFTER} ثانیه پاک می‌شود."
                        ),
                        delete_after=NOTICE_DELETE_AFTER
                    )
                except Exception as e:
                    print(f"⚠️ LOCK NOTICE ERROR: {e}", flush=True)
            return

        # ============ دستورات مدیریتی ============

        # باز کردن قفل گروه
        if is_command(clean_text, "باز", "بازکردن", "unlock"):
            if not can_manage:
                return
            had = False
            if group_locks.get(chat_id, False):
                group_locks[chat_id] = False
                had = True
            if chat_id in temp_locks:
                del temp_locks[chat_id]
                had = True
            if had:
                await bot.send_message(chat_id=message.chat_id, text="🔓 **گروه باز شد!**", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            else:
                await bot.send_message(chat_id=message.chat_id, text="ℹ️ گروه از قبل باز بود.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        # قفل گروه دستی
        if is_command(clean_text, "قفل گروه", "قفل گروهی", "قفلگروه"):
            if not can_manage:
                return
            group_locks[chat_id] = True
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                "🔒 **گروه قفل شد!**\n\n"
                "از این پس تنها مالک و افراد ویژه می‌توانند پیام ارسال کنند.\n\n"
                "برای باز کردن: `باز`"))
            return

        # قفل موقت
        temp_lock_match = re.match(r"^قفل\s+(\d+)$", clean_text)
        if temp_lock_match:
            if not can_manage:
                return
            hours = int(temp_lock_match.group(1))
            if hours <= 0 or hours > 168:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد بین 1 تا 168 ساعت.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            end_time = time.time() + (hours * 3600)
            temp_locks[chat_id] = end_time
            group_locks[chat_id] = False
            end_str = datetime.fromtimestamp(end_time).strftime("%H:%M - %Y/%m/%d")
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                f"🔒 **قفل موقت فعال شد!**\n\n"
                f"⏱️ **مدت:** {hours} ساعت\n"
                f"🕐 **پایان:** {end_str}\n\n"
                f"برای باز کردن: `باز`"))
            return

        # قفل زمان‌بندی
        sched_match = re.match(r"^قفل\s+(\d{1,2}):(\d{2})\s+(?:تا\s+)?(\d{1,2}):(\d{2})$", clean_text)
        if sched_match:
            if not can_manage:
                return
            sh, sm, eh, em = map(int, sched_match.groups())
            if not (0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
                await bot.send_message(chat_id=message.chat_id, text="⚠️ ساعت نامعتبر.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            if chat_id not in scheduled_locks:
                scheduled_locks[chat_id] = []
            scheduled_locks[chat_id].append((sh, sm, eh, em))
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                f"🔒 **قفل زمان‌بندی شده فعال شد!**\n\n"
                f"⏰ **از:** `{sh:02d}:{sm:02d}`\n"
                f"⏰ **تا:** `{eh:02d}:{em:02d}`\n\n"
                f"📋 تعداد قفل‌های زمان‌بندی: {len(scheduled_locks[chat_id])}\n"
                f"برای حذف: `حذف قفل زمان‌بندی`"))
            return

        # حذف قفل زمان‌بندی
        if is_command(clean_text, "حذف قفل زمان‌بندی", "حذف قفل زمانبندی"):
            if not can_manage:
                return
            if chat_id in scheduled_locks:
                scheduled_locks[chat_id] = []
            await bot.send_message(chat_id=message.chat_id, text="✅ قفل‌های زمان‌بندی حذف شدند.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        # لیست قفل گروه
        if is_command(clean_text, "لیست قفل گروه", "وضعیت قفل گروه"):
            if not can_manage:
                return
            status = []
            if group_locks.get(chat_id, False):
                status.append("🔴 **قفل دستی:** فعال")
            else:
                status.append("🟢 **قفل دستی:** غیرفعال")

            if chat_id in temp_locks:
                rem = get_remaining_time(temp_locks[chat_id])
                status.append(f"🟡 **قفل موقت:** فعال (باقی: {rem})")
            else:
                status.append("🟢 **قفل موقت:** غیرفعال")

            if chat_id in scheduled_locks and scheduled_locks[chat_id]:
                sched_str = "\n".join([f"  • {sh:02d}:{sm:02d} تا {eh:02d}:{em:02d}" for sh, sm, eh, em in scheduled_locks[chat_id]])
                status.append(f"🟡 **قفل‌های زمان‌بندی:**\n{sched_str}")
            else:
                status.append("🟢 **قفل زمان‌بندی:** غیرفعال")

            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
                "   ⚡ **FLUXBOT** ⚡\n"
                "   🔒 وضعیت قفل گروه 🔒\n"
                "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                + "\n\n".join(status) +
                "\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"))
            return

        # ============ بررسی سکوت ============
        now = time.time()
        chat_mutes = mute_list.get(chat_id, {})
        if sender_id in chat_mutes:
            end_time = chat_mutes[sender_id]
            if now < end_time:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                except:
                    pass
                # اطلاع به کاربر هر 30 ثانیه یک بار
                notice_key = f"mute_notice:{chat_id}:{sender_id}"
                last_notice = handle_message.processed.get(notice_key, 0)
                if ct - last_notice > 30:
                    handle_message.processed[notice_key] = ct
                    remaining = get_remaining_time(end_time)
                    end_dt = datetime.fromtimestamp(end_time).strftime("%H:%M")
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=(
                                f"🔇 **{display_name} عزیز**\n\n"
                                f"شما در لیست سکوت قرار دارید.\n"
                                f"⏳ **باقی‌مانده:** `{remaining}`\n"
                                f"🕐 **پایان:** `{end_dt}`"
                            ),
                            delete_after=NOTICE_DELETE_AFTER
                        )
                    except:
                        pass
                return
            else:
                del chat_mutes[sender_id]

        # ============ شمارنده 200 پیام ============
        if chat_id not in bot_data["group_message_count"]:
            bot_data["group_message_count"][chat_id] = 0
        bot_data["group_message_count"][chat_id] += 1

        if bot_data["group_message_count"][chat_id] >= 200:
            bot_data["group_message_count"][chat_id] = 0
            bot_data["promo_sent"][chat_id] = bot_data["promo_sent"].get(chat_id, 0) + 1
            save_data(bot_data)
            try:
                await bot.send_message(chat_id=chat_id, text=(
                    "╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   🌊 جریان قدرت 🌊\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                    "💎 **از مدیریت حرفه‌ای لذت می‌برید؟**\n\n"
                    "برای حمایت از ما لطفاً در کانال رسمی عضو شوید:\n📢 **@Fluxbot1**\n\n"
                    "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"))
            except:
                pass
        else:
            save_data(bot_data)

        # ============ خوش‌آمدگویی ============
        if settings["welcome"] and bot_is_active:
            welcomed = bot_data.get("welcomed_users", {}).get(chat_id, {})
            if sender_id not in welcomed:
                chat_name = await get_chat_name(chat_id)
                now_str = get_now_time()
                try:
                    await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                        f"╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   🌊 جریان قدرت 🌊\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                        f"🌟 **به گروه {chat_name} خوش آمدید!** 🌟\n\n"
                        f"👤 **کاربر گرامی {display_name}:**\nاز اینکه به جمع ما پیوستید بی‌نهایت خوشحالیم. 🌹\n\n"
                        f"⏰ **زمان ورود:** {now_str}\n\n"
                        f"💎 **امکانات FluxBot:**\n├ 📊 `پروفایل`\n├ 🐺 `تنظیم اصل [نام]`\n├ 🎭 `تنظیم لقب [نام]`\n├ 👑 `مقام`\n└ 📚 `راهنما`\n\n"
                        f"━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"))
                except:
                    pass
                if chat_id not in bot_data["welcomed_users"]:
                    bot_data["welcomed_users"][chat_id] = {}
                bot_data["welcomed_users"][chat_id][sender_id] = True
                save_data(bot_data)

        # ============ آمار پیام ============
        today = get_local_now().strftime("%Y-%m-%d")
        if chat_id not in bot_data["message_counts"]:
            bot_data["message_counts"][chat_id] = {}
        if sender_id not in bot_data["message_counts"][chat_id]:
            bot_data["message_counts"][chat_id][sender_id] = {"today": 0, "date": today}
        else:
            if bot_data["message_counts"][chat_id][sender_id]["date"] != today:
                bot_data["message_counts"][chat_id][sender_id] = {"today": 0, "date": today}
        bot_data["message_counts"][chat_id][sender_id]["today"] += 1
        save_data(bot_data)

        # ============ دستورات ============

        if is_command(clean_text, "فعال", "فاعل"):
            if not can_manage:
                return
            reply_text = "✅ ربات از قبل فعال است." if bot_is_active else "✅ ربات فعال شد."
            bot_is_active = True
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        if is_command(clean_text, "غیرفعال", "غيرفعال"):
            if not is_owner:
                return
            reply_text = "⛔ ربات از قبل غیرفعال است." if not bot_is_active else "🛑 ربات غیرفعال شد."
            bot_is_active = False
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        # ⭐ قابلیت جدید: حذف پیام اخطار
        warn_delete_match = re.match(r"^حذف\s+پیام\s+اخطار\s+(\d+)$", clean_text)
        if warn_delete_match:
            if not is_owner:
                return
            seconds = int(warn_delete_match.group(1))
            if seconds < 0 or seconds > 3600:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد باید بین 0 تا 3600 باشد.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            
            if "warn_delete_after" not in bot_data:
                bot_data["warn_delete_after"] = {}
            
            if seconds == 0:
                bot_data["warn_delete_after"][chat_id] = 0
                save_data(bot_data)
                await bot.send_message(
                    chat_id=message.chat_id,
                    text="✅ **حذف خودکار پیام اخطار غیرفعال شد.**\n\n📌 از این پس پیام‌های اخطار باقی می‌مانند.",
                    reply_to_message_id=message.message_id,
                    delete_after=NOTICE_DELETE_AFTER
                )
            else:
                bot_data["warn_delete_after"][chat_id] = seconds
                save_data(bot_data)
                mins = seconds // 60
                secs = seconds % 60
                if mins > 0:
                    time_str = f"{mins} دقیقه" + (f" و {secs} ثانیه" if secs > 0 else "")
                else:
                    time_str = f"{seconds} ثانیه"
                await bot.send_message(
                    chat_id=message.chat_id,
                    text=f"✅ **حذف خودکار پیام اخطار فعال شد!**\n\n⏱️ زمان: **{time_str}**\n\n📌 از این پس پیام‌های اخطار و اخراج پس از این مدت پاک می‌شوند.",
                    reply_to_message_id=message.message_id,
                    delete_after=NOTICE_DELETE_AFTER
                )
            return

        # بن
        if is_command(clean_text, "بن", "سیک", "اخراج", "ban"):
            if not can_manage:
                return
            reply_id = extract_reply_id(message)
            target_user_id = None
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]
            if not target_user_id:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ لطفاً روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            try:
                t_info = await get_user_info(chat_id, target_user_id)
                t_display = format_user_display(t_info, target_user_id)
                await bot.ban_member_chat(chat_id, target_user_id)
                if chat_id not in bot_data["banned_users"]:
                    bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][target_user_id] = time.time()
                save_data(bot_data)
                
                del_after = get_warn_delete_after(chat_id)
                del_param = del_after if del_after > 0 else None
                kwargs = {
                    "chat_id": message.chat_id,
                    "reply_to_message_id": message.message_id,
                    "text": f"🚫 **کاربر اخراج شد!** 🚫\n\n👤 **کاربر:** {t_display}\n📌 **دلیل:** تخلف از قوانین"
                }
                if del_param:
                    kwargs["delete_after"] = del_param
                await bot.send_message(**kwargs)
            except Exception as e:
                print(f"❌ BAN: {e}", flush=True)
            return

        # انبن
        if is_command(clean_text, "انبن", "آنبن", "unban"):
            if not can_manage:
                return
            reply_id = extract_reply_id(message)
            target_user_id = None
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]
            if not target_user_id:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            try:
                t_info = await get_user_info(chat_id, target_user_id)
                t_display = format_user_display(t_info, target_user_id)
                await bot.unban_member_chat(chat_id, target_user_id)
                if chat_id in bot_data["banned_users"] and target_user_id in bot_data["banned_users"][chat_id]:
                    del bot_data["banned_users"][chat_id][target_user_id]
                    save_data(bot_data)
                
                del_after = get_warn_delete_after(chat_id)
                del_param = del_after if del_after > 0 else None
                kwargs = {
                    "chat_id": message.chat_id,
                    "reply_to_message_id": message.message_id,
                    "text": f"✅ **کاربر آنبن شد!** ✅\n\n👤 **کاربر:** {t_display}\n🌟 از لیست سیاه حذف شد."
                }
                if del_param:
                    kwargs["delete_after"] = del_param
                await bot.send_message(**kwargs)
            except Exception as e:
                print(f"❌ UNBAN: {e}", flush=True)
            return

        # فیلتر
        filter_match = re.match(r"^فیلتر\s+(.+)$", clean_text)
        if filter_match:
            if not is_owner:
                return
            word = filter_match.group(1).strip()
            if not word:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ یک کلمه وارد کنید.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            fw_list = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if word in fw_list:
                await bot.send_message(chat_id=message.chat_id, text=f"⚠️ «{word}» از قبل فیلتر شده.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            if len(fw_list) >= MAX_FILTER_WORDS:
                await bot.send_message(chat_id=message.chat_id, text=f"⚠️ حداکثر {MAX_FILTER_WORDS} کلمه.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            fw_list.append(word)
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"✅ **کلمه فیلتر شد!**\n\n🚫 کلمه: `{word}`\n📊 تعداد: {len(fw_list)}/{MAX_FILTER_WORDS}",
                delete_after=NOTICE_DELETE_AFTER)
            return

        unfilter_match = re.match(r"^حذف\s+فیلتر\s+(.+)$", clean_text)
        if unfilter_match:
            if not is_owner:
                return
            word = unfilter_match.group(1).strip()
            fw_list = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if word in fw_list:
                fw_list.remove(word)
                save_data(bot_data)
                await bot.send_message(chat_id=message.chat_id, text=f"✅ «{word}» حذف شد.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            else:
                await bot.send_message(chat_id=message.chat_id, text=f"⚠️ «{word}» نبود.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        if is_command(clean_text, "لیست فیلتر", "فیلترها"):
            if not can_manage:
                return
            words = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if not words:
                text = "📋 **لیست فیلتر خالی است.**"
            else:
                word_list = "\n".join([f"├ 🚫 {w}" for w in words])
                text = f"📋 **کلمات فیلترشده ({len(words)}/{MAX_FILTER_WORDS}):**\n\n{word_list}"
            await bot.send_message(chat_id=message.chat_id, text=text, reply_to_message_id=message.message_id)
            return

        # ============ سرگرمی‌ها ============
        if is_command(clean_text, "جک", "جوک"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"😂 **جوک امروز:**\n\n{random.choice(JOKES)}\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت")
            return

        if is_command(clean_text, "ضرب المثل", "ضرب‌المثل"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"📜 **ضرب‌المثل:**\n\n{random.choice(PROVERBS)}\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت")
            return

        if is_command(clean_text, "دانستی", "دانستنی", "میدونستی"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"💡 **دانستنی:**\n\n{random.choice(TRIVIA)}\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت")
            return

        if is_command(clean_text, "فکت", "fact"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"🧠 **فکت علمی:**\n\n{random.choice(FACTS)}\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت")
            return

        if is_command(clean_text, "پ ن پ", "پنپ", "پند"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"💚 **پند و اندرز:**\n\n{random.choice(PNP)}\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت")
            return

        if is_command(clean_text, "شعر", "شعر بگو"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"📝 **شعر:**\n\n{random.choice(POEMS)}\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت")
            return

        if is_command(clean_text, "فال", "فال حافظ"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"{random.choice(FAL)}\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت")
            return

        if is_command(clean_text, "شانس", "شانس من"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"{random.choice(LUCK)}\n\n━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت")
            return

        if is_command(clean_text, "لیست سرگرمی", "سرگرمی‌ها", "سرگرمی"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                "🎮 **لیست سرگرمی‌های FluxBot**\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "😂 `جک` یا `جوک` → جوک رندوم\n"
                "📜 `ضرب المثل` → ضرب‌المثل\n"
                "💡 `دانستی` → دانستنی\n"
                "🧠 `فکت` → فکت علمی\n"
                "💚 `پ ن پ` → پند و اندرز\n"
                "📝 `شعر` → شعر رندوم\n"
                "🔮 `فال` → فال حافظ\n"
                "🍀 `شانس` → شانس امروز\n\n"
                "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"))
            return

        # آمار گروه
        if is_command(clean_text, "آمار گروه", "برترین‌ها", "تاپ"):
            today = get_local_now().strftime("%Y-%m-%d")
            counts = bot_data["message_counts"].get(chat_id, {})
            today_counts = [(uid, data["today"]) for uid, data in counts.items() if data.get("date") == today and data.get("today", 0) > 0]
            today_counts.sort(key=lambda x: x[1], reverse=True)
            top10 = today_counts[:10]
            if not top10:
                await bot.send_message(chat_id=message.chat_id, text="📊 **امروز پیامی ارسال نشده.**", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
            lines = []
            for i, (uid, count) in enumerate(top10):
                u_info = await get_user_info(chat_id, uid)
                name = format_user_display(u_info, uid)
                lines.append(f"{medals[i]} {name} — `{count}` پیام")
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=("╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   🏆 برترین‌های امروز 🏆\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                      + "\n".join(lines) + f"\n\n━━━━━━━━━━━━━━━━━━━\n📅 {today}\n⚡ **FLUXBOT** | جریان قدرت"))
            return

        # سکوت
        mute_match = re.match(r"^سکوت\s+(\d+)$", clean_text)
        if mute_match:
            if not can_manage:
                return
            minutes = int(mute_match.group(1))
            if minutes <= 0:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد باید بیشتر از صفر باشد.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            target_user_id = None
            reply_id = extract_reply_id(message)
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]
            if not target_user_id:
                target_user_id = sender_id
            end_time = time.time() + (minutes * 60)
            if chat_id not in mute_list:
                mute_list[chat_id] = {}
            mute_list[chat_id][target_user_id] = end_time
            end_dt = datetime.fromtimestamp(end_time).strftime("%H:%M")
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"🔇 کاربر سکوت شد.\n⏱️ مدت: {minutes} دقیقه\n🕐 پایان: {end_dt}",
                delete_after=NOTICE_DELETE_AFTER)
            return

        # تنظیم اخطار
        warn_set_match = re.match(r"^تنظیم\s+اخطار\s+(\d+)$", clean_text)
        if warn_set_match:
            if not is_owner:
                return
            limit = int(warn_set_match.group(1))
            if limit <= 0 or limit > 500:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد بین 1 تا 500.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            bot_data["warn_limit"][chat_id] = limit
            settings["warning"] = True
            bot_data["settings"] = settings
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, text=f"✅ سیستم اخطار فعال شد (حداکثر: {limit})", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        # اخطار دستی
        if is_command(clean_text, "اخطار"):
            if not is_owner:
                return
            target_user_id = None
            reply_id = extract_reply_id(message)
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]
            if not target_user_id:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            target_info = await get_user_info(chat_id, target_user_id)
            await add_warning(chat_id, target_user_id, "اخطار دستی از طرف مالک", user_info=target_info)
            return

        # ویژه
        if is_command(clean_text, "ویژه", "ادمین", "ویژه کردن", "ادمین کردن"):
            if not is_owner:
                return
            target_user_id = None
            reply_id = extract_reply_id(message)
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]
            if not target_user_id:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            if chat_id not in bot_data["special_users"]:
                bot_data["special_users"][chat_id] = {}
            bot_data["special_users"][chat_id][target_user_id] = True
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, text="⭐ کاربر با موفقیت ویژه شد!", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        if is_command(clean_text, "حذف ویژه", "لغو ویژه", "حذف ادمین"):
            if not is_owner:
                return
            target_user_id = None
            reply_id = extract_reply_id(message)
            if reply_id:
                cache = load_cache()
                if chat_id in cache and reply_id in cache[chat_id]:
                    target_user_id = cache[chat_id][reply_id]
            if target_user_id and chat_id in bot_data["special_users"]:
                if target_user_id in bot_data["special_users"][chat_id]:
                    del bot_data["special_users"][chat_id][target_user_id]
                    save_data(bot_data)
                    await bot.send_message(chat_id=message.chat_id, text="❌ کاربر از لیست ویژه حذف شد.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                    return
            await bot.send_message(chat_id=message.chat_id, text="⚠️ کاربر در لیست ویژه نبود.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        # قفل‌ها
        feature_match = re.match(
            r"^(لینک|آیدی|اسپم|هایپرلینک|خوش‌آمدگویی|خوش‌امدگویی|فحش|فوروارد|هدایت|گیف|خداحافظی)\s+(باز|بسته)$",
            clean_text
        )
        if feature_match:
            if not can_manage:
                return
            feature = feature_match.group(1)
            state = feature_match.group(2)
            feature_key_map = {
                "لینک": "link", "آیدی": "id", "اسپم": "spam",
                "هایپرلینک": "hyperlink", "خوش‌آمدگویی": "welcome",
                "خوش‌امدگویی": "welcome", "فحش": "profanity",
                "فوروارد": "forward", "هدایت": "forward",
                "گیف": "gif", "خداحافظی": "goodbye"
            }
            key = feature_key_map.get(feature)
            if key:
                settings[key] = (state == "بسته")
                bot_data["settings"] = settings
                save_data(bot_data)
                status_text = "بسته" if settings[key] else "باز"
                await bot.send_message(chat_id=message.chat_id, text=f"✅ {feature} {status_text} شد.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        # لیست قفل
        if is_command(clean_text, "لیست قفل"):
            if not can_manage:
                return
            def st(v): return "🔴 بسته" if v else "🟢 باز"
            warn_limit = bot_data["warn_limit"].get(chat_id, 3)
            warn_status = "🔴 فعال" if settings["warning"] else "🟢 غیرفعال"
            filter_count = len(ensure_list_dict(bot_data, "filtered_words", chat_id))
            gl, gl_reason = is_group_locked(chat_id)
            group_lock_status = f"🔴 فعال ({gl_reason})" if gl else "🟢 غیرفعال"
            
            wda = get_warn_delete_after(chat_id)
            if wda > 0:
                mins = wda // 60
                secs = wda % 60
                if mins > 0:
                    wda_str = f"{mins}د {secs}ث" if secs > 0 else f"{mins} دقیقه"
                else:
                    wda_str = f"{wda} ثانیه"
                warn_delete_status = f"🟡 {wda_str}"
            else:
                warn_delete_status = "🟢 غیرفعال"
            
            reply_text = (
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   📋 وضعیت قفل‌ها 📋\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                f"🔗 **لینک:** {st(settings['link'])}\n"
                f"🆔 **آیدی:** {st(settings['id'])}\n"
                f"📢 **اسپم:** {st(settings['spam'])}\n"
                f"🔗 **هایپرلینک:** {st(settings['hyperlink'])}\n"
                f"👋 **خوش‌آمدگویی:** {st(settings['welcome'])}\n"
                f"🤬 **فحش:** {st(settings.get('profanity', True))}\n"
                f"📨 **فوروارد:** {st(settings.get('forward', False))}\n"
                f"🎞️ **گیف:** {st(settings.get('gif', False))}\n"
                f"👋 **خداحافظی:** {st(settings.get('goodbye', False))}\n"
                f"🔒 **قفل گروه:** {group_lock_status}\n"
                f"⚠️ **اخطار:** {warn_status} (حداکثر: {warn_limit})\n"
                f"⏱️ **حذف خودکار اخطار:** {warn_delete_status}\n"
                f"🚫 **کلمات فیلتر:** {filter_count}/{MAX_FILTER_WORDS}\n\n"
                "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # راهنما
        if is_command(clean_text, "راهنما", "help", "دستور", "دستورات"):
            help_text = (
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   📚 راهنمای ربات 📚\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                "👤 **دستورات کاربران:**\n"
                "├ 👑 `مقام`\n"
                "├ 📊 `پروفایل` / `آمار`\n"
                "├ 🏆 `آمار گروه`\n"
                "├ 🐺 `تنظیم اصل [نام]`\n"
                "├ 🎭 `تنظیم لقب [نام]`\n"
                "├ 😂 `جک` / 📜 `ضرب المثل`\n"
                "├ 💡 `دانستی` / 🧠 `فکت`\n"
                "├ 💚 `پ ن پ` / 📝 `شعر`\n"
                "├ 🔮 `فال` / 🍀 `شانس`\n"
                "└ 📚 `راهنما`\n\n"
                "👑 **دستورات مالک / ویژه:**\n"
                "├ ✅ `فعال` / 🛑 `غیرفعال`\n"
                "├ 🚫 `بن` / ✅ `انبن` (ریپلای)\n"
                "├ 🔇 `سکوت [عدد]`\n"
                "├ ⚠️ `اخطار` / ⚙️ `تنظیم اخطار [عدد]`\n"
                "├ ⏱️ `حذف پیام اخطار [عدد]`\n"
                "├ ⭐ `ویژه` / ❌ `حذف ویژه`\n"
                "├ 🚫 `فیلتر [کلمه]` / ❌ `حذف فیلتر [کلمه]`\n"
                "└ 📋 `لیست فیلتر`\n\n"
                "🔒 **قفل گروه:**\n"
                "├ 🔒 `قفل گروه`\n"
                "├ ⏱️ `قفل [عدد]` (ساعت)\n"
                "├ ⏰ `قفل 13:00 14:00`\n"
                "├ 🔓 `باز`\n"
                "└ 📋 `لیست قفل گروه`\n\n"
                "⚙️ **قفل‌ها (باز/بسته):**\n"
                "├ 🔗 `لینک` / 🆔 `آیدی`\n"
                "├ 📢 `اسپم` / 🔗 `هایپرلینک`\n"
                "├ 🤬 `فحش` / 📨 `فوروارد`\n"
                "├ 🎞️ `گیف` / 👋 `خداحافظی`\n"
                "└ 📋 `لیست قفل`\n\n"
                "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=message.chat_id, text=help_text, reply_to_message_id=message.message_id)
            return

        # تنظیم اصل
        asl_match = re.match(r"^تنظیم\s+اصل\s+(.+)$", clean_text)
        if asl_match:
            asl_value = asl_match.group(1).strip()
            if not asl_value:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ مقدار اصل را وارد کنید.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            taken_list = ensure_list_dict(bot_data, "taken_asl", chat_id)
            current_asl = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("asl")
            if asl_value in taken_list and asl_value != current_asl:
                await bot.send_message(chat_id=message.chat_id, text=f"❌ اصل «{asl_value}» تکراری است.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            if chat_id not in bot_data["user_titles"]:
                bot_data["user_titles"][chat_id] = {}
            if sender_id not in bot_data["user_titles"][chat_id]:
                bot_data["user_titles"][chat_id][sender_id] = {}
            old_asl = bot_data["user_titles"][chat_id][sender_id].get("asl")
            if old_asl and old_asl in taken_list:
                taken_list.remove(old_asl)
            bot_data["user_titles"][chat_id][sender_id]["asl"] = asl_value
            if asl_value not in taken_list:
                taken_list.append(asl_value)
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, text=f"✅ اصل ثبت شد:\n🐺 `{asl_value}`", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        # تنظیم لقب
        laghab_match = re.match(r"^تنظیم\s+لقب\s+(.+)$", clean_text)
        if laghab_match:
            laghab_value = laghab_match.group(1).strip()
            if not laghab_value:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ مقدار لقب را وارد کنید.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            taken_list = ensure_list_dict(bot_data, "taken_laghab", chat_id)
            current_laghab = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("laghab")
            if laghab_value in taken_list and laghab_value != current_laghab:
                await bot.send_message(chat_id=message.chat_id, text=f"❌ لقب «{laghab_value}» تکراری است.", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
                return
            if chat_id not in bot_data["user_titles"]:
                bot_data["user_titles"][chat_id] = {}
            if sender_id not in bot_data["user_titles"][chat_id]:
                bot_data["user_titles"][chat_id][sender_id] = {}
            old_laghab = bot_data["user_titles"][chat_id][sender_id].get("laghab")
            if old_laghab and old_laghab in taken_list:
                taken_list.remove(old_laghab)
            bot_data["user_titles"][chat_id][sender_id]["laghab"] = laghab_value
            if laghab_value not in taken_list:
                taken_list.append(laghab_value)
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, text=f"✅ لقب ثبت شد:\n🎭 `{laghab_value}`", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        # پروفایل / آمار
        if is_command(clean_text, "پروفایل", "آمار", "امار", "آمارم", "امارم", "profile"):
            user_titles = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {})
            asl = user_titles.get("asl", "ثبت نشده")
            laghab = user_titles.get("laghab", "ثبت نشده")
            today = get_local_now().strftime("%Y-%m-%d")
            counts = bot_data["message_counts"].get(chat_id, {}).get(sender_id, {})
            today_count = counts.get("today", 0) if counts.get("date") == today else 0
            if chat_id not in bot_data["join_dates"]:
                bot_data["join_dates"][chat_id] = {}
            if sender_id not in bot_data["join_dates"][chat_id]:
                bot_data["join_dates"][chat_id][sender_id] = get_now_time()
                save_data(bot_data)
            join_date = bot_data["join_dates"][chat_id][sender_id]
            special_status = "⭐ ویژه" if is_special else "عادی"
            warn_count = bot_data["warnings"].get(chat_id, {}).get(sender_id, 0)
            warn_limit = bot_data["warn_limit"].get(chat_id, 3)
            reply_text = (
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   📊 پروفایل کاربر 📊\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                f"👤 **کاربر:** {display_name}\n\n"
                "┌──── مشخصات ────┐\n"
                f"│ 🐺 اصل: `{asl}`\n"
                f"│ 🎭 لقب: `{laghab}`\n"
                f"│ 👑 مقام: {role}\n"
                f"│ ⭐ وضعیت: {special_status}\n"
                f"│ ⚠️ اخطار: [{warn_count}/{warn_limit}]\n"
                f"│ 📅 پیوست: {join_date}\n"
                f"│ 💬 پیام امروز: {today_count}\n"
                "└────────────────────┘\n\n"
                "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # مقام
        if is_command(clean_text, "مقام"):
            await bot.send_message(chat_id=message.chat_id, text=f"👤 **مقام شما:** {role}", reply_to_message_id=message.message_id, delete_after=NOTICE_DELETE_AFTER)
            return

        # ============ بررسی خودکار ============
        if not bot_is_active:
            return
        if can_manage:
            return

        # 1. فحش
        if settings.get("profanity", True):
            bad_word = contains_profanity(raw_text)
            if bad_word:
                print(f"🤬 PROFANITY: {bad_word}", flush=True)
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]:
                        await add_warning(chat_id, sender_id, "استفاده از فحش", user_info=user_info)
                except Exception as e:
                    print(f"❌ DELETE: {e}", flush=True)
                return

        # 2. فیلتر کلمات
        if settings["filter"]:
            filtered_list = ensure_list_dict(bot_data, "filtered_words", chat_id)
            matched = contains_filtered_word(raw_text, filtered_list)
            if matched:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]:
                        await add_warning(chat_id, sender_id, "کلمه فیلترشده", user_info=user_info)
                except Exception as e:
                    print(f"❌ DELETE: {e}", flush=True)
                return

        # 3. اسپم
        if settings["spam"]:
            if chat_id not in spam_tracker:
                spam_tracker[chat_id] = {}
            if sender_id not in spam_tracker[chat_id]:
                spam_tracker[chat_id][sender_id] = []
            spam_tracker[chat_id][sender_id] = [t for t in spam_tracker[chat_id][sender_id] if ct - t < 5]
            spam_tracker[chat_id][sender_id].append(ct)
            if len(spam_tracker[chat_id][sender_id]) >= 5:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]:
                        await add_warning(chat_id, sender_id, "ارسال اسپم", user_info=user_info)
                except Exception as e:
                    print(f"❌ DELETE: {e}", flush=True)
                return

        # 4. لینک
        if settings["link"] and contains_link(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال لینک", user_info=user_info)
            except Exception as e:
                print(f"❌ DELETE: {e}", flush=True)
            return

        # 5. هایپرلینک
        if settings["hyperlink"] and contains_hyperlink(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال هایپرلینک", user_info=user_info)
            except Exception as e:
                print(f"❌ DELETE: {e}", flush=True)
            return

        # 6. آیدی
        if settings["id"] and contains_id(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال آیدی", user_info=user_info)
            except Exception as e:
                print(f"❌ DELETE: {e}", flush=True)
            return

        # 7. فوروارد
        if settings.get("forward", False) and is_forwarded(message):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال پیام فوروارد", user_info=user_info)
            except Exception as e:
                print(f"❌ DELETE: {e}", flush=True)
            return

        # 8. گیف
        if settings.get("gif", False) and is_gif(message):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال گیف", user_info=user_info)
            except Exception as e:
                print(f"❌ DELETE: {e}", flush=True)
            return

    except Exception as e:
        print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)


async def main():
    print("🤖 FLUXBOT STARTING...", flush=True)
    print(f"💾 DATA PATHS: {DATA_PATHS}", flush=True)
    print(f"💾 CACHE PATHS: {CACHE_PATHS}", flush=True)
    print(f"🌍 TIMEZONE: Iran (UTC+3:30)", flush=True)
    print(f"⏱️ NOTICE DELETE: {NOTICE_DELETE_AFTER}s", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
