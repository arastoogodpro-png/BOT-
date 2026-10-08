import asyncio
import json
import os
from pathlib import Path
from typing import Any

from rubka.asynco import Robot
from rubka.context import Message


TOKEN = os.getenv("RUBIKA_TOKEN", "").strip()

DATA_DIR = Path(os.getenv("BOT_DATA_DIR", "data"))
ACTIVE_FILE = DATA_DIR / "active_groups.json"
MUTED_FILE = DATA_DIR / "muted_users.json"
CACHE_FILE = DATA_DIR / "message_cache.json"

START_DELAY = 30
REPLY_DELAY = 5
RECONNECT_DELAY = 10
MAX_CACHE_PER_GROUP = 5000


if not TOKEN:
    raise RuntimeError(
        "RUBIKA_TOKEN تنظیم نشده است. "
        "در Runflare متغیر محیطی RUBIKA_TOKEN را تنظیم کن."
    )

DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[JSON LOAD ERROR] {path}: {exc}", flush=True)
        return default


def save_json(path: Path, value: Any) -> None:
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
    except OSError as exc:
        print(f"[JSON SAVE ERROR] {path}: {exc}", flush=True)


active_groups: set[str] = {
    str(x)
    for x in load_json(ACTIVE_FILE, [])
    if x
}

muted_users: dict[str, set[str]] = {}
raw_muted = load_json(MUTED_FILE, {})
if isinstance(raw_muted, dict):
    for group_id, users in raw_muted.items():
        if isinstance(users, (list, tuple, set)):
            muted_users[str(group_id)] = {
                str(x) for x in users if x
            }

message_cache: dict[str, dict[str, str]] = {}
raw_cache = load_json(CACHE_FILE, {})
if isinstance(raw_cache, dict):
    for group_id, messages in raw_cache.items():
        if isinstance(messages, dict):
            message_cache[str(group_id)] = {
                str(mid): str(uid)
                for mid, uid in messages.items()
                if mid and uid
            }


def save_state() -> None:
    save_json(ACTIVE_FILE, sorted(active_groups))
    save_json(
        MUTED_FILE,
        {
            group_id: sorted(users)
            for group_id, users in muted_users.items()
        },
    )


def save_message_cache() -> None:
    save_json(
        CACHE_FILE,
        {
            group_id: dict(messages)
            for group_id, messages in message_cache.items()
        },
    )


bot = Robot(TOKEN)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u200c", " ").replace("\u200d", "")
    return " ".join(text.strip().split())


def get_chat_id(message: Message) -> str | None:
    for field in ("chat_id", "chat_guid", "object_guid"):
        value = getattr(message, field, None)
        if value:
            return str(value)
    return None


def get_user_id(message: Message) -> str | None:
    for field in (
        "sender_id",
        "author_guid",
        "sender_guid",
        "user_id",
    ):
        value = getattr(message, field, None)
        if value:
            return str(value)

    raw = getattr(message, "raw_data", None)
    if isinstance(raw, dict):
        for field in (
            "sender_id",
            "author_guid",
            "sender_guid",
            "user_id",
        ):
            value = raw.get(field)
            if value:
                return str(value)

    return None


def get_message_id(message: Message) -> str | None:
    for field in ("message_id", "id"):
        value = getattr(message, field, None)
        if value:
            return str(value)

    raw = getattr(message, "raw_data", None)
    if isinstance(raw, dict):
        value = raw.get("message_id") or raw.get("id")
        if value:
            return str(value)

    return None


def get_reply_message_id(message: Message) -> str | None:
    value = getattr(message, "reply_to_message_id", None)
    if value:
        return str(value)

    raw = getattr(message, "raw_data", None)
    if isinstance(raw, dict):
        value = (
            raw.get("reply_to_message_id")
            or raw.get("reply_message_id")
        )
        if value:
            return str(value)

    return None


def contains_identifier(value: Any, wanted: str) -> bool:
    if value is None:
        return False

    wanted = str(wanted)

    if isinstance(value, str):
        return value == wanted

    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) == wanted:
                return True
            if contains_identifier(item, wanted):
                return True
        return False

    if isinstance(value, (list, tuple, set)):
        return any(
            contains_identifier(item, wanted)
            for item in value
        )

    return False


