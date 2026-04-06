"""Activity logging — granular event stream for every agent action.

Captures tool calls, decisions, assistant messages, and errors as an
append-only JSONL file.

Directory layout ("Both, but separate"):
  runs/{run_id}/
    activity_summary.json     ← quick summary (overseer reads this first)
    state.json                ← pipeline state
    report.md                 ← markdown report
    detailed/
      activity_log.jsonl      ← full event stream (overseer dives in if needed)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ── Event Types ──
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_ASSISTANT_MESSAGE = "assistant_message"
EVENT_DECISION = "decision"
EVENT_AGENT_START = "agent_start"
EVENT_AGENT_END = "agent_end"
EVENT_ERROR = "error"
EVENT_CLUSTER_DETECTED = "cluster_detected"
EVENT_CHECKPOINT = "checkpoint"


@dataclass
class ActivityEvent:
    """A single logged event in the activity stream.

    Schema designed for downstream agent consumption.  Every event carries
    enough context for another agent to reconstruct a hierarchical context
    tree:  pipeline → run → phase → agent → step.

    Fields:
        ts          – epoch seconds (float) for fast machine sorting
        timestamp   – ISO-8601 for human readability
        pipeline    – pipeline identity string
        run_id      – unique run identifier
        phase       – pipeline phase (scout / novelty / build / promote / pipeline)
        agent       – agent name within the phase
        step        – monotonic step counter per agent
        event       – event type constant (EVENT_*)
        is_test     – True when the run was started with --test
        detail      – event-specific payload
        duration_ms – optional wall-clock duration of the logged action
    """

    ts: float
    timestamp: str
    pipeline: str  # e.g. "twitter-reddit-github" — identifies which pipeline
    run_id: str
    phase: str  # scout | novelty | build | promote | pipeline
    agent: str
    step: int
    event: str  # one of the EVENT_* constants
    is_test: bool = False
    detail: dict[str, Any] = field(default_factory=dict)
    duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Drop None fields for cleaner JSONL
        return {k: v for k, v in d.items() if v is not None}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class ActivityLogger:
    """Append-only activity logger that writes JSONL to a run directory.

    Usage:
        logger = ActivityLogger(run_id, run_dir, pipeline_name="twitter-reddit-github")
        logger.log_agent_start("scout", prompt="...")
        logger.log_tool_call("scout", "twitter_search", {"query": "AI"}, result={...}, duration_ms=120)
        logger.log_agent_end("scout", result={...})
        logger.flush()
    """

    def __init__(
        self,
        run_id: str,
        run_dir: Path,
        pipeline_name: str = "unknown",
        is_test: bool = False,
    ) -> None:
        self.run_id = run_id
        self.run_dir = run_dir
        self.pipeline_name = pipeline_name
        self.is_test = is_test
        self._current_phase: str = "pipeline"  # updated by set_phase()
        self._step_counters: dict[str, int] = {}
        self._stats: dict[str, dict[str, int]] = {}

        # "Both, but separate" layout:
        #   detailed/activity_log.jsonl  ← full event stream
        #   activity_summary.json        ← quick summary at top level
        self._detailed_dir = run_dir / "detailed"
        self._log_path = self._detailed_dir / "activity_log.jsonl"
        self._buffer: list[str] = []
        self._flush_every = 10  # flush to disk every N events

        run_dir.mkdir(parents=True, exist_ok=True)
        self._detailed_dir.mkdir(parents=True, exist_ok=True)
        log.debug("ActivityLogger initialized: %s", self._log_path)

    def set_phase(self, phase: str) -> None:
        """Set the current pipeline phase (scout/novelty/build/promote)."""
        self._current_phase = phase

    # ── Step Counter ──

    def _next_step(self, agent: str) -> int:
        """Get the next step number for a given agent."""
        self._step_counters.setdefault(agent, 0)
        self._step_counters[agent] += 1
        return self._step_counters[agent]

    # ── Stats Tracking ──

    def _increment_stat(self, agent: str, key: str, amount: int = 1) -> None:
        self._stats.setdefault(agent, {})
        self._stats[agent][key] = self._stats[agent].get(key, 0) + amount

    def get_stats(self) -> dict[str, dict[str, int]]:
        """Return per-agent statistics."""
        return dict(self._stats)

    def get_agent_stats(self, agent: str) -> dict[str, int]:
        """Return statistics for a specific agent."""
        return dict(self._stats.get(agent, {}))

    # ── Core Write ──

    def _write_event(self, event: ActivityEvent) -> None:
        """Buffer an event and flush periodically."""
        line = event.to_json()
        self._buffer.append(line)
        self._increment_stat(event.agent, "total_events")

        if len(self._buffer) >= self._flush_every:
            self.flush()

    def flush(self) -> None:
        """Write buffered events to disk."""
        if not self._buffer:
            return
        with open(self._log_path, "a") as f:
            for line in self._buffer:
                f.write(line + "\n")
        self._buffer.clear()

    # ── Event Factory ──

    def _make_event(
        self, agent: str, step: int, event: str,
        detail: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> ActivityEvent:
        """Create an ActivityEvent with all context fields populated."""
        now = datetime.now()
        return ActivityEvent(
            ts=now.timestamp(),
            timestamp=now.isoformat(),
            pipeline=self.pipeline_name,
            run_id=self.run_id,
            phase=self._current_phase,
            agent=agent,
            step=step,
            event=event,
            is_test=self.is_test,
            detail=detail or {},
            duration_ms=duration_ms,
        )

    # ── High-Level Logging Methods ──

    def log_agent_start(self, agent: str, **detail: Any) -> None:
        """Log that an agent has started executing."""
        self._step_counters[agent] = 0
        self._write_event(self._make_event(agent, 0, EVENT_AGENT_START, detail))
        self._increment_stat(agent, "started")

    def log_agent_end(self, agent: str, **detail: Any) -> None:
        """Log that an agent has finished executing."""
        step = self._step_counters.get(agent, 0) + 1
        self._write_event(self._make_event(agent, step, EVENT_AGENT_END, detail))
        self._increment_stat(agent, "completed")
        self.flush()  # always flush on agent end

    def log_tool_call(
        self,
        agent: str,
        tool_name: str,
        tool_input: Any,
        tool_output: Any = None,
        duration_ms: int | None = None,
    ) -> None:
        """Log a tool invocation with input, output, and timing."""
        step = self._next_step(agent)

        # Truncate large outputs to keep logs manageable
        output_summary = _truncate(tool_output, max_len=2000)
        input_summary = _truncate(tool_input, max_len=1000)

        self._write_event(self._make_event(
            agent, step, EVENT_TOOL_CALL,
            detail={
                "tool": tool_name,
                "input": input_summary,
                "output": output_summary,
            },
            duration_ms=duration_ms,
        ))
        self._increment_stat(agent, "tool_calls")
        self._increment_stat(agent, f"tool:{tool_name}")

    def log_assistant_message(self, agent: str, text: str) -> None:
        """Log an assistant text message (reasoning, decisions, etc.)."""
        step = self._next_step(agent)
        self._write_event(self._make_event(
            agent, step, EVENT_ASSISTANT_MESSAGE,
            detail={"text": _truncate_str(text, 3000)},
        ))
        self._increment_stat(agent, "messages")

    def log_decision(self, agent: str, decision: str, **detail: Any) -> None:
        """Log a key decision point (cluster detected, idea rejected, etc.)."""
        step = self._next_step(agent)
        self._write_event(self._make_event(
            agent, step, EVENT_DECISION,
            detail={"decision": decision, **detail},
        ))
        self._increment_stat(agent, "decisions")

    def log_error(self, agent: str, error: str, **detail: Any) -> None:
        """Log an error during agent execution."""
        step = self._next_step(agent)
        self._write_event(self._make_event(
            agent, step, EVENT_ERROR,
            detail={"error": error, **detail},
        ))
        self._increment_stat(agent, "errors")
        self.flush()  # always flush on error

    def log_checkpoint(self, phase: str, action: str, **detail: Any) -> None:
        """Log a human checkpoint approval/rejection."""
        self._write_event(self._make_event(
            "pipeline", self._next_step("pipeline"), EVENT_CHECKPOINT,
            detail={"phase": phase, "action": action, **detail},
        ))

    # ── Summary Generation ──

    def generate_summary(self) -> dict[str, Any]:
        """Generate a summary of all activity for the run.

        This summary lives at runs/{run_id}/activity_summary.json (top level).
        The full JSONL lives at runs/{run_id}/detailed/activity_log.jsonl.
        """
        self.flush()
        return {
            "pipeline": self.pipeline_name,
            "run_id": self.run_id,
            "is_test": self.is_test,
            "generated_at": datetime.now().isoformat(),
            "total_events": sum(
                s.get("total_events", 0) for s in self._stats.values()
            ),
            "per_agent": {
                agent: {
                    "total_events": stats.get("total_events", 0),
                    "tool_calls": stats.get("tool_calls", 0),
                    "messages": stats.get("messages", 0),
                    "decisions": stats.get("decisions", 0),
                    "errors": stats.get("errors", 0),
                }
                for agent, stats in self._stats.items()
                if agent != "pipeline"
            },
            "pipeline_events": self._stats.get("pipeline", {}),
            "detailed_log": str(self._log_path),
        }

    def save_summary(self) -> Path:
        """Save the activity summary as a JSON file."""
        self.flush()
        summary = self.generate_summary()
        path = self.run_dir / "activity_summary.json"
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)
        return path


# ── Helpers ──

def _truncate(obj: Any, max_len: int = 2000) -> Any:
    """Truncate a value to keep logs manageable."""
    if obj is None:
        return None
    s = json.dumps(obj, default=str) if not isinstance(obj, str) else obj
    if len(s) > max_len:
        return s[:max_len] + f"... [truncated, {len(s)} chars total]"
    # Return original type if it wasn't truncated
    return obj


def _truncate_str(s: str, max_len: int = 3000) -> str:
    """Truncate a string."""
    if len(s) > max_len:
        return s[:max_len] + f"... [truncated, {len(s)} chars total]"
    return s


class ToolTimer:
    """Context manager to time tool calls.

    Usage:
        with ToolTimer() as t:
            result = do_something()
        logger.log_tool_call("scout", "my_tool", input, result, duration_ms=t.elapsed_ms)
    """

    def __init__(self) -> None:
        self.start_time: float = 0
        self.elapsed_ms: int = 0

    def __enter__(self) -> ToolTimer:
        self.start_time = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed_ms = int((time.monotonic() - self.start_time) * 1000)
