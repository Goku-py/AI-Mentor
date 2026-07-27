from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import urllib.parse
from collections import OrderedDict
from typing import Any

import httpx
from flask import current_app

from app_pkg.security.middleware import SECURITY_METRICS, _add_metric

_logger = logging.getLogger(__name__)

_ai_client: httpx.AsyncClient | None = None

def _get_ai_client() -> httpx.AsyncClient:
    global _ai_client
    if _ai_client is None:
        _ai_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
    return _ai_client

def _get_valid_gemini_api_key() -> str | None:
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if api_key.startswith('"') and api_key.endswith('"'):
        api_key = api_key[1:-1].strip()
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        return None
    return api_key

def _extract_gemini_text(response_json: dict[str, Any]) -> str | None:
    candidates = response_json.get("candidates")
    if not isinstance(candidates, list):
        return None
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if (
                isinstance(part, dict)
                and isinstance(part.get("text"), str)
                and part["text"].strip()
            ):
                return part["text"].strip()
    return None

def _map_gemini_http_error(status_code: int, body_text: str, error_message: str) -> str:
    haystack = f"{error_message}\n{body_text}".lower()
    if status_code == 403 and (
        "api has not been used" in haystack
        or "service disabled" in haystack
        or "is disabled" in haystack
    ):
        return "AI_MENTOR_API_DISABLED"
    if status_code == 429 or "quota" in haystack or "rate limit" in haystack:
        return "AI_MENTOR_QUOTA_EXCEEDED"
    return "AI_MENTOR_API_ERROR"

def _ai_mentor_status_from_feedback(feedback: str) -> str:
    if feedback == "AI_MENTOR_DISABLED":
        return "disabled"
    if feedback == "AI_MENTOR_QUOTA_EXCEEDED":
        return "quota_exceeded"
    if feedback == "AI_MENTOR_BAD_RESPONSE":
        return "bad_response"
    if feedback == "AI_MENTOR_API_ERROR":
        return "api_error"
    return "ok"

MAX_GLOBAL_AI_CALLS_PER_DAY = int(os.environ.get("MAX_GLOBAL_AI_CALLS_PER_DAY", "5000"))

_AI_QUOTA_REDIS_PREFIX = "ai_quota:"

def _ai_quota_redis_key() -> str:
    return f"{_AI_QUOTA_REDIS_PREFIX}{time.strftime('%Y-%m-%d')}"

def _check_ai_quota() -> bool:
    client = None
    try:
        from app_pkg.extensions import get_redis_client
        client = get_redis_client()
    except ImportError:
        client = None
    if client is not None:
        key = _ai_quota_redis_key()
        value = client.get(key)
        return value is not None and int(value) >= MAX_GLOBAL_AI_CALLS_PER_DAY
    return SECURITY_METRICS.get("ai_mentor_calls_made", 0) >= MAX_GLOBAL_AI_CALLS_PER_DAY

def _increment_ai_quota() -> None:
    client = None
    try:
        from app_pkg.extensions import get_redis_client
        client = get_redis_client()
    except ImportError:
        client = None
    if client is not None:
        key = _ai_quota_redis_key()
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)
        pipe.execute()
    else:
        _add_metric("ai_mentor_calls_made")

_AI_MENTOR_CACHE: OrderedDict = OrderedDict()
_AI_MENTOR_CACHE_SIZE = 500

_logger = logging.getLogger("app_pkg")

MAX_AI_CODE_CHARS = 10000

_MENTOR_PROMPTS = (
    "You are a strict coding instructor helping a beginner."
    " A student submitted code that has errors.\n"
    "RULES YOU MUST FOLLOW:\n"
    "- For EVERY issue you mention, you MUST reference the exact line number.\n"
    "- Use simple, plain language that a beginner can understand.\n"
    "- Explain what is wrong in simple terms.\n"
    "- Give a HINT toward the exact line or concept that needs fixing.\n"
    "- Do NOT give the corrected code.\n"
    "- Be VERY BRIEF — max 3 sentences per error.\n"
    "- Focus ONLY on errors that prevent the code from running."
    " Do NOT comment on style issues (line length, indentation, trailing whitespace, TODO comments).\n\n"
    "Detected issues:\n{error_context}\n\n"
    "Student code ({language}) with line numbers:\n"
    "```\n{numbered_lines}\n```"
)

def _build_mentor_prompt(code: str, language: str, error_context: str) -> str:
    safe = code[:MAX_AI_CODE_CHARS]
    if len(code) > MAX_AI_CODE_CHARS:
        safe += "\n... [TRUNCATED DUE TO LENGTH BUDGET]"
    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(safe.splitlines(), start=1))
    return _MENTOR_PROMPTS.format(error_context=error_context, numbered_lines=numbered, language=language)

