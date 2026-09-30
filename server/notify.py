"""Alert subscriptions and a MOCK SMS/email provider.

No real messages are sent. `send()` logs a masked message to the server console.
To go live, replace `send()` with a call to an SMS gateway (e.g. Twilio, MSG91)
and an email service, and run a scheduler that calls forecast_bundle() per
subscription.
"""
import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("kisanmausam.notify")
STORE = Path(__file__).parent / "subscriptions.json"
_lock = threading.Lock()
PHONE = re.compile(r"^(?:\+?91)?([6-9]\d{9})$")
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def normalize_contact(channel, contact):
    contact = (contact or "").strip().replace(" ", "").replace("-", "")
    if channel == "sms":
        m = PHONE.match(contact)
        if not m:
            raise ValueError("Enter a valid 10-digit Indian mobile number.")
        return "+91" + m.group(1)
    if channel == "email":
        if not EMAIL.match(contact):
            raise ValueError("Enter a valid email address.")
        return contact.lower()
    raise ValueError("Unknown channel.")


def mask(contact):
    return contact[:3] + "*" * max(0, len(contact) - 6) + contact[-3:] if "@" not in contact else \
        contact[0] + "***@" + contact.split("@")[1]


def compose(name, alerts, lang="en", limit=300):
    """Short text message for the most severe upcoming alerts."""
    hi = lang == "hi"
    if not alerts:
        body = "अगले 3 दिन कोई चेतावनी नहीं।" if hi else "No warnings for the next 3 days."
    else:
        top = sorted(alerts, key=lambda a: (-{"info": 0, "watch": 1, "warning": 2, "danger": 3}[a["severity"]], a["valid_from"]))[0]
        title = top["title_hi"] if hi else top["title_en"]
        msg = top["message_hi"] if hi else top["message_en"]
        body = f"{title} ({top['valid_from'][5:]}): {msg}"
    text = f"KisanMausam - {name}: {body}"
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def send(channel, contact, text):
    log.info("[MOCK %s to %s] %s", channel.upper(), mask(contact), text)


def _load():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def subscribe(record):
    with _lock:
        items = [s for s in _load() if not (s["contact"] == record["contact"] and s["code"] == record["code"])]
        record["created"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        items.append(record)
        tmp = STORE.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(STORE)


def unsubscribe(contact, code):
    with _lock:
        items = _load()
        kept = [s for s in items if not (s["contact"] == contact and s["code"] == code)]
        if len(kept) != len(items):
            tmp = STORE.with_suffix(".tmp")
            tmp.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(STORE)
        return len(items) - len(kept)
