"""Tracker Adapter — event-driven triggers that auto-create runs.

Transforms Agent Swarm from "you call it" to "events trigger it."

Supported triggers:
    - Webhook (generic HTTP POST)
    - GitHub Issues (via webhook payload)
    - Schedule (periodic polling)
    - Manual queue

Usage:
    from agent_swarm.tracker import TrackerAdapter, WebhookTrigger

    tracker = TrackerAdapter(run_machine)
    tracker.register(WebhookTrigger())

    # GitHub webhook fires → run auto-created
    tracker.handle_webhook({
        "action": "labeled",
        "label": {"name": "ready"},
        "issue": {"number": 42, "title": "Fix auth bug", "body": "..."}
    })

For a full HTTP server:
    tracker.start_server(port=9000)
    # POST http://localhost:9000/webhook → triggers runs
"""

__all__ = [
    'TriggerEvent', 'TriggerFilter', 'LabelFilter', 'PriorityFilter',
    'TrackerAdapter', 'AutomationRule', 'AutomationRegistry',
]
import asyncio
import json
import re
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler


@dataclass
class TriggerEvent:
    """A trigger event that may create a run."""
    source: str         # github, linear, webhook, schedule, manual
    event_type: str     # issue_labeled, issue_opened, webhook_received, scheduled
    ref: str = ""       # issue#42, LIN-123
    goal: str = ""      # Extracted goal/description
    context: str = ""   # Additional context
    priority: int = 5
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_run_config(self):
        from .run_machine import RunConfig
        return RunConfig(
            goal=self.goal, trigger=self.source, trigger_ref=self.ref,
            context=self.context, priority=self.priority, metadata=self.metadata,
        )


class TriggerFilter:
    """Base class for trigger filters — decides if an event should create a run."""
    def should_trigger(self, event: TriggerEvent) -> bool:
        return True

class LabelFilter(TriggerFilter):
    """Only trigger on specific labels (e.g., 'ready', 'agent-swarm')."""
    def __init__(self, labels: List[str]):
        self.labels = {l.lower() for l in labels}
    def should_trigger(self, event: TriggerEvent) -> bool:
        event_labels = {l.lower() for l in event.metadata.get("labels", [])}
        return bool(self.labels & event_labels)

class PriorityFilter(TriggerFilter):
    """Only trigger if priority is high enough."""
    def __init__(self, max_priority: int = 5):
        self.max_priority = max_priority
    def should_trigger(self, event: TriggerEvent) -> bool:
        return event.priority <= self.max_priority


