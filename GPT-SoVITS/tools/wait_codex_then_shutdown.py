"""Watch codex++ agent task; shutdown when it goes idle (or exits / timeout).
Idle rule: newest rollout jsonl under ~/.codex/sessions not modified for 5 min.
Fallback: codex-plus-plus.exe gone, or 120 min hard cap. Then shutdown /s /t 60.
"""
import subprocess
import time
from pathlib import Path

SESSIONS = Path.home() / ".codex" / "sessions"
APP = "codex-plus-plus.exe"
IDLE_SEC = 300
CAP_SEC = 120 * 60
POLL = 60


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def app_alive():
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {APP}"],
                         capture_output=True, text=True).stdout
    return APP.lower() in out.lower()


def newest_rollout():
    best = None
    try:
        for f in SESSIONS.rglob("*.jsonl"):
            if best is None or f.stat().st_mtime > best.stat().st_mtime:
                best = f
    except Exception:
        pass
    return best


def main():
    start = time.time()
    log("watching codex++ ...")
    while True:
        waited = time.time() - start
        alive = app_alive()
        f = newest_rollout()
        mtime = f.stat().st_mtime if f else 0
        idle = time.time() - mtime
        log(f"waited={waited:.0f}s alive={alive} idle={idle:.0f}s file={f.name if f else None}")
        if not alive:
            log("codex++ exited -> shutdown")
            break
        if idle >= IDLE_SEC:
            log("rollout idle >= 5min -> shutdown")
            break
        if waited >= CAP_SEC:
            log("hard cap 120min -> shutdown")
            break
        time.sleep(POLL)
    subprocess.run(["shutdown", "/s", "/t", "60", "/c",
                    "Sia-ai: codex++ done, auto shutdown"], capture_output=True)
    log("shutdown scheduled (60s)")


if __name__ == "__main__":
    main()
