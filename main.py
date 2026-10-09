import os
import re
import json
import time
import asyncio
import random
from datetime import datetime, timedelta, timezone
from rubka import Robot, Message
from rubka.keypad import ChatKeypadBuilder

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("❌ RUBIKA_TOKEN تنظیم نشده است.")

bot = Robot(token=TOKEN)

# ================== تایم‌زون ایران ==================
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))
def get_local_now():
    return datetime.now(IRAN_TZ)

# ================== مسیرها ==================
DATA_PATHS = ["/data/bot_data.json", "/app/data/bot_data.json", "/app/bot_data.json", "/tmp/bot_data.json", "./bot_data.json"]
CACHE_PATHS = ["/data/message_cache.json", "/app/data/message_cache.json", "/app/message_cache.json", "/tmp/message_cache.json", "./message_cache.json"]

for _p in ["/data", "/app/data", "/tmp"]:
    try: os.makedirs(_p, exist_ok=True)
    except: pass

BTN_CHANNEL = "📢 کانال رسمی"
BTN_HELP = "📚 آموزش فعال‌سازی"
BTN_USERS = "👥 کاربران"
BTN_GROUPS = "🏠 گروه‌های فعال"
MAX_FILTER_WORDS = 50

CHANNEL_USERNAME = "@RPCITY_PHANTOM"
PROMO_INTERVAL = 2 * 60 * 60  # 2 ساعت

# ================== کش‌ها ==================
username_cache = {}
mute_list = {}
spam_tracker = {}
group_locks = {}
temp_locks = {}
scheduled_locks = {}
processed_messages = {}
save_counter = {"data": 0, "cache": 0}


# ================== توابع کمکی ==================
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
            print(f"🗑️ DEL msg={message_id} in {delay_seconds}s", flush=True)
        except Exception as e:
            print(f"⚠️ DEL FAIL: {e}", flush=True)
    try: asyncio.create_task(_del())
    except: pass


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
    except: pass
    return None


# ================== لیست فحش‌ها ==================
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
    "خارکسه","خوارکسده","گوزو","گوزیدن","عنین","پدرسگ","مادرجنده","کیرخوری",
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
]

FACTS = [
    "🧠 مغز انسان ۲٪ وزن بدن را دارد اما ۲۰٪ انرژی مصرف می‌کند!",
    "🦷 مینای دندان سخت‌ترین ماده در بدن انسان است.",
    "👁️ چشم انسان می‌تواند حدود ۱۰ میلیون رنگ را تشخیص دهد.",
    "💤 انسان در طول عمرش حدود ۲۵ سال می‌خوابد!",
    "🫀 قلب انسان روزانه حدود ۱۰۰ هزار بار می‌تپد.",
    "🩸 رگ‌های خونی بدن اگر باز شوند، حدود ۱۰۰ هزار کیلومتر طول دارند!",
]

PNP = [
    "پند: با دلِ خودت روراست باش، حتی اگر به ضررت باشه. 💚",
    "پند: هرگز قضاوت نکن تا خودت در اون موقعیت قرار نگیری. ⚖️",
    "پند: کسی که از تو تعریف می‌کنه، ممکنه پشت سرت بد بگه. 🤐",
    "پند: موفقیت یعنی بلند شدن بعد از هر زمین خوردن. 💪",
    "پند: به کسی که بهت دروغ می‌گه، فرصت دوم نده. 🚫",
]

POEMS = [
    "دوش دیدم که ملائک در میخانه زدند / گل آدم بسرشتند و به پیمانه زدند. 🍷",
    "بنی آدم اعضای یک پیکرند / که در آفرینش ز یک گوهرند. 🤝",
    "توانا بود هر که دانا بود / ز دانش دل پیر برنا بود. 📚",
    "هر که را جامه ز عشقی چاک شد / او ز حرص و عیب کلی پاک شد. ❤️",
]

FAL = [
    "🔮 **فال امروز:** روز خوبی در انتظارته! 🍀",
    "🔮 **فال امروز:** مراقب باش، یه نفر داره پشت سرت حرف می‌زنه. 🤫",
    "🔮 **فال امروز:** پول به دستت می‌رسه، ولی خرجش نکن! 💰",
    "🔮 **فال امروز:** یه سفر کوتاه در پیش داری. ✈️",
    "🔮 **فال امروز:** دل به کسی نبند که لیاقتت رو نداره. 💔",
]

LUCK = [
    "🍀 **شانس امروز:** ۱۰ از ۱۰! فوق‌العاده‌ست!",
    "🍀 **شانس امروز:** ۹ از ۱۰! عالیه!",
    "🍀 **شانس امروز:** ۸ از ۱۰! خوبه!",
    "🍀 **شانس امروز:** ۷ از ۱۰! معمولیه.",
    "🍀 **شانس امروز:** ۵ از ۱۰! یه ذره ضعیفه.",
    "🍀 **شانس امروز:** ۳ از ۱۰! امروز احتیاط کن!",
]


# ================== توابع عمومی ==================
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


def extract_reply_id(message):
    for attr in ['reply_to_message_id', 'reply_to', 'reply_message_id']:
        try:
            val = getattr(message, attr, None)
            if val:
                if hasattr(val, 'message_id'): return str(val.message_id)
                return str(val)
        except: pass
    return None


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
        msg_type = str(getattr(message, 'type', '') or getattr(message, 'message_type', '')).lower()
        return 'gif' in msg_type or 'animation' in msg_type
    except: return False