def has_admin_role(value: Any) -> bool:
    admin_words = {
        "admin",
        "administrator",
        "owner",
        "creator",
        "مدیر",
        "ادمین",
        "مالک",
    }

    if value is None:
        return False

    if isinstance(value, str):
        return value.strip().lower() in admin_words

    if isinstance(value, dict):
        for key, item in value.items():
            key_name = str(key).strip().lower()
            if key_name in {
                "type",
                "role",
                "status",
                "member_type",
                "chat_member_status",
            }:
                if has_admin_role(item):
                    return True
            elif has_admin_role(item):
                return True
        return False

    if isinstance(value, (list, tuple, set)):
        return any(has_admin_role(item) for item in value)

    return False


async def is_group_admin(group_id: str, user_id: str) -> bool:
    try:
        result = await bot.get_chat_admins(group_id)
        if contains_identifier(result, user_id):
            print(
                f"[ADMIN CHECK] {user_id} -> ADMIN",
                flush=True,
            )
            return True
    except Exception as exc:
        print(
            f"[ADMIN LIST ERROR] {type(exc).__name__}: {exc}",
            flush=True,
        )

    try:
        result = await bot.get_chat_member(group_id, user_id)
        if has_admin_role(result):
            print(
                f"[ADMIN CHECK] get_chat_member -> ADMIN",
                flush=True,
            )
            return True
    except Exception as exc:
        print(
            f"[MEMBER CHECK ERROR] {type(exc).__name__}: {exc}",
            flush=True,
        )

    return False


async def delayed_reply(message: Message, text: str) -> None:
    await asyncio.sleep(REPLY_DELAY)

    try:
        result = message.reply(text)
        if hasattr(result, "__await__"):
            await result
        return
    except Exception as exc:
        print(
            f"[REPLY ERROR] {type(exc).__name__}: {exc}",
            flush=True,
        )

    chat_id = get_chat_id(message)
    if not chat_id:
        return

    try:
        result = bot.send_message(chat_id, text)
        if hasattr(result, "__await__"):
            await result
    except Exception as exc:
        print(
            f"[REPLY FALLBACK ERROR] {type(exc).__name__}: {exc}",
            flush=True,
        )


def remember_message(message: Message) -> None:
    group_id = get_chat_id(message)
    message_id = get_message_id(message)
    user_id = get_user_id(message)

    if not group_id or not message_id or not user_id:
        return

    cache = message_cache.setdefault(group_id, {})
    cache[message_id] = user_id

    if len(cache) > MAX_CACHE_PER_GROUP:
        extra = len(cache) - MAX_CACHE_PER_GROUP
        for old_id in list(cache.keys())[:extra]:
            cache.pop(old_id, None)

    save_message_cache()


def get_reply_target_from_raw(message: Message) -> str | None:
    raw = getattr(message, "raw_data", None)
    if not isinstance(raw, dict):
        return None

    for key in (
        "reply_to_message",
        "reply_message",
        "replied_message",
    ):
        data = raw.get(key)
        if isinstance(data, dict):
            for field in (
                "sender_id",
                "author_guid",
                "sender_guid",
                "user_id",
            ):
                value = data.get(field)
                if value:
                    return str(value)

    return None


async def safe_delete(group_id: str, message_id: str) -> None:
    try:
        result = bot.delete_message(group_id, message_id)
        if hasattr(result, "__await__"):
            await result
    except Exception as exc:
        print(
            f"[DELETE ERROR] {type(exc).__name__}: {exc}",
            flush=True,
        )


