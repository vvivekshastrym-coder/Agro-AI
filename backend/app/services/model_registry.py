"""Server-side model registry and deterministic task router for AgroGPT.

Config only; no keys here. Entries can be overridden by env vars
(AGROGPT_MODEL_<TASK>=provider:model). `eval_scores` stays empty until the G1/G7
evaluation fills it: no model is promoted on general benchmarks alone.
"""
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ModelSpec:
    provider: str            # gemini | openai | anthropic
    model: str
    capabilities: List[str]  # text, vision, tools, streaming, multilingual
    context_window: int
    cost_tier: str           # low | medium | high (relative; real prices tracked in usage logs)
    fallbacks: List[str] = field(default_factory=list)  # registry keys
    eval_scores: Dict[str, float] = field(default_factory=dict)  # filled by G7, never invented


REGISTRY: Dict[str, ModelSpec] = {
    "gemini_flash": ModelSpec("gemini", "gemini-2.5-flash", ["text", "vision", "streaming", "multilingual"],
                              1_000_000, "low", ["openai_mini", "claude_haiku"]),
    "openai_mini": ModelSpec("openai", "gpt-4o-mini", ["text", "vision", "tools", "streaming"],
                             128_000, "low", ["claude_haiku"]),
    "claude_haiku": ModelSpec("anthropic", "claude-3-5-haiku-20241022", ["text", "tools"],
                              200_000, "low", []),
}

# Task -> registry key. Today every text task maps to the existing primary model; reasoning/vision
# upgrades are config changes AFTER the evaluation shows a benefit.
TASK_DEFAULTS = {
    "simple": "gemini_flash",
    "complex": "gemini_flash",
    "image": "gemini_flash",
    "current_data": "gemini_flash",
    "safety": "gemini_flash",
}

_CHEM = re.compile(r"pesticid|insecticid|fungicid|herbicid|spray|dose|dosage|fertili[sz]er|urea|dap|mop|"
                   r"chemical|ಕೀಟನಾಶಕ|ಶಿಲೀಂಧ್ರನಾಶಕ|ಗೊಬ್ಬರ|ಯೂರಿಯಾ|ಪ್ರಮಾಣ|ಸಿಂಪಡ", re.I)
_LIVE = re.compile(r"today|tomorrow|now|current|price|rate|weather|rain|forecast|scheme|subsid|mandi|apmc|"
                   r"ಇಂದು|ನಾಳೆ|ಬೆಲೆ|ಮಳೆ|ಹವಾಮಾನ|ಯೋಜನೆ|ಮಾರುಕಟ್ಟೆ", re.I)
_COMPLEX = re.compile(r"why|compare|plan|schedule|strategy|yield|decline|declin|ಯೋಜನೆ ರೂಪಿಸಿ|ಏಕೆ|ಹೋಲಿಸಿ", re.I)


def classify_question(text: str, has_image: bool = False) -> str:
    """Deterministic router. Safety wins over everything, then image, live data, complexity."""
    t = text or ""
    if _CHEM.search(t):
        return "safety"
    if has_image:
        return "image"
    if _LIVE.search(t):
        return "current_data"
    if _COMPLEX.search(t) or len(t) > 280:
        return "complex"
    return "simple"


def model_for(task: str) -> ModelSpec:
    override = os.getenv(f"AGROGPT_MODEL_{task.upper()}")
    if override and override in REGISTRY:
        return REGISTRY[override]
    return REGISTRY[TASK_DEFAULTS.get(task, "gemini_flash")]
