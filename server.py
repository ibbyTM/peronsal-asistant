import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import agents
import memory

load_dotenv()

app = FastAPI()

class ChatRequest(BaseModel):
    message: str
    agent_id: str = "accountability"

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


@app.get("/api/agents")
def get_agents():
    return [
        {"id": k, "name": v["name"], "subtitle": v["subtitle"],
         "color": v["color"], "emoji": v["emoji"]}
        for k, v in agents.AGENTS.items()
    ]


@app.post("/api/chat")
def chat(req: ChatRequest):
    msg = req.message.strip()
    if not msg:
        raise HTTPException(400, "Empty message")
    reply = agents.chat(req.agent_id, msg)
    return {"text": reply}


@app.get("/api/tasks")
def get_tasks():
    return memory.get_tasks()


@app.post("/api/tasks")
def add_task(req: TaskRequest):
    return memory.add_task(req.title, req.priority)


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: int):
    if memory.complete_task(task_id):
        return {"ok": True}
    raise HTTPException(404, "Task not found")


@app.get("/api/journal")
def get_journal():
    return memory.get_journal(30)


@app.post("/api/trade")
def log_trade(req: TradeRequest):
    return memory.log_trade(
        req.symbol, req.direction, req.entry,
        req.exit_price, req.size, req.notes, req.followed_rules
    )


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


@app.post("/api/agents/{agent_id}/clear")
def clear_history(agent_id: str):
    memory.clear_agent_history(agent_id)
    return {"ok": True}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
