"""Agent Swarm Pro SDK — call Pro server from local code.

This is a thin HTTP client. All logic runs on the server.
The user never sees server code.

Usage:
    pip install agent-swarm-core

    from agent_swarm.pro_client import ProClient

    client = ProClient(api_key="ask_xxx", server="https://agentswarm.dev")

    # Submit a run
    run = client.submit("Analyze AI market trends")
    print(run)  # {"run_id": "run_abc", "state": "queued"}

    # Wait for completion
    result = client.wait(run["run_id"])

    # Get proof
    proof = client.proof(run["run_id"])
    print(proof["tasks_completed"])

    # Approve/reject
    client.approve(run["run_id"], approved=True, notes="Looks good")

    # Import local workspace
    client.import_workspace("my_workspace.json")
"""

__all__ = ['ProClient', 'ProClientError']

import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Dict, List, Optional


class ProClientError(Exception):
    """Error from Pro server."""
    def __init__(self, status: int, message: str, detail: str = ""):
        self.status = status
        self.message = message
        self.detail = detail
        super().__init__(f"[{status}] {message}" + (f" — {detail}" if detail else ""))


class ProClient:
    """SDK for Agent Swarm Pro server.

    Thin HTTP client — all logic runs on the server.
    Zero dependencies beyond Python stdlib.

    Args:
        api_key: Your Pro API key (ask_xxx...)
        server: Pro server URL (default: http://localhost:8000)
    """

    def __init__(self, api_key: str, server: str = None):
        self.api_key = api_key
        self.server = (server or os.environ.get("AGENT_SWARM_SERVER", "http://localhost:8000")).rstrip("/")
        self._timeout = 30

    # ── Runs ───────────────────────────────────────

    def submit(self, goal: str, tasks: List[Dict] = None,
               playbook: str = "", context: str = "",
               requires_approval: bool = False, priority: int = 5) -> Dict:
        """Submit a run to the server.

        Args:
            goal: What you want the agents to do
            tasks: Optional list of task dicts [{"id":"t1","description":"...","role":"...","dependencies":[]}]
            playbook: Optional playbook name (discover, review, etc.)
            context: Additional context
            requires_approval: Whether run needs manual approval
            priority: 1=highest, 10=lowest

        Returns:
            {"run_id": "run_xxx", "state": "queued", "proof_url": "/api/runs/run_xxx/proof"}
        """
        body = {"goal": goal, "priority": priority,
                "requires_approval": requires_approval}
        if tasks:
            body["tasks"] = tasks
        if playbook:
            body["playbook"] = playbook
        if context:
            body["context"] = context
        return self._post("/api/runs", body)

    def get_run(self, run_id: str) -> Dict:
        """Get run details and current state."""
        return self._get(f"/api/runs/{run_id}")

    def list_runs(self, state: str = None) -> List[Dict]:
        """List your runs. Optional filter by state."""
        url = "/api/runs"
        if state:
            url += f"?state={state}"
        return self._get(url).get("runs", [])

    def cancel(self, run_id: str) -> Dict:
        """Cancel a queued or running run."""
        return self._post(f"/api/runs/{run_id}/cancel", {})

    def wait(self, run_id: str, timeout: float = 300, poll_interval: float = 2) -> Dict:
        """Wait for a run to complete. Returns final run state.

        Args:
            run_id: Run to wait for
            timeout: Max seconds to wait
            poll_interval: Seconds between status checks
        """
        start = time.time()
        terminal = {"completed", "failed", "rejected", "cancelled"}
        while time.time() - start < timeout:
            run = self.get_run(run_id)
            state = run.get("state", "")
            if state in terminal:
                return run
            time.sleep(poll_interval)
        raise ProClientError(408, f"Timeout waiting for run {run_id} after {timeout}s")

    # ── Proof Bundle ───────────────────────────────

    def proof(self, run_id: str) -> Dict:
        """Get proof bundle for a completed run.

        Returns tasks, tokens, cost, approval status, state history.
        """
        return self._get(f"/api/runs/{run_id}/proof")

    # ── Approvals ──────────────────────────────────

    def pending_approvals(self) -> List[Dict]:
        """List runs waiting for your approval."""
        return self._get("/api/approvals").get("approvals", [])

    def approve(self, run_id: str, approved: bool = True, notes: str = "") -> Dict:
        """Approve or reject a run.

        Args:
            run_id: Run to decide on
            approved: True to approve, False to reject
            notes: Optional notes explaining decision
        """
        return self._post(f"/api/approvals/{run_id}",
                          {"approved": approved, "notes": notes})

    # ── Billing ────────────────────────────────────

    def billing(self) -> Dict:
        """Get your current plan, usage, and limits."""
        return self._get("/api/billing")

    def plans(self) -> Dict:
        """List available plans and pricing."""
        return self._get("/api/billing/plans")

    # ── Workspace ──────────────────────────────────

    def import_workspace(self, path: str) -> Dict:
        """Import a local workspace export to Pro server.

        Requires Pro plan. Free users will get 403.

        Args:
            path: Path to workspace JSON file (from: python -m agent_swarm export)
        """
        with open(path) as f:
            data = json.load(f)
        return self._post("/api/workspace/import", data)

    def workspace_status(self) -> Dict:
        """Check if imported workspace data exists on server."""
        return self._get("/api/workspace/status")

    # ── Webhooks ───────────────────────────────────

    def send_webhook(self, payload: Dict) -> Dict:
        """Send a generic webhook to trigger a run.

        Args:
            payload: {"goal": "...", "context": "...", "priority": 5}
        """
        return self._post("/api/webhooks/generic", payload)

    # ── Keys ───────────────────────────────────────

    def list_keys(self) -> List[Dict]:
        """List your API keys."""
        return self._get("/api/keys").get("keys", [])

    # ── Scheduler (Pro) ────────────────────────────

    def schedule(self, goal: str, cron: str, context: str = "") -> Dict:
        """Create a scheduled recurring run.

        Args:
            goal: What to execute on each run
            cron: Cron expression (e.g., "0 9 * * MON" = Monday 9am)
            context: Additional context for each run

        Examples:
            client.schedule("Competitor analysis", cron="0 9 * * MON")   # Weekly Monday 9am
            client.schedule("AI news summary", cron="0 8 * * *")         # Daily 8am
            client.schedule("Monthly report", cron="0 10 1 * *")         # 1st of month
        """
        return self._post("/api/schedules",
                          {"goal": goal, "cron": cron, "context": context})

    def list_schedules(self) -> List[Dict]:
        """List your scheduled jobs."""
        return self._get("/api/schedules").get("schedules", [])

    def delete_schedule(self, schedule_id: str) -> Dict:
        """Delete a scheduled job."""
        return self._request("DELETE", f"/api/schedules/{schedule_id}")

    # ── Chain (Pro) ────────────────────────────────

    def chain(self, steps: List[Dict], stop_on_failure: bool = True) -> Dict:
        """Submit a multi-step run chain.

        Each step gets the previous step's result as context automatically.

        Args:
            steps: List of {"goal": "..."} dicts
            stop_on_failure: Stop chain if any step fails

        Example:
            client.chain([
                {"goal": "Research competitors"},
                {"goal": "Compare findings"},        # gets step 1 result
                {"goal": "Write strategy report"},   # gets step 2 result
            ])
        """
        return self._post("/api/chains",
                          {"steps": steps, "stop_on_failure": stop_on_failure})

    def list_chains(self) -> List[Dict]:
        """List your run chains."""
        return self._get("/api/chains").get("chains", [])

    def get_chain(self, chain_id: str) -> Dict:
        """Get chain details and status of each step."""
        return self._get(f"/api/chains/{chain_id}")

    # ── Reports (Pro) ─────────────────────────────

    def report(self, run_id: str) -> Dict:
        """Generate a shareable HTML report from a completed run.

        Returns report_id and shareable URL.
        """
        return self._post(f"/api/reports/{run_id}", {})

    def report_url(self, run_id: str) -> str:
        """Generate report and return the shareable URL."""
        r = self.report(run_id)
        return f"{self.server}{r.get('url', '')}"

    def list_reports(self) -> List[Dict]:
        """List your generated reports."""
        return self._get("/api/reports").get("reports", [])

    # ── Health ─────────────────────────────────────

    def health(self) -> Dict:
        """Check server health."""
        return self._get_no_auth("/api/health")

    # ── SSE Events ─────────────────────────────────

    def events(self, timeout: float = 30):
        """Stream real-time events from the server (generator).

        Usage:
            for event in client.events(timeout=60):
                print(event)
        """
        url = f"{self.server}/api/events/stream"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                buffer = ""
                for line in resp:
                    line = line.decode("utf-8", errors="replace")
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data:
                            try:
                                yield json.loads(data)
                            except json.JSONDecodeError:
                                pass
        except (urllib.error.URLError, TimeoutError):
            return

    # ── Internal ───────────────────────────────────

    def _get(self, path: str) -> Dict:
        return self._request("GET", path)

    def _get_no_auth(self, path: str) -> Dict:
        url = f"{self.server}{path}"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            try:
                detail = json.loads(body).get("detail", "")
            except Exception:
                detail = body[:200]
            raise ProClientError(e.code, e.reason, detail)
        except urllib.error.URLError as e:
            raise ProClientError(0, f"Connection failed: {self.server}", str(e))

    def _post(self, path: str, body: Dict) -> Dict:
        return self._request("POST", path, body)

    def _request(self, method: str, path: str, body: Dict = None) -> Dict:
        url = f"{self.server}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode() if e.fp else ""
            try:
                detail = json.loads(body_text).get("detail", "")
            except Exception:
                detail = body_text[:200]
            raise ProClientError(e.code, e.reason, detail)
        except urllib.error.URLError as e:
            raise ProClientError(0, f"Connection failed: {self.server}", str(e))

    def __repr__(self):
        return f"ProClient(server='{self.server}', key='{self.api_key[:12]}...')"
