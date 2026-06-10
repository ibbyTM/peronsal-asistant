import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import bot
import memory

load_dotenv()

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

class TradeRequest(BaseModel):
    symbol: str
    direction: str
    entry: float
    exit_price: float
    size: float
    notes: str = ""
    followed_rules: bool = True

class TaskRequest(BaseModel):
    title: str
    priority: str = "medium"

class RulesRequest(BaseModel):
    rules: list


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(req: ChatRequest):
    msg = req.message.strip()
    if not msg:
        raise HTTPException(400, "Empty message")
    if msg.startswith("/"):
        result = bot.handle_command(msg)
        if result == "__TRADE_LOG__":
            return {"type": "trade_form"}
        return {"type": "command", "text": result}
    reply = bot.chat(msg)
    return {"type": "message", "text": reply}


@app.get("/api/tasks")
def get_tasks():
    return memory.get_tasks()


@app.post("/api/tasks")
def add_task(req: TaskRequest):
    task = memory.add_task(req.title, req.priority)
    return task


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: int):
    if memory.complete_task(task_id):
        return {"ok": True}
    raise HTTPException(404, "Task not found")


@app.get("/api/journal")
def get_journal():
    return memory.get_journal(20)


@app.post("/api/trade")
def log_trade(req: TradeRequest):
    trade = memory.log_trade(
        req.symbol, req.direction, req.entry,
        req.exit_price, req.size, req.notes, req.followed_rules
    )
    return trade


@app.get("/api/stats")
def get_stats():
    return memory.get_stats()


@app.get("/api/rules")
def get_rules():
    return memory.get_trading_rules()


@app.post("/api/rules")
def set_rules(req: RulesRequest):
    memory.set_trading_rules(req.rules)
    return {"ok": True}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
