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
        # Reddit & HN: browser-based manual login
        if not username:
            username = click.prompt(f"{'Reddit' if platform == 'reddit' else 'Hacker News'} username")

        identity_dir = IDENTITIES_DIR / platform / username
        platform_name = "Reddit" if platform == "reddit" else "Hacker News"

        console.print(f"\nOpening Chrome for {platform_name} login...")
        console.print("Please log in manually in the browser window.")
        console.print("(Handle any CAPTCHA/2FA prompts)")

        try:
            metadata = asyncio.run(
                plat.auth_interactive(identity_dir, username=username)
            )
            _save_identity(platform, username, metadata)
            console.print(f"[green]✅ Login detected! Session saved.[/green]")
            console.print(f"   Identity: [bold]{platform}:{username}[/bold]")
        except Exception as e:
            console.print(f"[red]❌ Login failed: {e}[/red]")
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


# ── Shared Action Helpers ─────────────────────────────────────────────


async def _do_post(platform: str, action: str, text: str, as_identity, dry_run, force, json_output):
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
        if json_output:
            click.echo(json.dumps({"dry_run": True, "platform": platform, "identity": identity.name, "text": text}))
        else:
            console.print(f"\n[dim]DRY RUN — nothing will be posted[/dim]")
            console.print(f"  Platform: {platform}")
            console.print(f"  Account:  {identity.name}")
            console.print(f"  Content:  {text}")
        return

    # Execute
    result = await plat.post(identity.identity_dir, text)

    if result.success:
        limiter.record(identity.name, action)
        identity.last_used = __import__("datetime").datetime.now().isoformat()
        identity.save()

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
    try:
        import growth.platforms.twitter.platform  # noqa: F401
    except ImportError:
        pass
    # Reddit and HN will be added as they're migrated
    # try:
    #     import growth.platforms.reddit.platform
    #     import growth.platforms.hn.platform
    # except ImportError:
    #     pass


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
