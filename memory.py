import json
import os
from datetime import datetime

DATA_FILE = os.getenv("DATA_FILE", "data.json")
REDIS_URL = os.getenv("REDIS_URL")
REDIS_KEY = "ace:data"

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
    "conversation_history": [],
    "conversation_summary": "",
    "stats": {
        "total_trades": 0,
        "winning_trades": 0,
        "total_pnl": 0.0,
        "streak": 0,
        "last_check_in": None
    }
}

def load() -> dict:
    r = _get_redis()
    if r:
        raw = r.get(REDIS_KEY)
        data = json.loads(raw) if raw else {}
    elif os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}
    for key, val in DEFAULT_DATA.items():
        if key not in data:
            data[key] = val
    return data

def save(data: dict) -> None:
    r = _get_redis()
    if r:
        r.set(REDIS_KEY, json.dumps(data, default=str))
    else:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)

def add_task(title: str, priority: str = "medium") -> dict:
    data = load()
    task = {
        "id": len(data["tasks"]) + 1,
        "title": title,
        "priority": priority,
        "done": False,
        "created": datetime.now().isoformat()
    }
    data["tasks"].append(task)
    save(data)
    return task

def complete_task(task_id: int) -> bool:
    data = load()
    for task in data["tasks"]:
        if task["id"] == task_id and not task["done"]:
            task["done"] = True
            task["completed"] = datetime.now().isoformat()
            save(data)
            return True
    return False

def get_tasks(include_done: bool = False) -> list:
    data = load()
    if include_done:
        return data["tasks"]
    return [t for t in data["tasks"] if not t["done"]]

def log_trade(symbol: str, direction: str, entry: float, exit_price: float,
              size: float, notes: str = "", followed_rules: bool = True) -> dict:
    data = load()
    pnl = (exit_price - entry) * size if direction.lower() == "long" else (entry - exit_price) * size
    trade = {
        "id": len(data["journal"]) + 1,
        "date": datetime.now().isoformat(),
        "symbol": symbol.upper(),
        "direction": direction.lower(),
        "entry": entry,
        "exit": exit_price,
        "size": size,
        "pnl": round(pnl, 2),
        "followed_rules": followed_rules,
        "notes": notes
    }
    data["journal"].append(trade)
    data["stats"]["total_trades"] += 1
    data["stats"]["total_pnl"] = round(data["stats"]["total_pnl"] + pnl, 2)
    if pnl > 0:
        data["stats"]["winning_trades"] += 1
        data["stats"]["streak"] = max(0, data["stats"].get("streak", 0)) + 1
    else:
        data["stats"]["streak"] = 0
    save(data)
    return trade

def get_journal(limit: int = 10) -> list:
    data = load()
    return data["journal"][-limit:]

def get_stats() -> dict:
    data = load()
    stats = data["stats"].copy()
    total = stats["total_trades"]
    stats["win_rate"] = round(stats["winning_trades"] / total * 100, 1) if total > 0 else 0.0
    return stats

def set_trading_rules(rules: list) -> None:
    data = load()
    data["trading_rules"] = rules
    save(data)

def get_trading_rules() -> list:
    data = load()
    return data["trading_rules"]

def add_message(role: str, content: str) -> None:
    data = load()
    data["conversation_history"].append({"role": role, "content": content})
    save(data)

def get_history() -> list:
    data = load()
    return data["conversation_history"]

def update_summary(summary: str, keep_last: int = 10) -> None:
    data = load()
    data["conversation_summary"] = summary
    data["conversation_history"] = data["conversation_history"][-keep_last:]
    save(data)

def get_summary() -> str:
    data = load()
    return data.get("conversation_summary", "")
