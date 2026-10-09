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
PROMO_INTERVAL = 5 * 60 * 60
PROMO_CHAT_COOLDOWN = 60 * 60
PROMO_MSG_THRESHOLD = 200

username_cache = {}
username_cache_ttl = {}
spam_tracker = {}
processed_messages = {}
text_dedup = {}
waiting_for_code = {}
group_info_cache = {}
group_info_cache_ttl = {}
save_counter = {"data": 0, "cache": 0}

EMPTY = "⚫"
RED = "🔴"
YELLOW = "🟡"


# ================== Game ==================
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
            cm = data.get("chat_member", data) if isinstance(data, dict) else {}
            info["name"] = cm.get("first_name") or cm.get("name") or cm.get("title")
            un = cm.get("username") or cm.get("user_name")
            if un: info["username"] = str(un).lstrip("@")
            st = str(cm.get("status", "")).strip().lower()
            if st in ("creator", "owner"): info["role"] = "مالک"
            elif st in ("admin", "administrator"): info["role"] = "ادمین"
            username_cache[key] = info
            username_cache_ttl[key] = now + 3600
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
    if BOT_ID_CACHE["id"]:
        return BOT_ID_CACHE["id"]
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
    print(f"⚠️ Target not found: rid={rid}", flush=True)
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


def can_send_promo_to_chat(chat_id):
    last = bot_data.get("last_chat_promo", {}).get(chat_id, 0)
    return (time.time() - last) >= PROMO_CHAT_COOLDOWN


