"""Built-in Tools — ready-to-use tools for Agent Swarm agents.

Zero external dependencies. All tools use Python stdlib only.

Usage:
    from agent_swarm.tools import ToolRegistry, BUILTIN_TOOLS

    # Use all built-in tools
    swarm = Swarm(llm=my_llm, tools=BUILTIN_TOOLS)

    # Or select specific tools
    from agent_swarm.tools import web_search, file_read, http_fetch
    swarm = Swarm(llm=my_llm, tools=[web_search, file_read, http_fetch])

    # Register custom tools
    registry = ToolRegistry()
    registry.register(my_custom_tool)

Available tools:
    web_search  — Search the web via DuckDuckGo (no API key needed)
    http_fetch  — Fetch URL content (HTML → text extraction)
    file_read   — Read local file contents
    file_write  — Write content to local file
    shell_exec  — Execute shell command (sandboxed timeout)
    json_parse  — Parse and query JSON/dict data
"""

__all__ = ['Tool', 'ToolRegistry', 'SAFE_TOOLS', 'BUILTIN_TOOLS', 'DEFAULT_REGISTRY']
import html
import json
import os
import re
import shlex
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Tool:
    """A callable tool that agents can use."""
    name: str
    description: str
    parameters: Dict[str, str] = field(default_factory=dict)  # param_name → description
    fn: Optional[Callable] = None
    safe: bool = True  # If False, requires explicit opt-in

    def __call__(self, **kwargs) -> str:
        if self.fn is None:
            return f"Tool '{self.name}' has no implementation"
        try:
            result = self.fn(**kwargs)
            return str(result) if result is not None else ""
        except Exception as e:
            return f"Tool error ({self.name}): {e}"

    def to_schema(self) -> Dict:
        """JSON schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    k: {"type": "string", "description": v}
                    for k, v in self.parameters.items()
                },
                "required": list(self.parameters.keys()),
            },
        }


class ToolRegistry:
    """Manage and dispatch tools."""

    def __init__(self, tools: List[Tool] = None):
        self._tools: Dict[str, Tool] = {}
        if tools:
            for t in tools:
                self.register(t)

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list(self) -> List[Tool]:
        return list(self._tools.values())

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def schemas(self) -> List[Dict]:
        return [t.to_schema() for t in self._tools.values()]

    def call(self, name: str, **kwargs) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Unknown tool: {name}"
        return tool(**kwargs)

    def format_for_prompt(self) -> str:
        """Format tool descriptions for inclusion in LLM prompt."""
        if not self._tools:
            return ""
        lines = ["[Available Tools]"]
        for t in self._tools.values():
            params = ", ".join(f"{k}: {v}" for k, v in t.parameters.items())
            lines.append(f"  - {t.name}({params}): {t.description}")
        lines.append("To use a tool, respond with: TOOL_CALL: tool_name(param=value)")
        return "\n".join(lines)


# ── Built-in Tool Implementations ──────────────────

def _web_search(query: str, max_results: str = "5") -> str:
    """Search the web using DuckDuckGo HTML (no API key needed)."""
    try:
        n = min(int(max_results), 10)
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgentSwarm/1.0)"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_content = resp.read().decode("utf-8", errors="replace")

        # Extract results from DuckDuckGo HTML
        results = []
        # Find result blocks
        blocks = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html_content, re.DOTALL)
        for href, title in blocks[:n]:
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            # Extract actual URL from DDG redirect
            if "uddg=" in href:
                actual = urllib.parse.unquote(href.split("uddg=")[-1].split("&")[0])
            else:
                actual = href
            results.append(f"- {clean_title}\n  {actual}")

        # Extract snippets
        snippets = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', html_content, re.DOTALL)
        for i, snip in enumerate(snippets[:n]):
            clean = re.sub(r'<[^>]+>', '', snip).strip()
            if i < len(results):
                results[i] += f"\n  {clean[:200]}"

        if not results:
            return f"No results found for: {query}"
        return f"Search results for '{query}':\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Search failed: {e}"


def _validate_url(url: str) -> Optional[str]:
    """Validate URL to prevent SSRF. Returns error message or None if safe."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return "Invalid URL format"
    if parsed.scheme not in ("http", "https"):
        return f"Blocked URL scheme: {parsed.scheme} (only http/https allowed)"
    hostname = parsed.hostname or ""
    if not hostname:
        return "Missing hostname"
    # Block private/internal IPs and cloud metadata
    blocked = ("localhost", "127.", "10.", "172.16.", "172.17.", "172.18.", "172.19.",
               "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
               "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
               "192.168.", "169.254.", "0.", "[::1]", "metadata.google",
               "metadata.aws", "100.100.100.200")
    if any(hostname.startswith(b) or hostname == b.rstrip(".") for b in blocked):
        return f"Blocked internal/private URL: {hostname}"
    return None


def _http_fetch(url: str, max_length: str = "5000") -> str:
    """Fetch URL content and extract text."""
    try:
        url_err = _validate_url(url)
        if url_err:
            return f"Fetch blocked: {url_err}"
        ml = min(int(max_length), 50000)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgentSwarm/1.0)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", errors="replace")

        if "json" in content_type:
            try:
                return json.dumps(json.loads(raw), indent=2, ensure_ascii=False)[:ml]
            except Exception:
                pass

        # Strip HTML tags for readability
        text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) > ml:
            text = text[:ml] + "\n[TRUNCATED]"
        return text
    except Exception as e:
        return f"Fetch failed: {e}"


