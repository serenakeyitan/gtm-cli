"""Click CLI entry point for growth-cli.

Command: `growth`

Terminal-native marketing automation.
Claude Code for marketers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from growth import __version__
from growth.config import (
    CONFIG_DIR,
    IDENTITIES_DIR,
    OUTPUT_DIR,
    ensure_dirs,
    GrowthConfig,
)

console = Console()

BURNER_WARNING = """
[bold yellow]⚠️  ACCOUNT SAFETY NOTICE[/bold yellow]

growth-cli automates actions on your social media accounts.
Built-in rate limits protect your accounts, but platform detection
is always a risk with any automation tool.

[bold]RECOMMENDATION:[/bold] Use dedicated/burner accounts, not your
personal accounts, for automated posting and engagement.

Future: growth-cli will offer pre-warmed accounts for purchase
so you don't need to risk any of your own.
"""


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Main Group ────────────────────────────────────────────────────────


@click.group()
@click.version_option(__version__)
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
@click.pass_context
def main(ctx, verbose):
    """growth-cli — Terminal-native marketing automation."""
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# ── Init ──────────────────────────────────────────────────────────────


@main.command()
def init():
    """Initialize growth-cli config directory."""
    ensure_dirs()
    config = GrowthConfig.load()
    config.save()

    # Initialize output as git repo
    output_dir = Path(config.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    git_dir = output_dir / ".git"
    if not git_dir.exists():
        import subprocess

        subprocess.run(["git", "init"], cwd=output_dir, capture_output=True)
        (output_dir / ".gitkeep").touch()
        subprocess.run(
            ["git", "add", ".gitkeep"],
            cwd=output_dir,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init: growth output initialized"],
            cwd=output_dir,
            capture_output=True,
        )

    console.print(f"\n✅ Config directory: {CONFIG_DIR}")
    console.print(f"✅ Identities:      {IDENTITIES_DIR}")
    console.print(f"✅ Output (git):     {output_dir}")
    console.print("\nNext: connect your first account with [bold]growth auth twitter[/bold]")

    # Check for old pipeline credentials to offer migration
    from growth.identity.migrate import OLD_SECRETS_DIR
    if OLD_SECRETS_DIR.exists():
        console.print(f"\n[dim]Found existing openclaw pipeline credentials at {OLD_SECRETS_DIR}[/dim]")
        console.print("[dim]Run [bold]growth migrate from-openclaw[/bold] to import them.[/dim]")

    # Show burner warning on first init
    if not config.burner_warning_shown:
        console.print(BURNER_WARNING)
        config.burner_warning_shown = True
        config.save()


# ── Auth ──────────────────────────────────────────────────────────────


@main.command()
@click.argument("platform", type=click.Choice(["twitter", "reddit", "hn"]))
@click.option("--username", "-u", help="Username for the account")
@click.option("--email", "-e", help="Email (Twitter only)")
@click.option("--stdin", "use_stdin", is_flag=True, hidden=True,
              help="Read credentials from stdin (for agent/non-interactive use)")
def auth(platform, username, email, use_stdin):
    """Connect a platform account.

    Credentials are prompted interactively by default.
    Use --stdin for non-interactive/agent flows (pipe credentials securely).
    """
    password = None
    ensure_dirs()

    # Import platform adapters to register them
    _ensure_platforms_registered()
    from growth.platforms.base import get_platform

    plat = get_platform(platform)

    if platform == "twitter":
        if not username:
            username = click.prompt("Twitter username (without @)")

        identity_dir = IDENTITIES_DIR / "twitter" / username

        if use_stdin:
            # Agent/non-interactive: read email + password from stdin
            import sys as _sys
            lines = _sys.stdin.read().strip().split("\n")
            email = email or (lines[0] if len(lines) > 0 else None)
            password = lines[1] if len(lines) > 1 else None
            console.print(f"\n  Logging in as @{username}...")
            try:
                metadata = asyncio.run(
                    plat.auth_interactive(
                        identity_dir, username=username, email=email, password=password,
                    )
                )
                _save_identity(platform, username, metadata)
                console.print(f"  [green]✅ Logged in![/green]")
            except Exception as e:
                console.print(f"  [red]❌ Login failed: {e}[/red]")
                sys.exit(1)
            return

        # Interactive flow: try browser first → fall back to cookie paste
        console.print(f"\n  Connecting Twitter account [bold]@{username}[/bold]")

        # Step 1: Try opening browser (smoothest — auto-grabs cookies)
        console.print("  Attempting to open Chrome...")
        if _auth_twitter_browser(username, identity_dir):
            return  # Success!

        # Step 2: Browser didn't work — fall back to cookie paste
        console.print("  [yellow]Chrome not available or timed out.[/yellow]")
        console.print("  No worries — let's grab cookies manually instead.\n")
        _auth_twitter_paste(username, identity_dir)

    elif platform in ("reddit", "hn"):
        platform_name = "Reddit" if platform == "reddit" else "Hacker News"
        if not username:
            username = click.prompt(f"{platform_name} username")

        identity_dir = IDENTITIES_DIR / platform / username

        if use_stdin:
            # Agent flow: expect cookie JSON on stdin
            import sys as _sys
            raw = _sys.stdin.read().strip()
            _auth_cookie_paste(platform, username, identity_dir, raw)
            return

        console.print(f"\n  Connecting {platform_name} account [bold]{username}[/bold]")

        method = click.prompt(
            "  Auth method",
            type=click.Choice(["browser", "cookies"]),
            default="cookies",
        )

        if method == "cookies":
            _auth_platform_cookie_paste(platform, platform_name, username, identity_dir)
        else:
            console.print(f"\n  Opening Chrome for {platform_name} login...")
            console.print("  Log in manually. Handle any CAPTCHA/2FA prompts.\n")
            try:
                metadata = asyncio.run(
                    plat.auth_interactive(identity_dir, username=username)
                )
                _save_identity(platform, username, metadata)
                console.print(f"  [green]✅ Login detected! Session saved.[/green]")
                console.print(f"     Identity: [bold]{platform}:{username}[/bold]")
            except Exception as e:
                console.print(f"  [red]❌ Login failed: {e}[/red]")
                console.print(f"\n  Try cookie auth instead:")
                console.print(f"    [bold]growth auth {platform} -u {username}[/bold]")
                sys.exit(1)


# ── Status ────────────────────────────────────────────────────────────


@main.command()
def status():
    """Show connected accounts and health."""
    from growth.identity.manager import IdentityManager
    from growth.safety.rate_limiter import get_rate_limiter

    mgr = IdentityManager()
    identities = mgr.list_all()

    if not identities:
        console.print("No accounts connected.")
        console.print("Run [bold]growth auth twitter[/bold] to get started.")
        return

    table = Table(title="Connected Accounts")
    table.add_column("Platform", style="cyan")
    table.add_column("Identity", style="bold")
    table.add_column("Status")
    table.add_column("Auth Method")
    table.add_column("Rate Profile")

    for identity in identities:
        status_str = {
            "healthy": "[green]✅ OK[/green]",
            "warning": "[yellow]⚠️ Warning[/yellow]",
            "suspended": "[red]🛑 Suspended[/red]",
            "expired": "[red]❌ Expired[/red]",
        }.get(identity.status, identity.status)

        table.add_row(
            identity.platform,
            identity.name,
            status_str,
            identity.auth_method,
            identity.rate_profile,
        )

    console.print(table)

    # Show rate limit status for each identity
    limiter = get_rate_limiter()
    console.print()
    for identity in identities:
        rl_status = limiter.get_status(identity.name, identity.platform)
        if any(v["cooldown"] != "ready" for v in rl_status.values()):
            console.print(f"[dim]Rate limits for {identity.name}:[/dim]")
            for action, s in rl_status.items():
                if s["cooldown"] != "ready":
                    console.print(f"  {action}: {s['this_hour']} this hour, cooldown {s['cooldown']}")


# ── Run (Strategy Execution) ──────────────────────────────────────────


@main.command("run")
@click.argument("strategy_name", required=False)
@click.option("--list", "list_strategies", is_flag=True, help="List available strategies")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
@click.option("--param", "-p", multiple=True, help="Strategy params as key=value")
@click.option("--json", "json_output", is_flag=True)
def run_strategy_cmd(strategy_name, list_strategies, dry_run, param, json_output):
    """Run a strategy or list available strategies."""
    _ensure_platforms_registered()

    from growth.engine.strategy_loader import Strategy, find_strategies

    if list_strategies or not strategy_name:
        strategies = find_strategies()
        if not strategies:
            console.print("No strategies found.")
            console.print("Built-in strategies should be in the strategies/ directory.")
            return

        console.print("\n  [bold]Available strategies:[/bold]\n")
        for path in strategies:
            try:
                s = Strategy.load(path)
                params_str = ", ".join(
                    f"{k}" + (" (required)" if v.get("required") else f"={v.get('default', '?')}")
                    for k, v in s.params.items()
                )
                console.print(f"  [bold cyan]{s.name}[/bold cyan]")
                console.print(f"    {s.description}")
                if params_str:
                    console.print(f"    [dim]Params: {params_str}[/dim]")
                console.print()
            except Exception as e:
                console.print(f"  [red]{path.name}: {e}[/red]")
        return

    # Find and load the strategy
    strategies = find_strategies()
    strategy_path = None
    for p in strategies:
        if p.stem == strategy_name or p.stem.replace("-", "_") == strategy_name.replace("-", "_"):
            strategy_path = p
            break

    if not strategy_path:
        # Try as a direct file path
        direct = Path(strategy_name)
        if direct.exists():
            strategy_path = direct
        else:
            console.print(f"[red]Strategy not found: {strategy_name}[/red]")
            console.print("Run [bold]growth run --list[/bold] to see available strategies.")
            sys.exit(1)

    strategy = Strategy.load(strategy_path)

    # Parse params
    user_params = {}
    for p_str in param:
        if "=" in p_str:
            k, _, v = p_str.partition("=")
            # Try to parse as int/float
            try:
                v = int(v)
            except ValueError:
                try:
                    v = float(v)
                except ValueError:
                    pass
            user_params[k.strip()] = v

    console.print(f"\n  [bold]Running strategy:[/bold] {strategy.name}")
    if strategy.description:
        console.print(f"  {strategy.description}")
    if dry_run:
        console.print("  [dim](dry run — nothing will be executed)[/dim]")
    console.print()

    # Use DAG runner for v0.2 module-based strategies, legacy runner for v0.1 step-based
    try:
        if strategy.is_dag:
            from growth.engine.dag_runner import run_dag_strategy
            state = asyncio.run(run_dag_strategy(strategy.raw, user_params, dry_run=dry_run))
        else:
            from growth.engine.runner import run_strategy
            state = asyncio.run(run_strategy(strategy, user_params, dry_run=dry_run))
    except ValueError as e:
        console.print(f"\n  [red]❌ Strategy error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n  [red]❌ Run failed: {e}[/red]")
        sys.exit(1)

    if json_output:
        click.echo(json.dumps(state, indent=2, default=str))
    else:
        # Print results — handle both legacy 'steps' and DAG 'modules' format
        items_dict = state.get("modules") or state.get("steps") or {}
        for step_id, step_state in items_dict.items():
            status = step_state.get("status", "?")
            icon = {"success": "✅", "dry_run": "👁", "skipped": "⏭", "failed": "❌"}.get(status, "?")
            count = step_state.get("count", "")
            count_str = f" ({count} items)" if count else ""
            use = step_state.get("use", "")
            use_str = f" [dim]{use}[/dim]" if use else ""

            console.print(f"  {icon} [bold]{step_id}[/bold]{use_str}{count_str}: {status}")

            # Show result data for legacy format
            result = step_state.get("result", {})
            if "results" in result:
                for item in result["results"][:5]:
                    title = item.get("title", item.get("text", ""))[:80]
                    score = item.get("score", 0)
                    console.print(f"      [{score}] {title}")

            if step_state.get("error"):
                console.print(f"      [red]{step_state['error']}[/red]")
            if step_state.get("errors"):
                for err in step_state["errors"][:3]:
                    console.print(f"      [dim red]{err}[/dim red]")

        console.print(f"\n  Status: [bold]{state['status']}[/bold]")
        if state.get("errors"):
            console.print(f"  Errors: {len(state['errors'])}")


# ── Log ───────────────────────────────────────────────────────────────


@main.group()
def migrate():
    """Migrate credentials from other tools."""
    pass


@migrate.command("from-openclaw")
def migrate_from_openclaw_cmd():
    """Import credentials from the old openclaw growth pipeline."""
    from growth.identity.migrate import migrate_from_openclaw, OLD_SECRETS_DIR

    if not OLD_SECRETS_DIR.exists():
        console.print(f"[yellow]Old pipeline secrets not found at {OLD_SECRETS_DIR}[/yellow]")
        return

    console.print(f"\n  Scanning {OLD_SECRETS_DIR}...\n")
    migrated = migrate_from_openclaw()

    if migrated:
        console.print(f"  [green]✅ Migrated {len(migrated)} identities:[/green]")
        for name in migrated:
            console.print(f"     {name}")
        console.print(f"\n  No re-authentication needed. Run [bold]growth status[/bold] to verify.")
    else:
        console.print("  No credentials found to migrate.")


@main.command("log")
@click.option("--count", default=10, help="Number of recent entries")
def show_log(count):
    """Show recent activity from the output repo."""
    from growth.output.logger import get_recent_posts

    posts = get_recent_posts(count)
    if not posts:
        console.print("No activity logged yet.")
        console.print("Posts will appear here after you use [bold]growth <platform> post[/bold]")
        return

    console.print(f"\n  [bold]Recent activity ({len(posts)} entries):[/bold]\n")
    for p in posts:
        platform = p.get("platform", "?")
        identity = p.get("identity", "?")
        posted_at = p.get("posted_at", "?")
        url = p.get("url", "")
        content = p.get("content", "")[:80]
        console.print(f"  [dim]{posted_at}[/dim]  [cyan]{platform}[/cyan]  {identity}")
        console.print(f"    {content}")
        if url:
            console.print(f"    [dim]{url}[/dim]")
        console.print()


# ── Modules ───────────────────────────────────────────────────────────


@main.group()
def modules():
    """Browse composable modules (Lego blocks for strategies)."""
    pass


@modules.command("list")
@click.option("--category", "-c", help="Filter by category (source, filter, action, monitor)")
@click.option("--json", "json_output", is_flag=True)
def modules_list(category, json_output):
    """List all available modules."""
    from growth.modules import registry

    if category:
        mods = registry.list_by_category(category)
    else:
        mods = registry.list_all()

    if json_output:
        click.echo(json.dumps([{"name": m.name, "category": m.category, "description": m.description,
                                 "platform": m.platform, "requires_auth": m.requires_auth}
                                for m in mods], indent=2))
        return

    if not mods:
        console.print("No modules found.")
        return

    current_cat = ""
    for m in mods:
        if m.category != current_cat:
            current_cat = m.category
            label = {"source": "SOURCES (Eyes)", "filter": "FILTERS (Brain)", "transform": "TRANSFORMS (Voice)",
                     "action": "ACTIONS (Hands)", "monitor": "MONITORS (Track)", "control": "CONTROL (Flow)"}.get(current_cat, current_cat.upper())
            console.print(f"\n  [bold]{label}[/bold]")
        auth = " 🔑" if m.requires_auth else ""
        console.print(f"    [cyan]{m.name:25s}[/cyan] {m.description}{auth}")

    console.print(f"\n  [dim]{len(mods)} modules total[/dim]")


@modules.command("info")
@click.argument("name")
def modules_info(name):
    """Show detailed info about a module."""
    from growth.modules import registry

    try:
        m = registry.get(name)
    except KeyError as e:
        console.print(f"[red]{e}[/red]")
        return

    console.print(f"\n  [bold]{m.name}[/bold]")
    console.print(f"  Category:    {m.category}")
    console.print(f"  Description: {m.description}")
    if m.platform:
        console.print(f"  Platform:    {m.platform}")
    console.print(f"  Auth:        {'Required 🔑' if m.requires_auth else 'Not needed'}")
    if m.param_schema:
        console.print(f"\n  [bold]Parameters:[/bold]")
        for k, v in m.param_schema.items():
            req = " (required)" if v.get("required") else f" (default: {v.get('default', '?')})"
            console.print(f"    {k}: {v.get('type', '?')}{req}")
    console.print()


# ── Traction ──────────────────────────────────────────────────────────


@main.command("traction")
@click.option("--refresh/--no-refresh", default=True, help="Fetch live data from platforms")
@click.option("--json", "json_output", is_flag=True)
def traction_cmd(refresh, json_output):
    """Check engagement on your posted content.

    Fetches live likes, comments, score, and views from each platform
    for every post in your output log.
    """
    _ensure_platforms_registered()
    from growth.output.traction import fetch_all_traction

    results = asyncio.run(fetch_all_traction(refresh=refresh))

    if not results:
        console.print("No posts tracked yet.")
        console.print("Posts appear here after you use [bold]growth <platform> post[/bold]")
        return

    if json_output:
        click.echo(json.dumps(results, indent=2))
        return

    console.print(f"\n  [bold]Traction Report ({len(results)} posts):[/bold]\n")

    for r in results:
        platform = r.get("platform", "?")
        content = r.get("content", "")[:60]
        posted_at = r.get("posted_at", "")[:10]
        error = r.get("error")

        # Platform icon
        icon = {"twitter": "🐦", "reddit": "🤖", "hn": "🟠"}.get(platform, "📝")

        console.print(f"  {icon} [bold]{platform}[/bold]  [dim]{posted_at}[/dim]")
        console.print(f"     {content}")

        if error:
            console.print(f"     [dim red]⚠ {error}[/dim red]")
        else:
            # Platform-specific metrics
            if platform == "twitter":
                likes = r.get("likes", "?")
                rts = r.get("retweets", "?")
                replies = r.get("replies", "?")
                views = r.get("views", "?")
                console.print(f"     ❤️ {likes}  🔁 {rts}  💬 {replies}  👁 {views}")
            elif platform == "reddit":
                score = r.get("score", "?")
                comments = r.get("comments", "?")
                ratio = r.get("upvote_ratio", "?")
                console.print(f"     ⬆️ {score}  💬 {comments}  📊 {ratio}")
            elif platform == "hn":
                points = r.get("points", "?")
                comments = r.get("comments", "?")
                console.print(f"     ▲ {points}  💬 {comments}")

        if r.get("url"):
            console.print(f"     [dim]{r['url'][:80]}[/dim]")
        console.print()


# ── Twitter Commands ──────────────────────────────────────────────────


@main.group()
def twitter():
    """Twitter commands."""
    _ensure_platforms_registered()


@twitter.command("post")
@click.argument("text")
@click.option("--as", "as_identity", help="Identity to use (e.g., twitter:handle)")
@click.option("--dry-run", is_flag=True, help="Preview without posting")
@click.option("--force", is_flag=True, help="Override rate limits (risky!)")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def twitter_post(text, as_identity, dry_run, force, json_output):
    """Post a tweet."""
    asyncio.run(_do_post("twitter", "post", text, as_identity, dry_run, force, json_output))


@twitter.command("user")
@click.argument("username")
@click.option("--as", "as_identity", help="Identity to use")
@click.option("--count", default=10, help="Number of tweets")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def twitter_user(username, as_identity, count, json_output):
    """Get recent tweets from a user."""
    asyncio.run(_do_user_tweets("twitter", username, as_identity, count, json_output))


@twitter.command("search")
@click.argument("query")
@click.option("--as", "as_identity", help="Identity to use")
@click.option("--count", default=20, help="Number of results")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def twitter_search(query, as_identity, count, json_output):
    """Search tweets."""
    asyncio.run(_do_search("twitter", query, as_identity, count, json_output))


@twitter.command("like")
@click.argument("tweet_id")
@click.option("--as", "as_identity", help="Identity to use")
@click.option("--dry-run", is_flag=True)
@click.option("--force", is_flag=True)
def twitter_like(tweet_id, as_identity, dry_run, force):
    """Like a tweet."""
    asyncio.run(_do_engage("twitter", tweet_id, "like", as_identity, dry_run, force))


@twitter.command("retweet")
@click.argument("tweet_id")
@click.option("--as", "as_identity", help="Identity to use")
@click.option("--dry-run", is_flag=True)
@click.option("--force", is_flag=True)
def twitter_retweet(tweet_id, as_identity, dry_run, force):
    """Retweet a tweet."""
    asyncio.run(_do_engage("twitter", tweet_id, "retweet", as_identity, dry_run, force))


@twitter.command("reply")
@click.argument("tweet_id")
@click.argument("text")
@click.option("--as", "as_identity", help="Identity to use")
@click.option("--dry-run", is_flag=True)
@click.option("--force", is_flag=True)
def twitter_reply(tweet_id, text, as_identity, dry_run, force):
    """Reply to a tweet."""
    asyncio.run(_do_reply("twitter", tweet_id, text, as_identity, dry_run, force))


# ── Reddit Commands ────────────────────────────────────────────────────


@main.group()
def reddit():
    """Reddit commands."""
    _ensure_platforms_registered()


@reddit.command("search")
@click.argument("query")
@click.option("--sub", help="Search within a subreddit")
@click.option("--count", default=10, help="Number of results")
@click.option("--json", "json_output", is_flag=True)
def reddit_search(query, sub, count, json_output):
    """Search Reddit."""
    asyncio.run(_do_search_generic("reddit", query, None, count, json_output, subreddit=sub))


@reddit.command("submit")
@click.option("--as", "as_identity", help="Identity to use")
@click.option("--sub", required=True, help="Subreddit to post in")
@click.option("--title", required=True, help="Post title")
@click.option("--body", default="", help="Post body text")
@click.option("--url", default="", help="Link URL (for link posts)")
@click.option("--dry-run", is_flag=True)
@click.option("--force", is_flag=True)
def reddit_submit(as_identity, sub, title, body, url, dry_run, force):
    """Submit a post to a subreddit."""
    asyncio.run(_do_post("reddit", "post", body, as_identity, dry_run, force, False,
                          subreddit=sub, title=title, url=url))


# ── HN Commands ───────────────────────────────────────────────────────


@main.group()
def hn():
    """Hacker News commands."""
    _ensure_platforms_registered()


@hn.command("search")
@click.argument("query")
@click.option("--count", default=10, help="Number of results")
@click.option("--json", "json_output", is_flag=True)
def hn_search(query, count, json_output):
    """Search Hacker News (via Algolia)."""
    asyncio.run(_do_search_generic("hn", query, None, count, json_output))


@hn.command("top")
@click.option("--count", default=15, help="Number of stories")
@click.option("--json", "json_output", is_flag=True)
def hn_top(count, json_output):
    """Show current HN front page stories."""
    asyncio.run(_do_trending("hn", count, json_output))


@hn.command("submit")
@click.option("--as", "as_identity", help="Identity to use")
@click.option("--title", required=True, help="Submission title")
@click.option("--url", default="", help="URL to submit (link post)")
@click.option("--text", default="", help="Body text (text/Ask HN post)")
@click.option("--dry-run", is_flag=True)
@click.option("--force", is_flag=True)
def hn_submit(as_identity, title, url, text, dry_run, force):
    """Submit to Hacker News. Provide --url for link posts, --text for text posts."""
    if not url and not text:
        click.echo("Error: provide --url (link post) or --text (text post)")
        sys.exit(1)
    asyncio.run(_do_post("hn", "submit", text, as_identity, dry_run, force, False,
                          title=title, url=url))


# ── Shared Action Helpers ─────────────────────────────────────────────


async def _do_post(platform: str, action: str, text: str, as_identity, dry_run, force, json_output, **kwargs):
    """Generic post action with rate limiting and safety checks."""
    from growth.identity.manager import IdentityManager
    from growth.platforms.base import get_platform
    from growth.safety.rate_limiter import get_rate_limiter

    mgr = IdentityManager()
    identity = mgr.resolve_as_flag(as_identity, platform)
    plat = get_platform(platform)
    limiter = get_rate_limiter()

    # Rate limit check
    rl = limiter.check(identity.name, platform, action)
    if not rl.allowed and not force:
        if json_output:
            click.echo(json.dumps({"success": False, "error": "rate_limited", "wait_seconds": rl.wait_seconds}))
        else:
            console.print(f"[yellow]⏳ Rate limit: {rl.reason}[/yellow]")
            console.print(f"   Wait {rl.wait_display} or use --force (risky!)")
        sys.exit(1)

    if not rl.allowed and force:
        console.print("[bold red]⚠️  FORCE OVERRIDE ACTIVE[/bold red]")
        console.print(f"Bypassing: {rl.reason}")
        console.print("This increases the risk of account suspension.")
        console.print("growth-cli is NOT responsible for accounts banned while using --force.")
        if not click.confirm("Continue?", default=False):
            sys.exit(0)

    if dry_run:
        extra_info = {k: v for k, v in kwargs.items() if v}
        if json_output:
            click.echo(json.dumps({"dry_run": True, "platform": platform, "identity": identity.name, "text": text, **extra_info}))
        else:
            console.print(f"\n[dim]DRY RUN — nothing will be posted[/dim]")
            console.print(f"  Platform: {platform}")
            console.print(f"  Account:  {identity.name}")
            if text:
                console.print(f"  Content:  {text}")
            for k, v in extra_info.items():
                console.print(f"  {k.capitalize():10s} {v}")
        return

    # Execute
    result = await plat.post(identity.identity_dir, text, **kwargs)

    if result.success:
        limiter.record(identity.name, action)
        identity.last_used = __import__("datetime").datetime.now().isoformat()
        identity.save()

        # Log to output repo
        from growth.output.logger import log_post
        log_post(platform, identity.name, text, {
            "post_id": result.post_id, "url": result.url,
        }, **kwargs)

        if json_output:
            click.echo(json.dumps({
                "success": True,
                "platform": platform,
                "identity": identity.name,
                "post_id": result.post_id,
                "url": result.url,
            }))
        else:
            console.print(f"[green]✅ Posted![/green]")
            if result.url:
                console.print(f"   {result.url}")
    else:
        if json_output:
            click.echo(json.dumps({"success": False, "error": result.error}))
        else:
            console.print(f"[red]❌ Failed: {result.error}[/red]")
        sys.exit(1)


async def _do_user_tweets(platform: str, username: str, as_identity, count: int, json_output: bool):
    """Fetch recent tweets from a specific user."""
    from growth.identity.manager import IdentityManager
    from growth.platforms.twitter.client import TwitterClient, TwitterClientError

    mgr = IdentityManager()
    identity = mgr.resolve_as_flag(as_identity, platform)
    cookie_path = identity.identity_dir / "cookies.json"
    client = TwitterClient(cookie_path=cookie_path)

    try:
        tweets = await client.get_user_tweets(username.lstrip("@"), count=count)
    except Exception as e:
        _handle_auth_error(e, platform)
        console.print(f"[red]❌ Failed: {e}[/red]")
        sys.exit(1)

    if json_output:
        click.echo(json.dumps(tweets, indent=2))
    else:
        if not tweets:
            console.print(f"No tweets found for @{username}")
            return
        console.print(f"\n  [bold]@{username}[/bold] — latest {len(tweets)} tweets:\n")
        for t in tweets:
            likes = t.get("favorite_count", 0)
            rts = t.get("retweet_count", 0)
            text = t.get("text", "")
            date = t.get("created_at", "")
            console.print(f"  [dim]{date}[/dim]")
            console.print(f"  {text[:280]}")
            console.print(f"  [dim]❤️ {likes}  🔁 {rts}[/dim]\n")


async def _do_search_generic(platform: str, query: str, as_identity, count: int, json_output: bool, **kwargs):
    """Generic search that works without auth (uses public APIs for Reddit/HN)."""
    from growth.platforms.base import get_platform

    plat = get_platform(platform)

    # Reddit/HN search doesn't need auth — uses public APIs
    # Use a dummy identity_dir (won't be accessed for search)
    from growth.config import IDENTITIES_DIR
    dummy_dir = IDENTITIES_DIR / platform / "_search"
    dummy_dir.mkdir(parents=True, exist_ok=True)

    try:
        results = await plat.search(dummy_dir, query, count=count, **kwargs)
    except Exception as e:
        console.print(f"[red]❌ Search failed: {e}[/red]")
        sys.exit(1)

    if json_output:
        click.echo(json.dumps([{"id": r.id, "title": r.title, "url": r.url, "author": r.author, "score": r.score} for r in results], indent=2))
    else:
        if not results:
            console.print("No results found.")
            return
        for r in results:
            score = f"[bold]{r.score}[/bold]" if r.score else "0"
            title = r.title or r.text[:120]
            console.print(f"  [{score}] {title}")
            if r.author:
                console.print(f"       [dim]by {r.author}[/dim]", end="")
            if r.url:
                console.print(f"  [dim]{r.url[:80]}[/dim]")
            else:
                console.print()


async def _do_trending(platform: str, count: int, json_output: bool):
    """Fetch trending/top content from a platform."""
    from growth.platforms.base import get_platform
    from growth.config import IDENTITIES_DIR

    plat = get_platform(platform)
    dummy_dir = IDENTITIES_DIR / platform / "_search"
    dummy_dir.mkdir(parents=True, exist_ok=True)

    try:
        results = await plat.trending(dummy_dir, count=count)
    except Exception as e:
        console.print(f"[red]❌ Failed: {e}[/red]")
        sys.exit(1)

    if json_output:
        click.echo(json.dumps([{"id": r.id, "title": r.title, "url": r.url, "score": r.score} for r in results], indent=2))
    else:
        if not results:
            console.print("No results found.")
            return
        console.print(f"\n  [bold]Top {len(results)} stories:[/bold]\n")
        for i, r in enumerate(results, 1):
            console.print(f"  {i:2}. [{r.score}] {r.title}")
            if r.url:
                console.print(f"       [dim]{r.url[:80]}[/dim]")


async def _do_search(platform: str, query: str, as_identity, count: int, json_output: bool):
    """Generic search action."""
    from growth.identity.manager import IdentityManager
    from growth.platforms.base import get_platform

    mgr = IdentityManager()
    identity = mgr.resolve_as_flag(as_identity, platform)
    plat = get_platform(platform)

    try:
        results = await plat.search(identity.identity_dir, query, count=count)
    except Exception as e:
        _handle_auth_error(e, platform)
        raise

    if json_output:
        click.echo(json.dumps([{"id": r.id, "text": r.text, "author": r.author, "score": r.score} for r in results]))
    else:
        if not results:
            console.print("No results found.")
            return
        for r in results:
            console.print(f"  [{r.score}] @{r.author}: {r.text[:120]}...")
            if r.url:
                console.print(f"    {r.url}")


async def _do_engage(platform: str, target_id: str, action: str, as_identity, dry_run, force):
    """Generic engage action (like, retweet, upvote)."""
    from growth.identity.manager import IdentityManager
    from growth.platforms.base import get_platform
    from growth.safety.rate_limiter import get_rate_limiter

    mgr = IdentityManager()
    identity = mgr.resolve_as_flag(as_identity, platform)
    plat = get_platform(platform)
    limiter = get_rate_limiter()

    rl = limiter.check(identity.name, platform, action)
    if not rl.allowed and not force:
        console.print(f"[yellow]⏳ Rate limit: {rl.reason}[/yellow]")
        sys.exit(1)

    if dry_run:
        console.print(f"[dim]DRY RUN — {action} on {target_id} as {identity.name}[/dim]")
        return

    result = await plat.engage(identity.identity_dir, target_id, action)
    if result.success:
        limiter.record(identity.name, action)
        console.print(f"[green]✅ {action.capitalize()}d![/green]")
    else:
        console.print(f"[red]❌ Failed: {result.error}[/red]")
        sys.exit(1)


async def _do_reply(platform: str, target_id: str, text: str, as_identity, dry_run, force):
    """Generic reply action."""
    from growth.identity.manager import IdentityManager
    from growth.platforms.base import get_platform
    from growth.safety.rate_limiter import get_rate_limiter

    mgr = IdentityManager()
    identity = mgr.resolve_as_flag(as_identity, platform)
    plat = get_platform(platform)
    limiter = get_rate_limiter()

    rl = limiter.check(identity.name, platform, "reply")
    if not rl.allowed and not force:
        console.print(f"[yellow]⏳ Rate limit: {rl.reason}[/yellow]")
        sys.exit(1)

    if dry_run:
        console.print(f"[dim]DRY RUN — reply to {target_id} as {identity.name}: {text}[/dim]")
        return

    result = await plat.reply(identity.identity_dir, target_id, text)
    if result.success:
        limiter.record(identity.name, "reply")
        console.print(f"[green]✅ Replied![/green]")
    else:
        console.print(f"[red]❌ Failed: {result.error}[/red]")
        sys.exit(1)


# ── Helpers ───────────────────────────────────────────────────────────


def _ensure_platforms_registered():
    """Import platform modules to trigger registration."""
    for mod in [
        "growth.platforms.twitter.platform",
        "growth.platforms.reddit.platform",
        "growth.platforms.hn.platform",
    ]:
        try:
            __import__(mod)
        except ImportError:
            pass


def _auth_twitter_browser(username: str, identity_dir: Path) -> bool:
    """Try to grab Twitter cookies by opening Chrome via Playwright.

    Opens your real Chrome browser to x.com. If you're already logged in,
    cookies are captured automatically. If not, log in manually.
    Returns True on success, False if Playwright is unavailable.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return False

    async def _grab():
        console.print("\n  Opening Chrome to x.com...")
        console.print("  If you're already logged in, cookies will be captured automatically.")
        console.print("  Otherwise, log in manually in the browser window.\n")

        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(channel="chrome", headless=False)
        except Exception:
            await pw.stop()
            return False

        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://x.com/home", wait_until="domcontentloaded")

        # Poll for login (up to 3 minutes)
        for _ in range(60):
            await __import__("asyncio").sleep(3)
            cookies = await context.cookies("https://x.com")
            cookie_dict = {c["name"]: c["value"] for c in cookies}
            if "auth_token" in cookie_dict and "ct0" in cookie_dict:
                _save_cookies(username, identity_dir, cookie_dict)
                await browser.close()
                await pw.stop()
                return True

        console.print("[yellow]  Timed out waiting for login.[/yellow]")
        await browser.close()
        await pw.stop()
        return False

    return asyncio.run(_grab())


