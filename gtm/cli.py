"""Click CLI entry point for gtm-cli.

Command: `gtm`

Terminal-native go-to-market CLI.
Claude Code for GTM engineers.
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

from gtm import __version__
from gtm.config import (
    CONFIG_DIR,
    IDENTITIES_DIR,
    ensure_dirs,
    GrowthConfig,
)

console = Console()

BURNER_WARNING = """
[bold yellow]⚠️  ACCOUNT SAFETY NOTICE[/bold yellow]

gtm-cli automates actions on your social media accounts.
Built-in rate limits protect your accounts, but platform detection
is always a risk with any automation tool.

[bold]RECOMMENDATION:[/bold] Use dedicated/burner accounts, not your
personal accounts, for automated posting and engagement.

Future: gtm-cli will offer pre-warmed accounts for purchase
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
    """gtm-cli — Terminal-native go-to-market CLI."""
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# ── Init ──────────────────────────────────────────────────────────────


@main.command()
def init():
    """Initialize gtm-cli config directory."""
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
            ["git", "commit", "-m", "init: gtm output initialized"],
            cwd=output_dir,
            capture_output=True,
        )

    console.print(f"\n✅ Config directory: {CONFIG_DIR}")
    console.print(f"✅ Identities:      {IDENTITIES_DIR}")
    console.print(f"✅ Output (git):     {output_dir}")
    console.print("\nNext: connect your first account with [bold]gtm auth twitter[/bold]")

    # Check for old pipeline credentials to offer migration
    from gtm.identity.migrate import OLD_SECRETS_DIR
    if OLD_SECRETS_DIR.exists():
        console.print(f"\n[dim]Found existing openclaw pipeline credentials at {OLD_SECRETS_DIR}[/dim]")
        console.print("[dim]Run [bold]gtm migrate from-openclaw[/bold] to import them.[/dim]")

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
    from gtm.platforms.base import get_platform

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
                console.print("  [green]✅ Logged in![/green]")
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
            _auth_cookie_paste(platform, username, identity_dir, raw, interactive=False)
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
                console.print("  [green]✅ Login detected! Session saved.[/green]")
                console.print(f"     Identity: [bold]{platform}:{username}[/bold]")
            except Exception as e:
                console.print(f"  [red]❌ Login failed: {e}[/red]")
                console.print("\n  Try cookie auth instead:")
                console.print(f"    [bold]gtm auth {platform} -u {username}[/bold]")
                sys.exit(1)


# ── Status ────────────────────────────────────────────────────────────


