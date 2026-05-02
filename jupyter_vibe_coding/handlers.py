"""
REST API handlers for jupyter-vibe-coding.

Endpoints
---------
POST /jupyter-vibe-coding/explain
    Body: { "ename": str, "evalue": str, "traceback": str }
    Returns: { "explanation": str }

POST /jupyter-vibe-coding/fix
    Body: { "code": str, "ename": str, "evalue": str, "traceback": str }
    Returns: { "fixed_code": str, "fix_summary": str }

POST /jupyter-vibe-coding/generate
    Body: { "prompt": str, "existing_code": str }
    Returns: { "code": str }
"""
import json
import os
import re
import traceback as tb_module
from typing import Any

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
import tornado


DEFAULT_MODEL = "gpt-4o-mini"
RuntimeConfig = dict[str, str | bool]


# ---------------------------------------------------------------------------
# Helper – call OpenAI
# ---------------------------------------------------------------------------

def _get_openai_client(runtime_config: RuntimeConfig | None = None):
    """Return an OpenAI client, raising a clear error if the key is missing."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The 'openai' package is required. Install it with: pip install openai"
        ) from exc

    runtime_config = runtime_config or {}
    api_key = (
        (runtime_config.get("api_key") if runtime_config.get("enabled") else None)
        or os.environ.get("JUPYTER_VIBE_CODING_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "No API key is configured. Set JUPYTER_VIBE_CODING_API_KEY "
            "(preferred) or OPENAI_API_KEY before using jupyter-vibe-coding."
        )

    base_url = (
        (runtime_config.get("base_url") if runtime_config.get("enabled") else None)
        or os.environ.get("JUPYTER_VIBE_CODING_BASE_URL")
    )
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    return OpenAI(**client_kwargs)


def _chat(
    messages: list,
    model: str | None = None,
    runtime_config: RuntimeConfig | None = None,
) -> str:
    """Send a chat completion request and return the assistant's text."""
    client = _get_openai_client(runtime_config=runtime_config)
    runtime_model = runtime_config.get("model") if runtime_config and runtime_config.get("enabled") else None
    selected_model = model or runtime_model or os.environ.get("JUPYTER_VIBE_CODING_MODEL") or DEFAULT_MODEL
    response = client.chat.completions.create(
        model=selected_model,
        messages=messages,
    )
    return response.choices[0].message.content or ""


def _get_runtime_config(body: dict[str, Any] | None) -> RuntimeConfig | None:
    """Parse optional request runtime config for API key, base URL and model."""
    if not body:
        return None

    raw = body.get("config")
    if not isinstance(raw, dict):
        return None

    enabled = bool(raw.get("enabled", False))
    if not enabled:
        return {"enabled": False}

    def _clean(value: Any) -> str:
        return str(value).strip() if value is not None else ""

    return {
        "enabled": True,
        "base_url": _clean(raw.get("base_url")),
        "api_key": _clean(raw.get("api_key")),
        "model": _clean(raw.get("model")),
    }


def _extract_code_block(text: str) -> str:
    """Extract the first fenced code block from *text*, or return *text* stripped."""
    import os
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------

def explain_error(
    ename: str,
    evalue: str,
    traceback: str,
    runtime_config: RuntimeConfig | None = None,
) -> str:
    """Use an LLM to explain the given Python error in plain language."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful Python programming assistant. "
                "When given a Python error, explain what caused it in plain, "
                "concise language that a student can understand. "
                "Do not include code in your answer unless it is essential."
            ),
        },
        {
            "role": "user",
            "content": (
                f"I got the following Python error:\n\n"
                f"Error type: {ename}\n"
                f"Error message: {evalue}\n\n"
                f"Traceback:\n{traceback}\n\n"
                f"Please explain what went wrong."
            ),
        },
    ]
    return _chat(messages, runtime_config=runtime_config)


# ---------------------------------------------------------------------------
# Fix
# ---------------------------------------------------------------------------

def fix_code(
    code: str,
    ename: str,
    evalue: str,
    traceback: str,
    runtime_config: RuntimeConfig | None = None,
) -> str:
    """Use an LLM to fix the Python code that produced the given error."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful Python programming assistant. "
                "When given Python code and an error it produced, return the "
                "corrected code only – no explanation, no markdown prose around "
                "it. Wrap the code in a single ```python ... ``` block."
            ),
        },
        {
            "role": "user",
            "content": (
                f"The following Python code produced an error:\n\n"
                f"```python\n{code}\n```\n\n"
                f"Error type: {ename}\n"
                f"Error message: {evalue}\n\n"
                f"Traceback:\n{traceback}\n\n"
                f"Please return the corrected code."
            ),
        },
    ]
    raw = _chat(messages, runtime_config=runtime_config)
    return _extract_code_block(raw)