def mark_promo_sent(chat_id):
    if "last_chat_promo" not in bot_data: bot_data["last_chat_promo"] = {}
    bot_data["last_chat_promo"][chat_id] = time.time()


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
    text = (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n"
        "   ⚡ **FLUXBOT** ⚡\n"
        f"   📋 لیست گروه‌ها ({len(groups)})\n"
        "╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
    )
    now = time.time()
    for i, gid in enumerate(groups, 1):
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
            await asyncio.sleep(0.15)
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
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎮 بازی‌های دیگه به زودی!\n\n"
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
        "🛡️ **امنیت و مدیریت گروه**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🔗 قفل لینک (حذف خودکار لینک)\n"
        "├ 🆔 قفل آیدی (حذف @username)\n"
        "├ 📢 قفل اسپم (ضد اسپم هوشمند)\n"
        "├ 🔗 قفل هایپرلینک (لینک مخفی)\n"
        "├ 🤬 قفل فحش (۱۰۰+ کلمه)\n"
        "├ 📨 قفل فوروارد\n"
        "├ 🎞️ قفل گیف\n"
        "├ 👋 قفل خداحافظی\n"
        "├ 👋 قفل خوش‌آمدگویی\n"
        "├ 🔒 قفل گروه دستی\n"
        "├ ⏱️ قفل موقت (به ساعت)\n"
        "└ ⏰ قفل زمان‌بندی (روزانه)\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "👑 **مدیریت کاربران**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ ⚠️ سیستم اخطار هوشمند\n"
        "├ 🚫 اخراج خودکار بعد از اخطار\n"
        "├ ❌ حذف اخطار (کل یا عددی)\n"
        "├ 🔇 سکوت با زمان دلخواه\n"
        "├ ⭐ ویژه کردن کاربران\n"
        "├ ❌ حذف از لیست ویژه\n"
        "├ 👤 نمایش مقام واقعی\n"
        "├ 🚫 دستور بن/سیک/اخراج\n"
        "└ ✅ دستور آنبن\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎮 **بازی و سرگرمی**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🎲 بازی دوز چهارتایی (دو نفره)\n"
        "├ 😂 جک و جوک\n"
        "├ 📜 ضرب‌المثل\n"
        "├ 💡 دانستی\n"
        "├ 🧠 فکت علمی\n"
        "├ 💚 پند و اندرز (پ ن پ)\n"
        "├ 📝 شعر\n"
        "├ 🔮 فال حافظ\n"
        "├ 🍀 شانس امروز\n"
        "└ 🎮 لیست بازی‌ها\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📊 **پروفایل و آمار**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🐺 تنظیم اصل اختصاصی\n"
        "├ 🎭 تنظیم لقب اختصاصی\n"
        "├ 📈 آمار پیام روزانه\n"
        "├ 📅 تاریخ پیوست به گروه\n"
        "├ 🏆 برترین‌های روز (تاپ ۱۰)\n"
        "├ 💎 نمایش امتیاز\n"
        "├ ⏰ ساعت و تاریخ زنده\n"
        "└ 👤 پروفایل کامل کاربران\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎟️ **سیستم دعوت دوستان**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🎫 کد دعوت ۶ رقمی اختصاصی\n"
        "├ 🎟️ سیستم ثبت کد دعوت\n"
        "├ ⭐ امتیاز به ازای هر دعوت\n"
        "├ 🏆 جدول برترین دعوت‌کنندگان\n"
        "└ 💎 امتیاز دو طرف (دعوت‌کننده و دعوت‌شده)\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ **ابزارهای مدیریتی**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ 🗑️ حذف فوری پیام\n"
        "├ ⏱️ حذف با تایمر (به دقیقه)\n"
        "├ 🚫 فیلتر کلمات (۵۰ کلمه)\n"
        "├ ❌ حذف از لیست فیلتر\n"
        "├ 📋 لیست کلمات فیلترشده\n"
        "├ 📢 تبلیغ خودکار هر ۵ ساعت\n"
        "├ 🎯 تبلیغ ۲۰۰ پیامی با کول‌داون\n"
        "└ 📚 راهنمای کامل\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "👤 **دستورات کاربران**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ `مقام` → مقام شما\n"
        "├ `پروفایل` یا `آمار` → پروفایل\n"
        "├ `تاپ` → برترین‌های گروه\n"
        "├ `ساعت` → ساعت و تاریخ\n"
        "├ `تنظیم اصل [نام]`\n"
        "├ `تنظیم لقب [نام]`\n"
        "├ `جک` / `ضرب المثل`\n"
        "├ `دانستی` / `فکت`\n"
        "├ `پ ن پ` / `شعر`\n"
        "├ `فال` / `شانس`\n"
        "└ `راهنما` → راهنمای کامل\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "👑 **دستورات مالک / ویژه**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ `فعال` / `غیرفعال` → روشن/خاموش\n"
        "├ `بن` / `سیک` / `اخراج` (ریپلای)\n"
        "├ `انبن` (ریپلای)\n"
        "├ `سکوت [دقیقه]` (ریپلای)\n"
        "├ `اخطار` (ریپلای)\n"
        "├ `حذف اخطار` (ریپلای)\n"
        "├ `حذف اخطار [عدد]` (ریپلای)\n"
        "├ `تنظیم اخطار [عدد]`\n"
        "├ `حذف پیام اخطار [ثانیه]`\n"
        "├ `ویژه` (ریپلای)\n"
        "├ `حذف ویژه` (ریپلای)\n"
        "├ `فیلتر [کلمه]`\n"
        "├ `حذف فیلتر [کلمه]`\n"
        "├ `لیست فیلتر`\n"
        "├ `حذف` (ریپلای) → حذف فوری\n"
        "├ `حذف [دقیقه]` (ریپلای)\n"
        "├ `قفل گروه` / `باز`\n"
        "├ `قفل [ساعت]`\n"
        "├ `قفل 13:00 14:00`\n"
        "├ `لیست قفل گروه`\n"
        "└ `لیست گروه ها` (فقط مالک توی پیوی)\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "👋 **خوش‌آمدگویی سفارشی**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ `تنظیم پیام خوش آمدگویی [متن]`\n"
        "├ `حذف پیام خوش آمدگویی`\n"
        "└ `نمایش پیام خوش آمدگویی`\n"
        "💡 متغیرها: {name}، {group}، {time}\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎮 **بازی دوز چهارتایی**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "├ `دوز` → شروع بازی\n"
        "├ `دوز قرمز` / `دوز زرد` → انتخاب رنگ\n"
        "├ `شرکت` → پیوستن به بازی\n"
        "├ `1` تا `7` → انداختن مهره\n"
        "├ `انصراف` → لغو بازی\n"
        "└ 🏆 ۴ مهره پشت سر هم = برد\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "✨ **چرا FluxBot؟**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ سرعت بالا و بدون تاخیر\n"
        "🎯 مدیریت هوشمند و دقیق\n"
        "🔐 امنیت کامل گروه شما\n"
        "💎 رابط کاربری زیبا و مدرن\n"
        "🚀 به‌روزرسانی مداوم\n"
        "🎮 سرگرمی بی‌نظیر برای اعضا\n"
        "📊 گزارش‌گیری دقیق\n"
        "💾 حفظ کامل اطلاعات\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🔗 **ربات رو به گروهت اضافه کن:**\n"
        "👉 **@Flux1bot**\n\n"
        "📢 **کانال رسمی:**\n"
        "➣ **@RPCITY_PHANTOM**\n"
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
        "group_message_count": {}, "promo_sent": {}, "filtered_words": {}, "banned_users": {},
        "last_promo_time": {},
        "invite_codes": {}, "code_to_user": {}, "points": {}, "invited_users": {},
        "known_users": {}, "games": {},
        "group_locks": {}, "temp_locks": {}, "scheduled_locks": {}, "mute_list": {},
        "last_chat_promo": {},
        "custom_welcome": {},
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
           "profanity", "forward", "gif", "goodbye", "auto_promo"]:
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