@main.command()
def status():
    """Show connected accounts and health."""
    from gtm.identity.manager import IdentityManager
    from gtm.safety.rate_limiter import get_rate_limiter

    mgr = IdentityManager()
    identities = mgr.list_all()

    if not identities:
        console.print("No accounts connected.")
        console.print("Run [bold]gtm auth twitter[/bold] to get started.")
        return

    table = Table(title="Connected Accounts")
    table.add_column("Platform", style="cyan")
    table.add_column("Identity", style="bold")
    table.add_column("Role")
    table.add_column("Status")
    table.add_column("Proxy", style="dim")

    for identity in identities:
        status_str = {
            "healthy": "[green]✅ OK[/green]",
            "warning": "[yellow]⚠️ Warning[/yellow]",
            "suspended": "[red]🛑 Suspended[/red]",
            "expired": "[red]❌ Expired[/red]",
        }.get(identity.status, identity.status)

        role_str = {
            "brand": "[bold]brand[/bold]",
            "organic": "organic",
            "supporter": "supporter",
            "scout": "[dim]scout[/dim]",
            "default": "[dim]default[/dim]",
        }.get(identity.role, identity.role)

        # Redact proxy credentials (user:pass@host → ***@host)
        proxy_raw = identity.proxy or "direct"
        if "@" in proxy_raw:
            proto_rest = proxy_raw.split("://", 1)
            if len(proto_rest) == 2:
                host_part = proto_rest[1].split("@", 1)[-1]
                proxy_str = f"{proto_rest[0]}://***@{host_part}"
            else:
                proxy_str = "***@" + proxy_raw.split("@", 1)[-1]
        else:
            proxy_str = proxy_raw

        table.add_row(
            identity.platform,
            identity.name,
            role_str,
            status_str,
            proxy_str,
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


# ── Rewrite (Platform Tone Adaptation) ────────────────────────────────


@main.command("rewrite")
@click.argument("text")
@click.option("--for", "target_platform", required=True, type=click.Choice(["twitter", "reddit", "hn"]),
              help="Target platform")
@click.option("--json", "json_output", is_flag=True)
def rewrite_cmd(text, target_platform, json_output):
    """Rewrite content for a platform's tone and style.

    Example: gtm rewrite "We just launched our AI tool!" --for reddit
    """
    from gtm.agents.base import load_style_guide

    style = load_style_guide(target_platform)

    platform_instructions = {
        "twitter": "Rewrite as a tweet (max 280 chars). Include hashtags if relevant.",
        "reddit": "Rewrite as a Reddit post title (line 1) and body (rest). All lowercase, organic tone, no self-promotion.",
        "hn": "Rewrite as a Hacker News title. Clean, factual, no clickbait, no editorializing.",
    }

    prompt = (
        f"{platform_instructions.get(target_platform, 'Rewrite for social media.')}\n\n"
        f"## Original\n{text}\n\n"
        f"## Style Rules\n{style}\n\n"
        f"## Output\nOutput ONLY the rewritten text."
    )

    import subprocess
    try:
        proc = subprocess.run(
            ["claude", "-p", "-", "--output-format", "text"],
            input=prompt, capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        if json_output:
            click.echo(json.dumps({"error": "claude CLI not found"}))
            sys.exit(1)
        console.print("[yellow]Claude CLI not found. Using deterministic adaptation...[/yellow]")
        asyncio.run(_fallback_rewrite(text, target_platform))
        return
    except subprocess.TimeoutExpired:
        if json_output:
            click.echo(json.dumps({"error": "timeout"}))
            sys.exit(1)
        console.print("[yellow]Rewrite timed out. Using deterministic adaptation...[/yellow]")
        asyncio.run(_fallback_rewrite(text, target_platform))
        return

    if proc.returncode != 0:
        err = proc.stderr.strip()[:200] if proc.stderr else "unknown error"
        if json_output:
            click.echo(json.dumps({"error": err}))
            sys.exit(1)
        console.print(f"[yellow]Rewrite failed: {err}[/yellow]")
        console.print("\n  [dim]Falling back to deterministic adaptation...[/dim]")
        asyncio.run(_fallback_rewrite(text, target_platform))
        return

    rewritten = proc.stdout.strip()
    if json_output:
        click.echo(json.dumps({"original": text, "rewritten": rewritten, "platform": target_platform}))
    else:
        console.print(f"\n  [bold]Original:[/bold] {text}")
        console.print(f"  [bold]For {target_platform}:[/bold] {rewritten}\n")


async def _fallback_rewrite(text: str, platform: str) -> None:
    """Deterministic rewrite when LLM is unavailable."""
    from gtm.modules import registry
    from gtm.modules.base import ModuleResult, ModuleContext

    adapt = registry.get("transform/platform_adapt")
    result = await adapt.run(
        ModuleResult(success=True, data=[{"text": text, "title": text}]),
        {"platform": platform},
        ModuleContext(),
    )
    if result.data:
        item = result.data[0]
        # HN adapter writes to 'title', others to 'text'
        if platform == "hn":
            adapted = item.get("title") or item.get("text") or text
        else:
            adapted = item.get("text") or item.get("title") or text
        console.print(f"\n  [bold]Adapted:[/bold] {adapted}\n")


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

    from gtm.engine.strategy_loader import Strategy, find_strategies

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

                # Detect execution mode from structure
                if s.is_dag:
                    has_agent = any("agent/" in m.get("use", "") for m in s.raw.get("modules", {}).values())
                    mode = "[yellow]hybrid[/yellow]" if has_agent else "[green]module-dag[/green]"
                elif s.steps:
                    has_agent = any(step.type == "agent" for step in s.steps)
                    mode = "[red]llm-agent[/red]" if has_agent else "[blue]legacy-steps[/blue]"
                else:
                    mode = "[dim]unknown[/dim]"

                console.print(f"  [bold cyan]{s.name}[/bold cyan]  {mode}")
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
            console.print("Run [bold]gtm run --list[/bold] to see available strategies.")
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

    if not json_output:
        console.print(f"\n  [bold]Running strategy:[/bold] {strategy.name}")
        if strategy.description:
            console.print(f"  {strategy.description}")
        if dry_run:
            console.print("  [dim](dry run — nothing will be executed)[/dim]")
        console.print()

    # Use DAG runner for v0.2 module-based strategies, legacy runner for v0.1 step-based
    try:
        if strategy.is_dag:
            from gtm.engine.dag_runner import run_dag_strategy
            state = asyncio.run(run_dag_strategy(strategy.raw, user_params, dry_run=dry_run))
        else:
            from gtm.engine.runner import run_strategy
            state = asyncio.run(run_strategy(strategy, user_params, dry_run=dry_run))
    except ValueError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e), "status": "failed"}))
        else:
            console.print(f"\n  [red]❌ Strategy error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        if json_output:
            click.echo(json.dumps({"error": str(e), "status": "failed"}))
        else:
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
    from gtm.identity.migrate import migrate_from_openclaw, OLD_SECRETS_DIR

    if not OLD_SECRETS_DIR.exists():
        console.print(f"[yellow]Old pipeline secrets not found at {OLD_SECRETS_DIR}[/yellow]")
        return

    console.print(f"\n  Scanning {OLD_SECRETS_DIR}...\n")
    migrated = migrate_from_openclaw()

    if migrated:
        console.print(f"  [green]✅ Migrated {len(migrated)} identities:[/green]")
        for name in migrated:
            console.print(f"     {name}")
        console.print("\n  No re-authentication needed. Run [bold]gtm status[/bold] to verify.")
    else:
        console.print("  No credentials found to migrate.")


@main.command("log")
@click.option("--count", default=10, help="Number of recent entries")
def show_log(count):
    """Show recent activity from the output repo."""
    from gtm.output.logger import get_recent_posts

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
    from gtm.modules import registry

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


@modules.command("create")
@click.argument("name")
@click.option("--description", "-d", default="", help="Module description")
def modules_create(name, description):
    """Scaffold a new strategy YAML file."""
    strategies_dir = Path("~/.config/gtm/strategies").expanduser()
    strategies_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize name — prevent path traversal
    import re
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '-', name)
    if safe_name != name:
        console.print(f"[yellow]Sanitized name: {name} → {safe_name}[/yellow]")

    filename = f"{safe_name}.yaml"
    filepath = strategies_dir / filename

    # Verify filepath stays within strategies dir
    if not filepath.resolve().is_relative_to(strategies_dir.resolve()):
        console.print("[red]Invalid strategy name.[/red]")
        return

    if filepath.exists():
        console.print(f"[yellow]Strategy already exists: {filepath}[/yellow]")
        if not click.confirm("Overwrite?"):
            return

    # Escape YAML special chars in user input
    safe_desc = (description or "My custom strategy").replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')

    template = f"""name: "{safe_name}"
description: "{safe_desc}"
version: "2.0"

# Identities this strategy needs (optional)
# identities:
#   twitter_account: {{ platform: twitter }}
#   reddit_account: {{ platform: reddit }}

# Parameters (user provides at runtime with -p key=value)
params:
  query: {{ required: true }}
  count: {{ default: 10 }}

# Module DAG — execution order inferred from 'input' dependencies
modules:
  # Step 1: Source — gather data
  search:
    use: twitter/search
    # as: $twitter_account
    params:
      query: "{{{{ query }}}}"
      count: "{{{{ count }}}}"

  # Step 2: Filter — process data
  filtered:
    use: filter/engagement
    input: search
    params:
      min_likes: 100

  # Step 3: Transform — adapt content
  adapted:
    use: transform/platform_adapt
    input: filtered
    params:
      platform: reddit

  # Step 4: Action — post (uncomment when ready)
  # post:
  #   use: reddit/submit
  #   input: adapted
  #   as: $reddit_account
  #   params:
  #     subreddit: "SaaS"
"""
    try:
        filepath.write_text(template)
    except OSError as e:
        console.print(f"[red]Failed to write strategy: {e}[/red]")
        return
    console.print(f"\n  [green]✅ Strategy created: {filepath}[/green]")
    console.print(f"  Edit it, then run: [bold]gtm run {safe_name}[/bold]")
    console.print("\n  Available modules: [bold]gtm modules list[/bold]")


@modules.command("info")
@click.argument("name")
def modules_info(name):
    """Show detailed info about a module."""
    from gtm.modules import registry

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
        console.print("\n  [bold]Parameters:[/bold]")
        for k, v in m.param_schema.items():
            req = " (required)" if v.get("required") else f" (default: {v.get('default', '?')})"
            console.print(f"    {k}: {v.get('type', '?')}{req}")
    console.print()


# ── Plan (NL → Strategy) ──────────────────────────────────────────────