@bot.on_message_group()
async def handle_group_message(
    bot_instance: Robot,
    message: Message,
):
    try:
        group_id = get_chat_id(message)
        user_id = get_user_id(message)

        if not group_id or not user_id:
            print(
                "[MESSAGE ERROR] chat_id یا user_id پیدا نشد.",
                flush=True,
            )
            return

        text = normalize_text(
            getattr(message, "text", None)
        )

        print(
            f"[MESSAGE] group={group_id} "
            f"user={user_id} text={text!r}",
            flush=True,
        )

        remember_message(message)

        # فعال
        if text == "فعال":
            print(
                f"[ACTIVATE] {group_id} by {user_id}",
                flush=True,
            )

            admin_ok = await is_group_admin(
                group_id,
                user_id,
            )

            if not admin_ok:
                await delayed_reply(
                    message,
                    "⛔ فقط مدیر گروه می‌تواند ربات را فعال کند.\n"
                    "اگر مدیر هستی، مطمئن شو ربات دسترسی مدیریت گروه را دارد.",
                )
                return

            was_active = group_id in active_groups

            active_groups.add(group_id)
            muted_users.setdefault(group_id, set())
            save_state()

            if was_active:
                await delayed_reply(
                    message,
                    "✅ ربات از قبل فعال بود و دوباره فعال شد.",
                )
            else:
                await delayed_reply(
                    message,
                    "✅ ربات در این گروه فعال شد.",
                )
            return

        # تا قبل از فعال شدن هیچ دستور مدیریتی اجرا نشود.
        if group_id not in active_groups:
            return

        # حذف پیام کاربر ساکت
        if user_id in muted_users.get(group_id, set()):
            message_id = get_message_id(message)
            if message_id:
                await safe_delete(group_id, message_id)
            return

        # سکوت
        if text != "سکوت":
            return

        if not await is_group_admin(group_id, user_id):
            await delayed_reply(
                message,
                "⛔ فقط مدیر گروه می‌تواند از دستور سکوت استفاده کند.",
            )
            return

        reply_id = get_reply_message_id(message)
        if not reply_id:
            await delayed_reply(
                message,
                "⚠️ روی پیام کاربر ریپلای کن و بنویس: سکوت",
            )
            return

        target_id = get_reply_target_from_raw(message)

        if not target_id:
            target_id = message_cache.get(
                group_id,
                {},
            ).get(reply_id)

        if not target_id:
            await delayed_reply(
                message,
                "⚠️ کاربر پیام ریپلای‌شده پیدا نشد. "
                "روی پیامی که ربات قبلاً دیده ریپلای کن و دوباره بنویس: سکوت",
            )
            return

        target_id = str(target_id)

        if target_id == user_id:
            await delayed_reply(
                message,
                "⛔ نمی‌توانی خودت را ساکت کنی.",
            )
            return

        if await is_group_admin(group_id, target_id):
            await delayed_reply(
                message,
                "⛔ مدیر گروه قابل سکوت نیست.",
            )
            return

        try:
            result = await bot_instance.restrict_chat_member(
                group_id,
                target_id,
                until=0,
            )
        except Exception as exc:
            print(
                f"[RESTRICT ERROR] {type(exc).__name__}: {exc}",
                flush=True,
            )
            await delayed_reply(
                message,
                "❌ سکوت انجام نشد. "
                "مطمئن شو ربات مدیر گروه است و اجازه مدیریت اعضا را دارد.",
            )
            return

        if isinstance(result, dict):
            status = str(
                result.get("status", "")
            ).strip().upper()

            if status and status != "OK":
                print(
                    f"[RESTRICT STATUS] {status}",
                    flush=True,
                )
                await delayed_reply(
                    message,
                    "❌ روبیکا درخواست سکوت را نپذیرفت.",
                )
                return

        muted_users.setdefault(group_id, set()).add(target_id)
        save_state()

        await delayed_reply(
            message,
            "✅ کاربر سکوت شد.",
        )

    except Exception as exc:
        print(
            f"[HANDLER ERROR] {type(exc).__name__}: {exc}",
            flush=True,
        )


async def run_bot() -> None:
    print(
        "🤖 RP Group Manager is starting...",
        flush=True,
    )

    print(
        "⏳ ربات ۳۰ ثانیه دیگر راه‌اندازی می‌شود...",
        flush=True,
    )

    await asyncio.sleep(START_DELAY)

    while True:
        try:
            print(
                "🚀 در حال اتصال به روبیکا...",
                flush=True,
            )

            await bot.run()

            print(
                "⚠️ حلقه دریافت پیام متوقف شد.",
                flush=True,
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"❌ خطای اتصال/اجرای ربات: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

        print(
            f"🔄 تلاش دوباره تا {RECONNECT_DELAY} ثانیه دیگر...",
            flush=True,
        )

        await asyncio.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    asyncio.run(run_bot())
