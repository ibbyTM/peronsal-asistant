import anthropic
import memory
from datetime import datetime

MODEL = "claude-haiku-4-5-20251001"
SUMMARIZE_AFTER = 16
client = anthropic.Anthropic()

AGENTS = {
    "accountability": {
        "name": "Ace",
        "subtitle": "Accountability",
        "color": "#7c6ef5",
        "emoji": "🎯",
        "system": """You are Ace — a direct accountability partner and friend.

- Talk like a real person texting, not an assistant writing an essay
- Keep it SHORT. 1-3 sentences max unless detail is genuinely needed
- No bullet points for simple responses. No headers. Just talk.
- Call out excuses once, clearly, then move on
- Ask one follow-up question max
- You have persistent memory across sessions — never say you won't remember

Be real. Be brief. Be useful."""
    },
    "trading": {
        "name": "Rex",
        "subtitle": "Trading",
        "color": "#f5a623",
        "emoji": "📈",
        "system": """You are Rex — a trading coach and journal partner.

- Short and direct. Talk like a trader, not a textbook.
- 1-3 sentences for most replies. Use bullets only when listing multiple data points.
- Always ask about rule adherence on every trade — no exceptions
- Zero tolerance for revenge trading excuses, but stay human about it
- You have persistent memory of every trade, rule, and P&L ever logged

Keep it tight."""
    },
    "therapy": {
        "name": "Sage",
        "subtitle": "Therapy",
        "color": "#4ec9a0",
        "emoji": "🌿",
        "system": """You are Sage — a calm, warm mental wellness companion.

- Short responses feel more human. 2-4 sentences usually. Go longer only when they need it.
- Validate first, always. Then one gentle question or reflection.
- No lists. No headers. Just warm, natural conversation.
- You have persistent memory — you remember their journey across sessions

Be present. Be real."""
    },
    "general": {
        "name": "Kai",
        "subtitle": "General",
        "color": "#60a5fa",
        "emoji": "⚡",
        "system": """You are Kai — a smart, quick assistant and friend.

- Match the user's energy. Short question = short answer.
- Talk like a friend, not a corporate chatbot.
- Only go long when the topic actually needs it.
- You have persistent memory across sessions

Fast. Sharp. Human."""
    }
}


def build_shared_context(agent_id: str) -> str:
    """Inject summaries from ALL other agents so every agent knows what was shared elsewhere."""
    other_summaries = []
    for aid in AGENTS:
        if aid == agent_id:
            continue
        summary = memory.get_agent_summary(aid)
        if summary:
            name = AGENTS[aid]["name"]
            other_summaries.append(f"[From {name}'s conversations]\n{summary}")
    return "\n\n".join(other_summaries)


def build_trading_context(agent_id: str) -> str:
    if agent_id not in ("trading", "accountability"):
        return ""
    today = datetime.now().strftime("%A, %B %d, %Y")
    stats = memory.get_stats()
    rules = memory.get_trading_rules()
    tasks = memory.get_tasks()
    parts = [f"Today: {today}"]
    if stats["total_trades"] > 0:
        parts.append(
            f"Trading — Trades: {stats['total_trades']}, Win rate: {stats['win_rate']}%, "
            f"P&L: ${stats['total_pnl']}, Streak: {stats['streak']}"
        )
    if rules:
        parts.append("Rules: " + "; ".join(rules))
    if tasks:
        titles = [t["title"] for t in tasks[:5]]
        parts.append(f"Pending tasks: " + ", ".join(titles))
    return "\n".join(parts)


def maybe_summarize(agent_id: str) -> None:
    history = memory.get_agent_history(agent_id)
    if len(history) < SUMMARIZE_AFTER:
        return
    old = history[:-6]
    if not old:
        return
    existing = memory.get_agent_summary(agent_id)
    prompt = "Summarize this conversation in 3-5 bullet points capturing key topics, emotions, decisions, and anything important to remember about this person:"
    if existing:
        prompt += f"\n\nPrevious summary:\n{existing}\n\nNew messages:"
    text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in old)
    resp = client.messages.create(
        model=MODEL, max_tokens=400,
        messages=[{"role": "user", "content": f"{prompt}\n\n{text}"}]
    )
    memory.update_agent_summary(agent_id, resp.content[0].text, keep_last=6)


def chat(agent_id: str, user_message: str) -> str:
    if agent_id not in AGENTS:
        agent_id = "general"

    memory.add_agent_message(agent_id, "user", user_message)
    maybe_summarize(agent_id)

    history = memory.get_agent_history(agent_id)
    summary = memory.get_agent_summary(agent_id)
    context = build_trading_context(agent_id)

    agent = AGENTS[agent_id]
    shared = build_shared_context(agent_id)
    system = agent["system"]
    if context:
        system += f"\n\n[Live context]\n{context}"
    if summary:
        system += f"\n\n[Your conversation memory]\n{summary}"
    if shared:
        system += f"\n\n[What the user shared with other agents — use this to know them better]\n{shared}"

    resp = client.messages.create(
        model=MODEL, max_tokens=300,
        system=system, messages=history
    )
    reply = resp.content[0].text
    memory.add_agent_message(agent_id, "assistant", reply)
    return reply
