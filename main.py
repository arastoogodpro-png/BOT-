import asyncio
import json
import os
from pathlib import Path
from typing import Any

from rubka.asynco import Robot
from rubka.context import Message


# =========================================================
# تنظیمات
# =========================================================

TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

DATA_DIR = Path(os.getenv("BOT_DATA_DIR", "data"))

ACTIVE_FILE = DATA_DIR / "active_groups.json"
MUTED_FILE = DATA_DIR / "muted_users.json"
CACHE_FILE = DATA_DIR / "message_cache.json"

MAX_CACHE = 5000

START_DELAY = 30


# =========================================================
# بررسی توکن
# =========================================================

if not TOKEN:
    raise RuntimeError(
        "RUBIKA_TOKEN تنظیم نشده است. "
        "آن را در متغیر محیطی Runflare قرار بده."
    )


DATA_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# ابزارهای فایل JSON
# =========================================================

def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except Exception as exc:
        print(f"[JSON LOAD ERROR] {path}: {exc}", flush=True)
        return default


def save_json(path: Path, value: Any) -> None:
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")

        with tmp.open("w", encoding="utf-8") as file:
            json.dump(
                value,
                file,
                ensure_ascii=False,
                indent=2
            )

        tmp.replace(path)

    except Exception as exc:
        print(f"[JSON SAVE ERROR] {path}: {exc}", flush=True)


# =========================================================
# وضعیت ربات
# =========================================================

active_groups: set[str] = set(
    str(x)
    for x in load_json(ACTIVE_FILE, [])
)


muted_users: dict[str, set[str]] = {
    str(group): set(str(user) for user in users)
    for group, users in load_json(MUTED_FILE, {}).items()
}


message_cache: dict[str, dict[str, str]] = {
    str(group): {
        str(message_id): str(user_id)
        for message_id, user_id in messages.items()
    }
    for group, messages in load_json(CACHE_FILE, {}).items()
}


# =========================================================
# ساخت ربات
# =========================================================

bot = Robot(TOKEN)


# =========================================================
# توابع کمکی
# =========================================================

def normalize_text(text: str | None) -> str:
    if not text:
        return ""

    return " ".join(text.strip().split())


def contains_identifier(value: Any, wanted: str) -> bool:

    if value is None:
        return False

    if isinstance(value, str):
        return value == wanted

    if isinstance(value, dict):
        return any(
            contains_identifier(v, wanted)
            for v in value.values()
        )

    if isinstance(value, (list, tuple, set)):
        return any(
            contains_identifier(v, wanted)
            for v in value
        )

    return False


async def is_group_admin(
    chat_id: str,
    user_id: str
) -> bool:

    try:
        admins = await bot.get_chat_admins(chat_id)

        return contains_identifier(
            admins,
            user_id
        )

    except Exception as exc:
        print(
            f"[ADMIN CHECK ERROR] {exc}",
            flush=True
        )

        return False


def remember_message(message: Message) -> None:

    try:
        group_id = str(message.chat_id)
        message_id = str(message.message_id)
        sender_id = str(message.sender_id)

        group_cache = message_cache.setdefault(
            group_id,
            {}
        )

        group_cache[message_id] = sender_id

        # محدود کردن کش
        if len(group_cache) > MAX_CACHE:

            extra = len(group_cache) - MAX_CACHE

            old_ids = list(group_cache.keys())[:extra]

            for old_id in old_ids:
                group_cache.pop(old_id, None)

        save_json(
            CACHE_FILE,
            {
                group: dict(messages)
                for group, messages in message_cache.items()
            }
        )

    except Exception as exc:
        print(
            f"[CACHE ERROR] {exc}",
            flush=True
        )


def save_state() -> None:

    save_json(
        ACTIVE_FILE,
        sorted(active_groups)
    )

    save_json(
        MUTED_FILE,
        {
            group: sorted(users)
            for group, users in muted_users.items()
        }
    )


# =========================================================
# دریافت پیام
# =========================================================