def summarize_fix(
    original_code: str,
    fixed_code: str,
    ename: str,
    evalue: str,
    traceback: str,
    runtime_config: RuntimeConfig | None = None,
) -> str:
    """Return a short plain-language summary of what was changed in a fix."""
    if original_code.strip() == fixed_code.strip():
        return "No code changes were needed."

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful Python programming assistant. "
                "Summarize code fixes in one short sentence. "
                "Focus on what was changed and why. "
                "Do not use markdown or bullet points."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Original code:\n"
                f"```python\n{original_code}\n```\n\n"
                f"Fixed code:\n"
                f"```python\n{fixed_code}\n```\n\n"
                f"Error type: {ename}\n"
                f"Error message: {evalue}\n\n"
                f"Traceback:\n{traceback}\n\n"
                "In one short sentence, describe what was fixed."
            ),
        },
    ]

    try:
        return _chat(messages, runtime_config=runtime_config).strip()
    except Exception:
        return f"Updated the code to address {ename}: {evalue}."


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def generate_code(
    prompt: str,
    existing_code: str = "",
    runtime_config: RuntimeConfig | None = None,
) -> str:
    """Use an LLM to generate or modify Python code from a prompt."""
    existing_code_block = existing_code.strip() or "# (empty cell)"
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful Python programming assistant. "
                "When given a request and current cell code, return Python code "
                "that fulfils the request, using the current code as context. "
                "Return only the code in a single ```python ... ``` block."
            ),
        },
        {
            "role": "user",
            "content": (
                "Current cell code:\n\n"
                f"```python\n{existing_code_block}\n```\n\n"
                "Requested change:\n\n"
                f"{prompt}\n\n"
                "Return the full updated cell code."
            ),
        },
    ]
    raw = _chat(messages, runtime_config=runtime_config)
    return _extract_code_block(raw)


# ---------------------------------------------------------------------------
# Tornado handlers
# ---------------------------------------------------------------------------

class ExplainHandler(APIHandler):
    """POST /jupyter-vibe-coding/explain"""

    @tornado.web.authenticated
    def post(self):
        body = self.get_json_body() or {}
        ename = body.get("ename", "")
        evalue = body.get("evalue", "")
        traceback = body.get("traceback", "")
        runtime_config = _get_runtime_config(body)

        try:
            explanation = explain_error(ename, evalue, traceback, runtime_config=runtime_config)
            self.finish(json.dumps({"explanation": explanation}))
        except Exception as exc:
            self.log.error("jupyter-vibe-coding explain error: %s", tb_module.format_exc())
            self.set_status(500)
            self.finish(json.dumps({"message": str(exc)}))


class FixHandler(APIHandler):
    """POST /jupyter-vibe-coding/fix"""

    @tornado.web.authenticated
    def post(self):
        body = self.get_json_body() or {}
        code = body.get("code", "")
        ename = body.get("ename", "")
        evalue = body.get("evalue", "")
        traceback = body.get("traceback", "")
        runtime_config = _get_runtime_config(body)

        try:
            fixed_code = fix_code(
                code,
                ename,
                evalue,
                traceback,
                runtime_config=runtime_config,
            )
            fix_summary = summarize_fix(
                code,
                fixed_code,
                ename,
                evalue,
                traceback,
                runtime_config=runtime_config,
            )
            self.finish(json.dumps({"fixed_code": fixed_code, "fix_summary": fix_summary}))
        except Exception as exc:
            self.log.error("jupyter-vibe-coding fix error: %s", tb_module.format_exc())
            self.set_status(500)
            self.finish(json.dumps({"message": str(exc)}))


class GenerateHandler(APIHandler):
    """POST /jupyter-vibe-coding/generate"""

    @tornado.web.authenticated
    def post(self):
        body = self.get_json_body() or {}
        prompt = body.get("prompt", "")
        existing_code = body.get("existing_code", "")
        runtime_config = _get_runtime_config(body)

        try:
            code = generate_code(prompt, existing_code, runtime_config=runtime_config)
            self.finish(json.dumps({"code": code}))
        except Exception as exc:
            self.log.error("jupyter-vibe-coding generate error: %s", tb_module.format_exc())
            self.set_status(500)
            self.finish(json.dumps({"message": str(exc)}))


# ---------------------------------------------------------------------------
# Route setup
# ---------------------------------------------------------------------------

def setup_handlers(web_app):
    """Register the jupyter-vibe-coding URL handlers with the Jupyter server."""
    host_pattern = ".*$"
    base_url = web_app.settings["base_url"]

    handlers = [
        (url_path_join(base_url, "jupyter-vibe-coding", "explain"), ExplainHandler),
        (url_path_join(base_url, "jupyter-vibe-coding", "fix"), FixHandler),
        (url_path_join(base_url, "jupyter-vibe-coding", "generate"), GenerateHandler),
    ]
    web_app.add_handlers(host_pattern, handlers)
