#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text
import bot
import memory

load_dotenv()

console = Console()


def prompt_trade_log() -> str:
    console.print("[bold cyan]Log a Trade[/bold cyan]")
    symbol = Prompt.ask("  Symbol (e.g. EURUSD, AAPL)")
    direction = Prompt.ask("  Direction", choices=["long", "short"])
    try:
        entry = float(Prompt.ask("  Entry price"))
        exit_price = float(Prompt.ask("  Exit price"))
        size = float(Prompt.ask("  Position size"))
    except ValueError:
        return "[red]Invalid price/size input.[/red]"
    notes = Prompt.ask("  Notes (optional)", default="")
    followed = Prompt.ask("  Followed your rules?", choices=["yes", "no"]) == "yes"
    trade = memory.log_trade(symbol, direction, entry, exit_price, size, notes, followed)
    pnl_color = "green" if trade["pnl"] >= 0 else "red"
    result = (
        f"[bold]Trade logged![/bold] {trade['symbol']} {trade['direction'].upper()} "
        f"[{pnl_color}]${trade['pnl']:+.2f}[/{pnl_color}]"
    )
    if not followed:
        result += "\n[bold red]You broke your rules. We need to talk about that.[/bold red]"
    return result


def print_welcome():
    text = Text()
    text.append("Ace", style="bold cyan")
    text.append(" — your accountability partner & friend\n", style="dim")
    text.append("Type ", style="dim")
    text.append("/help", style="bold yellow")
    text.append(" for commands, or just chat.", style="dim")
    console.print(Panel(text, border_style="cyan"))


def run():
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[bold red]Error:[/bold red] ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    print_welcome()

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Later! Stay disciplined.[/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            console.print("[dim]Later! Stay disciplined.[/dim]")
            break

        if user_input.startswith("/"):
            result = bot.handle_command(user_input)
            if result == "__TRADE_LOG__":
                result = prompt_trade_log()
            console.print(f"\n[bold green]Ace[/bold green]: {result}")
        else:
            with console.status("[dim]thinking...[/dim]", spinner="dots"):
                reply = bot.chat(user_input)
            console.print(f"\n[bold green]Ace[/bold green]: {reply}")


if __name__ == "__main__":
    run()
