import json
import os
import time
from pathlib import Path
from typing import Any

from rubka import Robot, Message


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
        "RUBIKA_TOKEN در Runflare تنظیم نشده است. "
        "یک Environment Variable با نام RUBIKA_TOKEN بساز "
        "و توکن ربات را در آن قرار بده."
    )

DATA_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# ابزار JSON
# =========================================================

def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"[JSON LOAD ERROR] {path}: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        return default


def save_json(path: Path, value: Any) -> bool:
    temp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(
                value,
                file,
                ensure_ascii=False,
                indent=2,
            )

        temp_path.replace(path)
        return True

    except OSError as exc:
        print(
            f"[JSON SAVE ERROR] {path}: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )

        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass

        return False


# =========================================================
# وضعیت ذخیره‌شده
# =========================================================

_raw_active_groups = load_json(
    ACTIVE_FILE,
    [],
)

active_groups: set[str] = {
    str(group_id)
    for group_id in _raw_active_groups
    if group_id is not None
}


_raw_muted_users = load_json(
    MUTED_FILE,
    {},
)

muted_users: dict[str, set[str]] = {}

if isinstance(_raw_muted_users, dict):
    for group_id, user_ids in _raw_muted_users.items():

        if isinstance(
            user_ids,
            (list, tuple, set),
        ):
            muted_users[str(group_id)] = {
                str(user_id)
                for user_id in user_ids
                if user_id is not None
            }


_raw_cache = load_json(
    CACHE_FILE,
    {},
)

message_cache: dict[str, dict[str, str]] = {}

if isinstance(_raw_cache, dict):

    for group_id, messages in _raw_cache.items():

        if not isinstance(
            messages,
            dict,
        ):
            continue

        message_cache[str(group_id)] = {
            str(message_id): str(user_id)
            for message_id, user_id in messages.items()
            if message_id is not None
            and user_id is not None
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
            if user_ids
        },
    )


def save_message_cache() -> None:

    save_json(
        CACHE_FILE,
        {
            group_id: dict(messages)
            for group_id, messages in message_cache.items()
            if messages
        },
    )


# =========================================================
# ساخت ربات
# =========================================================

bot = Robot(
    token=TOKEN,
    safeSendMode=True,
    max_cache_size=2000,
    max_msg_age=60,
    retries=5,
    retry_delay=1.0,
    timeout=15,
)


# =========================================================
# ابزارهای پیام
# =========================================================

def normalize_text(value: Any) -> str:

    if value is None:
        return ""

    return " ".join(
        str(value).strip().split()
    )


def get_chat_id(
    message: Message,
) -> str | None:

    value = getattr(
        message,
        "chat_id",
        None,
    )

    if value is None:
        value = getattr(
            message,
            "chat_guid",
            None,
        )

    if value is None:
        return None

    return str(value)


def get_user_id(
    message: Message,
) -> str | None:

    for attr in (
        "sender_id",
        "author_guid",
        "sender_guid",
        "user_id",
    ):

        value = getattr(
            message,
            attr,
            None,
        )

        if value is not None:
            return str(value)

    return None


def get_message_id(
    message: Message,
) -> str | None:

    value = getattr(
        message,
        "message_id",
        None,
    )

    if value is None:
        value = getattr(
            message,
            "id",
            None,
        )

    if value is None:
        return None

    return str(value)


def get_reply_message_id(
    message: Message,
) -> str | None:

    for attr in (
        "reply_to_message_id",
        "reply_message_id",
    ):

        value = getattr(
            message,
            attr,
            None,
        )

        if value is not None:
            return str(value)

    reply = getattr(
        message,
        "reply_to_message",
        None,
    )

    if isinstance(
        reply,
        dict,
    ):

        value = (
            reply.get("message_id")
            or reply.get("id")
        )

        if value is not None:
            return str(value)

    elif reply is not None:

        for attr in (
            "message_id",
            "id",
        ):

            value = getattr(
                reply,
                attr,
                None,
            )

            if value is not None:
                return str(value)

    return None