@main.command("plan")
@click.argument("description")
@click.option("--save", "-s", default="", help="Save to strategy file name")
@click.option("--json", "json_output", is_flag=True)
def plan_cmd(description, save, json_output):
    """Generate a strategy YAML from a natural language description.

    Example: gtm plan "scout Twitter for AI tools, filter viral ones, post top 3 to Reddit"
    """
    _ensure_platforms_registered()
    from gtm.modules import registry as mod_registry

    # Build module catalog for the LLM
    modules_info = []
    for mod in mod_registry.list_all():
        modules_info.append(f"  {mod.name} — {mod.description}")
    modules_catalog = "\n".join(modules_info)

    prompt = (
        "You are a strategy builder for gtm-cli. Generate a YAML strategy file.\n\n"
        "## User's Description\n"
        f"{description}\n\n"
        "## Available Modules\n"
        f"{modules_catalog}\n\n"
        "## YAML Format\n"
        "```yaml\n"
        "name: \"Strategy Name\"\n"
        "description: \"What this does\"\n"
        "version: \"2.0\"\n"
        "identities:\n"
        "  twitter_account: { platform: twitter }\n"
        "params:\n"
        "  query: { required: true }\n"
        "modules:\n"
        "  step1:\n"
        "    use: module/name\n"
        "    params: { key: \"{{ query }}\" }\n"
        "  step2:\n"
        "    use: module/name\n"
        "    input: step1\n"
        "    params: { ... }\n"
        "```\n\n"
        "## Rules\n"
        "- Use ONLY modules from the catalog above\n"
        "- Connect modules via 'input' field (creates DAG)\n"
        "- Use {{ param_name }} for user-provided values\n"
        "- Prefer direct API modules over agent/* modules\n"
        "- Output ONLY the YAML. No explanation.\n"
    )

    import subprocess
    try:
        proc = subprocess.run(
            ["claude", "-p", "-", "--output-format", "text"],
            input=prompt, capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:
        if json_output:
            click.echo(json.dumps({"error": "claude CLI not found"}))
        else:
            console.print("[red]Claude CLI not found. Install: npm install -g @anthropic-ai/claude-code[/red]")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        if json_output:
            click.echo(json.dumps({"error": "timeout"}))
        else:
            console.print("[yellow]Strategy generation timed out.[/yellow]")
        sys.exit(1)

    if proc.returncode != 0:
        err = proc.stderr.strip()[:200] if proc.stderr else "unknown error"
        if json_output:
            click.echo(json.dumps({"error": err}))
        else:
            console.print(f"[yellow]Strategy generation failed: {err}[/yellow]")
        sys.exit(1)

    yaml_text = proc.stdout.strip()

    # Strip markdown code fences if present
    if yaml_text.startswith("```"):
        lines = yaml_text.split("\n")
        yaml_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    if json_output:
        click.echo(json.dumps({"yaml": yaml_text}))
        return

    console.print("\n  [bold]Generated strategy:[/bold]\n")
    console.print(yaml_text)

    if save:
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '-', save)
        strategies_dir = Path("~/.config/gtm/strategies").expanduser()
        strategies_dir.mkdir(parents=True, exist_ok=True)
        filepath = strategies_dir / f"{safe_name}.yaml"
        try:
            filepath.write_text(yaml_text)
            console.print(f"\n  [green]✅ Saved to {filepath}[/green]")
            console.print(f"  Run: [bold]gtm run {safe_name} --dry-run[/bold]")
        except OSError as e:
            console.print(f"[red]Failed to save: {e}[/red]")
    else:
        console.print(f"\n  [dim]To save: gtm plan \"{description}\" --save my-strategy[/dim]")


# ── Listen (Social Listening) ─────────────────────────────────────────


@main.command("listen")
@click.argument("query")
@click.option("--platforms", "-p", default="twitter,reddit,hn", help="Platforms to scan (comma-separated)")
@click.option("--count", default=5, help="Results per platform")
@click.option("--json", "json_output", is_flag=True)
def listen_cmd(query, platforms, count, json_output):
    """Monitor platforms for a topic — find mentions, trends, opportunities."""
    _ensure_platforms_registered()
    from gtm.output.listener import listen
    from gtm.identity.manager import IdentityManager

    platform_list = [p.strip() for p in platforms.split(",")]

    # Resolve identity dirs for auth-required platforms
    mgr = IdentityManager()
    identity_dirs = {}
    for p in platform_list:
        try:
            identity = mgr.get_for_platform(p)
            identity_dirs[p] = identity.identity_dir
        except ValueError:
            pass  # No auth for this platform — search may still work (Reddit, HN)

    results = asyncio.run(listen(query, platform_list, count, identity_dirs))

    if json_output:
        click.echo(json.dumps(results, indent=2, default=str))
        return

    total = sum(len(v) for v in results.values())
    console.print(f"\n  [bold]Listening for '{query}' — {total} results across {len(platform_list)} platforms:[/bold]\n")

    icons = {"twitter": "🐦", "reddit": "🤖", "hn": "🟠"}

    for platform, items in results.items():
        icon = icons.get(platform, "📝")
        console.print(f"  {icon} [bold]{platform}[/bold] ({len(items)} results)")
        for item in items[:count]:
            title = item.get("title", item.get("text", ""))[:80]
            score = item.get("favorite_count", item.get("score", item.get("points", 0)))
            author = item.get("author", item.get("user", {}).get("screen_name", "")) if isinstance(item.get("user"), dict) else item.get("author", "")
            console.print(f"    [{score}] {title}")
            if author:
                console.print(f"         [dim]by {author}[/dim]")
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
    from gtm.output.traction import fetch_all_traction

    results = asyncio.run(fetch_all_traction(refresh=refresh))

    if not results:
        console.print("No posts tracked yet.")
        console.print("Posts appear here after you use [bold]gtm <platform> post[/bold]")
        return

    # Check for alerts
    if refresh:
        from gtm.output.alerts import check_alerts
        alerts = check_alerts(results)
        if alerts and not json_output:
            console.print(f"\n  [bold yellow]🔔 {len(alerts)} new alert(s)![/bold yellow]\n")
            for a in alerts:
                icon = {"twitter": "🐦", "reddit": "🤖", "hn": "🟠"}.get(a["platform"], "📝")
                console.print(f"  {icon} [bold]{a['metric']}[/bold] hit {a['threshold']}! (now {a['current']})")
                console.print(f"     {a['content']}")
                console.print()

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
@click.argument("text", required=False, default="")
@click.option("--as", "as_identity", help="Identity to use (e.g., twitter:handle)")
@click.option("--generate", "-g", "generate_prompt", default="", help="Generate content from a description")
@click.option("--dry-run", is_flag=True, help="Preview without posting")
@click.option("--force", is_flag=True, help="Override rate limits (risky!)")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def twitter_post(text, as_identity, generate_prompt, dry_run, force, json_output):
    """Post a tweet. Use --generate to have LLM draft the content."""
    if generate_prompt:
        text = _generate_content("twitter", generate_prompt)
        if not text:
            sys.exit(1)
        if not dry_run and not json_output:
            console.print("\n  [bold]Generated tweet:[/bold]")
            console.print(f"  {text}\n")
            if not click.confirm("  Post this?", default=True):
                console.print("  Cancelled.")
                return
    elif not text:
        console.print("[red]Provide text or use --generate[/red]")
        sys.exit(1)
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
@click.option("--title", default="", help="Post title")
@click.option("--body", default="", help="Post body text")
@click.option("--url", default="", help="Link URL (for link posts)")
@click.option("--generate", "-g", "generate_prompt", default="", help="Generate title + body from description")
@click.option("--dry-run", is_flag=True)
@click.option("--force", is_flag=True)
def reddit_submit(as_identity, sub, title, body, url, generate_prompt, dry_run, force):
    """Submit a post to a subreddit. Use --generate to draft content."""
    if generate_prompt:
        generated = _generate_content("reddit", generate_prompt, subreddit=sub)
        if not generated:
            sys.exit(1)
        # Parse title and body from generated content
        lines = generated.strip().split("\n", 1)
        title = title or lines[0]
        body = body or (lines[1].strip() if len(lines) > 1 else "")
        if not dry_run:
            console.print(f"\n  [bold]Generated Reddit post for r/{sub}:[/bold]")
            console.print(f"  Title: {title}")
            console.print(f"  Body:  {body[:200]}{'...' if len(body) > 200 else ''}\n")
            if not click.confirm("  Post this?", default=True):
                console.print("  Cancelled.")
                return
    elif not title:
        console.print("[red]Provide --title or use --generate[/red]")
        sys.exit(1)
    asyncio.run(_do_post("reddit", "post", body, as_identity, dry_run, force, False,
                          subreddit=sub, title=title, url=url))