def _file_read(path: str, max_lines: str = "500") -> str:
    """Read a local file."""
    try:
        ml = min(int(max_lines), 10000)
        if not os.path.isfile(path):
            return f"File not found: {path}"
        with open(path, "r", errors="replace") as f:
            lines = f.readlines()
        if len(lines) > ml:
            return "".join(lines[:ml]) + f"\n[TRUNCATED: {len(lines)} total lines, showing {ml}]"
        return "".join(lines)
    except Exception as e:
        return f"File read failed: {e}"


def _file_write(path: str, content: str, base_dir: str = None) -> str:
    """Write content to a local file. Requires base_dir for safety."""
    try:
        if base_dir is None:
            base_dir = os.getcwd()
        resolved = os.path.realpath(os.path.join(base_dir, path))
        if not resolved.startswith(os.path.realpath(base_dir)):
            return f"File write blocked: path '{path}' escapes base directory '{base_dir}'"
        if os.path.isabs(path) and not path.startswith(os.path.realpath(base_dir)):
            return f"File write blocked: absolute path '{path}' outside base directory"
        path = resolved
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"File write failed: {e}"


_BLOCKED_COMMANDS = frozenset({
    "rm", "rmdir", "del", "format", "mkfs", "dd",
    "curl", "wget", "nc", "ncat", "netcat",
    "chmod", "chown", "chgrp", "sudo", "su",
    "shutdown", "reboot", "halt", "poweroff",
    "kill", "killall", "pkill",
})

_BLOCKED_PATTERNS = ("| sh", "| bash", "| zsh", "> /dev/", "| curl", "| wget",
                     "$(",  "`", "&&rm", "; rm", ";rm")


def _shell_exec(command: str, timeout: str = "30") -> str:
    """Execute a shell command with timeout. Blocks dangerous commands."""
    try:
        # Check blocklist
        parts = shlex.split(command)
        base_cmd = os.path.basename(parts[0]).lower() if parts else ""
        if base_cmd in _BLOCKED_COMMANDS:
            return f"Shell exec blocked: '{base_cmd}' is not allowed"
        cmd_lower = command.lower()
        for pat in _BLOCKED_PATTERNS:
            if pat in cmd_lower:
                return f"Shell exec blocked: dangerous pattern detected"
        to = min(int(timeout), 120)
        result = subprocess.run(
            parts, capture_output=True, text=True,
            timeout=to, cwd=os.getcwd()
        )
        output = ""
        if result.stdout:
            output += result.stdout[:5000]
        if result.stderr:
            output += f"\n[STDERR] {result.stderr[:2000]}"
        if result.returncode != 0:
            output += f"\n[EXIT CODE: {result.returncode}]"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Shell exec failed: {e}"


def _json_parse(data: str, query: str = "") -> str:
    """Parse JSON string and optionally extract a field using dot notation."""
    try:
        obj = json.loads(data)
        if query:
            for key in query.split("."):
                if isinstance(obj, dict):
                    obj = obj.get(key, f"Key not found: {key}")
                elif isinstance(obj, list) and key.isdigit():
                    obj = obj[int(key)]
                else:
                    return f"Cannot navigate '{key}' in {type(obj).__name__}"
        return json.dumps(obj, indent=2, ensure_ascii=False) if isinstance(obj, (dict, list)) else str(obj)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"


# ── Tool Definitions ───────────────────────────────

web_search = Tool(
    name="web_search",
    description="Search the web. Returns titles, URLs, and snippets.",
    parameters={"query": "Search query", "max_results": "Max results (default 5)"},
    fn=_web_search,
)

http_fetch = Tool(
    name="http_fetch",
    description="Fetch a URL and return its text content.",
    parameters={"url": "URL to fetch", "max_length": "Max chars to return (default 5000)"},
    fn=_http_fetch,
)

file_read = Tool(
    name="file_read",
    description="Read contents of a local file.",
    parameters={"path": "File path to read", "max_lines": "Max lines (default 500)"},
    fn=_file_read,
)

file_write = Tool(
    name="file_write",
    description="Write content to a local file.",
    parameters={"path": "File path to write", "content": "Content to write"},
    fn=_file_write,
    safe=False,
)

shell_exec = Tool(
    name="shell_exec",
    description="Execute a shell command and return output.",
    parameters={"command": "Shell command to run", "timeout": "Timeout seconds (default 30)"},
    fn=_shell_exec,
    safe=False,
)

json_parse = Tool(
    name="json_parse",
    description="Parse JSON and optionally query with dot notation (e.g., 'data.items.0.name').",
    parameters={"data": "JSON string", "query": "Dot-notation path (optional)"},
    fn=_json_parse,
)

# Safe tools (no side effects)
SAFE_TOOLS = [web_search, http_fetch, file_read, json_parse]

# All tools (including potentially dangerous ones)
BUILTIN_TOOLS = [web_search, http_fetch, file_read, file_write, shell_exec, json_parse]

# Default registry
DEFAULT_REGISTRY = ToolRegistry(SAFE_TOOLS)