def get_promo_text():
    return (
        "╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   🌊 جریان قدرت 🌊\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        "💎 **از مدیریت حرفه‌ای لذت می‌برید؟**\n\n"
        "🎁 برای حمایت از ما لطفاً در کانال رسمی عضو شوید:\n"
        "📢 **@RPCITY_PHANTOM**\n\n"
        "💖 **عضویت شما، انگیزه ماست.**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"
    )


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
        "├ 🐺 `تنظیم اصل [نام]`\n├ 🎭 `تنظیم لقب [نام]`\n"
        "├ 🎟️ `زدن کد دعوت`\n├ 🎫 `کد دعوت من`\n├ ⭐ `امتیاز من`\n"
        "├ 📖 `قابلیت‌های ربات`\n"
        "├ 🏆 `لیست برتر دعوت‌کنندگان`\n├ 🎮 `لیست بازی`\n"
        "├ 😂 `جک` / 📜 `ضرب المثل`\n├ 💡 `دانستی` / 🧠 `فکت`\n"
        "├ 💚 `پ ن پ` / 📝 `شعر`\n├ 🔮 `فال` / 🍀 `شانس`\n"
        "└ 📚 `راهنما`\n\n"
        "🎮 **بازی دوز (فقط گروه):**\n"
        "├ `دوز` → شروع\n├ `شرکت` → پیوستن\n"
        "├ `1` تا `7` → انداختن\n└ `انصراف` → لغو\n\n"
        "👑 **مالک / ویژه:**\n"
        "├ ✅ `فعال` / 🛑 `غیرفعال`\n├ 🚫 `بن` / `سیک` / `اخراج` (ریپلای)\n"
        "├ ✅ `انبن` (ریپلای)\n├ 🔇 `سکوت [دقیقه]` (ریپلای)\n"
        "├ ⚠️ `اخطار` (ریپلای)\n├ ❌ `حذف اخطار` (ریپلای)\n"
        "├ ❌ `حذف اخطار [عدد]` (ریپلای)\n├ ⚙️ `تنظیم اخطار [عدد]`\n"
        "├ ⏱️ `حذف پیام اخطار [ثانیه]`\n├ ⭐ `ویژه` (ریپلای)\n"
        "├ ❌ `حذف ویژه` (ریپلای)\n├ 🚫 `فیلتر [کلمه]`\n└ 📋 `لیست فیلتر`\n\n"
        "👋 **خوش‌آمدگویی سفارشی:**\n"
        "├ `تنظیم پیام خوش آمدگویی [متن]`\n"
        "├ `حذف پیام خوش آمدگویی`\n"
        "└ `نمایش پیام خوش آمدگویی`\n\n"
        "🗑️ **مدیریت پیام:**\n"
        "├ 🗑️ `حذف` (ریپلای)\n└ ⏱️ `حذف [دقیقه]` (ریپلای)\n\n"
        "🔒 **قفل گروه:**\n"
        "├ 🔒 `قفل گروه`\n├ ⏱️ `قفل [ساعت]`\n├ ⏰ `قفل 13:00 14:00`\n"
        "├ 🔓 `باز`\n└ 📋 `لیست قفل گروه`\n\n"
        "⚙️ **قفل‌ها:**\n"
        "├ 🔗 `لینک` / 🆔 `آیدی`\n├ 📢 `اسپم` / 🔗 `هایپرلینک`\n"
        "├ 🤬 `فحش` / 📨 `فوروارد`\n├ 🎞️ `گیف` / 👋 `خداحافظی`\n"
        "└ 📋 `لیست قفل`\n\n"
        "📋 **دستور مالک خاص:**\n"
        "└ `لیست گروه ها` (توی پیوی)\n\n"
        "━━━━━━━━━━━━━━━━━━━\n⚡ **FLUXBOT** | جریان قدرت"
    )