class TrackerAdapter:
    """Central adapter that receives events and creates runs."""

    def __init__(self, run_machine=None):
        self._run_machine = run_machine
        self._filters: List[TriggerFilter] = []
        self._parsers: Dict[str, Callable] = {}  # source → parser function
        self._on_trigger: List[Callable] = []
        self._event_log: List[Dict] = []

        # Register default parsers
        self._parsers["github"] = self._parse_github
        self._parsers["linear"] = self._parse_linear
        self._parsers["webhook"] = self._parse_generic_webhook

    def add_filter(self, f: TriggerFilter):
        self._filters.append(f)

    def on_trigger(self, callback: Callable):
        """Register callback: callback(TriggerEvent, run_id)"""
        self._on_trigger.append(callback)

    def register_parser(self, source: str, parser: Callable):
        """Register custom event parser: parser(payload) → TriggerEvent or None"""
        self._parsers[source] = parser

    def handle_webhook(self, payload: Dict, source: str = None) -> Optional[str]:
        """Process incoming webhook payload. Returns run_id if triggered, None otherwise.
        Source is auto-detected from payload if not specified."""
        if source is None:
            # Auto-detect source
            if "issue" in payload or "pull_request" in payload:
                source = "github"
            elif "data" in payload and "identifier" in payload.get("data", {}):
                source = "linear"
            else:
                source = "webhook"

        parser = self._parsers.get(source, self._parse_generic_webhook)
        event = parser(payload)
        if event is None:
            return None

        # Apply filters
        for f in self._filters:
            if not f.should_trigger(event):
                self._event_log.append({"event": event.event_type, "ref": event.ref,
                                        "filtered": True, "timestamp": time.time()})
                return None

        # Create run
        run_id = None
        if self._run_machine:
            config = event.to_run_config()
            run_id = self._run_machine.submit(config)

        self._event_log.append({"event": event.event_type, "ref": event.ref,
                                "run_id": run_id, "timestamp": time.time()})

        for cb in self._on_trigger:
            try:
                cb(event, run_id)
            except Exception:
                pass

        return run_id

    def handle_schedule(self, goal: str, context: str = "", priority: int = 5) -> Optional[str]:
        """Manually schedule a run (for cron/periodic triggers)."""
        event = TriggerEvent(source="schedule", event_type="scheduled",
                             goal=goal, context=context, priority=priority)
        if self._run_machine:
            return self._run_machine.submit(event.to_run_config())
        return None

    def event_log(self, limit: int = 50) -> List[Dict]:
        return self._event_log[-limit:]

    # ── Parsers ────────────────────────────────────

    @staticmethod
    def _parse_github(payload: Dict) -> Optional[TriggerEvent]:
        """Parse GitHub webhook payload."""
        action = payload.get("action", "")
        issue = payload.get("issue", {})
        pr = payload.get("pull_request", {})

        # Issue labeled with trigger label
        if action == "labeled" and issue:
            label = payload.get("label", {}).get("name", "")
            return TriggerEvent(
                source="github", event_type="issue_labeled",
                ref=f"issue#{issue.get('number', '')}",
                goal=issue.get("title", ""),
                context=issue.get("body", "")[:2000],
                metadata={"labels": [l["name"] for l in issue.get("labels", [])],
                          "url": issue.get("html_url", ""),
                          "author": issue.get("user", {}).get("login", "")},
            )

        # Issue opened
        if action == "opened" and issue:
            return TriggerEvent(
                source="github", event_type="issue_opened",
                ref=f"issue#{issue.get('number', '')}",
                goal=issue.get("title", ""),
                context=issue.get("body", "")[:2000],
                metadata={"labels": [l["name"] for l in issue.get("labels", [])],
                          "url": issue.get("html_url", "")},
                priority=7,  # Lower priority for newly opened (may not be ready)
            )

        # PR review requested
        if action == "review_requested" and pr:
            return TriggerEvent(
                source="github", event_type="pr_review_requested",
                ref=f"pr#{pr.get('number', '')}",
                goal=f"Review PR: {pr.get('title', '')}",
                context=pr.get("body", "")[:2000],
                metadata={"url": pr.get("html_url", ""),
                          "diff_url": pr.get("diff_url", "")},
                priority=3,
            )

        return None

    @staticmethod
    def _parse_linear(payload: Dict) -> Optional[TriggerEvent]:
        """Parse Linear webhook payload."""
        action = payload.get("action", "")
        data = payload.get("data", {})

        if action == "update" and data.get("state", {}).get("name") == "Ready":
            return TriggerEvent(
                source="linear", event_type="issue_ready",
                ref=data.get("identifier", ""),
                goal=data.get("title", ""),
                context=data.get("description", "")[:2000],
                metadata={"url": data.get("url", ""),
                          "labels": [l.get("name", "") for l in data.get("labels", [])]},
            )
        return None

    @staticmethod
    def _parse_generic_webhook(payload: Dict) -> Optional[TriggerEvent]:
        """Parse generic webhook."""
        return TriggerEvent(
            source="webhook", event_type="webhook_received",
            goal=payload.get("goal", payload.get("title", payload.get("message", ""))),
            context=payload.get("context", payload.get("body", payload.get("description", "")))[:2000],
            ref=payload.get("ref", payload.get("id", "")),
            priority=payload.get("priority", 5),
            metadata=payload,
        )

    # ── HTTP Server (lightweight webhook receiver) ──

    def start_server(self, port: int = 9000, background: bool = True, webhook_secret: str = None):
        """Start a lightweight HTTP server to receive webhooks.
        If webhook_secret is set, requests must include valid HMAC signature."""
        adapter = self
        secret = webhook_secret

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8", errors="replace")

                # HMAC signature verification (GitHub-style X-Hub-Signature-256)
                if secret:
                    import hmac as _hmac, hashlib as _hashlib
                    sig_header = self.headers.get("X-Hub-Signature-256", "")
                    expected = "sha256=" + _hmac.new(
                        secret.encode(), body.encode(), _hashlib.sha256
                    ).hexdigest()
                    if not _hmac.compare_digest(sig_header, expected):
                        self.send_response(403)
                        self.end_headers()
                        self.wfile.write(b'{"error":"Invalid signature"}')
                        return

                try:
                    payload = json.loads(body)
                except Exception:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'{"error":"Invalid JSON"}')
                    return

                # Detect source from headers
                source = "webhook"
                if self.headers.get("X-GitHub-Event"):
                    source = "github"
                elif self.headers.get("X-Linear-Event"):
                    source = "linear"

                run_id = adapter.handle_webhook(payload, source)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "triggered" if run_id else "filtered",
                    "run_id": run_id,
                }).encode())

            def log_message(self, format, *args):
                pass  # Suppress HTTP logs

        server = HTTPServer(("127.0.0.1", port), Handler)
        if background:
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            return server
        else:
            server.serve_forever()


