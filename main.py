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

MAX_CACHE_PER_GROUP = 5000
START_DELAY = 30
RECONNECT_DELAY = 10


# =========================================================
# توکن
# =========================================================

if not TOKEN:
    raise RuntimeError(
        "RUBIKA_TOKEN تنظیم نشده است. "
        "در Runflare داخل «تنظیم متغیر محیطی» یک متغیر با نام "
        "RUBIKA_TOKEN بساز و توکن ربات را در مقدار آن قرار بده."
    )

DATA_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# ابزار JSON
# =========================================================

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
        temp_path = path.with_suffix(path.suffix + ".tmp")

        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(
                value,
                f,
                ensure_ascii=False,
                indent=2,
            )

        temp_path.replace(path)

    except OSError as exc:
        print(f"[JSON SAVE ERROR] {path}: {exc}", flush=True)


# =========================================================
# وضعیت ذخیره‌شده
# =========================================================

active_groups: set[str] = {
    str(group_id)
    for group_id in load_json(ACTIVE_FILE, [])
}

muted_users: dict[str, set[str]] = {
    str(group_id): {
        str(user_id)
        for user_id in user_ids
    }
    for group_id, user_ids in load_json(MUTED_FILE, {}).items()
}

message_cache: dict[str, dict[str, str]] = {
    str(group_id): {
        str(message_id): str(user_id)
        for message_id, user_id in messages.items()
    }
    for group_id, messages in load_json(CACHE_FILE, {}).items()
}


def save_state() -> None:
    save_json(
        ACTIVE_FILE,
        sorted(active_groups),
    )

    save_json(
        MUTED_FILE,
        {
            group_id: sorted(user_ids)
            for group_id, user_ids in muted_users.items()
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


# =========================================================
# ساخت ربات
# =========================================================

bot = Robot(TOKEN)


# =========================================================
# شناسه‌ها و متن
# =========================================================

def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).strip().split())


def get_chat_id(message: Message) -> str | None:
    value = getattr(message, "chat_id", None)

    if value is None:
        value = getattr(message, "chat_guid", None)

    return str(value) if value else None


def get_user_id(message: Message) -> str | None:
    value = getattr(message, "sender_id", None)

    if value is None:
        value = getattr(message, "author_guid", None)

    if value is None:
        value = getattr(message, "sender_guid", None)

    return str(value) if value else None


def get_message_id(message: Message) -> str | None:
    value = getattr(message, "message_id", None)

    if value is None:
        value = getattr(message, "id", None)

    return str(value) if value else None


def get_reply_message_id(message: Message) -> str | None:
    value = getattr(
        message,
        "reply_to_message_id",
        None,
    )

    if value is None:
        reply = getattr(
            message,
            "reply_to_message",
            None,
        )

        if isinstance(reply, dict):
            value = (
                reply.get("message_id")
                or reply.get("id")
            )
        elif reply is not None:
            value = (
                getattr(reply, "message_id", None)
                or getattr(reply, "id", None)
            )

    return str(value) if value else None


# =========================================================
# تشخیص مدیر
# =========================================================

def contains_identifier(value: Any, wanted: str) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return value == wanted

    if isinstance(value, dict):
        return any(
            contains_identifier(item, wanted)
            for item in value.values()
        )

    if isinstance(value, (list, tuple, set)):
        return any(
            contains_identifier(item, wanted)
            for item in value
        )

    return False


async def is_group_admin(
    group_id: str,
    user_id: str,
) -> bool:
    try:
        admins = await bot.get_chat_admins(group_id)
        return contains_identifier(
            admins,
            user_id,
        )

    except Exception as exc:
        print(
            f"[ADMIN CHECK ERROR] {type(exc).__name__}: {exc}",
            flush=True,
        )
        return False


# =========================================================
# ذخیره پیام برای ریپلای
# =========================================================

def remember_message(message: Message) -> None:
    group_id = get_chat_id(message)
    message_id = get_message_id(message)
    user_id = get_user_id(message)

    if not group_id or not message_id or not user_id:
        return

    group_cache = message_cache.setdefault(
        group_id,
        {},
    )

    group_cache[message_id] = user_id

    if len(group_cache) > MAX_CACHE_PER_GROUP:
        extra = len(group_cache) - MAX_CACHE_PER_GROUP

        old_ids = list(group_cache.keys())[:extra]

        for old_id in old_ids:
            group_cache.pop(old_id, None)

    save_message_cache()