def get_users_text():
    c = len(ensure_list(bot_data.get("started_users", [])))
    return f"👥 **کاربران:** **{c}**\n\n⚡ **FLUXBOT**"


def get_groups_text():
    c = len(ensure_list(bot_data.get("known_groups", [])))
    return f"🏠 **گروه‌های فعال:** **{c}**\n\n⚡ **FLUXBOT**"


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
    """🆕 متن خوش‌آمدگویی سفارشی یا پیش‌فرض"""
    custom = bot_data.get("custom_welcome", {}).get(chat_id)
    now_str = get_now_time()
    if custom:
        # جایگزینی متغیرها
        text = custom.replace("{name}", display_name)
        text = text.replace("{group}", chat_name)
        text = text.replace("{time}", now_str)
        return text
    # پیش‌فرض
    return (
        f"╭─━━━━━━━━━━━━━━━━━━━─╮\n   ⚡ **FLUXBOT** ⚡\n   🌊 جریان قدرت 🌊\n╰─━━━━━━━━━━━━━━━━━━━─╯\n\n"
        f"🌟 **به گروه {chat_name} خوش آمدید!** 🌟\n\n"
        f"👤 **{display_name} عزیز:**\nخوشحالیم که به ما پیوستید. 🌹\n\n"
        f"⏰ **ورود:** {now_str}\n\n"
        f"💎 **امکانات:**\n"
        f"├ 📊 `پروفایل`\n├ 🎮 `دوز`\n"
        f"├ 🐺 `تنظیم اصل [نام]`\n└ 📚 `راهنما`\n\n⚡ **FLUXBOT**"
    )


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

        # ============ پیوی ============
        if is_private_chat(chat_id):
            if is_owner_check and clean_text in ("لیست گروه ها", "لیست گروه‌ها", "گروه ها", "گروه‌ها", "لیست گروها"):
                msg = await bot.send_message(chat_id=chat_id, text="⏳ در حال جمع‌آوری...")
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
                await bot.send_message(chat_id=chat_id, text=get_groups_text()); return
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

            # 🆕 دکمه قابلیت‌ها
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

        locked, reason = is_group_locked(chat_id)
        if locked and not can_manage:
            try: await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except Exception as e:
                print(f"⚠️ delete locked: {e}", flush=True)
            return

        games = get_games()

        if clean_text in ("لیست بازی", "لیست بازی ها", "لیست بازی‌ها", "بازی ها", "بازی‌ها"):
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=get_games_list_text())
            return

        # 🆕 تنظیم پیام خوش‌آمدگویی (فقط مالک)
        cwm = re.match(r"^تنظیم\s+پیام\s+خوش\s*آمدگویی\s+(.+)$", clean_text)
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
                "📌 **متن تنظیم‌شده:**\n"
                f"{welcome_text}\n\n"
                "💡 متغیرها:\n"
                "├ `{name}` → نام کاربر\n"
                "├ `{group}` → نام گروه\n"
                "└ `{time}` → زمان ورود\n\n"
                "⚡ **FLUXBOT**"))
            return

        if is_command(clean_text, "حذف پیام خوش آمدگویی", "حذف پیام خوش‌آمدگویی", "پاک پیام خوش آمدگویی"):
            if not is_owner_group: return
            if "custom_welcome" not in bot_data: bot_data["custom_welcome"] = {}
            if chat_id in bot_data["custom_welcome"]:
                del bot_data["custom_welcome"][chat_id]
                save_data(bot_data, force=True)
                await bot.send_message(chat_id=chat_id, text="✅ **پیام خوش‌آمدگویی حذف شد.** الان پیام پیش‌فرض ارسال می‌شه.", reply_to_message_id=message.message_id)
            else:
                await bot.send_message(chat_id=chat_id, text="ℹ️ پیام سفارشی تنظیم نشده.", reply_to_message_id=message.message_id)
            return

        if is_command(clean_text, "نمایش پیام خوش آمدگویی", "نمایش پیام خوش‌آمدگویی"):
            if not can_manage: return
            custom = bot_data.get("custom_welcome", {}).get(chat_id)
            if custom:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                    "📋 **پیام خوش‌آمدگویی فعلی:**\n\n" + custom + "\n\n⚡ **FLUXBOT**"))
            else:
                await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text="ℹ️ پیام پیش‌فرض فعاله.")
            return

        # === بازی دوز ===
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
                f"⏳ **منتظر حریف...**\n\n📌 برای پیوستن: `شرکت`\n📌 برای لغو: `انصراف`\n\n⚡ **FLUXBOT**"))
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

        # === دستورات ===
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
            if had:
                save_data(bot_data, force=True)
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

        if chat_id not in bot_data["group_message_count"]: bot_data["group_message_count"][chat_id] = 0
        bot_data["group_message_count"][chat_id] += 1
        if bot_data["group_message_count"][chat_id] >= PROMO_MSG_THRESHOLD:
            bot_data["group_message_count"][chat_id] = 0
            save_data(bot_data, force=True)
            if can_send_promo_to_chat(chat_id):
                try:
                    await bot.send_message(chat_id=chat_id, text=get_promo_text())
                    mark_promo_sent(chat_id)
                    save_data(bot_data, force=True)
                    print(f"📢 200-MSG PROMO sent to {chat_id}", flush=True)
                except Exception as e:
                    print(f"⚠️ promo 200msg: {e}", flush=True)
            else:
                left = PROMO_CHAT_COOLDOWN - (time.time() - bot_data.get("last_chat_promo", {}).get(chat_id, 0))
                print(f"⏸️ Promo skipped (cooldown {int(left)}s left)", flush=True)
        else: save_data(bot_data)

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
                await bot.send_message(chat_id=chat_id, text=f"❌ خطا: {e}", reply_to_message_id=message.message_id)
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
                await bot.send_message(chat_id=chat_id, text=f"✅ {f} {s} شد.", reply_to_message_id=message.message_id)
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
            await bot.send_message(chat_id=chat_id, reply_to_message_id=message.message_id, text=(
                "📋 **قفل‌ها**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 لینک: {st(settings['link'])}\n🆔 آیدی: {st(settings['id'])}\n"
                f"📢 اسپم: {st(settings['spam'])}\n🔗 هایپرلینک: {st(settings['hyperlink'])}\n"
                f"👋 خوش‌آمد: {st(settings.get('welcome', True))}\n🤬 فحش: {st(settings.get('profanity', True))}\n"
                f"📨 فوروارد: {st(settings.get('forward', False))}\n🎞️ گیف: {st(settings.get('gif', False))}\n"
                f"🔒 قفل گروه: {gs}\n⚠️ اخطار: {ws} ({wl})\n⏱️ حذف اخطار: {wds}\n"
                f"🚫 فیلتر: {fc}/{MAX_FILTER_WORDS}\n\n⚡ **FLUXBOT**"))
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

        if is_command(clean_text, "مقام"):
            await bot.send_message(chat_id=chat_id, text=f"👤 {role}", reply_to_message_id=message.message_id)
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


