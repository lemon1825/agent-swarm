"""vLLM Optimizer Presets — model-specific optimal settings.

Based on FlashAttention-4 (Zadouri et al., 2026) and Megatron Core (NVIDIA, 2026):
- Different models have different optimal batch sizes, quantization, and context lengths
- MoE models need specific expert parallelism settings
- FlashAttention version affects throughput significantly

Usage:
    from agent_swarm.vllm_presets import get_preset, list_presets, vllm_optimized

    # Get optimal settings for a model
    preset = get_preset("meta-llama/Llama-3.1-8B-Instruct")
    print(preset)

    # Create optimized vLLM connector
    from agent_swarm import Swarm
    swarm = Swarm(llm=vllm_optimized("meta-llama/Llama-3.1-8B-Instruct"))
"""

__all__ = ['get_preset', 'list_presets', 'vllm_optimized', 'VLLMPreset', 'PRESETS']

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class VLLMPreset:
    """Optimal vLLM serving configuration for a model."""
    model: str
    display_name: str
    family: str                          # llama, mistral, qwen, deepseek, phi, gemma
    parameters: str                      # "8B", "70B", "685B"
    architecture: str                    # dense, moe

    # Serving settings
    recommended_gpu_memory_gb: int = 24  # minimum VRAM
    recommended_tensor_parallel: int = 1 # TP for multi-GPU
    recommended_max_model_len: int = 4096
    recommended_gpu_memory_utilization: float = 0.9
    recommended_dtype: str = "auto"      # auto, float16, bfloat16
    recommended_quantization: str = ""   # awq, gptq, fp8, ""

    # Generation defaults
    default_temperature: float = 0.3
    default_max_tokens: int = 2000

    # MoE specific
    moe_num_experts: int = 0
    moe_top_k: int = 0

    # Performance notes
    notes: str = ""

    # vllm serve command
    def serve_command(self, port: int = 8000) -> str:
        cmd = f"vllm serve {self.model} --port {port}"
        if self.recommended_tensor_parallel > 1:
            cmd += f" --tensor-parallel-size {self.recommended_tensor_parallel}"
        if self.recommended_max_model_len != 4096:
            cmd += f" --max-model-len {self.recommended_max_model_len}"
        if self.recommended_gpu_memory_utilization != 0.9:
            cmd += f" --gpu-memory-utilization {self.recommended_gpu_memory_utilization}"
        if self.recommended_quantization:
            cmd += f" --quantization {self.recommended_quantization}"
        if self.recommended_dtype != "auto":
            cmd += f" --dtype {self.recommended_dtype}"
        return cmd

    def summary(self) -> str:
        lines = [
            f"{self.display_name} ({self.parameters}, {self.architecture})",
            f"  GPU: {self.recommended_gpu_memory_gb}GB+ VRAM, TP={self.recommended_tensor_parallel}",
            f"  Context: {self.recommended_max_model_len} tokens",
            f"  Quantization: {self.recommended_quantization or 'none (full precision)'}",
            f"  Command: {self.serve_command()}",
        ]
        if self.notes:
            lines.append(f"  Notes: {self.notes}")
        return "\n".join(lines)


# ── Model Presets ────────────────────────────────────

