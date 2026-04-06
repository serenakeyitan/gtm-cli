"""Run state management — read/write/persist state.json for each pipeline run."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RunState:
    run_id: str
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "running"  # running | paused | completed | failed
    current_phase: str = "init"
    scout_output: list[dict[str, Any]] = field(default_factory=list)
    novelty_output: list[dict[str, Any]] = field(default_factory=list)
    build_results: list[dict[str, Any]] = field(default_factory=list)
    test_results: list[dict[str, Any]] = field(default_factory=list)
    promote_results: list[dict[str, Any]] = field(default_factory=list)
    approvals: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    activity_stats: dict[str, Any] = field(default_factory=dict)
    completed_at: str | None = None

    def set_scout_output(self, ideas: list[dict[str, Any]]) -> None:
        self.scout_output = ideas
        self.current_phase = "scout_done"

    def set_novelty_output(self, ideas: list[dict[str, Any]]) -> None:
        self.novelty_output = ideas
        self.current_phase = "novelty_done"

    def add_build_result(self, result: dict[str, Any]) -> None:
        self.build_results.append(result)

    def set_builds_complete(self) -> None:
        self.current_phase = "builds_done"

    def add_test_result(self, result: dict[str, Any]) -> None:
        self.test_results.append(result)

    def set_tests_complete(self) -> None:
        self.current_phase = "tests_done"

    def add_promote_result(self, result: dict[str, Any]) -> None:
        self.promote_results.append(result)

    def set_promote_complete(self) -> None:
        self.current_phase = "promote_done"

    def approved_ideas(self, phase: str) -> list[dict[str, Any]]:
        """Get approved ideas for a given phase, or all if no approval recorded."""
        approval = self.approvals.get(phase)
        if phase == "scout":
            source = self.scout_output
        elif phase == "novelty":
            source = self.novelty_output
        else:
            return []

        if approval is None:
            return source

        approved_ids = set(approval.get("approved_ids", []))
        if not approved_ids:
            return source
        return [i for i in source if i.get("id") in approved_ids]

    def record_approval(self, phase: str, approved_ids: list[str] | None = None) -> None:
        self.approvals[phase] = {
            "approved": True,
            "approved_ids": approved_ids or [],
            "timestamp": datetime.now().isoformat(),
        }

    def record_rejection(self, phase: str, reason: str = "") -> None:
        self.approvals[phase] = {
            "approved": False,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }

    def add_error(self, phase: str, error: str, fatal: bool = False) -> None:
        self.errors.append(
            {
                "phase": phase,
                "error": error,
                "fatal": fatal,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def set_activity_stats(self, stats: dict[str, Any]) -> None:
        """Store per-agent activity statistics from the ActivityLogger."""
        self.activity_stats = stats

    def mark_complete(self) -> None:
        self.status = "completed"
        self.current_phase = "done"
        self.completed_at = datetime.now().isoformat()

    def mark_failed(self, reason: str = "") -> None:
        self.status = "failed"
        self.add_error(self.current_phase, reason, fatal=True)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, run_dir: Path) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "state.json"
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path

    @classmethod
    def load(cls, run_dir: Path) -> RunState:
        path = run_dir / "state.json"
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def create(cls, run_id: str) -> RunState:
        return cls(run_id=run_id)


def generate_run_id() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M")


def get_run_dir(run_id: str, base: Path | None = None) -> Path:
    base = base or Path("runs")
    return base / run_id
