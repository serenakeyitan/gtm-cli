"""Interactive account selector — always asks the user.

When a user has multiple accounts on the same platform,
this module shows the list and asks them to pick.

When an account fails, it asks: rotate or stop?
"""

from __future__ import annotations

import logging
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from gtm.identity.manager import Identity, IdentityManager

log = logging.getLogger(__name__)
console = Console()

ROLE_CHOICES = ["brand", "organic", "supporter", "scout", "default"]


def select_account(
    mgr: IdentityManager,
    platform: str,
    as_flag: str | None = None,
    interactive: bool = True,
) -> Identity:
    """Select which account to use for a platform action.

    Flow:
    1. If --as flag provided → use that specific account
    2. If only 1 account on platform → use it (no need to ask)
    3. If multiple accounts → show list, ask user to pick

    Args:
        mgr: IdentityManager instance
        platform: "twitter", "reddit", "hn"
        as_flag: value of --as flag (None if not provided)
        interactive: if False, use first available (for non-interactive/agent use)

    Returns:
        Selected Identity

    Raises:
        ValueError if no accounts available
    """
    # --as flag: explicit selection by name OR by role
    if as_flag:
        # Check if it's a role name (brand, organic, supporter, scout)
        if as_flag in ROLE_CHOICES:
            return _select_by_role(mgr, platform, as_flag, interactive)
        return mgr.get(as_flag)

    accounts = mgr.list_platform(platform)
    healthy = [a for a in accounts if a.status in ("healthy", "warning")]

    if not healthy:
        if accounts:
            raise ValueError(
                f"All {platform} accounts are expired/suspended. "
                f"Run: gtm auth {platform}"
            )
        raise ValueError(f"No {platform} account connected. Run: gtm auth {platform}")

    # Only 1 account → use it
    if len(healthy) == 1:
        return healthy[0]

    # Multiple accounts — ask user
    if not interactive:
        return healthy[0]  # non-interactive: use first

    return _prompt_account_selection(healthy, platform)


def _select_by_role(
    mgr: IdentityManager,
    platform: str,
    role: str,
    interactive: bool = True,
) -> Identity:
    """Select an account by role. Picks the healthiest, least-recently-used."""
    accounts = mgr.list_platform(platform)
    matching = [a for a in accounts if a.role == role and a.status in ("healthy", "warning")]

    if not matching:
        raise ValueError(
            f"No healthy {platform} account with role '{role}'. "
            f"Available roles: {set(a.role for a in accounts) or 'none'}"
        )

    if len(matching) == 1:
        return matching[0]

    # Sort by: healthy first, then least-recently-used
    def sort_key(a: Identity):
        health = 0 if a.status == "healthy" else 1
        last = a.last_used or "0000"
        return (health, last)

    matching.sort(key=sort_key)

    if not interactive:
        return matching[0]

    # Multiple matches — ask user
    console.print(f"\n  [bold]{len(matching)} '{role}' accounts on {platform}:[/bold]")
    return _prompt_account_selection(matching, platform)


def _prompt_account_selection(accounts: list[Identity], platform: str) -> Identity:
    """Show account list and ask user to pick."""
    console.print(f"\n  [bold]Multiple {platform} accounts available:[/bold]\n")

    table = Table(show_header=True)
    table.add_column("#", style="bold", width=3)
    table.add_column("Account", style="cyan")
    table.add_column("Role")
    table.add_column("Status")
    table.add_column("Last Used", style="dim")

    for i, acct in enumerate(accounts, 1):
        status = {"healthy": "[green]✅ OK[/green]", "warning": "[yellow]⚠️[/yellow]"}.get(acct.status, acct.status)
        last = acct.last_used[:10] if acct.last_used else "never"
        table.add_row(str(i), acct.name, acct.role, status, last)

    console.print(table)

    choice = click.prompt(
        "  Which account?",
        type=click.IntRange(1, len(accounts)),
        default=1,
    )
    selected = accounts[choice - 1]
    console.print(f"  → Using [bold]{selected.name}[/bold]\n")
    return selected


def handle_account_failure(
    failed_identity: Identity,
    mgr: IdentityManager,
    platform: str,
    error: str,
    interactive: bool = True,
) -> Identity | None:
    """When an account fails, ask the user what to do.

    Options:
    1. Try another account (shows list of healthy alternatives)
    2. Stop and fix the failed account

    Returns:
        Alternative Identity to try, or None to stop.
    """
    console.print(f"\n  [red]❌ Account failed: {failed_identity.name}[/red]")
    console.print(f"  Error: {error}\n")

    if not interactive:
        return None  # non-interactive: stop on failure

    # Find alternatives
    all_accounts = mgr.list_platform(platform)
    alternatives = [
        a for a in all_accounts
        if a.name != failed_identity.name and a.status in ("healthy", "warning")
    ]

    if not alternatives:
        console.print("  No other healthy accounts available.")
        console.print(f"  Fix this account: [bold]gtm auth {platform}[/bold]")
        return None

    console.print(f"  {len(alternatives)} other account(s) available.\n")
    action = click.prompt(
        "  What do you want to do?",
        type=click.Choice(["rotate", "stop"]),
        default="rotate",
    )

    if action == "stop":
        console.print(f"  Stopped. Fix the account: [bold]gtm auth {platform}[/bold]")
        return None

    # Let user pick which alternative
    return _prompt_account_selection(alternatives, platform)


def prompt_role(username: str) -> str:
    """Ask user what role this account serves during auth."""
    console.print(f"\n  What role does [bold]{username}[/bold] serve?\n")
    console.print("    [bold]brand[/bold]      — your main/official account")
    console.print("    [bold]organic[/bold]    — looks like a real person, casual posting")
    console.print("    [bold]supporter[/bold]  — likes, retweets, engagement")
    console.print("    [bold]scout[/bold]      — read-only, used for scraping/monitoring")
    console.print("    [bold]default[/bold]    — no specific role\n")

    role = click.prompt(
        "  Role",
        type=click.Choice(ROLE_CHOICES),
        default="default",
    )
    return role
