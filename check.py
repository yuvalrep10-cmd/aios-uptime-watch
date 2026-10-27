"""שומר חיצוני לאפליקציית הבריאות - רץ ב-GitHub Actions, מחוץ לבית.

בודק את הכתובת הציבורית (דף ציבורי של הנתב, 200 = המחשב, Tailscale והנתב חיים).
שתי בדיקות רצופות שנכשלו = הודעת טלגרם אחת. חזרה = הודעה אחת עם משך הנפילה.
הכתובת, הטוקן ומזהה הצ'אט הם סודות של המאגר - לא כתובים בקוד.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

URL = os.environ["WATCH_URL"]
TOKEN = os.environ["TG_TOKEN"]
CHAT = os.environ["TG_CHAT"]
STATE = "state.json"
FAILS_TO_ALERT = 2
IL = ZoneInfo("Asia/Jerusalem")


def probe():
    last = ""
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "aios-uptime-watch"})
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200:
                    return True, ""
                last = f"HTTP {r.status}"
        except Exception as e:  # noqa: BLE001
            last = type(e).__name__ + (f" {getattr(e, 'code', '')}" if hasattr(e, "code") else "")
        if attempt < 2:
            time.sleep(20)
    return False, last.strip()


def send(text):
    data = json.dumps({"chat_id": CHAT, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status == 200


def hhmm(iso):
    return datetime.fromisoformat(iso).astimezone(IL).strftime("%d.%m %H:%M")


def dur(a, b):
    m = int((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() // 60)
    h, m = divmod(m, 60)
    return f"{h} שעות ו-{m} דקות" if h else f"{m} דקות"


def main():
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        st = {"state": "up", "since": None, "fails": 0, "first_fail": None}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ok, why = probe()
    before = json.dumps(st, sort_keys=True)

    if ok:
        if st["state"] == "down":
            send("✅ אפליקציית הבריאות חזרה לעבוד.\n"
                 f"הייתה למטה בערך {dur(st['since'], now)} (מ-{hhmm(st['since'])}).")
            st.update(state="up", since=now)
        st.update(fails=0, first_fail=None)
    else:
        st["fails"] = min(st.get("fails", 0) + 1, FAILS_TO_ALERT)
        st["first_fail"] = st.get("first_fail") or now
        if st["state"] == "up" and st["fails"] >= FAILS_TO_ALERT:
            send("🔴 אפליקציית הבריאות לא עונה מבחוץ מאז "
                 f"{hhmm(st['first_fail'])} בערך.\n"
                 "כנראה הנייח כבוי או בלי חשמל/אינטרנט (הבדיקה רצה מחוץ לבית).\n"
                 f"פרט טכני: {why or 'אין תשובה'}")
            st.update(state="down", since=st["first_fail"])

    # שמירה על פעילות במאגר - GitHub מכבה תזמון במאגר ציבורי בלי פעילות 60 יום
    last = st.get("touched")
    if not last or datetime.fromisoformat(now) - datetime.fromisoformat(last) > timedelta(days=20):
        st["touched"] = now

    if json.dumps(st, sort_keys=True) != before:
        json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("changed")
    print("ok" if ok else f"fail: {why}")


if __name__ == "__main__":
    sys.exit(main())