COOKIE_EDITOR_EXTENSION = "https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm"


def _auth_twitter_paste(username: str, identity_dir: Path) -> None:
    """Auth Twitter by pasting cookies. Supports multiple formats:
    1. Cookie-Editor JSON export (recommended — one click)
    2. document.cookie string
    3. Manual auth_token + ct0 values
    """
    console.print(f"""
  [bold cyan]Grab your Twitter cookies (30 seconds):[/bold cyan]

  [bold]Easiest — Cookie-Editor extension (recommended):[/bold]
    1. Install Cookie-Editor: [link={COOKIE_EDITOR_EXTENSION}]{COOKIE_EDITOR_EXTENSION}[/link]
    2. Go to [bold]x.com[/bold] (make sure you're logged in)
    3. Click the Cookie-Editor icon → [bold]Export[/bold] (copies JSON to clipboard)
    4. Paste below

  [bold]Alternative — browser console:[/bold]
    1. Go to [bold]x.com[/bold] → open console ([bold]Cmd+Option+J[/bold])
    2. Type [bold]allow pasting[/bold] then Enter
    3. Type [bold]document.cookie[/bold] then Enter
    4. Copy the output and paste below
""")

    raw = click.prompt("  Paste cookies").strip()

    if not raw:
        console.print("[red]  ❌ No cookies pasted.[/red]")
        sys.exit(1)

    cookie_dict = _parse_cookies(raw)

    if "auth_token" not in cookie_dict or "ct0" not in cookie_dict:
        console.print("[yellow]  Couldn't find auth_token/ct0 in the paste.[/yellow]")
        console.print("  Let's enter them manually:\n")
        console.print("  In Chrome: [bold]Cmd+Option+I[/bold] → [bold]Application[/bold] tab → [bold]Cookies[/bold] → [bold]https://x.com[/bold]")
        console.print("  Find [bold]auth_token[/bold] and [bold]ct0[/bold], copy each Value:\n")
        auth_token = click.prompt("  auth_token").strip()
        ct0 = click.prompt("  ct0").strip()
        if not auth_token or not ct0:
            console.print("[red]  ❌ Both auth_token and ct0 are required.[/red]")
            sys.exit(1)
        cookie_dict = {"auth_token": auth_token, "ct0": ct0}

    _save_cookies(username, identity_dir, cookie_dict)


