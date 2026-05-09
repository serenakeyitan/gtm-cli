# CP9 + CP10 — sub-rule auto-fetch + submit gate

> **Status: ✅ SHIPPED.** Both checkpoints landed on `main` on 2026-05-05
> (PR #13 was the merge anchor; PR #14 was closed in-flight as its
> content cascaded). 26 e2e checks. The auto-fetcher is now the
> `gtm reddit fetch-sub-rules` command; the hard preflight gate runs on
> every `gtm reddit submit` (override with `--no-preflight` or
> `--override`). This file is preserved as the historical design record.

**Why:** today, `gtm reddit preflight` returns PASS for any sub not in
`gtm/data/reddit_sub_rules.yaml` (only `rule_found=False`). That means we
can post to a brand-new sub with zero knowledge of its self-promo rule,
flair requirement, or karma gate. User asks: "read the subreddit rule
every time you select subreddits to post — this should be a built-in step."

This is two checkpoints, atomic per checkpoint, stacked.

## CP9 — auto-fetch sub rules from Reddit when missing or stale

**Module:** `gtm/modules/sub_rules_fetcher.py`

```python
fetch_sub_meta(sub: str) -> dict
  # Pulls https://www.reddit.com/r/<sub>/about.json + /rules.json.
  # Returns {subscribers, public_description, rules: [...], created_utc,
  #          submission_type ('any'|'link'|'self'), flair_required: bool,
  #          fetched_at: iso8601}.
  # Raises FetchError on 404/timeout/JSON.

derive_yaml_entry(meta: dict) -> dict
  # Heuristics → YAML row:
  #   - flair_required: scan rule titles + submission_type
  #   - notes: join rule short_names, subscriber count, scope hint
  #   - permanent_skip: false (default; only humans set true)
  #   - min_*: null (api doesn't expose these; humans add post-removal)
  #   - last_fetched: iso8601 utc
  #   - source: 'auto' (vs 'manual' for human-curated)

upsert_sub_rule(sub, entry, path=DEFAULT_RULES_PATH) -> None
  # Inserts/merges entry into yaml under subs.<sub>. Preserves human-set
  # fields (min_*, permanent_skip, notes if source=manual).

is_stale(entry, max_age_days=30) -> bool
  # last_fetched older than max_age_days → True.
```

**CLI:** `gtm reddit fetch-sub-rules <sub> [--force]`
- Fetches, merges, writes YAML, prints what changed.

**Constraints:**
- One file changed per concern: fetcher module is new, YAML schema gains
  `last_fetched` + `source` keys (backward-compat: missing = treated as
  manual, never auto-overwritten).
- No new deps. Uses stdlib `urllib` like preflight.py does.
- All markdown-driven: NO TypeScript, no JS. Pure Python + YAML.

## CP10 — wire preflight into submit as hard gate

**Edits:** `gtm/launch/submit.py`, `gtm/launch/post.py`, `gtm/cli.py` (the
submit subcommand).

Flow on `gtm post submit <id>`:
1. Read post frontmatter → extract sub from channel.
2. Call preflight (which will auto-fetch via CP9 if missing/stale).
3. Verdict:
   - `PASS` → proceed
   - `BORDERLINE` → print warning + proceed unless `--strict`
   - `FAIL` → block. Print reasons + notes. Require `--override "<reason>"`
     to proceed (recorded in post frontmatter).
4. Always print sub `notes` (e.g., "flair required", "10% rule") before
   submitting so the operator sees the rule even on PASS.

**E2E coverage (CP9 + CP10 combined ≥ 30 checks):**
- CP9: missing → auto-fetch → yaml updated; stale → refetch; manual rule
  preserved; `--no-fetch` flag respected; permanent_skip not overwritten.
- CP10: PASS proceeds; FAIL blocks; FAIL + --override proceeds + records;
  BORDERLINE warns; --strict treats borderline as fail; notes printed.

## Order of operations
1. Land CP9 (PR off main).
2. Branch CP10 off CP9 (stacked).
3. After both merged, retire d4's "skip — sub spam risk" check from being a
   manual judgment call — preflight will catch it.

## What this does NOT do
- Doesn't read sidebar HTML. Sidebar rules text is the most accurate source
  but requires HTML parsing; api `/about.json` + `/rules.json` are 80% of
  the value with 0 dep cost.
- Doesn't detect the ChatGPTCoding "flair UI bug" (that's a Playwright
  issue, not a rule).
- Doesn't enforce "Pale already posted to this sub yesterday" (that's a
  per-account rate concern; separate CP).
