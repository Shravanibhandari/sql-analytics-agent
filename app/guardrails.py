"""Input guardrails.

Layer 1: regex checks (always on, fast, no LLM needed).
Layer 2: NeMo Guardrails input rail (uses a custom Python action, no LLM call).
If NeMo cannot start (missing package / config problem) we silently rely on layer 1.
"""
import re
from pathlib import Path

BAD_PATTERNS = [
    r"<\s*script",                          # script tags
    r"--",                                  # SQL comment
    r"/\*",                                 # comment expansion
    r"\bdrop\s+(table|database)\b",
    r"\btruncate\s+table\b",
    r"\b(or|and)\s+['\"]?(\d+)['\"]?\s*=\s*['\"]?\2['\"]?",  # tautology: OR 1=1
    r"\bor\s+['\"]\w*['\"]\s*=\s*['\"]\w*['\"]",             # OR 'a'='a'
    r";\s*(delete|drop|update|insert|alter|create)\b",
    r"\bunion\s+select\b",
]

CONFIG_DIR = Path(__file__).resolve().parent.parent / "guardrails_config"
_rails = None
_rails_failed = False
REFUSAL = "I can't process that request because it looks unsafe."


def regex_check(text: str) -> bool:
    """True = input is safe."""
    return not any(re.search(p, text, re.I) for p in BAD_PATTERNS)


def _get_rails():
    global _rails, _rails_failed
    if _rails is not None or _rails_failed:
        return _rails
    try:
        from nemoguardrails import LLMRails, RailsConfig

        from langchain_core.language_models.fake import FakeListLLM

        # NeMo wants an LLM object even though our input rail never needs one,
        # so we give it a tiny dummy one (no API calls, no cost).
        dummy = FakeListLLM(responses=["OK"] * 100)
        config = RailsConfig.from_path(str(CONFIG_DIR))
        rails = LLMRails(config, llm=dummy)
        rails.register_action(lambda text="": regex_check(text), name="check_input_action")
        _rails = rails
    except Exception:
        _rails_failed = True
    return _rails


def nemo_check(text: str):
    """True/False from NeMo, or None if NeMo is unavailable."""
    rails = _get_rails()
    if rails is None:
        return None
    try:
        reply = rails.generate(messages=[{"role": "user", "content": text}])
        content = reply["content"] if isinstance(reply, dict) else str(reply)
        return REFUSAL not in content
    except Exception:
        return None


def check_input(text: str) -> bool:
    """True = safe to send to the LLM."""
    if not regex_check(text):
        return False
    result = nemo_check(text)
    return True if result is None else result
