import os
import re
import json
import time
import asyncio
import random
from datetime import datetime
from rubka import Robot, Message
from rubka.keypad import ChatKeypadBuilder

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

DATA_PATHS = ["/app/bot_data.json", "/app/data/bot_data.json", "/tmp/bot_data.json", "./bot_data.json"]
CACHE_PATHS = ["/app/message_cache.json", "/app/data/message_cache.json", "/tmp/message_cache.json", "./message_cache.json"]

BTN_CHANNEL_TEXT = "📢 کانال رسمی"
BTN_HELP_TEXT = "📚 آموزش فعال‌سازی"
BTN_USERS_TEXT = "👥 کاربران"
BTN_GROUPS_TEXT = "🏠 گروه‌های فعال"
MAX_FILTER_WORDS = 50

username_cache = {}


# ================== تابع کمکی حیاتی (رفع باگ) ==================
def ensure_list(value):
    """اطمینان از اینکه مقدار یک لیست است. اگه دیکشنری بود، به لیست تبدیل می‌کند."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.keys()) if value else []
    if isinstance(value, str):
        return [value] if value else []
    return []


def ensure_list_dict(d, key, sub_key=None):
    """اطمینان از لیست بودن دیکشنری داخلی"""
    if key not in d:
        d[key] = []
        return d[key]
    if sub_key is not None:
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
    return datetime.now().strftime("%H:%M - %Y/%m/%d")


def extract_reply_id(message):
    for attr in ['reply_to_message_id', 'reply_to', 'reply_message_id']:
        if hasattr(message, attr):
            val = getattr(message, attr)
            if val:
                if hasattr(val, 'message_id'):
                    return str(val.message_id)
                return str(val)
    return None


async def get_user_info(chat_id, user_id):
    cache_key = f"{chat_id}:{user_id}"
    if cache_key in username_cache and username_cache[cache_key].get("username"):
        return username_cache[cache_key]
    info = {"name": None, "username": None, "role": "عضو"}
    try:
        member_info = await bot.get_chat_member(chat_id, user_id)
        if member_info:
            data = member_info.get("data", member_info) if isinstance(member_info, dict) else member_info
            chat_member = data.get("chat_member", data) if isinstance(data, dict) else {}
            info["name"] = chat_member.get("first_name") or chat_member.get("name") or chat_member.get("title")
            uname = chat_member.get("username") or chat_member.get("user_name") or chat_member.get("user_username")
            if uname:
                info["username"] = str(uname).lstrip("@")
            status = str(chat_member.get("status", "")).strip().lower()
            if status in ("creator", "owner"):
                info["role"] = "مالک"
            elif status in ("admin", "administrator"):
                info["role"] = "ادمین"
            username_cache[cache_key] = info
    except Exception as e:
        print(f"⚠️ USER INFO ERROR: {e}", flush=True)
    return info


def format_user_display(user_info, user_id):
    if user_info.get("username"):
        return f"@{user_info['username']}"
    elif user_info.get("name"):
        return user_info["name"]
    return "کاربر"


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
        "warn_limit": {}, "started_users": [], "known_groups": [],
        "group_message_count": {}, "promo_sent": {}, "filtered_words": {},
        "banned_users": {},
        "settings": {"link": False, "id": False, "spam": False, "hyperlink": False,
                     "welcome": True, "warning": False, "filter": True, "auto_ban": True,
                     "profanity": True},
    }
    for path in DATA_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # اطمینان از لیست بودن فیلدهای حیاتی
                    for list_key in ["started_users", "known_groups"]:
                        if list_key in loaded:
                            loaded[list_key] = ensure_list(loaded[list_key])
                    for k, v in default_data.items():
                        if k not in loaded:
                            loaded[k] = v
                    if "settings" in loaded and "profanity" not in loaded["settings"]:
                        loaded["settings"]["profanity"] = True
                    return loaded
        except Exception as e:
            print(f"⚠️ LOAD DATA {path}: {e}", flush=True)
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
settings = bot_data.get("settings", {"link": False, "id": False, "spam": False, "hyperlink": False, "welcome": True, "warning": False, "filter": True, "auto_ban": True, "profanity": True})
if "profanity" not in settings:
    settings["profanity"] = True
message_cache = load_cache()
spam_tracker = {}


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
    minutes = int(diff // 60)
    seconds = int(diff % 60)
    if minutes > 0:
        return f"{minutes} دقیقه و {seconds} ثانیه"
    return f"{seconds} ثانیه"


# ================== اخطار ==================
async def add_warning(chat_id, user_id, reason=""):
    try:
        if chat_id not in bot_data["warnings"]:
            bot_data["warnings"][chat_id] = {}
        if user_id not in bot_data["warnings"][chat_id]:
            bot_data["warnings"][chat_id][user_id] = 0
        bot_data["warnings"][chat_id][user_id] += 1
        count = bot_data["warnings"][chat_id][user_id]
        limit = bot_data["warn_limit"].get(chat_id, 3)
        save_data(bot_data)

        user_info = await get_user_info(chat_id, user_id)
        display = format_user_display(user_info, user_id)

        warn_text = (
            f"⚠️ **اخطار!** ⚠️\n\n"
            f"👤 **کاربر:** {display}\n"
            f"📌 **دلیل:** {reason if reason else 'تخلف از قوانین'}\n"
            f"📊 **اخطار فعلی:** [{count}/{limit}]\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ **FLUXBOT** | جریان قدرت"
        )
        try:
            await bot.send_message(chat_id=chat_id, text=warn_text)
        except Exception as e:
            print(f"⚠️ WARN SEND: {e}", flush=True)

        if count >= limit and settings.get("auto_ban", True):
            try:
                await bot.ban_member_chat(chat_id, user_id)
                if chat_id not in bot_data["banned_users"]:
                    bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][user_id] = time.time()
                save_data(bot_data)
                await bot.send_message(chat_id=chat_id,
                    text=f"🚫 **کاربر اخراج شد!**\n\n👤 {display}\n📊 تعداد اخطار: [{count}/{limit}]")
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
        # اطمینان حیاتی از لیست بودن
        if not isinstance(bot_data.get("started_users"), list):
            bot_data["started_users"] = ensure_list(bot_data.get("started_users"))
        if user_id not in bot_data["started_users"]:
            bot_data["started_users"].append(user_id)
            save_data(bot_data)
    except Exception as e:
        print(f"⚠️ REGISTER USER ERROR: {e}", flush=True)


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
        print(f"⚠️ REGISTER GROUP ERROR: {e}", flush=True)


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
        if ct - handle_message.last_cleanup > 30:
            handle_message.processed = {k: v for k, v in handle_message.processed.items() if ct - v < 30}
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

        # شمارنده 200 پیام
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

        # بررسی سکوت
        now = time.time()
        chat_mutes = mute_list.get(chat_id, {})
        if sender_id in chat_mutes:
            end_time = chat_mutes[sender_id]
            if now < end_time:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                except Exception as e:
                    print(f"❌ DELETE MUTED: {e}", flush=True)
                u_info = await get_user_info(chat_id, sender_id)
                u_display = format_user_display(u_info, sender_id)
                remaining = get_remaining_time(end_time)
                end_dt = datetime.fromtimestamp(end_time).strftime("%H:%M")
                try:
                    await bot.send_message(chat_id=chat_id, text=(
                        f"🔇 **کاربر گرامی {u_display}**\n\n"
                        f"شما در لیست سکوت قرار دارید و تا این لحظه نمی‌توانید پیام ارسال کنید.\n\n"
                        f"⏳ **زمان باقی‌مانده:** `{remaining}`\n"
                        f"🕐 **پایان سکوت:** `{end_dt}`\n\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"⚡ **FLUXBOT** | جریان قدرت"))
                except:
                    pass
                return
            else:
                del chat_mutes[sender_id]

        user_info = await get_user_info(chat_id, sender_id)
        role = user_info["role"]
        display_name = format_user_display(user_info, sender_id)
        is_owner = (role == "مالک")
        is_special = bot_data.get("special_users", {}).get(chat_id, {}).get(sender_id, False)
        can_manage = is_owner or is_special

        # خوش‌آمدگویی
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

        # آمار پیام
        today = datetime.now().strftime("%Y-%m-%d")
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
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "غیرفعال", "غيرفعال"):
            if not is_owner:
                return
            reply_text = "⛔ ربات از قبل غیرفعال است." if not bot_is_active else "🛑 ربات غیرفعال شد."
            bot_is_active = False
            await bot.send_message(chat_id=message.chat_id, text=reply_text, reply_to_message_id=message.message_id)
            return

        # --- بن ---
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
                await bot.send_message(chat_id=message.chat_id, text="⚠️ لطفاً روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            try:
                t_info = await get_user_info(chat_id, target_user_id)
                t_display = format_user_display(t_info, target_user_id)
                await bot.ban_member_chat(chat_id, target_user_id)
                if chat_id not in bot_data["banned_users"]:
                    bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][target_user_id] = time.time()
                save_data(bot_data)
                await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                    f"🚫 **کاربر اخراج شد!** 🚫\n\n👤 **کاربر:** {t_display}\n📌 **دلیل:** تخلف از قوانین\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"))
            except Exception as e:
                print(f"❌ BAN ERROR: {e}", flush=True)
            return

        # --- انبن ---
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
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            try:
                t_info = await get_user_info(chat_id, target_user_id)
                t_display = format_user_display(t_info, target_user_id)
                await bot.unban_member_chat(chat_id, target_user_id)
                if chat_id in bot_data["banned_users"] and target_user_id in bot_data["banned_users"][chat_id]:
                    del bot_data["banned_users"][chat_id][target_user_id]
                    save_data(bot_data)
                await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                    f"✅ **کاربر آنبن شد!** ✅\n\n👤 **کاربر:** {t_display}\n🌟 از لیست سیاه حذف شد.\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"))
            except Exception as e:
                print(f"❌ UNBAN ERROR: {e}", flush=True)
            return

        # --- فیلتر ---
        filter_match = re.match(r"^فیلتر\s+(.+)$", clean_text)
        if filter_match:
            if not is_owner:
                return
            word = filter_match.group(1).strip()
            if not word:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ یک کلمه وارد کنید.", reply_to_message_id=message.message_id)
                return
            # اطمینان از لیست بودن
            fw_list = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if word in fw_list:
                await bot.send_message(chat_id=message.chat_id, text=f"⚠️ کلمه «{word}» از قبل فیلتر شده.", reply_to_message_id=message.message_id)
                return
            if len(fw_list) >= MAX_FILTER_WORDS:
                await bot.send_message(chat_id=message.chat_id, text=f"⚠️ حداکثر {MAX_FILTER_WORDS} کلمه.", reply_to_message_id=message.message_id)
                return
            fw_list.append(word)
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id,
                text=f"✅ **کلمه فیلتر شد!**\n\n🚫 کلمه: `{word}`\n📊 تعداد: {len(fw_list)}/{MAX_FILTER_WORDS}")
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
                await bot.send_message(chat_id=message.chat_id, text=f"✅ کلمه «{word}» حذف شد.", reply_to_message_id=message.message_id)
            else:
                await bot.send_message(chat_id=message.chat_id, text=f"⚠️ کلمه «{word}» نبود.", reply_to_message_id=message.message_id)
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
            text = (
                "🎮 **لیست سرگرمی‌های FluxBot**\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "😂 `جک` یا `جوک` → جوک رندوم\n"
                "📜 `ضرب المثل` → ضرب‌المثل رندوم\n"
                "💡 `دانستی` → دانستنی رندوم\n"
                "🧠 `فکت` → فکت علمی رندوم\n"
                "💚 `پ ن پ` → پند و اندرز رندوم\n"
                "📝 `شعر` → شعر رندوم\n"
                "🔮 `فال` → فال حافظ\n"
                "🍀 `شانس` → شانس امروز\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **FLUXBOT** | جریان قدرت"
            )
            await bot.send_message(chat_id=message.chat_id, text=text, reply_to_message_id=message.message_id)
            return

        # آمار گروه
        if is_command(clean_text, "آمار گروه", "برترین‌ها", "تاپ"):
            today = datetime.now().strftime("%Y-%m-%d")
            counts = bot_data["message_counts"].get(chat_id, {})
            today_counts = [(uid, data["today"]) for uid, data in counts.items() if data.get("date") == today and data.get("today", 0) > 0]
            today_counts.sort(key=lambda x: x[1], reverse=True)
            top10 = today_counts[:10]
            if not top10:
                await bot.send_message(chat_id=message.chat_id, text="📊 **امروز پیامی ارسال نشده.**", reply_to_message_id=message.message_id)
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
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد باید بیشتر از صفر باشد.", reply_to_message_id=message.message_id)
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
                text=f"🔇 کاربر سکوت شد.\n⏱️ مدت: {minutes} دقیقه\n🕐 پایان: {end_dt}")
            return

        # تنظیم اخطار
        warn_set_match = re.match(r"^تنظیم\s+اخطار\s+(\d+)$", clean_text)
        if warn_set_match:
            if not is_owner:
                return
            limit = int(warn_set_match.group(1))
            if limit <= 0 or limit > 500:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد بین 1 تا 500.", reply_to_message_id=message.message_id)
                return
            bot_data["warn_limit"][chat_id] = limit
            settings["warning"] = True
            bot_data["settings"] = settings
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, text=f"✅ سیستم اخطار فعال شد (حداکثر: {limit})", reply_to_message_id=message.message_id)
            return

        # اخطار
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
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            await add_warning(chat_id, target_user_id, "اخطار دستی از طرف مالک")
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
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام کاربر ریپلای کنید.", reply_to_message_id=message.message_id)
                return
            if chat_id not in bot_data["special_users"]:
                bot_data["special_users"][chat_id] = {}
            bot_data["special_users"][chat_id][target_user_id] = True
            save_data(bot_data)
            await bot.send_message(chat_id=message.chat_id, text="⭐ کاربر با موفقیت ویژه شد!", reply_to_message_id=message.message_id)
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
                    await bot.send_message(chat_id=message.chat_id, text="❌ کاربر از لیست ویژه حذف شد.", reply_to_message_id=message.message_id)
                    return
            await bot.send_message(chat_id=message.chat_id, text="⚠️ کاربر در لیست ویژه نبود.", reply_to_message_id=message.message_id)
            return

        # قفل‌ها
        feature_match = re.match(r"^(لینک|آیدی|اسپم|هایپرلینک|خوش‌آمدگویی|خوش‌امدگویی|فحش)\s+(باز|بسته)$", clean_text)
        if feature_match:
            if not can_manage:
                return
            feature = feature_match.group(1)
            state = feature_match.group(2)
            feature_key_map = {
                "لینک": "link", "آیدی": "id", "اسپم": "spam",
                "هایپرلینک": "hyperlink", "خوش‌آمدگویی": "welcome",
                "خوش‌امدگویی": "welcome", "فحش": "profanity"
            }
            key = feature_key_map.get(feature)
            if key:
                settings[key] = (state == "بسته")
                bot_data["settings"] = settings
                save_data(bot_data)
                status_text = "بسته" if settings[key] else "باز"
                await bot.send_message(chat_id=message.chat_id, text=f"✅ {feature} {status_text} شد.", reply_to_message_id=message.message_id)
            return

        # لیست قفل
        if is_command(clean_text, "لیست قفل"):
            if not can_manage:
                return
            def st(v): return "🔴 بسته" if v else "🟢 باز"
            warn_limit = bot_data["warn_limit"].get(chat_id, 3)
            warn_status = "🔴 فعال" if settings["warning"] else "🟢 غیرفعال"
            filter_count = len(ensure_list_dict(bot_data, "filtered_words", chat_id))
            reply_text = (
                "╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   📋 وضعیت قفل‌ها 📋\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                f"🔗 **لینک:** {st(settings['link'])}\n"
                f"🆔 **آیدی:** {st(settings['id'])}\n"
                f"📢 **اسپم:** {st(settings['spam'])}\n"
                f"🔗 **هایپرلینک:** {st(settings['hyperlink'])}\n"
                f"👋 **خوش‌آمدگویی:** {st(settings['welcome'])}\n"
                f"🤬 **فحش:** {st(settings.get('profanity', True))}\n"
                f"⚠️ **اخطار:** {warn_status} (حداکثر: {warn_limit})\n"
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
                "├ 📊 `پروفایل`\n"
                "├ 🏆 `آمار گروه`\n"
                "├ 🐺 `تنظیم اصل [نام]`\n"
                "├ 🎭 `تنظیم لقب [نام]`\n"
                "├ 😂 `جک` / `جوک`\n"
                "├ 📜 `ضرب المثل`\n"
                "├ 💡 `دانستی`\n"
                "├ 🧠 `فکت`\n"
                "├ 💚 `پ ن پ`\n"
                "├ 📝 `شعر`\n"
                "├ 🔮 `فال`\n"
                "├ 🍀 `شانس`\n"
                "├ 🎮 `لیست سرگرمی`\n"
                "└ 📚 `راهنما`\n\n"
                "👑 **دستورات مالک / ویژه:**\n"
                "├ ✅ `فعال` / 🛑 `غیرفعال`\n"
                "├ 🚫 `بن` / `سیک` / `اخراج`\n"
                "├ ✅ `انبن`\n"
                "├ 🔇 `سکوت [عدد]`\n"
                "├ ⚠️ `اخطار`\n"
                "├ ⚙️ `تنظیم اخطار [عدد]`\n"
                "├ ⭐ `ویژه` / ❌ `حذف ویژه`\n"
                "├ 🚫 `فیلتر [کلمه]`\n"
                "├ ❌ `حذف فیلتر [کلمه]`\n"
                "├ 📋 `لیست فیلتر`\n"
                "├ 🔗 `لینک باز/بسته`\n"
                "├ 🆔 `آیدی باز/بسته`\n"
                "├ 📢 `اسپم باز/بسته`\n"
                "├ 🔗 `هایپرلینک باز/بسته`\n"
                "├ 🤬 `فحش باز/بسته`\n"
                "├ 👋 `خوش‌آمدگویی باز/بسته`\n"
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
                await bot.send_message(chat_id=message.chat_id, text="⚠️ مقدار اصل را وارد کنید.", reply_to_message_id=message.message_id)
                return
            taken_list = ensure_list_dict(bot_data, "taken_asl", chat_id)
            current_asl = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("asl")
            if asl_value in taken_list and asl_value != current_asl:
                await bot.send_message(chat_id=message.chat_id, text=f"❌ اصل «{asl_value}» تکراری است.", reply_to_message_id=message.message_id)
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
            await bot.send_message(chat_id=message.chat_id, text=f"✅ اصل ثبت شد:\n🐺 `{asl_value}`", reply_to_message_id=message.message_id)
            return

        # تنظیم لقب
        laghab_match = re.match(r"^تنظیم\s+لقب\s+(.+)$", clean_text)
        if laghab_match:
            laghab_value = laghab_match.group(1).strip()
            if not laghab_value:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ مقدار لقب را وارد کنید.", reply_to_message_id=message.message_id)
                return
            taken_list = ensure_list_dict(bot_data, "taken_laghab", chat_id)
            current_laghab = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("laghab")
            if laghab_value in taken_list and laghab_value != current_laghab:
                await bot.send_message(chat_id=message.chat_id, text=f"❌ لقب «{laghab_value}» تکراری است.", reply_to_message_id=message.message_id)
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
            await bot.send_message(chat_id=message.chat_id, text=f"✅ لقب ثبت شد:\n🎭 `{laghab_value}`", reply_to_message_id=message.message_id)
            return

        # پروفایل
        if is_command(clean_text, "پروفایل", "آمارم", "امارم", "profile"):
            user_titles = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {})
            asl = user_titles.get("asl", "ثبت نشده")
            laghab = user_titles.get("laghab", "ثبت نشده")
            today = datetime.now().strftime("%Y-%m-%d")
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
            await bot.send_message(chat_id=message.chat_id, text=f"👤 **مقام شما:** {role}", reply_to_message_id=message.message_id)
            return

        # ============ بررسی خودکار ============
        if not bot_is_active:
            return
        if can_manage:
            return

        # فحش
        if settings.get("profanity", True):
            bad_word = contains_profanity(raw_text)
            if bad_word:
                print(f"🤬 PROFANITY: {bad_word}", flush=True)
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]:
                        await add_warning(chat_id, sender_id, f"استفاده از فحش")
                except Exception as e:
                    print(f"❌ DELETE: {e}", flush=True)
                return

        # فیلتر
        if settings["filter"]:
            filtered_list = ensure_list_dict(bot_data, "filtered_words", chat_id)
            matched = contains_filtered_word(raw_text, filtered_list)
            if matched:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]:
                        await add_warning(chat_id, sender_id, f"کلمه فیلترشده")
                except Exception as e:
                    print(f"❌ DELETE: {e}", flush=True)
                return

        # اسپم
        if settings["spam"]:
            now = time.time()
            if chat_id not in spam_tracker:
                spam_tracker[chat_id] = {}
            if sender_id not in spam_tracker[chat_id]:
                spam_tracker[chat_id][sender_id] = []
            spam_tracker[chat_id][sender_id] = [t for t in spam_tracker[chat_id][sender_id] if now - t < 5]
            spam_tracker[chat_id][sender_id].append(now)
            if len(spam_tracker[chat_id][sender_id]) >= 5:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]:
                        await add_warning(chat_id, sender_id, "ارسال اسپم")
                except Exception as e:
                    print(f"❌ DELETE: {e}", flush=True)
                return

        # لینک
        if settings["link"] and contains_link(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال لینک")
            except Exception as e:
                print(f"❌ DELETE: {e}", flush=True)
            return

        # هایپرلینک
        if settings["hyperlink"] and contains_hyperlink(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال هایپرلینک")
            except Exception as e:
                print(f"❌ DELETE: {e}", flush=True)
            return

        # آیدی
        if settings["id"] and contains_id(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]:
                    await add_warning(chat_id, sender_id, "ارسال آیدی")
            except Exception as e:
                print(f"❌ DELETE: {e}", flush=True)
            return

    except Exception as e:
        print(f"❌ HANDLER ERROR: {type(e).__name__}: {e}", flush=True)


async def main():
    print("🤖 FLUXBOT STARTING...", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
