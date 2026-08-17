"""
guardrails.py — v3.0
--------------------
Code-level safety enforcement. No LLM involvement.

All checks are deterministic, regex/rule-based, and run independently of
whatever the LLM decides to output. Cannot be bypassed by prompt engineering.

USAGE:
    from agents.guardrails import check_input, check_output

    # INPUT — call before routing or LLM
    result = check_input(user_text)
    if not result.safe:
        return result.user_message, []   # do not proceed to LLM

    # OUTPUT — call before returning answer to UI
    result = check_output(llm_answer, retrieval_confidence=0.87)
    final_answer = result.text           # use this, not the raw LLM output
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Limits ────────────────────────────────────────────────────────────────────

MAX_INPUT_CHARS  = 2000   # questions longer than this are rejected
MAX_OUTPUT_CHARS = 4000   # answers longer than this are truncated before display

# ── Prompt injection patterns ─────────────────────────────────────────────────
#
# Compiled once at import time. Pattern match on the raw user message text
# (case-insensitive). Any match → reject without calling the LLM.

_INJECTION_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [

    # Instruction override / reset
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?(previous|your)\s+(instructions?|rules?|prompt)",
    r"forget\s+(all\s+)?(previous|your)\s+(instructions?|rules?|prompt)",
    r"override\s+(all\s+)?(previous\s+)?instructions",
    r"new\s+instructions?\s*:",
    r"updated?\s+instructions?\s*:",
    r"stop\s+following\s+(your\s+)?instructions",

    # Persona / role injection
    r"you\s+are\s+now\s+(a|an)\s+",
    r"act\s+as\s+(a|an|if)\s+",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"roleplay\s+as\s+",
    r"from\s+now\s+on\s+(you\s+)?(are|will|should)\s+",
    r"switch\s+(to\s+)?mode",
    r"enter\s+(developer|admin|god|sudo|unrestricted)\s+mode",

    # System prompt extraction
    r"(reveal|show|print|display|repeat|output|tell\s+me)\s+(your|the)\s+(system\s+)?prompt",
    r"what\s+(are|is)\s+your\s+(instructions?|rules?|system\s+prompt|training|guidelines)",
    r"(dump|leak|expose)\s+(your\s+)?(prompt|instructions?|context|system)",
    r"repeat\s+(everything|all)\s+(above|before|prior)",

    # Jailbreak keywords / common exploit strings
    r"\bDAN\b",
    r"developer\s+mode",
    r"\bjailbreak\b",
    r"do\s+anything\s+now",
    r"no\s+(ethical\s+)?restrictions",
    r"without\s+(any\s+)?restrictions",
    r"bypass\s+(your\s+)?(restrictions?|filters?|safety|guidelines)",
    r"disable\s+(your\s+)?(safety|filter|guardrail)",

    # Prompt delimiter injection (technique to confuse tokenizer context)
    r"###\s*(instructions?|system|human|assistant|end)",
    r"<\s*/?system\s*>",
    r"\[INST\]",
    r"<<\s*SYS\s*>>",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[/INST\]",
    r"<\|endoftext\|>",
]]

# ── PII patterns ──────────────────────────────────────────────────────────────
#
# Two lists:
#  _INPUT_PII_PATTERNS  — things that should NOT be in a user question;
#                          we warn the user and refuse to process.
#  _OUTPUT_PII_PATTERNS — scrubbed from ALL LLM-generated responses before display.

# Patterns that flag real customer data in input
_INPUT_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    # SSN: 123-45-6789 or 123 45 6789
    (re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b"), "Social Security Number"),
    # 16-digit card number (groups of 4)
    (re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"), "card number"),
    # Bank account / large numeric string (10–17 digits standalone)
    (re.compile(r"(?<!\d)\d{10,17}(?!\d)"), "account number"),
]

# Patterns scrubbed from output (superset of input patterns)
_OUTPUT_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    # SSN with dashes/spaces
    (re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b"), "[SSN REDACTED]"),
    # 16-digit card
    (re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"), "[CARD# REDACTED]"),
    # 9-digit routing number (standalone)
    (re.compile(r"(?<!\d)\d{9}(?!\d)"), "[ROUTING# REDACTED]"),
    # Bank account 10–17 digits
    (re.compile(r"(?<!\d)\d{10,17}(?!\d)"), "[ACCT# REDACTED]"),
    # US phone numbers
    (re.compile(r"\b(?:\+1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b"), "[PHONE REDACTED]"),
    # Email addresses in generated text
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[EMAIL REDACTED]"),
]

# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class InputCheckResult:
    safe: bool
    reason: str          # internal — do NOT surface to user
    user_message: str    # shown to user if not safe; empty string if safe


@dataclass
class OutputCheckResult:
    safe: bool           # False = hard-blocked; caller must use .text regardless
    text: str            # final text to show user (redacted / truncated / blocked)
    blocked: bool        # True = retrieval guardrail fired, LLM answer suppressed
    was_modified: bool   # True = PII redacted or text truncated
    reason: str          # internal reason


# ── Canned messages ───────────────────────────────────────────────────────────

_INJECTION_USER_MSG = (
    "⚠️ Your message was flagged as potentially unsafe and could not be processed. "
    "Please ask a straightforward question about bank SOPs and procedures."
)

_PII_INPUT_USER_MSG = (
    "⚠️ Your message appears to contain sensitive personal information ({pii_type}). "
    "This assistant answers questions about bank policies — "
    "please do not include personal financial details in your question."
)

_LENGTH_USER_MSG = (
    "⚠️ Your message is too long ({length:,} characters). "
    "Please keep questions under {max_len:,} characters."
)

_RETRIEVAL_BLOCK_MSG = (
    "⚠️ **Not covered in SOP documents.**\n\n"
    "This answer could not be grounded in the available policy content. "
    "Please consult your supervisor or the relevant policy owner directly."
)

_TRUNCATION_SUFFIX = (
    "\n\n_[Response truncated. Ask a more specific question for a shorter answer.]_"
)


# ══════════════════════════════════════════════════════════════════════════════
# INPUT-SIDE CHECKS
# ══════════════════════════════════════════════════════════════════════════════

def check_input(text: str) -> InputCheckResult:
    """
    Run all input-side guardrail checks.

    Returns InputCheckResult. If result.safe is False, the caller MUST NOT
    proceed to retrieval or the LLM — return result.user_message to the UI.
    """
    # 1. Length gate
    if len(text) > MAX_INPUT_CHARS:
        return InputCheckResult(
            safe=False,
            reason=f"Input too long: {len(text)} chars (max {MAX_INPUT_CHARS})",
            user_message=_LENGTH_USER_MSG.format(
                length=len(text), max_len=MAX_INPUT_CHARS
            ),
        )

    # 2. Prompt injection detection
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return InputCheckResult(
                safe=False,
                reason=f"Injection pattern matched: {pattern.pattern!r}",
                user_message=_INJECTION_USER_MSG,
            )

    # 3. PII in user question — protect users from inadvertently sending PII to the LLM
    for pattern, pii_type in _INPUT_PII_PATTERNS:
        if pattern.search(text):
            return InputCheckResult(
                safe=False,
                reason=f"PII detected in input: {pii_type}",
                user_message=_PII_INPUT_USER_MSG.format(pii_type=pii_type),
            )

    return InputCheckResult(safe=True, reason="", user_message="")


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT-SIDE CHECKS
# ══════════════════════════════════════════════════════════════════════════════

def check_output(
    text: str,
    retrieval_confidence: float = 1.0,
    confidence_threshold: float = 0.25,
) -> OutputCheckResult:
    """
    Run all output-side guardrail checks.

    retrieval_confidence: cosine similarity of the top retrieved chunk (0–1).
    confidence_threshold: if retrieval_confidence falls below this, the LLM's
                          answer is hard-blocked regardless of its content.

    Returns OutputCheckResult. The caller MUST use result.text — never the
    original LLM response — to render in the UI.
    """
    # 1. Hard-block: retrieval below threshold — override whatever the LLM said
    if retrieval_confidence < confidence_threshold:
        return OutputCheckResult(
            safe=False,
            text=_RETRIEVAL_BLOCK_MSG,
            blocked=True,
            was_modified=True,
            reason=(
                f"Retrieval confidence {retrieval_confidence:.3f} "
                f"< threshold {confidence_threshold}"
            ),
        )

    was_modified = False
    processed = text

    # 2. PII redaction — scrub any PII patterns from LLM-generated text
    for pattern, replacement in _OUTPUT_PII_PATTERNS:
        cleaned = pattern.sub(replacement, processed)
        if cleaned != processed:
            was_modified = True
            processed = cleaned

    # 3. Script/HTML injection prevention
    #    (Streamlit renders markdown — strip any <script> or javascript: URLs)
    cleaned = re.sub(
        r"<script[^>]*>.*?</script>", "", processed,
        flags=re.IGNORECASE | re.DOTALL
    )
    cleaned = re.sub(r"javascript\s*:", "[blocked]", cleaned, flags=re.IGNORECASE)
    if cleaned != processed:
        was_modified = True
        processed = cleaned

    # 4. Control-character sanitization (null bytes, escape sequences, etc.)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", processed)
    if cleaned != processed:
        was_modified = True
        processed = cleaned

    # 5. Response length cap
    if len(processed) > MAX_OUTPUT_CHARS:
        processed = processed[:MAX_OUTPUT_CHARS] + _TRUNCATION_SUFFIX
        was_modified = True

    return OutputCheckResult(
        safe=True,
        text=processed,
        blocked=False,
        was_modified=was_modified,
        reason="",
    )