async def get_user_info(chat_id, user_id):
    key = f"{chat_id}:{user_id}"
    cached = username_cache.get(key)
    if cached and (cached.get("username") or cached.get("name")):
        return cached

    info = {"name": None, "username": None, "role": "عضو"}
    try:
        member_info = await bot.get_chat_member(chat_id, user_id)
        if member_info:
            data = member_info.get("data", member_info) if isinstance(member_info, dict) else member_info
            cm = data.get("chat_member", data) if isinstance(data, dict) else {}
            info["name"] = (cm.get("first_name") or cm.get("name") or cm.get("title") or
                           cm.get("display_name") or cm.get("full_name"))
            uname = cm.get("username") or cm.get("user_name") or cm.get("user_username")
            if uname: info["username"] = str(uname).lstrip("@")
            status = str(cm.get("status", "")).strip().lower()
            if status in ("creator", "owner"): info["role"] = "مالک"
            elif status in ("admin", "administrator"): info["role"] = "ادمین"
            else:
                access = cm.get("access_list", [])
                if isinstance(access, list) and access:
                    if "BanMember" in access or "DeleteGlobalAllMessages" in access:
                        info["role"] = "ادمین"
            username_cache[key] = info
    except Exception as e:
        print(f"⚠️ USER: {e}", flush=True)
    return info


def format_user_display(ui, uid):
    if ui.get("username"): return f"@{ui['username']}"
    if ui.get("name"): return ui["name"]
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
    except: return "گروه"


# ================== فایل‌ها ==================
def load_cache():
    for path in CACHE_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    print(f"✅ CACHE: {path}", flush=True)
                    return json.load(f)
        except: pass
    return {}