@reddit.command("preflight")
@click.argument("sub")
@click.option("--identity", required=True,
              help="Reddit username to preflight (e.g. Pale_Stand5217 or u/Pale_Stand5217)")
@click.option("--json", "json_output", is_flag=True, help="JSON output for scripts")
def reddit_preflight(sub, identity, json_output):
    """Preflight a Reddit (identity, sub) pair against per-sub karma/age rules.

    Exit codes: 0 = PASS or BORDERLINE; 1 = FAIL; 2 = error fetching user.
    """
    from gtm.modules.preflight import preflight, PreflightError

    try:
        result = preflight(identity, sub)
    except PreflightError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]preflight error:[/red] {e}")
        sys.exit(2)

    if json_output:
        click.echo(json.dumps(result, indent=2))
    else:
        s = result["stats"]
        click.echo(f"identity: u/{s.get('username', identity)}")
        click.echo(f"  karma: {s['total_karma']} total "
                   f"(link {s['link_karma']}, comment {s['comment_karma']})")
        click.echo(f"  age: {s['age_days']} days")
        click.echo(f"sub: r/{result['sub']}")
        if not result["rule_found"]:
            click.echo("  rule: (no rule on file — treating as PASS)")
        else:
            for r in result["reasons"]:
                rk = r.get("rule", "?")
                if r["status"] == "fail":
                    click.echo(f"  rule: {rk} FAIL ({r.get('detail', '')})")
                elif r["status"] == "borderline":
                    pct = r.get("margin_pct", 0)
                    click.echo(f"  rule: {rk}>={r.get('floor')} "
                               f"(margin: {pct}% — borderline)")
                else:
                    floor = r.get("floor")
                    if floor is None:
                        click.echo(f"  rule: {rk} ✓ ({r.get('detail', '')})")
                    else:
                        click.echo(f"  rule: {rk}>={floor} ✓")
        verdict = result["verdict"]
        color = {"PASS": "green", "BORDERLINE": "yellow", "FAIL": "red"}.get(verdict, "white")
        console.print(f"verdict: [{color}]{verdict}[/{color}]")
        if result.get("notes"):
            click.echo(f"notes: \"{result['notes']}\"")
        if result.get("permanent_skip"):
            click.echo("permanent_skip: true")

    if result["verdict"] == "FAIL":
        sys.exit(1)


@reddit.command("log")
@click.argument("url")
@click.option("--as", "as_identity", required=True,
              help="Reddit username that posted (e.g. Pale_Stand5217)")
@click.option("--product", required=True,
              help="Product tag for the dashboard row (e.g. first-tree)")
@click.option("--direction", required=True,
              help="Campaign direction tag (e.g. github-scan-menubar)")
@click.option("--note", default="",
              help="Free-form note for the dashboard row")
@click.option("--kind", default="self", type=click.Choice(["self", "image", "link"]),
              help="Post kind (default: self)")
@click.option("--image", default="",
              help="Image path for kind=image rows (relative to dashboard)")
@click.option("--dashboard", "dashboard_paths", multiple=True,
              type=click.Path(exists=True, dir_okay=False),
              help="Dashboard HTML file(s) to update. Defaults to "
                   "~/atf-launch/dashboard.html and ~/atf-launch/dist/index.html "
                   "if they exist.")
@click.option("--pid", "explicit_pid", default=None,
              help="Override the auto-generated pN id (rarely needed).")
@click.option("--dry-run", is_flag=True, help="Show what would change, don't write.")
def reddit_log(url, as_identity, product, direction, note, kind, image,
               dashboard_paths, explicit_pid, dry_run):
    """Log a Reddit post that was made outside `gtm` (e.g. via prefill or manual Chrome).

    Fetches live engagement, picks the next pN id, and atomically appends
    a new row to the launch dashboard's POSTS array. Idempotent — if the
    URL already exists, refreshes its score/comments instead of duplicating.

    \b
    Example:
      gtm reddit log https://www.reddit.com/r/opensource/comments/1t4re4k/ \\
        --as Pale_Stand5217 \\
        --product first-tree \\
        --direction github-scan-menubar \\
        --note "manual prefill · permanent_skip override · monitor 24h"
    """
    from gtm.output.traction import fetch_reddit_engagement

    # Resolve dashboard paths
    paths = [Path(p) for p in dashboard_paths] if dashboard_paths else []
    if not paths:
        for default in [Path.home() / "atf-launch" / "dashboard.html",
                        Path.home() / "atf-launch" / "dist" / "index.html"]:
            if default.exists():
                paths.append(default)
    if not paths:
        raise click.UsageError(
            "No dashboard file specified and no defaults found at "
            "~/atf-launch/dashboard.html or ~/atf-launch/dist/index.html. "
            "Pass --dashboard <path>."
        )

    # Derive sub + date from URL and now()
    import re as _re
    from datetime import datetime, timezone
    sub_match = _re.search(r"/r/([^/]+)/", url)
    sub = sub_match.group(1) if sub_match else "?"
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    channel = f"reddit r/{sub}"
    account = f"u/{as_identity}"

    # Fetch live engagement once
    async def _fetch():
        return await fetch_reddit_engagement(url)
    eng = asyncio.run(_fetch())
    if "error" in eng:
        console.print(f"[yellow]Warning: could not fetch engagement: {eng['error']}[/yellow]")
        score, comments = 0, 0
    else:
        score, comments = eng.get("score", 0), eng.get("comments", 0)

    for path in paths:
        _log_post_to_dashboard(
            path, url=url, product=product, direction=direction,
            date=date, channel=channel, account=account,
            score=score, comments=comments, kind=kind, image=image,
            note=note, explicit_pid=explicit_pid, dry_run=dry_run,
        )


