import json
import os
from datetime import datetime

DATA_FILE = os.getenv("DATA_FILE", "data.json")
REDIS_URL = os.getenv("REDIS_URL")
GLOBAL_KEY = "ace:data"

_redis = None

def _get_redis():
    global _redis
    if _redis is None and REDIS_URL:
        import redis
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


DEFAULT_DATA = {
    "tasks": [],
    "journal": [],
    "trading_rules": [],
    "stats": {
        "total_trades": 0,
        "winning_trades": 0,
        "total_pnl": 0.0,
        "streak": 0,
    },
    "agents": {
        "accountability": {"history": [], "summary": ""},
        "trading":        {"history": [], "summary": ""},
        "therapy":        {"history": [], "summary": ""},
        "general":        {"history": [], "summary": ""},
    }
}


def _rkey(key: str) -> str:
    return f"ace:{key}"


def load() -> dict:
    r = _get_redis()
    if r:
        raw = r.get(GLOBAL_KEY)
        data = json.loads(raw) if raw else {}
    elif os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            data = json.load(f)
    else:
        data = {}
    # fill missing keys
    for k, v in DEFAULT_DATA.items():
        if k not in data:
            data[k] = v
    for agent_id in DEFAULT_DATA["agents"]:
        if agent_id not in data["agents"]:
            data["agents"][agent_id] = {"history": [], "summary": ""}
    return data


def save(data: dict) -> None:
    r = _get_redis()
    if r:
        r.set(GLOBAL_KEY, json.dumps(data, default=str))
    else:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


# ── Tasks ──
def add_task(title: str, priority: str = "medium") -> dict:
    data = load()
    task = {"id": len(data["tasks"]) + 1, "title": title,
            "priority": priority, "done": False, "created": datetime.now().isoformat()}
    data["tasks"].append(task)
    save(data)
    return task


def complete_task(task_id: int) -> bool:
    data = load()
    for t in data["tasks"]:
        if t["id"] == task_id and not t["done"]:
            t["done"] = True
            t["completed"] = datetime.now().isoformat()
            save(data)
            return True
    return False


def get_tasks(include_done: bool = False) -> list:
    data = load()
    return data["tasks"] if include_done else [t for t in data["tasks"] if not t["done"]]


# ── Trading ──
def log_trade(symbol, direction, entry, exit_price, size, notes="", followed_rules=True) -> dict:
    data = load()
    pnl = (exit_price - entry) * size if direction.lower() == "long" else (entry - exit_price) * size
    trade = {
        "id": len(data["journal"]) + 1,
        "date": datetime.now().isoformat(),
        "symbol": symbol.upper(), "direction": direction.lower(),
        "entry": entry, "exit": exit_price, "size": size,
        "pnl": round(pnl, 2), "followed_rules": followed_rules, "notes": notes
    }
    data["journal"].append(trade)
    s = data["stats"]
    s["total_trades"] += 1
    s["total_pnl"] = round(s["total_pnl"] + pnl, 2)
    if pnl > 0:
        s["winning_trades"] += 1
        s["streak"] = s.get("streak", 0) + 1
    else:
        s["streak"] = 0
    save(data)
    return trade


def get_journal(limit: int = 20) -> list:
    return load()["journal"][-limit:]


def get_stats() -> dict:
    s = load()["stats"].copy()
    total = s["total_trades"]
    s["win_rate"] = round(s["winning_trades"] / total * 100, 1) if total > 0 else 0.0
    return s


def set_trading_rules(rules: list) -> None:
    data = load()
    data["trading_rules"] = rules
    save(data)


def get_trading_rules() -> list:
    return load()["trading_rules"]


# ── Per-agent conversation memory ──
def get_agent_history(agent_id: str) -> list:
    return load()["agents"].get(agent_id, {}).get("history", [])


def get_agent_summary(agent_id: str) -> str:
    return load()["agents"].get(agent_id, {}).get("summary", "")


def add_agent_message(agent_id: str, role: str, content: str) -> None:
    data = load()
    if agent_id not in data["agents"]:
        data["agents"][agent_id] = {"history": [], "summary": ""}
    data["agents"][agent_id]["history"].append({"role": role, "content": content})
    save(data)


def update_agent_summary(agent_id: str, summary: str, keep_last: int = 6) -> None:
    data = load()
    if agent_id not in data["agents"]:
        data["agents"][agent_id] = {"history": [], "summary": ""}
    data["agents"][agent_id]["summary"] = summary
    data["agents"][agent_id]["history"] = data["agents"][agent_id]["history"][-keep_last:]
    save(data)


def clear_agent_history(agent_id: str) -> None:
    data = load()
    if agent_id in data["agents"]:
        data["agents"][agent_id] = {"history": [], "summary": ""}
    save(data)


# legacy shims so main.py / old bot.py don't break
def add_message(role, content): add_agent_message("accountability", role, content)
def get_history(): return get_agent_history("accountability")
def get_summary(): return get_agent_summary("accountability")
def update_summary(summary, keep_last=6): update_agent_summary("accountability", summary, keep_last)
