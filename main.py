import asyncio
import json
import os
from pathlib import Path
from typing import Any

from rubka import Robot
from rubka.context import Message

# =========================
# تنظیمات
# =========================
TOKEN = os.getenv("RUBIKA_TOKEN", "CGCEHD0GJVKFRAZSGVZUKXXNFZZWIDPXTAZGBFFDJQNKUIHKRYISDXOMWXWGJBSL").strip()
DATA_DIR = Path(os.getenv("BOT_DATA_DIR", "data"))
ACTIVE_FILE = DATA_DIR / "active_groups.json"
MUTED_FILE = DATA_DIR / "muted_users.json"
CACHE_FILE = DATA_DIR / "message_cache.json"
MAX_CACHE = 5000

if not TOKEN or TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
    raise RuntimeError(
        "توکن ربات تنظیم نشده است. متغیر RUBIKA_TOKEN را تنظیم کنید "
        "یا مقدار TOKEN در main.py را قرار دهید."
    )

DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, value: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# فعال بودن ربات در هر گروه
active_groups: set[str] = set(load_json(ACTIVE_FILE, []))

# کاربران ساکت‌شده: {group_guid: [user_guid, ...]}
muted_users: dict[str, set[str]] = {
    group: set(users)
    for group, users in load_json(MUTED_FILE, {}).items()
}

# کش پیام‌ها برای فهمیدن اینکه پیام ریپلای‌شده متعلق به کدام کاربر بوده است.
# این فایل باعث می‌شود بعد از ری‌استارت هم پیام‌های دیده‌شده قابل ریپلای باشند.
message_cache: dict[str, dict[str, str]] = {
    str(group): {str(mid): str(uid) for mid, uid in messages.items()}
    for group, messages in load_json(CACHE_FILE, {}).items()
}

bot = Robot(TOKEN)


def contains_identifier(value: Any, wanted: str) -> bool:
    """در پاسخ‌های API به‌صورت بازگشتی دنبال شناسه می‌گردد."""
    if value is None:
        return False
    if isinstance(value, str):
        return value == wanted
    if isinstance(value, dict):
        return any(contains_identifier(v, wanted) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(contains_identifier(v, wanted) for v in value)
    return False


async def is_group_admin(chat_id: str, user_id: str) -> bool:
    """چون خروجی get_chat_admins مخصوص فهرست مدیران است، وجود شناسه کاربر کافی است."""
    try:
        admins = await bot.get_chat_admins(chat_id)
        return contains_identifier(admins, user_id)
    except Exception as exc:
        print(f"[ADMIN CHECK ERROR] {exc}")
        return False


def remember_message(message: Message) -> None:
    group = str(message.chat_id)
    mid = str(message.message_id)
    uid = str(message.sender_id)
    group_cache = message_cache.setdefault(group, {})
    group_cache[mid] = uid

    # محدود کردن اندازه کش هر گروه
    if len(group_cache) > MAX_CACHE:
        extra = len(group_cache) - MAX_CACHE
        for old_mid in list(group_cache.keys())[:extra]:
            group_cache.pop(old_mid, None)

    save_json(
        CACHE_FILE,
        {g: dict(messages) for g, messages in message_cache.items()},
    )


def save_state() -> None:
    save_json(ACTIVE_FILE, sorted(active_groups))
    save_json(
        MUTED_FILE,
        {g: sorted(users) for g, users in muted_users.items()},
    )


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.strip().split())


@bot.on_message()
async def handle_message(bot_instance: Robot, message: Message):
    if not message.is_group:
        return

    group_id = str(message.chat_id)
    user_id = str(message.sender_id)
    text = normalize_text(message.text)

    # هر پیام دیده‌شده را قبل از اجرای دستورات ذخیره می‌کنیم تا ریپلای قابل شناسایی باشد.
    try:
        remember_message(message)
    except Exception as exc:
        print(f"[CACHE ERROR] {exc}")

    # اول از همه، پیام افراد ساکت حذف می‌شود.
    # حتی اگر متن، عکس، استیکر، فایل و ... باشد، message handler آن را دریافت می‌کند.
    if group_id in active_groups and user_id in muted_users.get(group_id, set()):
        try:
            await bot_instance.delete_message(group_id, str(message.message_id))
        except Exception as exc:
            print(f"[DELETE MUTED MESSAGE ERROR] {exc}")
        return

    # فعال‌سازی فقط توسط مدیر گروه
    if text == "فعال":
        if not await is_group_admin(group_id, user_id):
            await message.reply("⛔ فقط مدیر گروه می‌تواند ربات را فعال کند.")
            return

        active_groups.add(group_id)
        muted_users.setdefault(group_id, set())
        save_state()
        await message.reply("✅ ربات در گروه فعال شد.")
        return

    # تا قبل از فعال‌سازی هیچ دستور مدیریتی اجرا نمی‌شود.
    if group_id not in active_groups:
        return

    # دستور سکوت فقط برای مدیرها و فقط به‌صورت ریپلای است.
    if text == "سکوت":
        if not await is_group_admin(group_id, user_id):
            return

        reply_id = getattr(message, "reply_to_message_id", None)
        if not reply_id:
            await message.reply("⚠️ روی پیام کاربر ریپلای کن و بنویس: سکوت")
            return

        target_id = message_cache.get(group_id, {}).get(str(reply_id))
        if not target_id:
            await message.reply(
                "⚠️ کاربر این پیام در حافظه ربات پیدا نشد. روی پیامی ریپلای کن که ربات قبلاً دیده باشد."
            )
            return

        # مدیران را نمی‌شود با این دستور ساکت کرد.
        if await is_group_admin(group_id, target_id):
            await message.reply("⛔ مدیران گروه قابل سکوت نیستند.")
            return

        try:
            # در کتابخانه Rubka، restrict_chat_member برای محدود کردن عضو وجود دارد.
            # until=0 برای محدودیت بدون زمان پایان استفاده می‌شود.
            result = await bot_instance.restrict_chat_member(
                group_id,
                target_id,
                until=0,
            )
        except Exception as exc:
            print(f"[RESTRICT ERROR] {exc}")
            await message.reply(
                "❌ سکوت انجام نشد. دسترسی‌های ادمینی ربات را بررسی کن؛ "
                "ربات باید امکان مدیریت/محدودکردن اعضا را داشته باشد."
            )
            return

        if isinstance(result, dict) and str(result.get("status", "OK")) not in {"OK", ""}:
            await message.reply("❌ روبیکا درخواست سکوت را نپذیرفت. دسترسی‌های ربات را بررسی کن.")
            return

        muted_users.setdefault(group_id, set()).add(target_id)
        save_state()
        await message.reply("✅ کاربر سکوت شد.")


if __name__ == "__main__":
    print("🤖 RP Group Manager is starting...", flush=True)

    print("🔌 در حال اتصال به روبیکا...", flush=True)

    try:
        bot.run()
    except Exception as exc:
        print(f"❌ خطای اجرای ربات: {exc}", flush=True)
        raise