def _log_post_to_dashboard(path: Path, *, url: str, product: str, direction: str,
                            date: str, channel: str, account: str,
                            score: int, comments: int, kind: str, image: str,
                            note: str, explicit_pid, dry_run: bool):
    """Append a new pN row to the POSTS array — or refresh if URL already there."""
    import re

    src = path.read_text()

    # Idempotent: if the URL is already in the file, refresh score/comments only.
    url_re = re.compile(rf"url:\s*'{re.escape(url)}'")
    if url_re.search(src):
        # Find the enclosing block and replace its score/comments
        m = url_re.search(src)
        block_start = src.rfind("{", 0, m.start())
        block_end_re = re.compile(r"^\s*\},?", flags=re.MULTILINE)
        end_m = block_end_re.search(src, m.end())
        if not end_m:
            console.print(f"[red]ERROR[/red] {path}: malformed block for existing URL")
            return
        block = src[block_start:end_m.end()]
        new_block = re.sub(r"score:\s*\d+", f"score: {score}", block)
        new_block = re.sub(r"comments:\s*\d+", f"comments: {comments}", new_block)
        if dry_run:
            console.print(f"[cyan]dry-run[/cyan] {path}: URL exists — would refresh to ({score}↑/{comments}c)")
            return
        new_src = src[:block_start] + new_block + src[end_m.end():]
        path.write_text(new_src)
        console.print(f"[green]✓[/green] {path}: refreshed existing row ({score}↑/{comments}c)")
        return

    # New row: pick next pid
    if explicit_pid:
        new_pid = explicit_pid
    else:
        existing = [int(x) for x in re.findall(r"id: 'p(\d+)'", src)]
        new_pid = f"p{(max(existing) + 1) if existing else 1}"

    # Build the live pN block
    fields = [
        f"id: '{new_pid}', product: '{product}', direction: '{direction}',",
        f"date: '{date}', channel: '{channel}', account: '{account}',",
        f"url: '{url}',",
    ]
    status_line = f"score: {score}, comments: {comments}, status: 'live', kind: '{kind}',"
    if image:
        status_line += f" image: '{image}',"
    fields.append(status_line)
    if note:
        fields.append(f"note: {note!r},")

    # Find POSTS terminator (top-level `^];` after a `const POSTS = [`)
    posts_close = re.search(r"^\];", src, flags=re.MULTILINE)
    if not posts_close:
        console.print(f"[red]ERROR[/red] {path}: couldn't find POSTS `];` terminator")
        return

    # Match indent of last entry by walking back from `];`
    tail = src[:posts_close.start()].rstrip()
    indent_match = re.search(r"\n(\s+)\},\s*$", tail)
    indent = indent_match.group(1) if indent_match else "  "
    body_indent = indent + "  "
    new_block = (
        indent + "{\n"
        + "\n".join(body_indent + line for line in fields) + "\n"
        + indent + "},\n"
    )

    if dry_run:
        console.print(f"[cyan]dry-run[/cyan] {path}: would add {new_pid} ({score}↑/{comments}c, r/{channel.split('r/')[-1]})")
        return

    new_src = src[:posts_close.start()] + new_block + src[posts_close.start():]
    path.write_text(new_src)
    console.print(f"[green]✓[/green] {path}: added {new_pid} ({score}↑/{comments}c)")


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
    from gtm.identity.manager import IdentityManager
    from gtm.platforms.base import get_platform
    from gtm.safety.rate_limiter import get_rate_limiter
    from gtm.identity.selector import select_account, handle_account_failure

    mgr = IdentityManager()
    try:
        identity = select_account(mgr, platform, as_flag=as_identity, interactive=not json_output)
    except ValueError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"\n  [red]❌ {e}[/red]\n")
        sys.exit(1)
    plat = get_platform(platform)
    limiter = get_rate_limiter()

    # 5-layer rate limit check (coordinator wraps per-account limiter)
    from gtm.safety.coordinator import get_coordinator
    coordinator = get_coordinator()
    rl = coordinator.check(identity.name, platform, action, proxy=identity.proxy,
                           target_url=kwargs.get("url", ""))
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
        console.print("gtm-cli is NOT responsible for accounts banned while using --force.")
        if not click.confirm("Continue?", default=False):
            sys.exit(0)

    if dry_run:
        extra_info = {k: v for k, v in kwargs.items() if v}
        if json_output:
            click.echo(json.dumps({"dry_run": True, "platform": platform, "identity": identity.name, "text": text, **extra_info}))
        else:
            console.print("\n[dim]DRY RUN — nothing will be posted[/dim]")
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
        coordinator.record(identity.name, platform, action, target_url=kwargs.get("url", ""))
        identity.last_used = __import__("datetime").datetime.now().isoformat()
        identity.save()

        # Log to output repo
        from gtm.output.logger import log_post
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
            console.print("[green]✅ Posted![/green]")
            if result.url:
                console.print(f"   {result.url}")
    else:
        if json_output:
            click.echo(json.dumps({"success": False, "error": result.error}))
            sys.exit(1)

        # Post failed — ask user: rotate to another account or stop?
        alt = handle_account_failure(identity, mgr, platform, result.error or "Unknown error",
                                     interactive=not json_output)
        if alt:
            # Check rate limit for alternative account (full 5-layer)
            rl_alt = coordinator.check(alt.name, platform, action, proxy=alt.proxy,
                                        target_url=kwargs.get("url", ""))
            if not rl_alt.allowed and not force:
                console.print(f"  [yellow]Alternative account also rate-limited: {rl_alt.reason}[/yellow]")
                sys.exit(1)
            if not rl_alt.allowed and force:
                console.print("[bold red]⚠️  FORCE OVERRIDE on alternative account[/bold red]")
                console.print(f"Bypassing: {rl_alt.reason}")
                if not click.confirm("Continue?", default=False):
                    sys.exit(0)

            console.print(f"  Retrying with [bold]{alt.name}[/bold]...")
            result = await plat.post(alt.identity_dir, text, **kwargs)
            if result.success:
                # Record across all 5 layers + update identity metadata
                coordinator.record(alt.name, platform, action, target_url=kwargs.get("url", ""))
                alt.last_used = __import__("datetime").datetime.now().isoformat()
                alt.save()

                from gtm.output.logger import log_post
                log_post(platform, alt.name, text, {"post_id": result.post_id, "url": result.url}, **kwargs)
                console.print("[green]✅ Posted![/green]")
                if result.url:
                    console.print(f"   {result.url}")
            else:
                console.print(f"[red]❌ Retry also failed: {result.error}[/red]")
                sys.exit(1)
        else:
            sys.exit(1)