# =========================================================
# فقط پیام‌های گروه
# =========================================================
#
# on_message_group باعث می‌شود این هندلر مستقیماً
# برای پیام‌های گروه ثبت شود.
# =========================================================

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

        # پیام را قبل از هر دستور ذخیره کن
        remember_message(message)

        # =================================================
        # فعال
        # =================================================

        if text == "فعال":

            # فقط مدیر اجازه فعال‌سازی دارد.
            if not await is_group_admin(
                group_id,
                user_id,
            ):
                return

            active_groups.add(group_id)

            muted_users.setdefault(
                group_id,
                set(),
            )

            save_state()

            try:
                await message.reply(
                    "✅ ربات در این گروه فعال شد."
                )
            except Exception as exc:
                print(
                    f"[ACTIVATE REPLY ERROR] "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

            return

        # =================================================
        # اگر گروه فعال نیست
        # =================================================

        if group_id not in active_groups:
            return

        # =================================================
        # حذف پیام کاربر ساکت‌شده
        # =================================================

        if user_id in muted_users.get(
            group_id,
            set(),
        ):
            message_id = get_message_id(message)

            if message_id:
                try:
                    await bot_instance.delete_message(
                        group_id,
                        message_id,
                    )
                except Exception as exc:
                    print(
                        f"[DELETE MUTED ERROR] "
                        f"{type(exc).__name__}: {exc}",
                        flush=True,
                    )

            return

        # =================================================
        # سکوت
        # =================================================

        if text != "سکوت":
            return

        # فقط مدیر
        if not await is_group_admin(
            group_id,
            user_id,
        ):
            return

        reply_id = get_reply_message_id(message)

        if not reply_id:
            await message.reply(
                "⚠️ روی پیام کاربر ریپلای کن و بنویس: سکوت"
            )
            return

        # اول از خود reply تلاش می‌کنیم
        target_id = None

        reply = getattr(
            message,
            "reply_to_message",
            None,
        )

        if isinstance(reply, dict):
            target_id = (
                reply.get("sender_id")
                or reply.get("author_guid")
                or reply.get("sender_guid")
                or reply.get("user_id")
            )
        elif reply is not None:
            target_id = (
                getattr(reply, "sender_id", None)
                or getattr(reply, "author_guid", None)
                or getattr(reply, "sender_guid", None)
                or getattr(reply, "user_id", None)
            )

        # اگر در reply نبود، از کش استفاده کن
        if not target_id:
            target_id = message_cache.get(
                group_id,
                {},
            ).get(reply_id)

        if not target_id:
            await message.reply(
                "⚠️ کاربر پیام ریپلای‌شده پیدا نشد. "
                "روی پیامی که ربات دیده ریپلای کن و دوباره بنویس: سکوت"
            )
            return

        target_id = str(target_id)

        # مدیران قابل سکوت نیستند
        if await is_group_admin(
            group_id,
            target_id,
        ):
            await message.reply(
                "⛔ مدیر گروه قابل سکوت نیست."
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
                f"[RESTRICT ERROR] "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

            await message.reply(
                "❌ سکوت انجام نشد. "
                "دسترسی مدیریت اعضای ربات را بررسی کن."
            )
            return

        # بررسی پاسخ API، در صورتی که دیکشنری باشد
        if isinstance(result, dict):
            status = str(
                result.get("status", "OK")
            )

            if status not in {
                "",
                "OK",
            }:
                await message.reply(
                    "❌ روبیکا درخواست سکوت را نپذیرفت."
                )
                return

        muted_users.setdefault(
            group_id,
            set(),
        ).add(target_id)

        save_state()

        await message.reply(
            "✅ کاربر سکوت شد."
        )

    except Exception as exc:
        print(
            f"[HANDLER ERROR] "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )


# =========================================================
# راه‌اندازی با تأخیر ۳۰ ثانیه + اتصال مجدد
# =========================================================

async def run_bot() -> None:

    print(
        "🤖 RP Group Manager is starting...",
        flush=True,
    )

    print(
        "⏳ ربات ۳۰ ثانیه دیگر راه‌اندازی می‌شود...",
        flush=True,
    )

    await asyncio.sleep(30)

    while True:
        try:

            print(
                "🚀 در حال اتصال به روبیکا...",
                flush=True,
            )

            await bot.run()

            print(
                "⚠️ اتصال ربات متوقف شد.",
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


# =========================================================
# شروع
# =========================================================

if __name__ == "__main__":
    asyncio.run(run_bot())