# ── Automation Layer (event-driven agent triggers) ──────────────

@dataclass(frozen=True)
class AutomationRule:
    """Event-driven automation rule.

    Like a smart home rule: "when motion detected (trigger) → turn on lights (action)."
    Automation rules define what happens when specific events occur.
    Immutable — runtime state is tracked separately in AutomationRegistry.
    """
    name: str
    trigger_source: str          # "github", "linear", "schedule", "webhook", "*"
    trigger_pattern: str = ""    # regex pattern to match event goal/ref
    action: str = ""             # goal template for the triggered run
    priority: int = 5
    enabled: bool = True
    cooldown_s: float = 60.0     # min seconds between triggers
    max_daily: int = 100         # max triggers per day


@dataclass
class _RuleState:
    """Mutable runtime state for an automation rule (internal only)."""
    last_triggered: float = 0.0
    daily_count: int = 0
    daily_reset: float = 0.0


class AutomationRegistry:
    """Registry of automation rules with cooldown and rate limiting.

    Always-on agents triggered by events from external systems.
    Rules define trigger → action mappings with cooldown and rate limiting.
    Runtime state (cooldown, daily counts) is kept in the registry, not on the rule.
    """

    def __init__(self, tracker: Optional[TrackerAdapter] = None):
        self._rules: Dict[str, AutomationRule] = {}
        self._state: Dict[str, _RuleState] = {}
        self._tracker = tracker
        self._execution_log: List[Dict] = []
        self._lock = threading.Lock()

    def register(self, rule: AutomationRule) -> None:
        """Register an automation rule."""
        with self._lock:
            self._rules[rule.name] = rule
            self._state[rule.name] = _RuleState()

    def unregister(self, name: str) -> bool:
        """Remove a rule. Returns True if found."""
        with self._lock:
            self._state.pop(name, None)
            return self._rules.pop(name, None) is not None

    def get(self, name: str) -> Optional[AutomationRule]:
        """Get a rule by name."""
        return self._rules.get(name)

    def list_rules(self) -> List[AutomationRule]:
        """List all rules."""
        return list(self._rules.values())

    def list_enabled(self) -> List[AutomationRule]:
        """List only enabled rules."""
        return [r for r in self._rules.values() if r.enabled]

    def match(self, event: TriggerEvent) -> List[AutomationRule]:
        """Find rules that match a trigger event."""
        now = time.time()
        matched = []

        with self._lock:
            for rule in self._rules.values():
                if not rule.enabled:
                    continue

                # Source match
                if rule.trigger_source != "*" and rule.trigger_source != event.source:
                    continue

                # Pattern match
                if rule.trigger_pattern:
                    text = f"{event.goal} {event.ref} {event.context}"
                    if not re.search(rule.trigger_pattern, text, re.IGNORECASE):
                        continue

                state = self._state.setdefault(rule.name, _RuleState())

                # Cooldown check
                if now - state.last_triggered < rule.cooldown_s:
                    continue

                # Daily limit check
                if state.daily_reset == 0.0 or now - state.daily_reset > 86400:
                    state.daily_count = 0
                    state.daily_reset = now
                if state.daily_count >= rule.max_daily:
                    continue

                matched.append(rule)

        return matched

    def execute(self, event: TriggerEvent) -> List[Optional[str]]:
        """Execute matching automation rules for an event.

        Returns list of run_ids created (None if tracker not configured).
        """
        matched = self.match(event)
        run_ids = []
        now = time.time()

        for rule in matched:
            # Build goal from template or use event goal
            goal = rule.action if rule.action else event.goal

            # Update runtime state (thread-safe)
            with self._lock:
                state = self._state.setdefault(rule.name, _RuleState())
                state.last_triggered = now
                state.daily_count += 1

            run_id = None
            if self._tracker:
                run_id = self._tracker.handle_schedule(
                    goal=goal,
                    context=event.context,
                    priority=rule.priority,
                )

            with self._lock:
                self._execution_log.append({
                    "rule": rule.name,
                    "event_source": event.source,
                    "event_ref": event.ref,
                    "run_id": run_id,
                    "timestamp": now,
                })
            run_ids.append(run_id)

        return run_ids

    def execution_log(self, limit: int = 50) -> List[Dict]:
        """Get recent execution history."""
        return self._execution_log[-limit:]

    @property
    def count(self) -> int:
        return len(self._rules)