async def _do_user_tweets(platform: str, username: str, as_identity, count: int, json_output: bool):
    """Fetch recent tweets from a specific user."""
    from gtm.identity.manager import IdentityManager
    from gtm.identity.selector import select_account
    from gtm.platforms.twitter.client import TwitterClient

    mgr = IdentityManager()
    try:
        identity = select_account(mgr, platform, as_flag=as_identity, interactive=not json_output)
    except ValueError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"\n  [red]❌ {e}[/red]\n")
        sys.exit(1)
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
    from gtm.platforms.base import get_platform

    plat = get_platform(platform)

    # Reddit/HN search doesn't need auth — uses public APIs
    # Use a dummy identity_dir (won't be accessed for search)
    from gtm.config import IDENTITIES_DIR
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
    from gtm.platforms.base import get_platform
    from gtm.config import IDENTITIES_DIR

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
    from gtm.identity.manager import IdentityManager
    from gtm.identity.selector import select_account
    from gtm.platforms.base import get_platform

    mgr = IdentityManager()
    try:
        identity = select_account(mgr, platform, as_flag=as_identity, interactive=not json_output)
    except ValueError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"\n  [red]❌ {e}[/red]\n")
        sys.exit(1)
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
    from gtm.identity.manager import IdentityManager
    from gtm.identity.selector import select_account
    from gtm.platforms.base import get_platform
    from gtm.safety.rate_limiter import get_rate_limiter

    mgr = IdentityManager()
    try:
        identity = select_account(mgr, platform, as_flag=as_identity, interactive=True)
    except ValueError as e:
        console.print(f"\n  [red]❌ {e}[/red]\n")
        sys.exit(1)
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
    from gtm.identity.manager import IdentityManager
    from gtm.identity.selector import select_account
    from gtm.platforms.base import get_platform
    from gtm.safety.rate_limiter import get_rate_limiter

    mgr = IdentityManager()
    try:
        identity = select_account(mgr, platform, as_flag=as_identity, interactive=True)
    except ValueError as e:
        console.print(f"\n  [red]❌ {e}[/red]\n")
        sys.exit(1)
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
        console.print("[green]✅ Replied![/green]")
    else:
        console.print(f"[red]❌ Failed: {result.error}[/red]")
        sys.exit(1)


# ── Helpers ───────────────────────────────────────────────────────────