def save_cache(cache, force=False):
    save_counter["cache"] += 1
    if not force and save_counter["cache"] % 10 != 0:
        return
    for path in CACHE_PATHS:
        try:
            dn = os.path.dirname(path)
            if dn and not os.path.exists(dn): os.makedirs(dn, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except: pass


def load_data():
    defaults = {
        "welcomed_users": {}, "user_titles": {}, "taken_asl": {}, "taken_laghab": {},
        "message_counts": {}, "join_dates": {}, "special_users": {}, "warnings": {},
        "warn_limit": {}, "warn_delete_after": {}, "started_users": [], "known_groups": [],
        "group_message_count": {}, "promo_sent": {}, "filtered_words": {}, "banned_users": {},
        "last_promo_time": {},
        "settings": {
            "link": False, "id": False, "spam": False, "hyperlink": False,
            "welcome": True, "warning": False, "filter": True, "auto_ban": True,
            "profanity": True, "forward": False, "gif": False, "goodbye": False,
            "auto_promo": True,
        },
    }
    for path in DATA_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for lk in ["started_users", "known_groups"]:
                        if lk in loaded: loaded[lk] = ensure_list(loaded[lk])
                    for k, v in defaults.items():
                        if k not in loaded: loaded[k] = v
                    if "settings" in loaded:
                        for sk, sv in defaults["settings"].items():
                            if sk not in loaded["settings"]:
                                loaded["settings"][sk] = sv
                    print(f"✅ DATA: {path}", flush=True)
                    return loaded
        except: pass
    return defaults


def save_data(data, force=False):
    save_counter["data"] += 1
    if not force and save_counter["data"] % 5 != 0:
        return
    for path in DATA_PATHS:
        try:
            dn = os.path.dirname(path)
            if dn and not os.path.exists(dn): os.makedirs(dn, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except: pass


# ================== وضعیت‌ها ==================
bot_is_active = True
bot_data = load_data()
settings = bot_data.get("settings", {})
for sk in ["link", "id", "spam", "hyperlink", "warning", "filter", "auto_ban",
           "profanity", "forward", "gif", "goodbye", "auto_promo"]:
    if sk not in settings: settings[sk] = False
# welcome پیش‌فرض True
if "welcome" not in settings: settings["welcome"] = True
message_cache = load_cache()


# ================== توابع تشخیص ==================
def contains_link(text):
    if not text: return False
    pats = [r'https?://\S+', r'www\.\S+', r't\.me/\S+', r'rubika\.ir/\S+',
            r'telegram\.me/\S+', r'\.ir/\S+', r'\.com/\S+', r'\.org/\S+',
            r'\.net/\S+', r'\.me/\S+']
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
    if group_locks.get(chat_id, False): return True, "قفل دستی"
    if chat_id in temp_locks:
        et = temp_locks[chat_id]
        if time.time() < et:
            return True, f"قفل موقت (پایان: {datetime.fromtimestamp(et).strftime('%H:%M')})"
        else: del temp_locks[chat_id]
    if chat_id in scheduled_locks and scheduled_locks[chat_id]:
        now = get_local_now()
        cm = now.hour * 60 + now.minute
        for sh, sm, eh, em in scheduled_locks[chat_id]:
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

        if user_info is None:
            user_info = await get_user_info(chat_id, user_id)
        display = format_user_display(user_info, user_id)
        del_after = get_warn_delete_after(chat_id)

        warn_text = (
            f"⚠️ **اخطار!** ⚠️\n\n"
            f"👤 **کاربر:** {display}\n"
            f"📌 **دلیل:** {reason if reason else 'تخلف از قوانین'}\n"
            f"📊 **اخطار فعلی:** [{count}/{limit}]\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ **FLUXBOT** | جریان قدرت"
        )
        try:
            result = await bot.send_message(chat_id=chat_id, text=warn_text)
            if del_after > 0:
                mid = extract_msg_id(result)
                if mid: await schedule_delete(chat_id, mid, del_after)
        except Exception as e:
            print(f"⚠️ WARN SEND: {e}", flush=True)

        if count >= limit and settings.get("auto_ban", True):
            try:
                await bot.ban_member_chat(chat_id, user_id)
                if chat_id not in bot_data["banned_users"]: bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][user_id] = time.time()
                save_data(bot_data, force=True)
                ban_msg = f"🚫 **کاربر اخراج شد!**\n\n👤 {display}\n📊 تعداد اخطار: [{count}/{limit}]"
                try:
                    result = await bot.send_message(chat_id=chat_id, text=ban_msg)
                    if del_after > 0:
                        mid = extract_msg_id(result)
                        if mid: await schedule_delete(chat_id, mid, del_after)
                except: pass
                bot_data["warnings"][chat_id][user_id] = 0
                save_data(bot_data, force=True)
                return True
            except Exception as e:
                print(f"❌ BAN: {e}", flush=True)
        return False
    except Exception as e:
        print(f"❌ ADD_WARN: {e}", flush=True)
        return False


def register_user(uid):
    try:
        if not uid: return
        if not isinstance(bot_data.get("started_users"), list):
            bot_data["started_users"] = ensure_list(bot_data.get("started_users"))
        if uid not in bot_data["started_users"]:
            bot_data["started_users"].append(uid)
            save_data(bot_data)
    except: pass


def register_group(gid):
    try:
        if not gid: return
        if not isinstance(bot_data.get("known_groups"), list):
            bot_data["known_groups"] = ensure_list(bot_data.get("known_groups"))
        if gid not in bot_data["known_groups"]:
            bot_data["known_groups"].append(gid)
            save_data(bot_data, force=True)
    except: pass


# ================== کیبورد ==================
def build_keypad():
    try:
        b = ChatKeypadBuilder()
        b1 = b.button_simple(id="btn_channel", text=BTN_CHANNEL)
        b2 = b.button_simple(id="btn_help", text=BTN_HELP)
        b3 = b.button_simple(id="btn_users", text=BTN_USERS)
        b4 = b.button_simple(id="btn_groups", text=BTN_GROUPS)
        b.row(b1, b2)
        b.row(b3, b4)
        return b.build()
    except Exception as e:
        print(f"❌ KEYPAD: {e}", flush=True)
        return None


# ================== متن‌ها ==================
def get_channel_text():
    return (
        "📢 **کانال رسمی FluxBot**\n\n"
        "➣ **@RPCITY_PHANTOM**\n\n"
        "🌟 برای حمایت از ما، دریافت آخرین اخبار،\n"
        "به‌روزرسانی‌ها و آموزش‌های ویژه،\n"
        "لطفاً در کانال رسمی ما عضو شوید. 🙏\n\n"
        "💎 **عضویت شما، انگیزه ما برای بهتر شدن است.**\n\n"
        "⚡ **FLUXBOT** | جریان قدرت"
    )


def get_promo_text():
    return (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
        "   ⚡ **FLUXBOT** ⚡\n"
        "   🌊 جریان قدرت 🌊\n"
        "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        "💎 **از مدیریت حرفه‌ای لذت می‌برید؟**\n\n"
        "🎁 برای حمایت از ما، دریافت آخرین اخبار،\n"
        "به‌روزرسانی‌ها و آموزش‌های ویژه،\n"
        "لطفاً در کانال رسمی ما عضو شوید. 🙏\n\n"
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
        "  📢 **کانال رسمی:**\n"
        "  ➣ **@RPCITY_PHANTOM**\n"
        "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        "💖 **عضویت شما، انگیزه ماست.**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ **FLUXBOT** | جریان قدرت"
    )


def get_help_text():
    return (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
        "   ⚡ **FLUXBOT** ⚡\n"
        "   📚 راهنمای کامل 📚\n"
        "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        "👤 **دستورات کاربران:**\n"
        "├ 👑 `مقام` → مقام شما\n"
        "├ 📊 `پروفایل` / `آمار`\n"
        "├ 🏆 `آمار گروه` / `تاپ`\n"
        "├ ⏰ `ساعت` → ساعت و تاریخ\n"
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
        "└ 📚 `راهنما`\n\n"
        "👑 **دستورات مالک / ویژه:**\n"
        "├ ✅ `فعال` / 🛑 `غیرفعال`\n"
        "├ 🚫 `بن` / `سیک` / `اخراج` (ریپلای)\n"
        "├ ✅ `انبن` / `آنبن` (ریپلای)\n"
        "├ 🔇 `سکوت [دقیقه]`\n"
        "├ ⚠️ `اخطار` (ریپلای)\n"
        "├ ⚙️ `تنظیم اخطار [عدد]`\n"
        "├ ⏱️ `حذف پیام اخطار [ثانیه]`\n"
        "├ ⭐ `ویژه` / ❌ `حذف ویژه`\n"
        "├ 🚫 `فیلتر [کلمه]`\n"
        "├ ❌ `حذف فیلتر [کلمه]`\n"
        "└ 📋 `لیست فیلتر`\n\n"
        "🗑️ **مدیریت پیام:**\n"
        "├ 🗑️ `حذف` (ریپلای)\n"
        "└ ⏱️ `حذف [دقیقه]` (ریپلای)\n\n"
        "🔒 **قفل گروه:**\n"
        "├ 🔒 `قفل گروه`\n"
        "├ ⏱️ `قفل [ساعت]`\n"
        "├ ⏰ `قفل 13:00 14:00`\n"
        "├ 🔓 `باز`\n"
        "├ 📋 `لیست قفل گروه`\n"
        "└ ❌ `حذف قفل زمان‌بندی`\n\n"
        "⚙️ **قفل‌ها (باز/بسته):**\n"
        "├ 🔗 `لینک` / 🆔 `آیدی`\n"
        "├ 📢 `اسپم` / 🔗 `هایپرلینک`\n"
        "├ 🤬 `فحش` / 📨 `فوروارد`\n"
        "├ 🎞️ `گیف` / 👋 `خداحافظی`\n"
        "├ 👋 `خوش‌آمدگویی`\n"
        "└ 📋 `لیست قفل`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ **FLUXBOT** | جریان قدرت"
    )


def get_users_text():
    c = len(ensure_list(bot_data.get("started_users", [])))
    return f"👥 **کاربران:** **{c}**\n\n⚡ **FLUXBOT**"


def get_groups_text():
    c = len(ensure_list(bot_data.get("known_groups", [])))
    return f"🏠 **گروه‌های فعال:** **{c}**\n\n⚡ **FLUXBOT**"


# ================== هندلر پیام ==================
@bot.on_message()
async def handle_message(bot, message):
    global bot_is_active, message_cache, bot_data, settings

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

        # ذخیره در کش
        if chat_id and msg_id and sender_id:
            if chat_id not in message_cache: message_cache[chat_id] = {}
            message_cache[chat_id][msg_id] = sender_id
            if len(message_cache[chat_id]) > 300:
                keys = list(message_cache[chat_id].keys())
                for k in keys[:-300]: del message_cache[chat_id][k]
            save_cache(message_cache)

        # فیلتر پیام تکراری
        ct = time.time()
        if len(processed_messages) > 500:
            processed_messages.clear()
        if msg_id in processed_messages:
            return
        processed_messages[msg_id] = ct

        print(f"📩 {chat_id} | {sender_id} | {raw_text!r}", flush=True)

        # ============ پیوی ============
        if is_private_chat(chat_id):
            if button_id == "btn_channel" or raw_text == BTN_CHANNEL:
                await bot.send_message(chat_id=chat_id, text=get_channel_text()); return
            if button_id == "btn_help" or raw_text == BTN_HELP:
                await bot.send_message(chat_id=chat_id, text=get_help_text()); return
            if button_id == "btn_users" or raw_text == BTN_USERS:
                await bot.send_message(chat_id=chat_id, text=get_users_text()); return
            if button_id == "btn_groups" or raw_text == BTN_GROUPS:
                await bot.send_message(chat_id=chat_id, text=get_groups_text()); return

            if is_command(clean_text, "start", "شروع", "منو"):
                text = (
                    "╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   🌊 جریان قدرت 🌊\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                    "🌟 **به ربات مدیریتی FluxBot خوش آمدید!**\n\n"
                    "🤖 ربات مدیریتی حرفه‌ای گروه‌های روبیکا\n\n"
                    "👇 **از منوی پایین انتخاب کنید:**"
                )
                kp = build_keypad()
                if kp:
                    try:
                        await bot.send_message(chat_id=chat_id, text=text, chat_keypad=kp, chat_keypad_type="New")
                    except:
                        await bot.send_message(chat_id=chat_id, text=text)
                else:
                    await bot.send_message(chat_id=chat_id, text=text)
                return
            return

        if not is_group_chat(chat_id): return

        # دریافت اطلاعات کاربر
        ui = await get_user_info(chat_id, sender_id)
        role = ui["role"]
        disp = format_user_display(ui, sender_id)
        is_owner = (role == "مالک")
        is_special = bot_data.get("special_users", {}).get(chat_id, {}).get(sender_id, False)
        can_manage = is_owner or is_special

        # بررسی قفل گروه
        locked, reason = is_group_locked(chat_id)
        if locked and not can_manage:
            try: await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except: pass
            return

        # ============ دستورات ============

        # ⏰ ساعت
        if is_command(clean_text, "ساعت", "زمان"):
            now = get_local_now()
            days = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
            wd = days[now.weekday()]
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                f"⏰ **ساعت فعلی**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🕐 `{now.strftime('%H:%M:%S')}`\n"
                f"📅 `{now.strftime('%Y/%m/%d')}`\n"
                f"📆 {wd}\n\n⚡ **FLUXBOT**"))
            return

        # حذف زمان‌بندی
        dtm = re.match(r"^حذف\s+(\d+)$", clean_text)
        if dtm:
            if not can_manage: return
            mins = int(dtm.group(1))
            if mins <= 0 or mins > 10080:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ عدد 1 تا 10080", reply_to_message_id=message.message_id); return
            rid = extract_reply_id(message)
            if not rid:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام ریپلای کنید.", reply_to_message_id=message.message_id); return
            await schedule_delete(chat_id, rid, mins * 60)
            if mins >= 60:
                h, m = mins // 60, mins % 60
                ts = f"{h} ساعت" + (f" و {m} دقیقه" if m > 0 else "")
            else: ts = f"{mins} دقیقه"
            await bot.send_message(chat_id=message.chat_id, text=f"⏱️ پیام پس از **{ts}** پاک می‌شه.", reply_to_message_id=message.message_id)
            return

        # حذف فوری
        if is_command(clean_text, "حذف", "پاک"):
            if not can_manage: return
            rid = extract_reply_id(message)
            if not rid:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ روی پیام ریپلای کنید.", reply_to_message_id=message.message_id); return
            try:
                await bot.delete_message(chat_id=chat_id, message_id=rid)
                await bot.send_message(chat_id=message.chat_id, text="🗑️ **حذف شد.**", reply_to_message_id=message.message_id)
            except: pass
            return

        # باز کردن قفل
        if is_command(clean_text, "باز", "بازکردن"):
            if not can_manage: return
            had = False
            if group_locks.get(chat_id, False): group_locks[chat_id] = False; had = True
            if chat_id in temp_locks: del temp_locks[chat_id]; had = True
            msg = "🔓 **گروه باز شد!**" if had else "ℹ️ از قبل باز بود."
            await bot.send_message(chat_id=message.chat_id, text=msg, reply_to_message_id=message.message_id)
            return

        # قفل گروه دستی
        if is_command(clean_text, "قفل گروه", "قفلگروه"):
            if not can_manage: return
            group_locks[chat_id] = True
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                "🔒 **گروه قفل شد!**\n\nفقط مالک و ویژه‌ها پیام بدن.\n\nباز کردن: `باز`"))
            return

        # قفل موقت
        tm = re.match(r"^قفل\s+(\d+)$", clean_text)
        if tm:
            if not can_manage: return
            h = int(tm.group(1))
            if h <= 0 or h > 168:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ 1 تا 168 ساعت", reply_to_message_id=message.message_id); return
            et = time.time() + h * 3600
            temp_locks[chat_id] = et
            group_locks[chat_id] = False
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                f"🔒 **قفل موقت: {h} ساعت**\n🕐 پایان: {datetime.fromtimestamp(et).strftime('%H:%M - %Y/%m/%d')}\n\nباز: `باز`"))
            return

        # قفل زمان‌بندی
        sm = re.match(r"^قفل\s+(\d{1,2}):(\d{2})\s+(?:تا\s+)?(\d{1,2}):(\d{2})$", clean_text)
        if sm:
            if not can_manage: return
            sh, sm2, eh, em = map(int, sm.groups())
            if not (0 <= sh <= 23 and 0 <= sm2 <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
                await bot.send_message(chat_id=message.chat_id, text="⚠️ ساعت نامعتبر", reply_to_message_id=message.message_id); return
            if chat_id not in scheduled_locks: scheduled_locks[chat_id] = []
            scheduled_locks[chat_id].append((sh, sm2, eh, em))
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                f"🔒 **قفل زمان‌بندی: {sh:02d}:{sm2:02d} تا {eh:02d}:{em:02d}**\n\nحذف: `حذف قفل زمان‌بندی`"))
            return

        if is_command(clean_text, "حذف قفل زمان‌بندی"):
            if not can_manage: return
            if chat_id in scheduled_locks: scheduled_locks[chat_id] = []
            await bot.send_message(chat_id=message.chat_id, text="✅ حذف شد.", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "لیست قفل گروه"):
            if not can_manage: return
            s = []
            s.append("🔴 قفل دستی: فعال" if group_locks.get(chat_id) else "🟢 قفل دستی: غیرفعال")
            if chat_id in temp_locks: s.append(f"🟡 قفل موقت: {get_remaining_time(temp_locks[chat_id])}")
            else: s.append("🟢 قفل موقت: غیرفعال")
            if chat_id in scheduled_locks and scheduled_locks[chat_id]:
                sl = "\n".join([f"  • {sh:02d}:{sm:02d} تا {eh:02d}:{em:02d}" for sh, sm, eh, em in scheduled_locks[chat_id]])
                s.append(f"🟡 زمان‌بندی:\n{sl}")
            else: s.append("🟢 زمان‌بندی: غیرفعال")
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                "🔒 **وضعیت قفل گروه**\n━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(s) + "\n\n⚡ **FLUXBOT**"))
            return

        # سکوت
        now = time.time()
        cm_list = mute_list.get(chat_id, {})
        if sender_id in cm_list:
            if now < cm_list[sender_id]:
                try: await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                except: pass
                return
            else: del cm_list[sender_id]

        # شمارنده 200 پیام
        if chat_id not in bot_data["group_message_count"]: bot_data["group_message_count"][chat_id] = 0
        bot_data["group_message_count"][chat_id] += 1
        if bot_data["group_message_count"][chat_id] >= 200:
            bot_data["group_message_count"][chat_id] = 0
            save_data(bot_data, force=True)
            try: await bot.send_message(chat_id=chat_id, text=get_promo_text())
            except: pass
        else: save_data(bot_data)

        # خوش‌آمدگویی
        if settings.get("welcome", True) and bot_is_active:
            welcomed = bot_data.get("welcomed_users", {}).get(chat_id, {})
            if sender_id not in welcomed:
                cn = await get_chat_name(chat_id)
                ns = get_now_time()
                try:
                    await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                        f"╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   🌊 جریان قدرت 🌊\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
                        f"🌟 **به گروه {cn} خوش آمدید!** 🌟\n\n"
                        f"👤 **{disp} عزیز:**\nاز پیوستن شما بی‌نهایت خوشحالیم. 🌹\n\n"
                        f"⏰ **زمان ورود:** {ns}\n\n"
                        f"💎 **امکانات FluxBot:**\n"
                        f"├ 📊 `پروفایل`\n"
                        f"├ 🐺 `تنظیم اصل [نام]`\n"
                        f"├ 🎭 `تنظیم لقب [نام]`\n"
                        f"├ 👑 `مقام`\n"
                        f"├ ⏰ `ساعت`\n"
                        f"└ 📚 `راهنما`\n\n"
                        f"━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"))
                except: pass
                if chat_id not in bot_data["welcomed_users"]: bot_data["welcomed_users"][chat_id] = {}
                bot_data["welcomed_users"][chat_id][sender_id] = True
                save_data(bot_data)

        # آمار
        today = get_local_now().strftime("%Y-%m-%d")
        if chat_id not in bot_data["message_counts"]: bot_data["message_counts"][chat_id] = {}
        if sender_id not in bot_data["message_counts"][chat_id]:
            bot_data["message_counts"][chat_id][sender_id] = {"today": 0, "date": today}
        elif bot_data["message_counts"][chat_id][sender_id]["date"] != today:
            bot_data["message_counts"][chat_id][sender_id] = {"today": 0, "date": today}
        bot_data["message_counts"][chat_id][sender_id]["today"] += 1
        save_data(bot_data)

        # ============ دستورات مدیریتی ============

        if is_command(clean_text, "فعال", "فاعل"):
            if not can_manage: return
            msg = "✅ از قبل فعال." if bot_is_active else "✅ فعال شد."
            bot_is_active = True
            await bot.send_message(chat_id=message.chat_id, text=msg, reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "غیرفعال"):
            if not is_owner: return
            msg = "⛔ از قبل غیرفعال." if not bot_is_active else "🛑 غیرفعال شد."
            bot_is_active = False
            await bot.send_message(chat_id=message.chat_id, text=msg, reply_to_message_id=message.message_id)
            return

        # حذف پیام اخطار
        wdm = re.match(r"^حذف\s+پیام\s+اخطار\s+(\d+)$", clean_text)
        if wdm:
            if not is_owner: return
            sec = int(wdm.group(1))
            if sec < 0 or sec > 3600:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ 0 تا 3600", reply_to_message_id=message.message_id); return
            if "warn_delete_after" not in bot_data: bot_data["warn_delete_after"] = {}
            if sec == 0:
                bot_data["warn_delete_after"][chat_id] = 0
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=message.chat_id, text="✅ **غیرفعال شد.** پیام‌های اخطار باقی می‌مونن.", reply_to_message_id=message.message_id)
            else:
                bot_data["warn_delete_after"][chat_id] = sec
                save_data(bot_data, force=True)
                m, s = sec // 60, sec % 60
                ts = f"{m} دقیقه" + (f" و {s} ثانیه" if s > 0 else "") if m > 0 else f"{sec} ثانیه"
                await bot.send_message(chat_id=message.chat_id, text=f"✅ **فعال شد ({ts}).** فقط پیام‌های اخطار پاک می‌شن.", reply_to_message_id=message.message_id)
            return

        # بن
        if is_command(clean_text, "بن", "سیک", "اخراج"):
            if not can_manage: return
            rid = extract_reply_id(message)
            tgt = None
            if rid:
                c = load_cache()
                if chat_id in c and rid in c[chat_id]: tgt = c[chat_id][rid]
            if not tgt:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ ریپلای کنید.", reply_to_message_id=message.message_id); return
            try:
                ti = await get_user_info(chat_id, tgt)
                td = format_user_display(ti, tgt)
                await bot.ban_member_chat(chat_id, tgt)
                if chat_id not in bot_data["banned_users"]: bot_data["banned_users"][chat_id] = {}
                bot_data["banned_users"][chat_id][tgt] = time.time()
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"🚫 **{td} اخراج شد!**")
            except Exception as e:
                print(f"❌ BAN: {e}", flush=True)
                await bot.send_message(chat_id=message.chat_id, text=f"❌ خطا: {e}", reply_to_message_id=message.message_id)
            return

        # انبن
        if is_command(clean_text, "انبن", "آنبن"):
            if not can_manage: return
            rid = extract_reply_id(message)
            tgt = None
            if rid:
                c = load_cache()
                if chat_id in c and rid in c[chat_id]: tgt = c[chat_id][rid]
            if not tgt:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ ریپلای کنید.", reply_to_message_id=message.message_id); return
            try:
                ti = await get_user_info(chat_id, tgt)
                td = format_user_display(ti, tgt)
                await bot.unban_member_chat(chat_id, tgt)
                if chat_id in bot_data["banned_users"] and tgt in bot_data["banned_users"][chat_id]:
                    del bot_data["banned_users"][chat_id][tgt]
                    save_data(bot_data, force=True)
                await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"✅ **{td} آنبن شد!**")
            except Exception as e:
                print(f"❌ UNBAN: {e}", flush=True)
            return

        # فیلتر
        fm = re.match(r"^فیلتر\s+(.+)$", clean_text)
        if fm:
            if not is_owner: return
            w = fm.group(1).strip()
            if not w: return
            fl = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if w in fl:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ از قبل فیلتر شده.", reply_to_message_id=message.message_id); return
            if len(fl) >= MAX_FILTER_WORDS:
                await bot.send_message(chat_id=message.chat_id, text=f"⚠️ حداکثر {MAX_FILTER_WORDS}", reply_to_message_id=message.message_id); return
            fl.append(w); save_data(bot_data, force=True)
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"✅ **«{w}» فیلتر شد** ({len(fl)}/{MAX_FILTER_WORDS})")
            return

        ufm = re.match(r"^حذف\s+فیلتر\s+(.+)$", clean_text)
        if ufm:
            if not is_owner: return
            w = ufm.group(1).strip()
            fl = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if w in fl:
                fl.remove(w); save_data(bot_data, force=True)
                await bot.send_message(chat_id=message.chat_id, text=f"✅ «{w}» حذف شد.", reply_to_message_id=message.message_id)
            else: await bot.send_message(chat_id=message.chat_id, text="⚠️ نبود.", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "لیست فیلتر"):
            if not can_manage: return
            w = ensure_list_dict(bot_data, "filtered_words", chat_id)
            if not w: t = "📋 خالی"
            else: t = f"📋 ({len(w)}/{MAX_FILTER_WORDS}):\n\n" + "\n".join([f"├ 🚫 {x}" for x in w])
            await bot.send_message(chat_id=message.chat_id, text=t, reply_to_message_id=message.message_id)
            return

        # سرگرمی‌ها
        if is_command(clean_text, "جک", "جوک"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"😂 **جوک:**\n\n{random.choice(JOKES)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "ضرب المثل", "ضرب‌المثل"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"📜 **ضرب‌المثل:**\n\n{random.choice(PROVERBS)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "دانستی", "دانستنی"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"💡 **دانستی:**\n\n{random.choice(TRIVIA)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "فکت"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"🧠 **فکت:**\n\n{random.choice(FACTS)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "پ ن پ", "پنپ"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"💚 **پند:**\n\n{random.choice(PNP)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "شعر"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"📝 **شعر:**\n\n{random.choice(POEMS)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "فال"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"{random.choice(FAL)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "شانس"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"{random.choice(LUCK)}\n\n⚡ **FLUXBOT**"); return
        if is_command(clean_text, "لیست سرگرمی", "سرگرمی"):
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                "🎮 **سرگرمی‌ها:**\n\n😂 `جک`\n📜 `ضرب المثل`\n💡 `دانستی`\n🧠 `فکت`\n💚 `پ ن پ`\n📝 `شعر`\n🔮 `فال`\n🍀 `شانس`\n⏰ `ساعت`\n\n⚡ **FLUXBOT**"))
            return

        # آمار گروه
        if is_command(clean_text, "آمار گروه", "تاپ", "برترین‌ها"):
            today = get_local_now().strftime("%Y-%m-%d")
            counts = bot_data["message_counts"].get(chat_id, {})
            tc = [(u, d["today"]) for u, d in counts.items() if d.get("date") == today and d.get("today", 0) > 0]
            tc.sort(key=lambda x: x[1], reverse=True)
            top = tc[:10]
            if not top:
                await bot.send_message(chat_id=message.chat_id, text="📊 امروز پیامی نبود.", reply_to_message_id=message.message_id); return
            medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
            lines = []
            for i, (u, c) in enumerate(top):
                uinfo = await get_user_info(chat_id, u)
                lines.append(f"{medals[i]} {format_user_display(uinfo, u)} — `{c}`")
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"🏆 **برترین‌های امروز:**\n\n" + "\n".join(lines) + "\n\n⚡ **FLUXBOT**")
            return

        # سکوت
        mm = re.match(r"^سکوت\s+(\d+)$", clean_text)
        if mm:
            if not can_manage: return
            mins = int(mm.group(1))
            if mins <= 0: return
            tgt = None
            rid = extract_reply_id(message)
            if rid:
                c = load_cache()
                if chat_id in c and rid in c[chat_id]: tgt = c[chat_id][rid]
            if not tgt: tgt = sender_id
            et = time.time() + mins * 60
            if chat_id not in mute_list: mute_list[chat_id] = {}
            mute_list[chat_id][tgt] = et
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=f"🔇 سکوت {mins} دقیقه (پایان: {datetime.fromtimestamp(et).strftime('%H:%M')})")
            return

        # تنظیم اخطار
        wsm = re.match(r"^تنظیم\s+اخطار\s+(\d+)$", clean_text)
        if wsm:
            if not is_owner: return
            lim = int(wsm.group(1))
            if lim <= 0 or lim > 500: return
            bot_data["warn_limit"][chat_id] = lim
            settings["warning"] = True
            bot_data["settings"] = settings
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=message.chat_id, text=f"✅ حد اخطار: {lim}", reply_to_message_id=message.message_id)
            return

        # اخطار دستی
        if is_command(clean_text, "اخطار"):
            if not is_owner: return
            tgt = None
            rid = extract_reply_id(message)
            if rid:
                c = load_cache()
                if chat_id in c and rid in c[chat_id]: tgt = c[chat_id][rid]
            if not tgt:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ ریپلای کنید.", reply_to_message_id=message.message_id); return
            ti = await get_user_info(chat_id, tgt)
            await add_warning(chat_id, tgt, "اخطار دستی مالک", user_info=ti)
            return

        # ویژه
        if is_command(clean_text, "ویژه", "ادمین"):
            if not is_owner: return
            tgt = None
            rid = extract_reply_id(message)
            if rid:
                c = load_cache()
                if chat_id in c and rid in c[chat_id]: tgt = c[chat_id][rid]
            if not tgt:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ ریپلای کنید.", reply_to_message_id=message.message_id); return
            if chat_id not in bot_data["special_users"]: bot_data["special_users"][chat_id] = {}
            bot_data["special_users"][chat_id][tgt] = True
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=message.chat_id, text="⭐ ویژه شد!", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "حذف ویژه", "لغو ویژه"):
            if not is_owner: return
            tgt = None
            rid = extract_reply_id(message)
            if rid:
                c = load_cache()
                if chat_id in c and rid in c[chat_id]: tgt = c[chat_id][rid]
            if tgt and chat_id in bot_data["special_users"] and tgt in bot_data["special_users"][chat_id]:
                del bot_data["special_users"][chat_id][tgt]
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=message.chat_id, text="❌ حذف شد.", reply_to_message_id=message.message_id)
            else:
                await bot.send_message(chat_id=message.chat_id, text="⚠️ نبود.", reply_to_message_id=message.message_id)
            return

        # قفل‌ها
        feat = re.match(r"^(لینک|آیدی|اسپم|هایپرلینک|خوش‌آمدگویی|فحش|فوروارد|هدایت|گیف|خداحافظی)\s+(باز|بسته)$", clean_text)
        if feat:
            if not can_manage: return
            f, s = feat.group(1), feat.group(2)
            km = {"لینک": "link", "آیدی": "id", "اسپم": "spam", "هایپرلینک": "hyperlink",
                  "خوش‌آمدگویی": "welcome", "فحش": "profanity", "فوروارد": "forward",
                  "هدایت": "forward", "گیف": "gif", "خداحافظی": "goodbye"}
            k = km.get(f)
            if k:
                settings[k] = (s == "بسته")
                bot_data["settings"] = settings
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=message.chat_id, text=f"✅ {f} {s} شد.", reply_to_message_id=message.message_id)
            return

        # لیست قفل
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
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                "📋 **قفل‌ها**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 لینک: {st(settings['link'])}\n"
                f"🆔 آیدی: {st(settings['id'])}\n"
                f"📢 اسپم: {st(settings['spam'])}\n"
                f"🔗 هایپرلینک: {st(settings['hyperlink'])}\n"
                f"👋 خوش‌آمد: {st(settings.get('welcome', True))}\n"
                f"🤬 فحش: {st(settings.get('profanity', True))}\n"
                f"📨 فوروارد: {st(settings.get('forward', False))}\n"
                f"🎞️ گیف: {st(settings.get('gif', False))}\n"
                f"🔒 قفل گروه: {gs}\n"
                f"⚠️ اخطار: {ws} ({wl})\n"
                f"⏱️ حذف اخطار: {wds}\n"
                f"🚫 فیلتر: {fc}/{MAX_FILTER_WORDS}\n\n⚡ **FLUXBOT**"))
            return

        # راهنما
        if is_command(clean_text, "راهنما", "help", "دستورات", "دستور", "commands"):
            await bot.send_message(chat_id=message.chat_id, text=get_help_text(), reply_to_message_id=message.message_id)
            return

        # تنظیم اصل
        am = re.match(r"^تنظیم\s+اصل\s+(.+)$", clean_text)
        if am:
            av = am.group(1).strip()
            if not av: return
            tl = ensure_list_dict(bot_data, "taken_asl", chat_id)
            ca = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("asl")
            if av in tl and av != ca:
                await bot.send_message(chat_id=message.chat_id, text="❌ تکراری", reply_to_message_id=message.message_id); return
            if chat_id not in bot_data["user_titles"]: bot_data["user_titles"][chat_id] = {}
            if sender_id not in bot_data["user_titles"][chat_id]: bot_data["user_titles"][chat_id][sender_id] = {}
            if ca and ca in tl: tl.remove(ca)
            bot_data["user_titles"][chat_id][sender_id]["asl"] = av
            if av not in tl: tl.append(av)
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=message.chat_id, text=f"✅ اصل: `{av}`", reply_to_message_id=message.message_id)
            return

        # تنظیم لقب
        lm = re.match(r"^تنظیم\s+لقب\s+(.+)$", clean_text)
        if lm:
            lv = lm.group(1).strip()
            if not lv: return
            tl = ensure_list_dict(bot_data, "taken_laghab", chat_id)
            cl = bot_data["user_titles"].get(chat_id, {}).get(sender_id, {}).get("laghab")
            if lv in tl and lv != cl:
                await bot.send_message(chat_id=message.chat_id, text="❌ تکراری", reply_to_message_id=message.message_id); return
            if chat_id not in bot_data["user_titles"]: bot_data["user_titles"][chat_id] = {}
            if sender_id not in bot_data["user_titles"][chat_id]: bot_data["user_titles"][chat_id][sender_id] = {}
            if cl and cl in tl: tl.remove(cl)
            bot_data["user_titles"][chat_id][sender_id]["laghab"] = lv
            if lv not in tl: tl.append(lv)
            save_data(bot_data, force=True)
            await bot.send_message(chat_id=message.chat_id, text=f"✅ لقب: `{lv}`", reply_to_message_id=message.message_id)
            return

        # پروفایل
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
            await bot.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text=(
                f"📊 **پروفایل {disp}**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🐺 اصل: `{asl}`\n"
                f"🎭 لقب: `{lgh}`\n"
                f"👑 مقام: {role}\n"
                f"⭐ وضعیت: {ss}\n"
                f"⚠️ اخطار: [{wc}/{wl}]\n"
                f"📅 پیوست: {jd}\n"
                f"💬 پیام امروز: {tc}\n\n⚡ **FLUXBOT**"))
            return

        if is_command(clean_text, "مقام"):
            await bot.send_message(chat_id=message.chat_id, text=f"👤 {role}", reply_to_message_id=message.message_id)
            return

        # ========== بررسی خودکار ==========
        if not bot_is_active: return
        if can_manage: return

        if settings.get("profanity", True):
            bw = contains_profanity(raw_text)
            if bw:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]: await add_warning(chat_id, sender_id, "فحش", user_info=ui)
                except: pass
                return

        if settings["filter"]:
            fl = ensure_list_dict(bot_data, "filtered_words", chat_id)
            m = contains_filtered_word(raw_text, fl)
            if m:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    if settings["warning"]: await add_warning(chat_id, sender_id, "کلمه فیلترشده", user_info=ui)
                except: pass
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
                except: pass
                return

        if settings["link"] and contains_link(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]: await add_warning(chat_id, sender_id, "لینک", user_info=ui)
            except: pass
            return

        if settings["hyperlink"] and contains_hyperlink(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]: await add_warning(chat_id, sender_id, "هایپرلینک", user_info=ui)
            except: pass
            return

        if settings["id"] and contains_id(raw_text):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]: await add_warning(chat_id, sender_id, "آیدی", user_info=ui)
            except: pass
            return

        if settings.get("forward", False) and is_forwarded(message):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]: await add_warning(chat_id, sender_id, "فوروارد", user_info=ui)
            except: pass
            return

        if settings.get("gif", False) and is_gif(message):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                if settings["warning"]: await add_warning(chat_id, sender_id, "گیف", user_info=ui)
            except: pass
            return

    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}", flush=True)