def get_reply_target_id(
    message: Message,
) -> str | None:

    reply = getattr(
        message,
        "reply_to_message",
        None,
    )

    if isinstance(
        reply,
        dict,
    ):

        value = (
            reply.get("sender_id")
            or reply.get("author_guid")
            or reply.get("sender_guid")
            or reply.get("user_id")
        )

        if value is not None:
            return str(value)

    elif reply is not None:

        for attr in (
            "sender_id",
            "author_guid",
            "sender_guid",
            "user_id",
        ):

            value = getattr(
                reply,
                attr,
                None,
            )

            if value is not None:
                return str(value)

    reply_id = get_reply_message_id(
        message
    )

    if not reply_id:
        return None

    group_id = get_chat_id(
        message
    )

    if not group_id:
        return None

    return (
        message_cache
        .get(group_id, {})
        .get(reply_id)
    )


# =========================================================
# تشخیص مدیر
# =========================================================

def contains_identifier(
    value: Any,
    wanted: str,
) -> bool:

    if value is None:
        return False

    if isinstance(
        value,
        str,
    ):
        return value == wanted

    if isinstance(
        value,
        dict,
    ):

        for item in value.values():

            if contains_identifier(
                item,
                wanted,
            ):
                return True

        return False

    if isinstance(
        value,
        (list, tuple, set),
    ):

        for item in value:

            if contains_identifier(
                item,
                wanted,
            ):
                return True

        return False

    return False


async def is_group_admin(
    group_id: str,
    user_id: str,
) -> bool:

    try:

        response = await bot.get_chat_admins(
            group_id
        )

        return contains_identifier(
            response,
            user_id,
        )

    except Exception as exc:

        print(
            f"[ADMIN CHECK ERROR] "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )

        return False


# =========================================================
# کش پیام‌ها برای ریپلای
# =========================================================

def remember_message(
    message: Message,
) -> None:

    group_id = get_chat_id(
        message
    )

    message_id = get_message_id(
        message
    )

    user_id = get_user_id(
        message
    )

    if not group_id:
        return

    if not message_id:
        return

    if not user_id:
        return

    group_cache = message_cache.setdefault(
        group_id,
        {},
    )

    group_cache[message_id] = user_id

    while len(group_cache) > MAX_CACHE_PER_GROUP:

        oldest_id = next(
            iter(group_cache)
        )

        group_cache.pop(
            oldest_id,
            None,
        )

    save_message_cache()


# =========================================================
# هندلر اصلی پیام‌ها
# =========================================================

