"""Deterministic guardrails for free-text questions and for model answers (no LLM involved)."""

from __future__ import annotations

import re
import unicodedata

MAX_QUESTION_CHARS = 300
MAX_ANSWER_CHARS = 1200

REFUSAL = (
    "I can only answer questions that explain this electricity bill (its charges, taxes, "
    "units, dates, payments or history). Please rephrase your question about the bill."
)
FALLBACK_ANSWER = "I could not produce a reliable answer to this question from the bill."

_CONTROL = re.compile(r"[\u0000-\u0008\u000b-\u001f\u007f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")

_INJECTION = re.compile(
    r"ignore (all |any |the )?(previous|above|prior|earlier)|disregard|forget (everything|your|the)"
    r"|system prompt|developer (mode|message)|jailbreak|you are now|act as|pretend|roleplay|role-play"
    r"|reveal|your (rules|instructions|prompt)|override|new instructions|bypass|\bDAN\b|prompt injection",
    re.I,
)
_PII = re.compile(
    r"\b(my|the|customer|owner'?s?)\s+(full\s+)?(name|address|cnic|phone|mobile|email|nic)\b"
    r"|\b(cnic|nic number|phone number|mobile number|e-?mail|home address|who (am i|owns|is the owner))\b"
    r"|\b(account|reference|consumer|contract|meter|invoice|customer)\s*(no\b|no\.|number|num\b|#|id\b)"
    r"|\b(name and address|address of)\b",
    re.I,
)
_TECH = re.compile(
    r"https?://|www\.|```|\bimport\s+\w+|\bdef\s+\w+\(|\bselect\s+.+\s+from\b|<script|\bos\.system|\beval\(|\bexec\("
    r"|\b(write|generate|create)\s+(me\s+)?(a\s+|some\s+)?(code|script|program|poem|story|essay|email|song|joke)\b"
    r"|\b(python|javascript|sql|bash|powershell|html)\b|\bcurl\b|\bapi key\b|\bpassword\b|\btranslate\b",
    re.I,
)
_DOMAIN = re.compile(
    r"\b(bill|billing|billed|unit|units|kwh|charge|charges|tax|taxes|gst|duty|fpa|fca|fuel|surcharge|late|"
    r"pay|paid|payment|payable|due|arrear|arrears|credit|month|months|year|last year|summer|winter|"
    r"tariff|load|sanctioned|meter reading|reading|consum\w*|electricity|solar|net[- ]?meter\w*|subsid\w*|"
    r"average|trend|expect|estimate|cost|set aside|compare|more|less|increase|decrease|total|amount|"
    r"history|rupees|pkr|rs|percent|share|issue|date|penalty|spread|budget|next|slab|energy|kw)\b",
    re.I,
)

_ANSWER_LEAKS = re.compile(
    r"system prompt|fact sheet|factsheet|raw extraction|my instructions|https?://|www\.|```|<script",
    re.I,
)
_URDU = re.compile(r"[\u0600-\u06ff]")


def normalize_question(text: str) -> str:
    """NFKC, strip control/zero-width characters, collapse whitespace, trim."""
    s = unicodedata.normalize("NFKC", text or "")
    s = _CONTROL.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def cache_key_text(text: str) -> str:
    """Normalised, case-insensitive form used for determinism keys (ignores trailing '?' / punctuation)."""
    return normalize_question(text).lower().rstrip(" ?.!")


def check_question(text: str) -> tuple[bool, str | None]:
    """Strict allowlist for free-text questions. Returns (allowed, reason_if_rejected)."""
    s = normalize_question(text)
    if not s:
        return False, "empty question"
    if len(s) > MAX_QUESTION_CHARS:
        return False, "question too long"
    if _URDU.search(s) and not re.search(r"[A-Za-z]", s):
        return False, "please ask in English"
    if _INJECTION.search(s):
        return False, "instruction override attempt"
    if _PII.search(s):
        return False, "personal identifier request"
    if _TECH.search(s):
        return False, "code, link or unrelated task request"
    if not _DOMAIN.search(s):
        return False, "not a question about this bill"
    return True, None


def check_answer(text: str) -> str | None:
    """Return a problem description if an answer must be rejected (hard check), else None."""
    if not text or not text.strip():
        return "empty answer"
    if len(text) >= MAX_ANSWER_CHARS:
        return f"answer is {len(text)} characters (limit {MAX_ANSWER_CHARS})"
    if _ANSWER_LEAKS.search(text):
        return "answer contains prompt/link/code content that must not be shown"
    return None


def soft_answer_flags(text: str) -> list[str]:
    flags = []
    if re.search(r"\d{8,}", text.replace(",", "")):
        flags.append("run of 8+ digits (possible identifier)")
    if _URDU.search(text):
        flags.append("contains Urdu characters")
    return flags