@bot.on_message()
async def handle_message(
    bot_instance: Robot,
    message: Message
):

    try:

        print(
            f"[MESSAGE] chat={getattr(message, 'chat_id', '?')} "
            f"text={getattr(message, 'text', '')}",
            flush=True
        )

        # فقط گروه
        if not getattr(message, "is_group", False):
            return

        group_id = str(message.chat_id)
        user_id = str(message.sender_id)

        text = normalize_text(
            getattr(message, "text", "")
        )

        # ذخیره پیام
        remember_message(message)

        # =================================================
        # فعال
        # =================================================

        if text == "فعال":

            print(
                f"[ACTIVATE] group={group_id} user={user_id}",
                flush=True
            )

            # برای اینکه حتی اگر قبلاً فعال بوده
            # دوباره دستور فعال جواب بدهد
            active_groups.add(group_id)

            muted_users.setdefault(
                group_id,
                set()
            )

            save_state()

            try:
                await message.reply(
                    "✅ ربات در این گروه فعال شد."
                )

            except Exception as exc:
                print(
                    f"[ACTIVATE REPLY ERROR] {exc}",
                    flush=True
                )

            return

        # =================================================
        # پیام افراد ساکت
        # =================================================

        if (
            group_id in active_groups
            and user_id in muted_users.get(
                group_id,
                set()
            )
        ):

            try:

                await bot_instance.delete_message(
                    group_id,
                    str(message.message_id)
                )

            except Exception as exc:

                print(
                    f"[DELETE MUTED ERROR] {exc}",
                    flush=True
                )

            return

        # =================================================
        # اگر گروه فعال نیست
        # =================================================

        if group_id not in active_groups:
            return

        # =================================================
        # سکوت
        # =================================================

        if text == "سکوت":

            if not await is_group_admin(
                group_id,
                user_id
            ):
                return

            reply_id = getattr(
                message,
                "reply_to_message_id",
                None
            )

            if not reply_id:

                await message.reply(
                    "⚠️ روی پیام کاربر ریپلای کن و بنویس: سکوت"
                )

                return

            target_id = message_cache.get(
                group_id,
                {}
            ).get(
                str(reply_id)
            )

            if not target_id:

                await message.reply(
                    "⚠️ پیام موردنظر در حافظه ربات پیدا نشد."
                )

                return

            # مدیر را نمی‌شود ساکت کرد
            if await is_group_admin(
                group_id,
                target_id
            ):

                await message.reply(
                    "⛔ مدیر گروه قابل سکوت نیست."
                )

                return

            try:

                await bot_instance.restrict_chat_member(
                    group_id,
                    target_id,
                    until=0
                )

            except Exception as exc:

                print(
                    f"[RESTRICT ERROR] {exc}",
                    flush=True
                )

                await message.reply(
                    "❌ سکوت انجام نشد. "
                    "دسترسی مدیریت اعضای ربات را بررسی کن."
                )

                return

            muted_users.setdefault(
                group_id,
                set()
            ).add(target_id)

            save_state()

            await message.reply(
                "✅ کاربر سکوت شد."
            )

    except Exception as exc:

        print(
            f"[MESSAGE HANDLER ERROR] {exc}",
            flush=True
        )


# =========================================================
# اجرای ربات با تأخیر و تلاش مجدد
# =========================================================

async def start_bot():

    print(
        "🤖 RP Group Manager is starting...",
        flush=True
    )

    print(
        f"⏳ ربات تا {START_DELAY} ثانیه دیگر شروع می‌شود...",
        flush=True
    )

    await asyncio.sleep(START_DELAY)

    while True:

        try:

            print(
                "🚀 در حال اتصال به روبیکا...",
                flush=True
            )

            await bot.run()

            print(
                "⚠️ اتصال ربات متوقف شد؛ "
                "۱۰ ثانیه بعد دوباره تلاش می‌کنم.",
                flush=True
            )

        except Exception as exc:

            print(
                f"❌ خطای اجرای ربات: {exc}",
                flush=True
            )

        await asyncio.sleep(10)


# =========================================================
# شروع
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            start_bot()
        )

    except KeyboardInterrupt:

        print(
            "🛑 ربات متوقف شد.",
            flush=True
    )
