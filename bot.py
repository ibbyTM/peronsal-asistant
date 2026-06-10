import anthropic
import memory
from datetime import datetime

MODEL = "claude-haiku-4-5-20251001"
MAX_HISTORY = 20
SUMMARIZE_AFTER = 16

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are Ace — a personal AI friend and accountability partner. You're direct, warm, and genuinely invested in the user's growth.

Your roles:
1. FRIEND: Chat naturally, remember context, be supportive but real. No sugarcoating.
2. TASK MANAGER: Help track and prioritize tasks. Push the user to follow through.
3. TRADING ACCOUNTABILITY PARTNER: Know their trading journey. Call them out when they break rules. Celebrate discipline.

Personality:
- Talk like a real friend, not a corporate assistant
- Be concise — no walls of text
- You have PERSISTENT memory — all conversations, trades, tasks, and rules are saved to a database. You WILL remember everything across sessions. Never tell the user you won't remember them.
- Ask follow-up questions when needed
- Hold the line on accountability: if they broke a rule, say so directly
- Celebrate wins, analyze losses constructively

Trading context you track:
- Their rules, P&L, win rate, current streak
- Whether they followed their rules on each trade
- Patterns in their mistakes

When discussing trades, always ask: did they follow their rules? If not, don't let it slide.

Keep responses focused and under 150 words unless detail is genuinely needed."""


def build_context_block() -> str:
    stats = memory.get_stats()
    rules = memory.get_trading_rules()
    tasks = memory.get_tasks()
    today = datetime.now().strftime("%A, %B %d, %Y")

    parts = [f"Today: {today}"]

    if stats["total_trades"] > 0:
        parts.append(
            f"Trading stats — Trades: {stats['total_trades']}, "
            f"Win rate: {stats['win_rate']}%, "
            f"Total P&L: ${stats['total_pnl']}, "
            f"Current streak: {stats['streak']}"
        )

    if rules:
        parts.append("Trading rules: " + "; ".join(rules))

    pending = [t["title"] for t in tasks]
    if pending:
        parts.append(f"Pending tasks ({len(pending)}): " + ", ".join(pending[:5]))

    return "\n".join(parts)


def maybe_summarize() -> None:
    history = memory.get_history()
    if len(history) < SUMMARIZE_AFTER:
        return

    old_messages = history[:-6]
    if not old_messages:
        return

    existing_summary = memory.get_summary()
    summary_prompt = "Summarize this conversation history in 3-5 bullet points, capturing key topics, decisions, and anything important about the user's tasks and trading:"
    if existing_summary:
        summary_prompt += f"\n\nPrevious summary:\n{existing_summary}\n\nNew messages to incorporate:"

    messages_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in old_messages
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": f"{summary_prompt}\n\n{messages_text}"}]
    )
    new_summary = response.content[0].text
    memory.update_summary(new_summary, keep_last=6)


def chat(user_message: str) -> str:
    memory.add_message("user", user_message)
    maybe_summarize()

    history = memory.get_history()
    summary = memory.get_summary()
    context = build_context_block()

    system = SYSTEM_PROMPT
    if context:
        system += f"\n\n[Current context]\n{context}"
    if summary:
        system += f"\n\n[Conversation summary]\n{summary}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=system,
        messages=history
    )

    reply = response.content[0].text
    memory.add_message("assistant", reply)
    return reply


def handle_command(cmd: str) -> str:
    parts = cmd.strip().lstrip("/").split(None, 2)
    if not parts:
        return "Unknown command. Type /help for options."

    action = parts[0].lower()

    if action == "help":
        return (
            "[bold]Commands:[/bold]\n"
            "  /task add <title>       — Add a task\n"
            "  /task done <id>         — Mark task complete\n"
            "  /task list              — List pending tasks\n"
            "  /trade log              — Log a trade (interactive)\n"
            "  /journal                — Show recent trades\n"
            "  /stats                  — Trading stats\n"
            "  /rules set <r1>;<r2>    — Set trading rules\n"
            "  /rules show             — Show trading rules\n"
            "  /clear                  — Clear conversation history\n"
            "  /quit                   — Exit"
        )

    if action == "task":
        if len(parts) < 2:
            return "Usage: /task add <title> | /task done <id> | /task list"
        sub = parts[1].lower()
        if sub == "add" and len(parts) >= 3:
            task = memory.add_task(parts[2])
            return f"[green]Task #{task['id']} added:[/green] {task['title']}"
        elif sub == "done" and len(parts) >= 3:
            try:
                tid = int(parts[2])
                if memory.complete_task(tid):
                    return f"[green]Task #{tid} completed![/green]"
                return f"[yellow]Task #{tid} not found or already done.[/yellow]"
            except ValueError:
                return "Usage: /task done <id>"
        elif sub == "list":
            tasks = memory.get_tasks()
            if not tasks:
                return "[yellow]No pending tasks. You're clear![/yellow]"
            lines = [f"  #{t['id']} [{t['priority']}] {t['title']}" for t in tasks]
            return "[bold]Pending tasks:[/bold]\n" + "\n".join(lines)
        return "Usage: /task add <title> | /task done <id> | /task list"

    if action == "journal":
        trades = memory.get_journal(10)
        if not trades:
            return "[yellow]No trades logged yet.[/yellow]"
        lines = []
        for t in trades:
            date = t["date"][:10]
            rules = "✓" if t["followed_rules"] else "✗"
            pnl_color = "green" if t["pnl"] >= 0 else "red"
            lines.append(f"  {date} {t['symbol']} {t['direction'].upper()} [{pnl_color}]${t['pnl']:+.2f}[/{pnl_color}] rules:{rules}")
        return "[bold]Recent trades:[/bold]\n" + "\n".join(lines)

    if action == "stats":
        s = memory.get_stats()
        pnl_color = "green" if s["total_pnl"] >= 0 else "red"
        return (
            f"[bold]Trading Stats[/bold]\n"
            f"  Trades: {s['total_trades']}\n"
            f"  Win rate: {s['win_rate']}%\n"
            f"  Total P&L: [{pnl_color}]${s['total_pnl']:+.2f}[/{pnl_color}]\n"
            f"  Streak: {s['streak']} {'🔥' if s['streak'] >= 3 else ''}"
        )

    if action == "rules":
        if len(parts) < 2:
            return "Usage: /rules set <r1>;<r2> | /rules show"
        sub = parts[1].lower()
        if sub == "show":
            rules = memory.get_trading_rules()
            if not rules:
                return "[yellow]No trading rules set. Use /rules set <r1>;<r2>[/yellow]"
            return "[bold]Your trading rules:[/bold]\n" + "\n".join(f"  {i+1}. {r}" for i, r in enumerate(rules))
        elif sub == "set" and len(parts) >= 3:
            rules = [r.strip() for r in parts[2].split(";") if r.strip()]
            memory.set_trading_rules(rules)
            return f"[green]Set {len(rules)} trading rules.[/green]"

    if action == "clear":
        memory.update_summary("", keep_last=0)
        return "[yellow]Conversation history cleared.[/yellow]"

    if action == "trade" and len(parts) >= 2 and parts[1].lower() == "log":
        return "__TRADE_LOG__"

    return f"[yellow]Unknown command: /{action}. Type /help for options.[/yellow]"
