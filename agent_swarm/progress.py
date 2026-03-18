"""Terminal Progress Display — real-time execution visualization.

Shows Swarm Cycle phases and task progress in the terminal.
No external dependencies — uses ANSI escape codes.

Usage:
    from agent_swarm.progress import ProgressDisplay
    
    progress = ProgressDisplay()
    progress.start("Analyze competitors", tasks=["research", "compare", "report"])
    progress.set_phase("scout")
    progress.update_task("research", "running")
    progress.update_task("research", "success", time_s=1.2)
    progress.finish()
"""
import sys
import time
from typing import Dict, List, Optional


# ANSI colors
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    PURPLE = "\033[35m"
    WHITE = "\033[37m"
    BG_SURFACE = "\033[48;5;234m"
    CLEAR_LINE = "\033[2K"
    UP = "\033[A"
    HIDE_CURSOR = "\033[?25l"
    SHOW_CURSOR = "\033[?25h"


PHASE_ICONS = {
    "idle": "○",
    "scout": "🔍",
    "build": "🔨",
    "guard": "🛡️",
    "evolve": "🧬",
    "done": "✓",
}

STATUS_ICONS = {
    "pending": f"{C.DIM}○{C.RESET}",
    "running": f"{C.CYAN}◉{C.RESET}",
    "success": f"{C.GREEN}✓{C.RESET}",
    "failed": f"{C.RED}✗{C.RESET}",
    "waiting": f"{C.YELLOW}⏳{C.RESET}",
    "skipped": f"{C.DIM}—{C.RESET}",
}

PHASE_COLORS = {
    "idle": C.DIM,
    "scout": C.CYAN,
    "build": C.PURPLE,
    "guard": C.YELLOW,
    "evolve": C.GREEN,
    "done": C.GREEN,
}


class ProgressDisplay:
    """Terminal-based real-time progress display."""

    def __init__(self, enable: bool = True):
        self.enabled = enable and sys.stdout.isatty()
        self.mission = ""
        self.phase = "idle"
        self.tasks: Dict[str, Dict] = {}
        self.task_order: List[str] = []
        self.skills: Dict[str, float] = {}
        self.log: List[str] = []
        self._start_time = 0
        self._lines_drawn = 0

    def start(self, mission: str, tasks: List[str] = None):
        """Start progress display."""
        self.mission = mission
        self._start_time = time.time()
        if tasks:
            for tid in tasks:
                self.tasks[tid] = {"status": "pending", "role": "", "time": 0}
                self.task_order.append(tid)
        if self.enabled:
            print(C.HIDE_CURSOR, end="")
        self._draw()

    def set_phase(self, phase: str):
        """Set current Swarm Cycle phase: scout/build/guard/evolve/done."""
        self.phase = phase
        self.log.append(f"{PHASE_ICONS.get(phase, '○')} {phase.upper()} phase")
        self._draw()

    def add_task(self, task_id: str, role: str = ""):
        """Register a task."""
        if task_id not in self.tasks:
            self.tasks[task_id] = {"status": "pending", "role": role, "time": 0}
            self.task_order.append(task_id)

    def update_task(self, task_id: str, status: str, role: str = None, time_s: float = None):
        """Update task status: pending/running/success/failed/waiting."""
        if task_id not in self.tasks:
            self.add_task(task_id)
        self.tasks[task_id]["status"] = status
        if role:
            self.tasks[task_id]["role"] = role
        if time_s:
            self.tasks[task_id]["time"] = time_s
        self._draw()

    def update_skill(self, name: str, fitness: float):
        """Update skill fitness."""
        self.skills[name] = fitness
        self._draw()

    def add_log(self, msg: str):
        """Add activity log entry."""
        elapsed = time.time() - self._start_time
        self.log.append(f"[{elapsed:.1f}s] {msg}")
        if len(self.log) > 8:
            self.log.pop(0)
        self._draw()

    def finish(self):
        """Finish display."""
        self.phase = "done"
        self._draw()
        if self.enabled:
            print(C.SHOW_CURSOR)
            print()

    def _draw(self):
        if not self.enabled:
            return

        # Clear previous output
        if self._lines_drawn > 0:
            sys.stdout.write(f"\033[{self._lines_drawn}A")

        lines = []
        elapsed = time.time() - self._start_time

        # Header
        lines.append(f"{C.BOLD}{'─' * 60}{C.RESET}")
        lines.append(f"{C.BOLD}  Agent Swarm{C.RESET} — {self.mission[:45]}")
        lines.append(f"{'─' * 60}")

        # Swarm Cycle phases
        phases = ["scout", "build", "guard", "evolve"]
        phase_str = "  "
        for i, p in enumerate(phases):
            idx = phases.index(self.phase) if self.phase in phases else -1
            if self.phase == "done":
                phase_str += f"{C.GREEN}{C.BOLD}✓ {p}{C.RESET}"
            elif p == self.phase:
                phase_str += f"{PHASE_COLORS[p]}{C.BOLD}▶ {p.upper()}{C.RESET}"
            elif i < idx:
                phase_str += f"{C.GREEN}✓ {p}{C.RESET}"
            else:
                phase_str += f"{C.DIM}○ {p}{C.RESET}"
            if i < len(phases) - 1:
                phase_str += f" {C.DIM}→{C.RESET} "
        lines.append(phase_str)
        lines.append("")

        # Tasks
        done = sum(1 for t in self.tasks.values() if t["status"] == "success")
        total = len(self.tasks)
        lines.append(f"  {C.BOLD}Tasks{C.RESET} {done}/{total}  {C.DIM}|{C.RESET}  {elapsed:.1f}s")

        for tid in self.task_order:
            t = self.tasks[tid]
            icon = STATUS_ICONS.get(t["status"], "○")
            role = f" {C.DIM}({t['role']}){C.RESET}" if t["role"] else ""
            time_str = f" {C.DIM}{t['time']:.1f}s{C.RESET}" if t["time"] else ""
            lines.append(f"    {icon} {tid}{role}{time_str}")

        # Skills
        if self.skills:
            lines.append("")
            lines.append(f"  {C.BOLD}Skills{C.RESET}")
            for name, fitness in self.skills.items():
                bar_len = 20
                filled = int(fitness * bar_len)
                bar = f"{C.GREEN}{'█' * filled}{C.RESET}{C.DIM}{'░' * (bar_len - filled)}{C.RESET}"
                lines.append(f"    {name[:18]:18s} {bar} {fitness*100:.0f}%")

        # Log
        if self.log:
            lines.append("")
            lines.append(f"  {C.BOLD}Log{C.RESET}")
            for entry in self.log[-5:]:
                lines.append(f"    {C.DIM}{entry}{C.RESET}")

        lines.append(f"{C.BOLD}{'─' * 60}{C.RESET}")

        # Output
        output = "\n".join(f"{C.CLEAR_LINE}{line}" for line in lines)
        sys.stdout.write(output + "\n")
        sys.stdout.flush()
        self._lines_drawn = len(lines)
