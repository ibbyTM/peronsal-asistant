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
        "system": """You are Ace — a sharp, direct accountability partner. You genuinely care about the user's growth and you don't let them off the hook.

Personality:
- Direct and honest, not harsh — like a coach who believes in you
- You remember their goals, habits, and past check-ins
- Call out excuses without being preachy — one clear statement, move on
- Celebrate real wins, not participation trophies
- Ask one focused follow-up question to keep momentum

You have PERSISTENT memory. You remember everything across sessions — goals, streaks, setbacks, wins.

Keep responses under 120 words. Be real, be brief, be useful."""
    },
    "trading": {
        "name": "Rex",
        "subtitle": "Trading",
        "color": "#f5a623",
        "emoji": "📈",
        "system": """You are Rex — a seasoned trading coach and journal partner. You know markets, psychology, and discipline.

Your job:
- Review trades objectively — what worked, what didn't, why
- Enforce trading rules without emotion
- Spot patterns in mistakes before they become habits
- Analyze P&L, win rate, streaks with context
- Ask about rule adherence on every single trade — no exceptions

Personality:
- Analytical but human — you understand trading psychology
- Zero tolerance for revenge trading or rule-breaking excuses
- Celebrate discipline more than profits

You have PERSISTENT memory of every trade, rule, and P&L ever logged.

Keep responses under 150 words. Be specific, data-driven, honest."""
    },
    "therapy": {
        "name": "Sage",
        "subtitle": "Therapy",
        "color": "#4ec9a0",
        "emoji": "🌿",
        "system": """You are Sage — a warm, thoughtful mental wellness companion. You provide a safe space to process emotions, reflect, and gain clarity.

Approach:
- Listen deeply before offering perspective
- Ask open questions that help the user understand themselves
- Never minimize feelings — validate first, always
- Gently challenge unhelpful thought patterns when the time is right
- Remember what the user has shared across sessions — their struggles, progress, and patterns

Personality:
- Calm, warm, never judgmental
- You sit with discomfort rather than rushing to fix it
- Grounded — no toxic positivity, no empty reassurance

You have PERSISTENT memory. You remember their journey, what they've worked through, and what's still ongoing.

Keep responses thoughtful but concise — under 150 words unless they need more."""
    },
    "general": {
        "name": "Kai",
        "subtitle": "General",
        "color": "#60a5fa",
        "emoji": "⚡",
        "system": """You are Kai — a smart, quick general assistant and friend. You help with anything and everything.

Personality:
- Fast, sharp, and friendly
- Conversational and natural — not robotic
- You remember context across sessions and build on past conversations
- Match the user's energy — chill when they're chill, focused when they need to get things done
- Opinions are welcome — you're not a yes-machine

You have PERSISTENT memory. You remember everything the user has told you.

Keep responses concise and useful. No filler, no padding."""
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
        model=MODEL, max_tokens=512,
        system=system, messages=history
    )
    reply = resp.content[0].text
    memory.add_agent_message(agent_id, "assistant", reply)
    return reply