_STYLE_ISSUE_CODES: set[str] = {
    "LONG_LINE",
    "TODO_COMMENT",
    "TRAILING_WHITESPACE",
    "TABS_INDENT",
}

def _build_error_context(execution: dict, issues: list[dict]) -> tuple[str, list[dict]]:
    ctx = ""
    all_errors: list[dict] = []
    for iss in issues:
        if iss.get("severity") == "error" and iss.get("code") not in _STYLE_ISSUE_CODES:
            all_errors.append({
                "line": iss.get("line"),
                "type": iss.get("code", "ERROR"),
                "message": iss.get("message"),
                "severity": "error",
            })
            ctx += f"Line {iss.get('line')}: {iss.get('message')}\n"
    if execution.get("error"):
        ee = execution["error"]
        ln = ee.get("line", "?")
        all_errors.append({
            "line": ln,
            "type": ee.get("type", "RuntimeError"),
            "message": ee.get("message", ""),
            "explanation": ee.get("explanation", ""),
            "severity": "error",
        })
        ctx += f"Line {ln}: {ee.get('type')} - {ee.get('message')}\n"
    if not all_errors:
        for warn in issues:
            if warn.get("severity") == "warning" and warn.get("code") not in _STYLE_ISSUE_CODES:
                ctx += f"Line {warn.get('line')}: {warn.get('message')}\n"
    return ctx, all_errors

async def _get_ai_mentorship(
    code: str,
    language: str,
    execution: dict,
    issues: list[dict],
) -> str:
    if _check_ai_quota():
        return "AI_MENTOR_QUOTA_EXCEEDED"
    api_key = _get_valid_gemini_api_key()
    if not api_key:
        return "AI_MENTOR_DISABLED"
    try:
        error_context, all_errors = _build_error_context(execution, issues)
        if all_errors or error_context:
            cache_key_str = f"{code[:MAX_AI_CODE_CHARS]}:{language}:{error_context}"
            cache_key = hashlib.sha256(cache_key_str.encode("utf-8")).hexdigest()
            if cache_key in _AI_MENTOR_CACHE:
                res = _AI_MENTOR_CACHE.pop(cache_key)
                _AI_MENTOR_CACHE[cache_key] = res
                return res
            prompt = _build_mentor_prompt(code, language, error_context)
            gemini_model = (os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()
            endpoint = (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/{urllib.parse.quote_plus(gemini_model)}:generateContent"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
            }
            _increment_ai_quota()
            _max_retries = 3
            client = _get_ai_client()
            for _attempt in range(_max_retries):
                try:
                    response = await client.post(
                        endpoint, json=payload, headers={"X-Goog-Api-Key": api_key},
                    )
                    status_code = response.status_code
                    raw_body = response.text
                    if status_code == 429 and _attempt < _max_retries - 1:
                        backoff = 2**_attempt
                        _logger.warning("Gemini rate limited (429). Retrying in %ds...", backoff)
                        await asyncio.sleep(backoff)
                        continue
                    break
                except httpx.RequestError:
                    _logger.exception("Gemini network error")
                    return "AI_MENTOR_API_ERROR"
            if status_code < 200 or status_code >= 300:
                _logger.error("Gemini unexpected status: %s", status_code)
                return _map_gemini_http_error(status_code, raw_body, "")
            try:
                parsed = json.loads(raw_body)
            except json.JSONDecodeError:
                preview = raw_body[:180].replace("\n", " ")
                _logger.exception("Gemini JSON decode failed. body_preview=%s", preview)
                return "AI_MENTOR_BAD_RESPONSE"
            feedback_text = _extract_gemini_text(parsed)
            try:
                usage = parsed.get("usageMetadata", {})
                if usage:
                    total_tokens = int(usage.get("totalTokenCount", 0))
                    _add_metric("ai_mentor_tokens_used", total_tokens)
                    _logger.info(
                        "gemini_api_usage",
                        extra={
                            "prompt_tokens": usage.get("promptTokenCount", 0),
                            "candidates_tokens": usage.get("candidatesTokenCount", 0),
                            "total_tokens": total_tokens,
                        },
                    )
            except (KeyError, TypeError, AttributeError) as e:
                _logger.warning("Failed to parse usageMetadata", exc_info=e)
            if feedback_text:
                _AI_MENTOR_CACHE[cache_key] = feedback_text
                if len(_AI_MENTOR_CACHE) > _AI_MENTOR_CACHE_SIZE:
                    _AI_MENTOR_CACHE.popitem(last=False)
                return feedback_text
            return "AI_MENTOR_BAD_RESPONSE"
    except Exception as exc:
        _logger.exception("Unexpected Gemini error type=%s", type(exc).__name__)
        return "AI_MENTOR_API_ERROR"
    return "LOOKS_GOOD"