@bot.on_message()
async def handle_group_message(
    bot_instance: Robot,
    message: Message,
):

    try:

        # فقط پیام‌های گروه
        if not bool(
            getattr(
                message,
                "is_group",
                False,
            )
        ):
            return

        group_id = get_chat_id(
            message
        )

        user_id = get_user_id(
            message
        )

        if not group_id or not user_id:

            print(
                "[MESSAGE ERROR] "
                "chat_id یا user_id پیدا نشد.",
                flush=True,
            )

            return

        text = normalize_text(
            getattr(
                message,
                "text",
                None,
            )
        )

        print(
            f"[MESSAGE] "
            f"group={group_id} "
            f"user={user_id} "
            f"text={text!r}",
            flush=True,
        )

        # ذخیره پیام
        remember_message(
            message
        )

        # =================================================
        # فعال
        # =================================================

        if text == "فعال":

            if not await is_group_admin(
                group_id,
                user_id,
            ):

                print(
                    f"[ACTIVATE DENIED] "
                    f"user={user_id} "
                    f"is not admin "
                    f"in {group_id}",
                    flush=True,
                )

                try:

                    await message.reply(
                        "⛔ فقط مدیر گروه "
                        "می‌تواند ربات را فعال کند."
                    )

                except Exception as exc:

                    print(
                        f"[ACTIVATE DENIED REPLY ERROR] "
                        f"{type(exc).__name__}: {exc}",
                        flush=True,
                    )

                return

            first_activation = (
                group_id
                not in active_groups
            )

            active_groups.add(
                group_id
            )

            muted_users.setdefault(
                group_id,
                set(),
            )

            save_state()

            try:

                if first_activation:

                    await message.reply(
                        "✅ ربات در این گروه فعال شد."
                    )

                else:

                    await message.reply(
                        "✅ ربات از قبل فعال بود "
                        "و دوباره فعال شد."
                    )

            except Exception as exc:

                print(
                    f"[ACTIVATE REPLY ERROR] "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

            return

        # =================================================
        # گروه فعال نشده
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

            message_id = get_message_id(
                message
            )

            if message_id:

                try:

                    await bot_instance.delete_message(
                        chat_id=group_id,
                        message_id=message_id,
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

        if not await is_group_admin(
            group_id,
            user_id,
        ):

            try:

                await message.reply(
                    "⛔ فقط مدیر گروه "
                    "می‌تواند از سکوت استفاده کند."
                )

            except Exception as exc:

                print(
                    f"[SILENCE ADMIN REPLY ERROR] "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

            return

        target_id = get_reply_target_id(
            message
        )

        if not target_id:

            try:

                await message.reply(
                    "⚠️ روی پیام کاربر ریپلای کن "
                    "و بنویس: سکوت"
                )

            except Exception as exc:

                print(
                    f"[SILENCE HELP REPLY ERROR] "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

            return

        # نمی‌تواند خودش را ساکت کند
        if target_id == user_id:

            try:

                await message.reply(
                    "⛔ نمی‌توانی خودت را ساکت کنی."
                )

            except Exception as exc:

                print(
                    f"[SELF SILENCE REPLY ERROR] "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

            return

        # مدیران قابل سکوت نیستند
        if await is_group_admin(
            group_id,
            target_id,
        ):

            try:

                await message.reply(
                    "⛔ مدیر گروه قابل سکوت نیست."
                )

            except Exception as exc:

                print(
                    f"[ADMIN TARGET REPLY ERROR] "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

            return

        # اعمال محدودیت
        try:

            result = await bot_instance.restrict_chat_member(
                chat_id=group_id,
                user_id=target_id,
                until=0,
            )

        except Exception as exc:

            print(
                f"[RESTRICT ERROR] "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

            try:

                await message.reply(
                    "❌ سکوت انجام نشد. "
                    "مطمئن شو ربات دسترسی مدیریت "
                    "اعضا را دارد."
                )

            except Exception as reply_exc:

                print(
                    f"[RESTRICT ERROR REPLY ERROR] "
                    f"{type(reply_exc).__name__}: "
                    f"{reply_exc}",
                    flush=True,
                )

            return

        # بررسی پاسخ API
        if isinstance(
            result,
            dict,
        ):

            status = str(
                result.get(
                    "status",
                    "OK",
                )
            ).upper()

            if status not in {
                "",
                "OK",
            }:

                try:

                    await message.reply(
                        "❌ درخواست سکوت "
                        "توسط روبیکا پذیرفته نشد.\n"
                        f"وضعیت: {status}"
                    )

                except Exception as exc:

                    print(
                        f"[RESTRICT STATUS REPLY ERROR] "
                        f"{type(exc).__name__}: {exc}",
                        flush=True,
                    )

                return

        # ذخیره کاربر ساکت‌شده
        muted_users.setdefault(
            group_id,
            set(),
        ).add(target_id)

        save_state()

        try:

            await message.reply(
                "✅ کاربر سکوت شد."
            )

        except Exception as exc:

            print(
                f"[SILENCE SUCCESS REPLY ERROR] "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

    except Exception as exc:

        print(
            f"[HANDLER ERROR] "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )


# =========================================================
# شروع ربات
# =========================================================

def start() -> None:

    print(
        "🤖 RP Group Manager is starting...",
        flush=True,
    )

    print(
        f"⏳ ربات {START_DELAY} ثانیه دیگر "
        "راه‌اندازی می‌شود...",
        flush=True,
    )

    time.sleep(
        START_DELAY
    )

    while True:

        try:

            print(
                "🚀 در حال اتصال به روبیکا...",
                flush=True,
            )

            # Rubka خودش event loop را مدیریت می‌کند
            bot.run()

            print(
                "⚠️ حلقه اجرای ربات متوقف شد.",
                flush=True,
            )

        except KeyboardInterrupt:

            print(
                "🛑 ربات توسط سیستم متوقف شد.",
                flush=True,
            )

            break

        except Exception as exc:

            print(
                f"❌ خطای اتصال/اجرای ربات: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

        print(
            f"🔄 تلاش دوباره تا "
            f"{RECONNECT_DELAY} ثانیه دیگر...",
            flush=True,
        )

        time.sleep(
            RECONNECT_DELAY
        )


# =========================================================
# اجرا
# =========================================================

if __name__ == "__main__":
    start()