# ================== تبلیغ خودکار هر 2 ساعت ==================
async def auto_promo_task():
    print("⏰ AUTO PROMO STARTED (every 2 hours)", flush=True)
    await asyncio.sleep(120)  # 2 دقیقه صبر اولیه

    while True:
        try:
            if not bot_data.get("settings", {}).get("auto_promo", True):
                await asyncio.sleep(300)
                continue

            groups = ensure_list(bot_data.get("known_groups", []))
            print(f"📢 PROMO | {len(groups)} groups", flush=True)

            sent = 0
            for gid in groups:
                try:
                    await bot.send_message(chat_id=gid, text=get_promo_text())
                    sent += 1
                    print(f"✅ PROMO→{gid}", flush=True)
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"⚠️ PROMO FAIL {gid}: {e}", flush=True)

            bot_data["last_promo_time"] = {"time": time.time(), "sent": sent}
            save_data(bot_data, force=True)
            print(f"💤 PROMO SLEEP 2h", flush=True)
            await asyncio.sleep(PROMO_INTERVAL)
        except Exception as e:
            print(f"❌ PROMO TASK: {e}", flush=True)
            await asyncio.sleep(60)


async def main():
    print("🤖 FLUXBOT STARTING...", flush=True)
    print(f"🌍 TZ: Iran (UTC+3:30)", flush=True)
    print(f"📢 CHANNEL: {CHANNEL_USERNAME}", flush=True)
    print(f"⏰ PROMO: every 2h", flush=True)
    try:
        asyncio.create_task(auto_promo_task())
    except Exception as e:
        print(f"⚠️ PROMO START: {e}", flush=True)
    try:
        await bot.run()
    except Exception as e:
        print(f"❌ BOT RUN: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