def _parse_cookies(raw: str) -> dict[str, str]:
    """Parse cookies from multiple formats:
    - Cookie-Editor JSON export: [{"name": "x", "value": "y"}, ...]
    - document.cookie string: "key1=val1; key2=val2; ..."
    """
    raw = raw.strip()

    # Try Cookie-Editor JSON format first
    if raw.startswith("["):
        try:
            cookies_list = json.loads(raw)
            return {c["name"]: c["value"] for c in cookies_list if "name" in c and "value" in c}
        except (json.JSONDecodeError, KeyError):
            pass

    # Try document.cookie string format
    cookie_dict = {}
    for pair in raw.replace('"', "").split(";"):
        pair = pair.strip()
        if "=" in pair:
            key, _, val = pair.partition("=")
            cookie_dict[key.strip()] = val.strip()

    return cookie_dict


def _save_cookies(username: str, identity_dir: Path, cookie_dict: dict) -> None:
    """Save cookies to disk with secure permissions."""
    import os
    import stat

    identity_dir.mkdir(parents=True, exist_ok=True)
    cookie_path = identity_dir / "cookies.json"

    import json as _json
    with open(cookie_path, "w") as f:
        _json.dump(cookie_dict, f, indent=2)

    os.chmod(cookie_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    os.chmod(identity_dir, stat.S_IRWXU)  # 0700

    _save_identity("twitter", username, {"auth_method": "cookies_manual"})
    console.print(f"\n  [green]✅ Cookies saved![/green]")
    console.print(f"     Identity: [bold]twitter:{username}[/bold]")
    console.print(f"\n     Test it: [bold]growth twitter search 'AI agents' --count 3[/bold]")


REDDIT_COOKIE_INSTRUCTIONS = """
  [bold cyan]Grab your Reddit cookies:[/bold cyan]

  1. Install Cookie-Editor: [link={ext}]{ext}[/link]
  2. Go to [bold]reddit.com[/bold] (make sure you're logged in)
  3. Click Cookie-Editor icon → [bold]Export[/bold]
  4. Paste the JSON below
""".format(ext=COOKIE_EDITOR_EXTENSION)

HN_COOKIE_INSTRUCTIONS = """
  [bold cyan]Grab your Hacker News cookies:[/bold cyan]

  1. Install Cookie-Editor: [link={ext}]{ext}[/link]
  2. Go to [bold]news.ycombinator.com[/bold] (make sure you're logged in)
  3. Click Cookie-Editor icon → [bold]Export[/bold]
  4. Paste the JSON below
""".format(ext=COOKIE_EDITOR_EXTENSION)


def _auth_platform_cookie_paste(platform: str, platform_name: str, username: str, identity_dir: Path) -> None:
    """Auth Reddit or HN by pasting Cookie-Editor JSON export."""
    if platform == "reddit":
        console.print(REDDIT_COOKIE_INSTRUCTIONS)
    else:
        console.print(HN_COOKIE_INSTRUCTIONS)

    raw = click.prompt("  Paste cookies").strip()
    _auth_cookie_paste(platform, username, identity_dir, raw)


def _auth_cookie_paste(platform: str, username: str, identity_dir: Path, raw: str) -> None:
    """Parse and save cookies for Reddit or HN."""
    import os
    import stat

    if not raw:
        console.print("[red]  ❌ No cookies pasted.[/red]")
        sys.exit(1)

    cookie_dict = _parse_cookies(raw)

    if platform == "reddit":
        # Reddit needs: reddit_session or token_v2
        if "reddit_session" not in cookie_dict and "token_v2" not in cookie_dict:
            console.print("[red]  ❌ No reddit_session or token_v2 found in cookies.[/red]")
            console.print("  Make sure you're logged into reddit.com before exporting.")
            sys.exit(1)

        # Save as Playwright storage_state format
        session_dir = identity_dir / "session"
        session_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(session_dir, stat.S_IRWXU)

        # Build minimal storage_state.json that Playwright expects
        cookies_list = [
            {
                "name": name,
                "value": value,
                "domain": ".reddit.com",
                "path": "/",
                "httpOnly": name in ("reddit_session", "token_v2"),
                "secure": True,
                "sameSite": "None",
            }
            for name, value in cookie_dict.items()
        ]
        storage_state = {"cookies": cookies_list, "origins": []}
        storage_path = session_dir / "storage_state.json"

        import json as _json
        with open(storage_path, "w") as f:
            _json.dump(storage_state, f, indent=2)
        os.chmod(storage_path, stat.S_IRUSR | stat.S_IWUSR)

    elif platform == "hn":
        # HN needs: user cookie
        if "user" not in cookie_dict:
            console.print("[red]  ❌ No 'user' cookie found.[/red]")
            console.print("  Make sure you're logged into news.ycombinator.com before exporting.")
            sys.exit(1)

        session_dir = identity_dir / "session"
        session_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(session_dir, stat.S_IRWXU)

        import json as _json
        cookie_path = session_dir / "hn_cookie.json"
        with open(cookie_path, "w") as f:
            _json.dump({"user_cookie": cookie_dict["user"]}, f, indent=2)
        os.chmod(cookie_path, stat.S_IRUSR | stat.S_IWUSR)

    _save_identity(platform, username, {"auth_method": "cookies_manual"})
    console.print(f"\n  [green]✅ Cookies saved![/green]")
    console.print(f"     Identity: [bold]{platform}:{username}[/bold]")

    if platform == "reddit":
        console.print(f"\n     Test it: [bold]growth reddit search 'test' --count 1[/bold]")
    else:
        console.print(f"\n     Test it: [bold]growth hn search 'test' --count 1[/bold]")


def _handle_auth_error(error: Exception, platform: str) -> None:
    """Catch auth/expired errors and show re-auth instructions."""
    from growth.platforms.twitter.client import TwitterAuthError

    if isinstance(error, TwitterAuthError):
        console.print(f"\n[bold red]🔑 Session expired[/bold red]")
        console.print(f"\n  Re-authenticate:  [bold]growth auth {platform}[/bold]\n")
        sys.exit(1)


def _save_identity(platform: str, username: str, metadata: dict):
    """Create and save an Identity after successful auth."""
    from growth.identity.manager import Identity

    identity = Identity(
        name=f"{platform}:{username}",
        platform=platform,
        username=username,
        auth_method=metadata.get("auth_method", "unknown"),
        rate_profile="conservative",
    )
    identity.save()


if __name__ == "__main__":
    main()
