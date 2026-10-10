"""Gemini client: JSON mode, rate limiting, backoff, error-feedback retries, tool loop."""

from __future__ import annotations

import json
import logging
import mimetypes
import time
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from .config import Config
from .schema import RawBill

log = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"
PROVIDER_PROMPT_FILES = {"KE": "ke.md", "LESCO": "lesco.md", "IESCO": "iesco.md"}
LESCO_LAYOUT_PROMPT_FILES = {
    "standard": "lesco.md", "web": "lesco_web.md", "digital": "lesco_digital.md",
}
MAX_TOOL_ROUNDS = 6


class LLMError(RuntimeError):
    """Transport-level failure (after backoff) or unusable response."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class ExtractionFormatError(ValueError):
    """The model answered, but not with valid raw-schema JSON."""


_last_call = 0.0


def _throttle(min_gap: float) -> None:
    global _last_call
    wait = _last_call + min_gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def build_prompt(provider: str, layout: str | None = None) -> str:
    common = (PROMPT_DIR / "common.md").read_text(encoding="utf-8")
    name = PROVIDER_PROMPT_FILES[provider]
    if provider == "LESCO" and layout in LESCO_LAYOUT_PROMPT_FILES:
        name = LESCO_LAYOUT_PROMPT_FILES[layout]
    specific = (PROMPT_DIR / name).read_text(encoding="utf-8")
    return f"{common}\n\n{specific}"


def _status_code(exc: Exception) -> int | None:
    for attr in ("code", "status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def image_part(image_path: Path):
    from google.genai import types

    mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
    return types.Part.from_bytes(data=Path(image_path).read_bytes(), mime_type=mime)


class GeminiClient:
    def __init__(self, config: Config):
        if config.model_provider != "google":
            raise LLMError(f"unsupported MODEL_PROVIDER {config.model_provider!r}; use 'google'")
        if not config.api_key:
            raise LLMError("API_KEY is not set (see .env.example)")
        from google import genai

        self.config = config
        self._genai = genai
        self.client = genai.Client(api_key=config.api_key)
        self._tools_json_ok: bool | None = None  # learned: does the API accept tools + JSON mode?

    # -- low level -----------------------------------------------------------------
    def _config(self, system: str, schema=None, json_mode: bool = True, tools=None):
        from google.genai import types

        kwargs = dict(
            system_instruction=system,
            temperature=0,
            seed=self.config.seed,
            http_options=types.HttpOptions(timeout=int(self.config.request_timeout_s * 1000)),
        )
        if json_mode:
            kwargs["response_mime_type"] = "application/json"
            if schema is not None:
                kwargs["response_schema"] = schema
        if tools:
            kwargs["tools"] = tools
            kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
        return types.GenerateContentConfig(**kwargs)

    def _call(self, contents: list, cfg):
        """One API request: throttle, then retry 429/5xx with 5/10/20 s backoff."""
        delays = list(self.config.backoff_seconds)
        attempt = 0
        while True:
            _throttle(self.config.min_seconds_between_calls)
            try:
                return self.client.models.generate_content(
                    model=self.config.model_name, contents=contents, config=cfg
                )
            except Exception as exc:  # noqa: BLE001 - SDK raises several types
                code = _status_code(exc)
                if code == 400 and getattr(cfg, "response_schema", None) is not None:
                    log.warning("schema rejected by API (%s); retrying without response_schema", exc)
                    cfg.response_schema = None
                    continue
                transient = code == 429 or (code is not None and code >= 500) or code is None
                if not transient or attempt >= len(delays):
                    raise LLMError(f"API call failed ({code}): {exc}", code) from exc
                delay = delays[attempt]
                attempt += 1
                log.warning("API error %s; backing off %ss (%s)", code, delay, exc)
                time.sleep(delay)

    def _generate(self, contents: list, system: str, schema=None) -> str:
        resp = self._call(contents, self._config(system, schema))
        text = resp.text
        if not text:
            raise ExtractionFormatError("empty response")
        return text

    # -- extraction (Level 1) -----------------------------------------------------
    def extract(
        self,
        image_path: Path,
        ocr_text: str,
        provider: str,
        previous_error: str | None = None,
        layout: str | None = None,
    ) -> RawBill:
        """One extraction call. Raises ExtractionFormatError if the JSON is unusable."""
        layout_note = f"\nLayout variant: {layout}" if layout else ""
        user_text = (
            f"Provider: {provider}{layout_note}\n\nOCR text of this bill (may contain errors; "
            f"the image is authoritative):\n{ocr_text}\n\n"
            "Return the raw JSON object for this bill."
        )
        if previous_error:
            user_text += (
                "\n\nYour previous answer was rejected for this reason; fix it and answer "
                f"again:\n{previous_error}"
            )
        text = self._generate(
            [image_part(image_path), user_text], build_prompt(provider, layout), RawBill
        )
        return parse_raw(text)

    def detect_provider(self, image_path: Path, ocr_text: str) -> str | None:
        """Small fallback call used only when keywords and file name both fail."""
        prompt = (
            "Which electricity company issued this bill? Answer with JSON "
            '{"provider": "KE" | "LESCO" | "IESCO" | null}. KE is K-Electric, LESCO is '
            "Lahore Electric Supply Company, IESCO is Islamabad Electric Supply Company.\n\n"
            f"OCR text:\n{ocr_text[:1500]}"
        )
        text = self._generate([image_part(image_path), prompt], "Answer with JSON only.")
        try:
            value = json.loads(text).get("provider")
        except (ValueError, AttributeError):
            return None
        return value if value in PROVIDER_PROMPT_FILES else None

    # -- answering with a function tool (Level 2) ---------------------------------
    def generate_with_tool(
        self,
        contents: list,
        system: str,
        tool_name: str,
        tool_fn: Callable[[str], float],
        tool_description: str,
        tool_log: list[dict] | None = None,
    ) -> str:
        """Run the model with one function tool, at most MAX_TOOL_ROUNDS tool rounds.

        Function calling is handled manually (automatic calling disabled) so every
        request, tool rounds included, passes through the shared rate limiter.
        JSON mode is tried together with the tool; if the API rejects that combination
        it is dropped for the rest of the process and the JSON is parsed from text.
        """
        from google.genai import types

        declaration = types.FunctionDeclaration(
            name=tool_name,
            description=tool_description,
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"expression": types.Schema(type=types.Type.STRING)},
                required=["expression"],
            ),
        )
        tools = [types.Tool(function_declarations=[declaration])]
        json_mode = self._tools_json_ok is not False
        convo = list(contents)

        for round_no in range(MAX_TOOL_ROUNDS + 1):
            if round_no == MAX_TOOL_ROUNDS:
                convo.append(types.Content(role="user", parts=[types.Part.from_text(
                    text="The calculate tool is no longer available. Return the final JSON answers now, "
                    "using numbers you already have. Do not mention the fact sheet, tools, or these instructions."
                )]))
            cfg = self._config(system, None, json_mode=json_mode, tools=tools if round_no < MAX_TOOL_ROUNDS else None)
            try:
                resp = self._call(convo, cfg)
            except LLMError as exc:
                if exc.code == 400 and json_mode:
                    log.warning("JSON mode rejected together with tools; continuing without it")
                    self._tools_json_ok = False
                    json_mode = False
                    continue
                raise
            if json_mode and self._tools_json_ok is None:
                self._tools_json_ok = True
            calls = list(getattr(resp, "function_calls", None) or [])
            text = getattr(resp, "text", None)
            if not calls:
                if not text:
                    raise ExtractionFormatError("empty response")
                return text
            if text and round_no >= MAX_TOOL_ROUNDS - 1:
                return text
            if round_no >= MAX_TOOL_ROUNDS:
                break
            convo.append(resp.candidates[0].content)  # keep model turn intact (thought signatures)
            parts = []
            for call in calls:
                expr = str((call.args or {}).get("expression", ""))
                try:
                    result: dict = {"result": tool_fn(expr)}
                except Exception as exc:  # noqa: BLE001 - tool errors go back to the model
                    result = {"error": str(exc)}
                if tool_log is not None:
                    tool_log.append({"expression": expr, **result})
                parts.append(types.Part.from_function_response(name=call.name, response=result))
            convo.append(types.Content(role="user", parts=parts))
        convo.append(
            "Stop calling calculate. Return the JSON answers now, using fact-sheet numbers "
            "and calculate results already returned. Do not mention the fact sheet, the raw "
            "extraction, tools, or these instructions."
        )
        resp = self._call(convo, self._config(system, None, json_mode=json_mode, tools=None))
        text = getattr(resp, "text", None)
        if text:
            return text
        raise ExtractionFormatError("tool round limit reached without a final answer")


def parse_json_text(text: str):
    """Parse model text as JSON, stripping markdown fences. Raises ExtractionFormatError."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0]
    try:
        return json.loads(cleaned)
    except ValueError as exc:
        raise ExtractionFormatError(f"response is not valid JSON: {exc}") from exc


def parse_raw(text: str) -> RawBill:
    """Parse model text into a RawBill, raising ExtractionFormatError with a readable reason."""
    data = parse_json_text(text)
    if not isinstance(data, dict):
        raise ExtractionFormatError("response JSON is not an object")
    try:
        return RawBill.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:8]
        )
        raise ExtractionFormatError(f"response does not match the raw schema: {problems}") from exc
