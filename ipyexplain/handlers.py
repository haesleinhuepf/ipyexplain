"""
REST API handlers for ipyexplain.

Endpoints
---------
POST /ipyexplain/explain
    Body: { "ename": str, "evalue": str, "traceback": str }
    Returns: { "explanation": str }

POST /ipyexplain/fix
    Body: { "code": str, "ename": str, "evalue": str, "traceback": str }
    Returns: { "fixed_code": str }

POST /ipyexplain/generate
    Body: { "prompt": str }
    Returns: { "code": str }
"""
import json
import os
import re
import traceback as tb_module

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
import tornado


# ---------------------------------------------------------------------------
# Helper – call OpenAI
# ---------------------------------------------------------------------------

def _get_openai_client():
    """Return an OpenAI client, raising a clear error if the key is missing."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The 'openai' package is required. Install it with: pip install openai"
        ) from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Please set it before using ipyexplain."
        )
    return OpenAI(api_key=api_key)


def _chat(messages: list, model: str = "gpt-4o-mini") -> str:
    """Send a chat completion request and return the assistant's text."""
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return response.choices[0].message.content or ""


def _extract_code_block(text: str) -> str:
    """Extract the first fenced code block from *text*, or return *text* stripped."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------

def explain_error(ename: str, evalue: str, traceback: str) -> str:
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
    return _chat(messages)


# ---------------------------------------------------------------------------
# Fix
# ---------------------------------------------------------------------------

def fix_code(code: str, ename: str, evalue: str, traceback: str) -> str:
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
    raw = _chat(messages)
    return _extract_code_block(raw)


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def generate_code(prompt: str) -> str:
    """Use an LLM to generate Python code from a natural-language prompt."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful Python programming assistant. "
                "When given a description, return Python code that fulfils it. "
                "Return only the code in a single ```python ... ``` block."
            ),
        },
        {
            "role": "user",
            "content": f"Write Python code that does the following:\n\n{prompt}",
        },
    ]
    raw = _chat(messages)
    return _extract_code_block(raw)


# ---------------------------------------------------------------------------
# Tornado handlers
# ---------------------------------------------------------------------------

class ExplainHandler(APIHandler):
    """POST /ipyexplain/explain"""

    @tornado.web.authenticated
    def post(self):
        body = self.get_json_body()
        ename = body.get("ename", "")
        evalue = body.get("evalue", "")
        traceback = body.get("traceback", "")

        try:
            explanation = explain_error(ename, evalue, traceback)
            self.finish(json.dumps({"explanation": explanation}))
        except Exception as exc:
            self.log.error("ipyexplain explain error: %s", tb_module.format_exc())
            self.set_status(500)
            self.finish(json.dumps({"message": str(exc)}))


class FixHandler(APIHandler):
    """POST /ipyexplain/fix"""

    @tornado.web.authenticated
    def post(self):
        body = self.get_json_body()
        code = body.get("code", "")
        ename = body.get("ename", "")
        evalue = body.get("evalue", "")
        traceback = body.get("traceback", "")

        try:
            fixed_code = fix_code(code, ename, evalue, traceback)
            self.finish(json.dumps({"fixed_code": fixed_code}))
        except Exception as exc:
            self.log.error("ipyexplain fix error: %s", tb_module.format_exc())
            self.set_status(500)
            self.finish(json.dumps({"message": str(exc)}))


class GenerateHandler(APIHandler):
    """POST /ipyexplain/generate"""

    @tornado.web.authenticated
    def post(self):
        body = self.get_json_body()
        prompt = body.get("prompt", "")

        try:
            code = generate_code(prompt)
            self.finish(json.dumps({"code": code}))
        except Exception as exc:
            self.log.error("ipyexplain generate error: %s", tb_module.format_exc())
            self.set_status(500)
            self.finish(json.dumps({"message": str(exc)}))


# ---------------------------------------------------------------------------
# Route setup
# ---------------------------------------------------------------------------

def setup_handlers(web_app):
    """Register the ipyexplain URL handlers with the Jupyter server."""
    host_pattern = ".*$"
    base_url = web_app.settings["base_url"]

    handlers = [
        (url_path_join(base_url, "ipyexplain", "explain"), ExplainHandler),
        (url_path_join(base_url, "ipyexplain", "fix"), FixHandler),
        (url_path_join(base_url, "ipyexplain", "generate"), GenerateHandler),
    ]
    web_app.add_handlers(host_pattern, handlers)