PRESETS: Dict[str, VLLMPreset] = {
    # Llama 3.1 family
    "meta-llama/Llama-3.1-8B-Instruct": VLLMPreset(
        model="meta-llama/Llama-3.1-8B-Instruct",
        display_name="Llama 3.1 8B",
        family="llama", parameters="8B", architecture="dense",
        recommended_gpu_memory_gb=24,
        recommended_tensor_parallel=1,
        recommended_max_model_len=8192,
        default_temperature=0.3, default_max_tokens=2000,
        notes="Best cost/performance for most Agent Swarm tasks. Single GPU sufficient.",
    ),
    "meta-llama/Llama-3.1-70B-Instruct": VLLMPreset(
        model="meta-llama/Llama-3.1-70B-Instruct",
        display_name="Llama 3.1 70B",
        family="llama", parameters="70B", architecture="dense",
        recommended_gpu_memory_gb=80,
        recommended_tensor_parallel=2,
        recommended_max_model_len=8192,
        default_temperature=0.3, default_max_tokens=2000,
        notes="High quality for complex analysis. Needs 2x A100/H100.",
    ),
    "meta-llama/Llama-3.1-70B-Instruct-AWQ": VLLMPreset(
        model="meta-llama/Llama-3.1-70B-Instruct-AWQ",
        display_name="Llama 3.1 70B (AWQ)",
        family="llama", parameters="70B", architecture="dense",
        recommended_gpu_memory_gb=48,
        recommended_tensor_parallel=1,
        recommended_max_model_len=8192,
        recommended_quantization="awq",
        notes="70B quality on single 48GB GPU via AWQ quantization.",
    ),

    # Mistral family
    "mistralai/Mistral-7B-Instruct-v0.3": VLLMPreset(
        model="mistralai/Mistral-7B-Instruct-v0.3",
        display_name="Mistral 7B",
        family="mistral", parameters="7B", architecture="dense",
        recommended_gpu_memory_gb=16,
        recommended_tensor_parallel=1,
        recommended_max_model_len=8192,
        notes="Fast and efficient. Good for writer/editor agents.",
    ),
    "mistralai/Mixtral-8x7B-Instruct-v0.1": VLLMPreset(
        model="mistralai/Mixtral-8x7B-Instruct-v0.1",
        display_name="Mixtral 8x7B (MoE)",
        family="mistral", parameters="46.7B", architecture="moe",
        recommended_gpu_memory_gb=80,
        recommended_tensor_parallel=2,
        recommended_max_model_len=8192,
        moe_num_experts=8, moe_top_k=2,
        notes="MoE: 46.7B params but only 12.9B active per token. Fast for its quality.",
    ),

    # Qwen family
    "Qwen/Qwen2.5-7B-Instruct": VLLMPreset(
        model="Qwen/Qwen2.5-7B-Instruct",
        display_name="Qwen 2.5 7B",
        family="qwen", parameters="7B", architecture="dense",
        recommended_gpu_memory_gb=16,
        recommended_tensor_parallel=1,
        recommended_max_model_len=8192,
        notes="Strong multilingual support. Good for Korean/Chinese tasks.",
    ),
    "Qwen/Qwen2.5-72B-Instruct": VLLMPreset(
        model="Qwen/Qwen2.5-72B-Instruct",
        display_name="Qwen 2.5 72B",
        family="qwen", parameters="72B", architecture="dense",
        recommended_gpu_memory_gb=80,
        recommended_tensor_parallel=2,
        recommended_max_model_len=8192,
        notes="Top-tier quality. Excellent for research and analysis agents.",
    ),

    # DeepSeek family
    "deepseek-ai/DeepSeek-V3": VLLMPreset(
        model="deepseek-ai/DeepSeek-V3",
        display_name="DeepSeek V3 (MoE)",
        family="deepseek", parameters="685B", architecture="moe",
        recommended_gpu_memory_gb=80,
        recommended_tensor_parallel=8,
        recommended_max_model_len=4096,
        moe_num_experts=256, moe_top_k=8,
        notes="685B total, 37B active. Needs 8x H100. State-of-the-art quality.",
    ),

    # Phi family (small/edge)
    "microsoft/Phi-3-mini-4k-instruct": VLLMPreset(
        model="microsoft/Phi-3-mini-4k-instruct",
        display_name="Phi-3 Mini",
        family="phi", parameters="3.8B", architecture="dense",
        recommended_gpu_memory_gb=8,
        recommended_tensor_parallel=1,
        recommended_max_model_len=4096,
        notes="Smallest viable model. Good for simple tasks or edge deployment.",
    ),

    # Gemma family
    "google/gemma-2-9b-it": VLLMPreset(
        model="google/gemma-2-9b-it",
        display_name="Gemma 2 9B",
        family="gemma", parameters="9B", architecture="dense",
        recommended_gpu_memory_gb=24,
        recommended_tensor_parallel=1,
        recommended_max_model_len=8192,
        notes="Google's open model. Strong reasoning for its size.",
    ),
}


def get_preset(model: str) -> Optional[VLLMPreset]:
    """Get optimal preset for a model.

    Args:
        model: HuggingFace model name (exact or partial match)

    Returns:
        VLLMPreset or None
    """
    # Exact match
    if model in PRESETS:
        return PRESETS[model]

    # Partial match
    model_lower = model.lower()
    for key, preset in PRESETS.items():
        if model_lower in key.lower() or key.lower() in model_lower:
            return preset

    return None


def list_presets(family: str = None, max_gpu_gb: int = None) -> List[VLLMPreset]:
    """List available presets with optional filters.

    Args:
        family: Filter by model family (llama, mistral, qwen, etc.)
        max_gpu_gb: Only show models that fit in this VRAM

    Returns:
        List of matching presets
    """
    presets = list(PRESETS.values())

    if family:
        presets = [p for p in presets if p.family == family.lower()]

    if max_gpu_gb:
        presets = [p for p in presets if p.recommended_gpu_memory_gb <= max_gpu_gb]

    return sorted(presets, key=lambda p: p.recommended_gpu_memory_gb)


def vllm_optimized(model: str, base_url: str = None, **overrides):
    """Create a vLLM connector with optimal preset settings.

    Args:
        model: HuggingFace model name
        base_url: vLLM server URL (default: http://localhost:8000/v1)
        **overrides: Override any preset default (temperature, max_tokens, etc.)

    Returns:
        LLM function ready for Swarm(llm=...)

    Example:
        from agent_swarm import Swarm
        from agent_swarm.vllm_presets import vllm_optimized

        swarm = Swarm(llm=vllm_optimized("meta-llama/Llama-3.1-8B-Instruct"))
    """
    from .llm_connectors import vllm

    preset = get_preset(model)

    if preset:
        temperature = overrides.get("temperature", preset.default_temperature)
        max_tokens = overrides.get("max_tokens", preset.default_max_tokens)
    else:
        temperature = overrides.get("temperature", 0.3)
        max_tokens = overrides.get("max_tokens", 2000)

    url = base_url or "http://localhost:8000/v1"

    return vllm(model=model, base_url=url,
                temperature=temperature, max_tokens=max_tokens)
