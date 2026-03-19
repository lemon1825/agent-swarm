"""One-line LLM connectors.

Usage:
    from agent_swarm import Swarm, openai, claude, ollama

    swarm = Swarm(llm=openai())                      # gpt-4o-mini default
    swarm = Swarm(llm=openai("gpt-4o"))              # specific model
    swarm = Swarm(llm=claude())                       # claude-sonnet default
    swarm = Swarm(llm=claude("claude-opus-4-6"))      # specific model
    swarm = Swarm(llm=ollama("llama3"))               # local model

All connectors return (output, usage_dict) for token tracking.
Falls back to string-only return if the LLM library is not installed.
"""

__all__ = ['openai', 'claude', 'ollama', 'litellm', 'vllm']


def openai(model: str = "gpt-4o-mini", temperature: float = 0.3,
           max_tokens: int = 2000, api_key: str = None,
           base_url: str = None):
    """Create an OpenAI LLM function.

    Requires: pip install openai
    Auth: OPENAI_API_KEY env var or api_key parameter.

    Also works with any OpenAI-compatible server (vLLM, LM Studio, etc.)
    by setting base_url.
    """
    _client = None

    async def llm(prompt, tools=None):
        nonlocal _client
        if _client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("OpenAI connector requires: pip install openai")
            kwargs = {}
            if api_key:
                kwargs["api_key"] = api_key
            if base_url:
                kwargs["base_url"] = base_url
            _client = AsyncOpenAI(**kwargs)

        r = await _client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        usage = {
            "prompt_tokens": r.usage.prompt_tokens,
            "completion_tokens": r.usage.completion_tokens,
            "total_tokens": r.usage.total_tokens,
        }
        return (r.choices[0].message.content, usage)

    return llm


def vllm(model: str, base_url: str = "http://localhost:8000/v1",
         temperature: float = 0.3, max_tokens: int = 2000):
    """Create a vLLM LLM function.

    vLLM provides an OpenAI-compatible API, so this is a convenience
    wrapper around openai() with the right defaults.

    Requires:
        - vLLM server running: vllm serve <model> --port 8000
        - pip install openai (client library)

    No API key needed (vLLM is self-hosted).

    Args:
        model: HuggingFace model name (must match vLLM server)
        base_url: vLLM server URL (default: http://localhost:8000/v1)
        temperature: Sampling temperature
        max_tokens: Max output tokens

    Examples:
        # Local vLLM server
        Swarm(llm=vllm("meta-llama/Llama-3.1-8B-Instruct"))

        # Remote vLLM server
        Swarm(llm=vllm("mistralai/Mistral-7B-Instruct-v0.3",
                        base_url="http://gpu-server:8000/v1"))

        # Multiple GPUs with different models
        researcher = vllm("meta-llama/Llama-3.1-70B-Instruct",
                          base_url="http://gpu1:8000/v1")
        writer = vllm("mistralai/Mixtral-8x7B-Instruct-v0.1",
                      base_url="http://gpu2:8000/v1")
    """
    return openai(
        model=model,
        base_url=base_url,
        api_key="EMPTY",  # vLLM doesn't need API key
        temperature=temperature,
        max_tokens=max_tokens,
    )


def claude(model: str = "claude-sonnet-4-20250514", temperature: float = 0.3,
           max_tokens: int = 2000, api_key: str = None):
    """Create a Claude LLM function.

    Requires: pip install anthropic
    Auth: ANTHROPIC_API_KEY env var or api_key parameter.
    """
    _client = None

    async def llm(prompt, tools=None):
        nonlocal _client
        if _client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError("Claude connector requires: pip install anthropic")
            kwargs = {}
            if api_key:
                kwargs["api_key"] = api_key
            _client = AsyncAnthropic(**kwargs)

        r = await _client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        usage = {
            "prompt_tokens": r.usage.input_tokens,
            "completion_tokens": r.usage.output_tokens,
            "total_tokens": r.usage.input_tokens + r.usage.output_tokens,
        }
        return (r.content[0].text, usage)

    return llm


def ollama(model: str = "llama3", base_url: str = "http://localhost:11434",
           temperature: float = 0.3):
    """Create an Ollama (local model) LLM function.

    Requires: Ollama running locally (ollama serve).
    No API key needed.
    """
    import urllib.request
    import json

    async def llm(prompt, tools=None):
        data = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }).encode()

        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        resp = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=120))
        body = json.loads(resp.read().decode())

        usage = {
            "prompt_tokens": body.get("prompt_eval_count", 0),
            "completion_tokens": body.get("eval_count", 0),
            "total_tokens": body.get("prompt_eval_count", 0) + body.get("eval_count", 0),
        }
        return (body.get("response", ""), usage)

    return llm


def litellm(model: str = "gpt-4o-mini", temperature: float = 0.3,
            max_tokens: int = 2000):
    """Create a LiteLLM function (supports 100+ providers).

    Requires: pip install litellm
    Auth: Provider-specific env vars (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
    """
    _module = None

    async def llm(prompt, tools=None):
        nonlocal _module
        if _module is None:
            try:
                import litellm as _litellm
                _module = _litellm
            except ImportError:
                raise ImportError("LiteLLM connector requires: pip install litellm")

        r = await _module.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        usage = {
            "prompt_tokens": r.usage.prompt_tokens,
            "completion_tokens": r.usage.completion_tokens,
            "total_tokens": r.usage.total_tokens,
        }
        return (r.choices[0].message.content, usage)

    return llm