async def auto_promo_task():
    print(f"⏰ AUTO PROMO STARTED (every {PROMO_INTERVAL // 3600} hours)", flush=True)
    await asyncio.sleep(180)
    while True:
        try:
            if not bot_data.get("settings", {}).get("auto_promo", True):
                await asyncio.sleep(300)
                continue
            groups = ensure_list(bot_data.get("known_groups", []))
            sent = 0
            skipped = 0
            for gid in groups:
                if not can_send_promo_to_chat(gid):
                    skipped += 1
                    continue
                try:
                    await bot.send_message(chat_id=gid, text=get_promo_text())
                    mark_promo_sent(gid)
                    sent += 1
                    save_data(bot_data, force=True)
                    await asyncio.sleep(3)
                except Exception as e:
                    print(f"⚠️ promo {gid}: {e}", flush=True)
            bot_data["last_promo_time"] = {"time": time.time(), "sent": sent, "skipped": skipped}
            save_data(bot_data, force=True)
            print(f"💤 AUTO PROMO | sent={sent} skipped={skipped}", flush=True)
            await asyncio.sleep(PROMO_INTERVAL)
        except Exception as e:
            print(f"❌ PROMO: {e}", flush=True)
            await asyncio.sleep(60)


async def main():
    print("🤖 FLUXBOT STARTING...", flush=True)
    print(f"👑 OWNER: {OWNER_ID}", flush=True)
    print(f"⏰ PROMO: every {PROMO_INTERVAL // 3600}h | cooldown {PROMO_CHAT_COOLDOWN // 60}min per chat", flush=True)
    try: asyncio.create_task(auto_promo_task())
    except: pass
    try: asyncio.create_task(cleanup_task())
    except: pass
    try: await bot.run()
    except Exception as e: print(f"❌ BOT RUN: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
