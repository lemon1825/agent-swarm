"""Auto-tool integration — LLM automatically calls tools when needed.

Usage:
    from agent_swarm import Swarm, openai, auto_tools

    swarm = Swarm(llm=auto_tools(openai()))

    # Agent will automatically use web_search, json_parse, etc.
    result = await swarm.run("Research Cursor's latest pricing")

The wrapper:
1. Appends available tool descriptions to the prompt
2. Detects tool call patterns in LLM output (e.g. TOOL_CALL: web_search(...))
3. Executes the tool
4. Feeds result back to LLM for final answer
"""

__all__ = ['auto_tools']

import json
import re
from typing import Callable, Dict, List, Optional

from .tools import SAFE_TOOLS, BUILTIN_TOOLS, ToolRegistry


_TOOL_INSTRUCTION = """

You have access to the following tools. To use a tool, write EXACTLY this format on its own line:
TOOL_CALL: tool_name(param1="value1", param2="value2")

Available tools:
{tool_descriptions}

Rules:
- Use tools when you need real data, file access, or computation
- You can use multiple tools (one per line)
- After tool results are provided, give your final answer
- If you don't need tools, just answer directly
"""


def auto_tools(llm: Callable, tools: List = None, max_tool_rounds: int = 3) -> Callable:
    """Wrap an LLM function to automatically call tools.

    Args:
        llm: Base LLM function (async def llm(prompt, tools=None) -> str)
        tools: Tool list (default: SAFE_TOOLS — web_search, json_parse, file_read, file_write)
        max_tool_rounds: Max rounds of tool calls before forcing final answer

    Returns:
        Wrapped LLM function with auto-tool capability
    """
    registry = ToolRegistry(tools or SAFE_TOOLS)
    tool_desc = _format_tool_descriptions(registry)
    instruction = _TOOL_INSTRUCTION.format(tool_descriptions=tool_desc)

    async def wrapped(prompt: str, tools_param=None) -> str:
        # Append tool instruction to prompt
        augmented = prompt + instruction

        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        output = ""

        for round_num in range(max_tool_rounds + 1):
            # Call LLM
            response = await llm(augmented, tools_param)

            # Extract output and usage
            if isinstance(response, tuple):
                output, usage = response
                for k in total_usage:
                    total_usage[k] += usage.get(k, 0)
            else:
                output = str(response) if response else ""

            # Check for tool calls
            tool_calls = _extract_tool_calls(output)
            if not tool_calls or round_num == max_tool_rounds:
                # No more tool calls or max rounds — return final answer
                clean = _remove_tool_calls(output)
                if total_usage["total_tokens"] > 0:
                    return (clean, total_usage)
                return clean

            # Execute tools and build context
            tool_results = []
            for tc in tool_calls:
                try:
                    result = _execute_tool(tc, registry)
                    tool_results.append(f"TOOL_RESULT ({tc['name']}): {result}")
                except Exception as e:
                    tool_results.append(f"TOOL_ERROR ({tc['name']}): {e}")

            # Build next prompt with results
            results_text = "\n".join(tool_results)
            augmented = (
                f"{prompt}\n\n"
                f"Previous response:\n{output}\n\n"
                f"Tool results:\n{results_text}\n\n"
                f"Now provide your final answer based on the tool results."
            )

        # Should not reach here
        return output

    return wrapped


def _format_tool_descriptions(registry: ToolRegistry) -> str:
    lines = []
    for schema in registry.schemas():
        name = schema["name"]
        desc = schema.get("description", "")
        params = schema.get("parameters", {}).get("properties", {})
        param_str = ", ".join(f'{k}="{v.get("description", k) if isinstance(v, dict) else k}"'
                              for k, v in params.items())
        lines.append(f"  - {name}({param_str}): {desc}")
    return "\n".join(lines)


def _extract_tool_calls(text: str) -> List[Dict]:
    """Extract TOOL_CALL: name(args) patterns from text."""
    calls = []
    pattern = r'TOOL_CALL:\s*(\w+)\(([^)]*)\)'
    for match in re.finditer(pattern, text):
        name = match.group(1)
        args_str = match.group(2)
        args = _parse_tool_args(args_str)
        calls.append({"name": name, "args": args, "raw": match.group(0)})
    return calls


def _parse_tool_args(args_str: str) -> Dict:
    """Parse key="value" argument pairs."""
    args = {}
    # Match key="value" or key='value'
    for match in re.finditer(r'(\w+)\s*=\s*["\']([^"\']*)["\']', args_str):
        args[match.group(1)] = match.group(2)
    return args


def _remove_tool_calls(text: str) -> str:
    """Remove TOOL_CALL lines from output."""
    lines = text.split("\n")
    cleaned = [l for l in lines if not l.strip().startswith("TOOL_CALL:")]
    return "\n".join(cleaned).strip()


def _execute_tool(tc: Dict, registry: ToolRegistry) -> str:
    """Execute a tool call and return result as string."""
    name = tc["name"]
    args = tc["args"]

    tool_fn = registry.get(name)
    if tool_fn is None:
        return f"Unknown tool: {name}"

    try:
        result = tool_fn(**args)
        if isinstance(result, str):
            return result[:2000]  # Truncate long results
        return str(result)[:2000]
    except TypeError as e:
        return f"Tool argument error: {e}"