def _ensure_platforms_registered():
    """Import platform modules to trigger registration."""
    for mod in [
        "gtm.platforms.twitter.platform",
        "gtm.platforms.reddit.platform",
        "gtm.platforms.hn.platform",
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


def _prompt_and_save_identity(platform: str, username: str, metadata: dict) -> None:
    """Prompt for role, then save identity."""
    from gtm.identity.selector import prompt_role
    from gtm.identity.manager import IdentityManager

    # Check if user already has accounts on this platform
    mgr = IdentityManager()
    existing = mgr.list_platform(platform)

    if existing:
        console.print(f"\n  [dim]You have {len(existing)} other {platform} account(s): {', '.join(a.name for a in existing)}[/dim]")

    role = prompt_role(username)
    _save_identity(platform, username, metadata, role=role)


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

    _prompt_and_save_identity("twitter", username, {"auth_method": "cookies_manual"})
    console.print("\n     Test it: [bold]gtm twitter search 'AI agents' --count 3[/bold]")


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


def _auth_cookie_paste(platform: str, username: str, identity_dir: Path, raw: str, interactive: bool = True) -> None:
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

    if interactive:
        _prompt_and_save_identity(platform, username, {"auth_method": "cookies_manual"})
    else:
        _save_identity(platform, username, {"auth_method": "cookies_manual"}, role="default")
        console.print("\n  [green]✅ Cookies saved![/green]")
        console.print(f"     Identity: [bold]{platform}:{username}[/bold]")

    if platform == "reddit":
        console.print("\n     Test it: [bold]gtm reddit search 'test' --count 1[/bold]")
    else:
        console.print("\n     Test it: [bold]gtm hn search 'test' --count 1[/bold]")


def _generate_content(platform: str, prompt: str, **kwargs) -> str | None:
    """Generate platform-native content using LLM.

    Uses the style guide for platform-specific tone.
    Returns generated text or None on failure.
    """
    from gtm.agents.base import load_style_guide

    style = load_style_guide(platform)
    subreddit = kwargs.get("subreddit", "")

    platform_instructions = {
        "twitter": "Write a tweet (max 280 chars). Include relevant hashtags.",
        "reddit": f"Write a Reddit post title (first line) and body (rest) for r/{subreddit}. Follow the style guide exactly — all lowercase, no self-promotion.",
        "hn": "Write a Hacker News submission title. Clean, factual, no clickbait.",
    }

    full_prompt = (
        f"## Task\n{platform_instructions.get(platform, 'Write a social media post.')}\n\n"
        f"## User's Description\n{prompt}\n\n"
        f"## Style Rules\n{style}\n\n"
        f"## Output\nOutput ONLY the final text. Nothing else."
    )

    try:
        import subprocess
        # Pipe prompt via stdin (not process args — avoids exposure in process list)
        proc = subprocess.run(
            ["claude", "-p", "-", "--output-format", "text"],
            input=full_prompt,
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip()[:200] if proc.stderr else "unknown error"
            console.print(f"[yellow]Content generation failed: {err}[/yellow]")
            return None
        result = proc.stdout.strip() or None
        if result:
            return result
        console.print("[yellow]LLM returned empty response.[/yellow]")
        return None

    except ImportError:
        console.print("[yellow]Content generation requires claude-agent-sdk.[/yellow]")
        console.print("Install: [bold]pip install gtm-cli[agents][/bold]")
        return None
    except Exception as e:
        console.print(f"[yellow]Content generation failed: {e}[/yellow]")
        return None


def _handle_auth_error(error: Exception, platform: str) -> None:
    """Catch auth/expired errors and show re-auth instructions."""
    from gtm.platforms.twitter.client import TwitterAuthError

    if isinstance(error, TwitterAuthError):
        console.print("\n[bold red]🔑 Session expired[/bold red]")
        console.print(f"\n  Re-authenticate:  [bold]gtm auth {platform}[/bold]\n")
        sys.exit(1)


def _save_identity(platform: str, username: str, metadata: dict, role: str = "default"):
    """Create and save an Identity after successful auth."""
    from gtm.identity.manager import Identity

    identity = Identity(
        name=f"{platform}:{username}",
        platform=platform,
        username=username,
        auth_method=metadata.get("auth_method", "unknown"),
        role=role,
        rate_profile="conservative",
    )
    identity.save()


@main.group()
def warmup():
    """Warm-up list — handles to ping at launch time."""
    pass


@warmup.command("add")
@click.argument("handle")
@click.option("--launch", required=True, help="Launch slug (e.g. first-tree)")
@click.option("--platform", required=True,
              type=click.Choice(["twitter", "reddit"]))
@click.option("--notes", default="")
def warmup_add(handle, launch, platform, notes):
    """Add HANDLE to a launch's warm-up list."""
    from gtm.modules import warmup as wm
    wm.add(launch, handle, platform, notes)
    click.echo(f"Added {platform}:{handle} to warmup for '{launch}'.")


@warmup.command("list")
@click.option("--launch", default=None, help="Filter to one launch")
def warmup_list(launch):
    """List warm-up entries."""
    from gtm.modules import warmup as wm
    if launch:
        entries = wm.list_for_launch(launch)
        if not entries:
            click.echo(f"No warmup entries for '{launch}'.")
            return
        click.echo(f"{launch}:")
        for e in entries:
            note = f"  ({e['notes']})" if e.get("notes") else ""
            click.echo(f"  {e['platform']}:{e['handle']}  [{e['added_at']}]{note}")
    else:
        for lname in wm.all_launches():
            click.echo(f"{lname}: {len(wm.list_for_launch(lname))} entries")


@warmup.command("remove")
@click.argument("handle")
@click.option("--launch", required=True)
@click.option("--platform", required=True,
              type=click.Choice(["twitter", "reddit"]))
def warmup_remove(handle, launch, platform):
    """Remove HANDLE from a launch's warm-up list."""
    from gtm.modules import warmup as wm
    if wm.remove(launch, handle, platform):
        click.echo(f"Removed {platform}:{handle} from '{launch}'.")
    else:
        click.echo("Not found.", err=True)
        sys.exit(1)


@main.command()
@click.option("--posts-file", required=True, type=click.Path(exists=True),
              help="JSON file with list of {platform, url, id, title, identity}")
@click.option("--auto", is_flag=True,
              help="Auto-post buy_signal replies (default: draft only)")
def engagement(posts_file, auto):
    """Run the engagement loop on a list of live posts."""
    from gtm.agents.engagement_loop import run_engagement_loop
    from gtm.config import IDENTITIES_DIR
    from gtm.engine.runner import _build_agent_config

    setup_logging(False)
    config = _build_agent_config(IDENTITIES_DIR)
    posts = json.loads(Path(posts_file).read_text())

    digest = asyncio.run(
        run_engagement_loop(posts, config, draft_only=not auto)
    )
    click.echo(json.dumps(digest, indent=2))


# ── Launch ────────────────────────────────────────────────────────────


@main.group()
def launch():
    """Launch directory — scaffold, link, and inspect."""
    pass


def _resolve_launch_dir(launch_path: str | None):
    """Resolve a LaunchDir from --launch <path> or walk-up from cwd."""
    from gtm.launch import LaunchDir

    if launch_path:
        return LaunchDir.load(Path(launch_path).expanduser().resolve())
    found = LaunchDir.find()
    if not found:
        click.echo(
            "No .gtm-launch.yaml found in cwd or any parent. "
            "Run `gtm launch init` or pass --launch <path>.",
            err=True,
        )
        sys.exit(1)
    return found


def _prompt_products() -> list[dict]:
    """Interactively collect product entries."""
    products: list[dict] = []
    click.echo("\nAdd products (blank key to finish):")
    while True:
        key = click.prompt("  product key", default="", show_default=False).strip()
        if not key:
            break
        name = click.prompt("    name", default=key)
        tagline = click.prompt("    tagline", default="")
        status = click.prompt(
            "    status",
            default="active",
            type=click.Choice(["active", "next", "future"]),
        )
        products.append(
            {"key": key, "name": name, "tagline": tagline, "status": status}
        )
    return products


def _prompt_directions() -> list[dict]:
    """Interactively collect direction entries."""
    directions: list[dict] = []
    click.echo("\nAdd directions (blank key to finish):")
    while True:
        key = click.prompt("  direction key", default="", show_default=False).strip()
        if not key:
            break
        label = click.prompt("    label", default=key)
        directions.append({"key": key, "label": label})
    return directions


@launch.command("init")
@click.argument("path", required=False, type=click.Path())
def launch_init(path):
    """Scaffold a new launch directory at PATH (default: cwd)."""
    from gtm.launch import LAUNCH_MARKER, LaunchDir
    from gtm.launch.dir import build_default_config, scaffold_layout

    target = Path(path).expanduser().resolve() if path else Path.cwd().resolve()
    marker = target / LAUNCH_MARKER
    if marker.exists():
        click.echo(
            f"{marker} already exists. Use `gtm launch info` to inspect, "
            f"or delete it first to re-init.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Initializing launch dir at {target}")
    products = _prompt_products()
    directions = _prompt_directions()

    cf_project = click.prompt(
        "Cloudflare Pages project name (blank to skip)",
        default="",
        show_default=False,
    ).strip()
    dashboard = {"cloudflare_project": cf_project} if cf_project else {}

    config = build_default_config(
        products=products,
        directions=directions,
        default_identity_by_platform={},
        dashboard=dashboard,
    )
    ld = LaunchDir(path=target, config=config)
    created = scaffold_layout(target, products)
    ld.write_marker()

    click.echo(f"\n✓ Wrote {ld.marker_path}")
    if created:
        click.echo(f"✓ Created {len(created)} files/dirs:")
        for p in created:
            click.echo(f"    {p.relative_to(target)}")
    click.echo(f"\nNext: `cd {target} && gtm launch info`")


@launch.command("link")
@click.argument("path", required=False, type=click.Path(exists=True, file_okay=False))
def launch_link(path):
    """Mark an existing directory as a launch dir.

    DOES NOT overwrite any existing files (dashboard.html, README.md, posts/, …).
    Only writes `.gtm-launch.yaml` after collecting prompts.
    """
    from gtm.launch import LAUNCH_MARKER, LaunchDir
    from gtm.launch.dir import build_default_config

    target = Path(path).expanduser().resolve() if path else Path.cwd().resolve()
    marker = target / LAUNCH_MARKER
    if marker.exists():
        click.echo(f"{marker} already exists. Nothing to do.", err=True)
        sys.exit(1)

    click.echo(f"Linking existing dir as launch dir: {target}")
    # Heuristic: any subdir with a posts/ folder OR ROADMAP.md is probably a product
    inferred = []
    for child in sorted(target.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "posts").is_dir() or (child / "ROADMAP.md").is_file():
            inferred.append(child.name)
    if inferred:
        click.echo(f"Inferred products from existing subdirs: {', '.join(inferred)}")
        if click.confirm("Use these as the product list?", default=True):
            products = [
                {"key": k, "name": k, "tagline": "", "status": "active"}
                for k in inferred
            ]
        else:
            products = _prompt_products()
    else:
        products = _prompt_products()

    directions = _prompt_directions()

    cf_project = click.prompt(
        "Cloudflare Pages project name (blank to skip)",
        default="",
        show_default=False,
    ).strip()
    dashboard = {"cloudflare_project": cf_project} if cf_project else {}

    config = build_default_config(
        products=products,
        directions=directions,
        default_identity_by_platform={},
        dashboard=dashboard,
    )
    ld = LaunchDir(path=target, config=config)
    ld.write_marker()
    click.echo(f"\n✓ Wrote {ld.marker_path} (existing files untouched)")


@launch.command("info")
@click.option("--launch", "launch_path", default=None,
              help="Explicit launch dir path (default: walk up from cwd)")
def launch_info(launch_path):
    """Print the current launch dir's config."""
    ld = _resolve_launch_dir(launch_path)
    click.echo(f"Launch dir: {ld.path}")
    click.echo(f"Marker:     {ld.marker_path}")
    click.echo(f"Version:    {ld.config.get('version', '?')}")

    click.echo("\nProducts:")
    if not ld.products:
        click.echo("  (none)")
    for p in ld.products:
        tag = f" — {p['tagline']}" if p.get("tagline") else ""
        click.echo(f"  • {p.get('key')} [{p.get('status', '?')}]{tag}")

    click.echo("\nDirections:")
    if not ld.directions:
        click.echo("  (none)")
    for d in ld.directions:
        click.echo(f"  • {d.get('key')} — {d.get('label')}")

    click.echo("\nDefault identities:")
    di = ld.default_identity_by_platform
    if not di:
        click.echo("  (none)")
    for plat, ident in di.items():
        click.echo(f"  • {plat}: {ident}")

    dash = ld.dashboard_config
    if dash:
        click.echo("\nDashboard:")
        for k, v in dash.items():
            click.echo(f"  • {k}: {v}")


@main.group()
def post():
    """Post lifecycle — list, status, (later) draft / submit / sync."""
    pass


def _format_relative(iso_ts: str | None) -> str:
    """Render an ISO timestamp as a coarse relative string (e.g. '3h', '2d').

    Empty / unparseable inputs return '-'. This is dashboard-grade rough, not
    a full humanize lib.
    """
    if not iso_ts:
        return "-"
    from datetime import datetime, timezone
    try:
        # Tolerate 'Z' suffix
        ts = iso_ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
    except (ValueError, TypeError):
        return iso_ts
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        return f"{secs // 3600}h"
    return f"{secs // 86400}d"


@post.command("list")
@click.option("--product", "product_filter", default=None,
              help="Filter to one product key")
@click.option("--status", "status_filter", default=None,
              help="Filter to one status (drafting|scheduled|live|removed)")
@click.option("--direction", "direction_filter", default=None,
              help="Filter to one direction key (matches frontmatter `direction`)")
@click.option("--launch", "launch_path", default=None,
              help="Explicit launch dir path (default: walk up from cwd)")
def post_list(product_filter, status_filter, direction_filter, launch_path):
    """Tabulate every post under the launch dir, newest first."""
    from rich.console import Console
    from rich.table import Table

    from gtm.launch import Post

    ld = _resolve_launch_dir(launch_path)
    posts = Post.find_all(ld)

    if product_filter:
        posts = [p for p in posts if p.product == product_filter]
    if status_filter:
        posts = [p for p in posts if p.status == status_filter]
    if direction_filter:
        posts = [p for p in posts if p.direction == direction_filter]

    console = Console()
    if not posts:
        console.print(f"0 posts in {ld.path}")
        return

    table = Table(title=f"Posts in {ld.path}", show_lines=False)
    table.add_column("id", style="cyan", no_wrap=True)
    table.add_column("product")
    table.add_column("direction")
    table.add_column("channel")
    table.add_column("identity")
    table.add_column("status")
    table.add_column("score", justify="right")
    table.add_column("comments", justify="right")
    table.add_column("posted_at")

    for p in posts:
        table.add_row(
            p.id or "-",
            p.product or "-",
            p.direction or "-",
            p.channel or "-",
            p.identity or "-",
            p.status or "-",
            str(p.score),
            str(p.comments),
            _format_relative(p.posted_at),
        )

    console.print(table)
    console.print(f"\n{len(posts)} post{'s' if len(posts) != 1 else ''}")


@post.command("status")
@click.argument("slug")
@click.option("--launch", "launch_path", default=None,
              help="Explicit launch dir path (default: walk up from cwd)")
def post_status(slug, launch_path):
    """Print one post's full frontmatter + body length."""
    from gtm.launch import Post

    ld = _resolve_launch_dir(launch_path)
    posts = Post.find_all(ld)
    match = next((p for p in posts if p.slug == slug or p.id == slug), None)
    if not match:
        click.echo(
            f"No post found with slug or id '{slug}' in {ld.path}.\n"
            f"Hint: run `gtm post list --launch {ld.path}` to see available slugs.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Post: {match.path}")
    click.echo(f"Slug: {match.slug}")
    click.echo("\nFrontmatter:")
    for k, v in match.frontmatter.items():
        if isinstance(v, dict):
            click.echo(f"  {k}:")
            for kk, vv in v.items():
                click.echo(f"    {kk}: {vv}")
        else:
            click.echo(f"  {k}: {v}")
    click.echo(f"\nBody length: {len(match.body)} chars ({len(match.body.splitlines())} lines)")


if __name__ == "__main__":
    main()
