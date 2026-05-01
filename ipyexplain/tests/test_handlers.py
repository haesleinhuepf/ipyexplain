"""
Unit tests for the ipyexplain Python backend.

These tests mock the OpenAI client so that no real API calls are made.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from ipyexplain.handlers import explain_error, fix_code, generate_code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_response(content: str):
    """Build a minimal mock of the OpenAI ChatCompletion response object."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# explain_error
# ---------------------------------------------------------------------------

class TestExplainError:
    def test_returns_explanation(self):
        mock_response = _make_mock_response("This is a NameError explanation.")

        with patch("ipyexplain.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            result = explain_error(
                ename="NameError",
                evalue="name 'x' is not defined",
                traceback="Traceback (most recent call last):\n  ...\nNameError: name 'x' is not defined",
            )

        assert result == "This is a NameError explanation."

    def test_passes_correct_messages(self):
        mock_response = _make_mock_response("explanation")

        with patch("ipyexplain.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            explain_error("TypeError", "bad type", "traceback text")

            call_kwargs = client.chat.completions.create.call_args
            messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs["messages"]
            # There should be a system message and a user message
            roles = [m["role"] for m in messages]
            assert "system" in roles
            assert "user" in roles

            # The user message should contain the error details
            user_msg = next(m["content"] for m in messages if m["role"] == "user")
            assert "TypeError" in user_msg
            assert "bad type" in user_msg


# ---------------------------------------------------------------------------
# fix_code
# ---------------------------------------------------------------------------

class TestFixCode:
    def test_extracts_code_block(self):
        raw = "```python\nprint('hello')\n```"
        mock_response = _make_mock_response(raw)

        with patch("ipyexplain.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            result = fix_code(
                code="pritn('hello')",
                ename="NameError",
                evalue="name 'pritn' is not defined",
                traceback="...",
            )

        assert result == "print('hello')"

    def test_returns_raw_if_no_code_block(self):
        raw = "x = 1 + 1"
        mock_response = _make_mock_response(raw)

        with patch("ipyexplain.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            result = fix_code("x = 1 +", "SyntaxError", "invalid syntax", "...")

        assert result == "x = 1 + 1"

    def test_passes_code_and_error_to_prompt(self):
        mock_response = _make_mock_response("```python\nfixed\n```")

        with patch("ipyexplain.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            fix_code("original_code()", "RuntimeError", "something went wrong", "traceback")

            call_kwargs = client.chat.completions.create.call_args
            messages = call_kwargs.kwargs.get("messages") or call_kwargs.kwargs["messages"]
            user_msg = next(m["content"] for m in messages if m["role"] == "user")
            assert "original_code()" in user_msg
            assert "RuntimeError" in user_msg


# ---------------------------------------------------------------------------
# generate_code
# ---------------------------------------------------------------------------

class TestGenerateCode:
    def test_extracts_code_block(self):
        raw = "```python\nimport pandas as pd\n```"
        mock_response = _make_mock_response(raw)

        with patch("ipyexplain.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            result = generate_code("import pandas")

        assert result == "import pandas as pd"

    def test_passes_prompt_to_messages(self):
        mock_response = _make_mock_response("```python\npass\n```")

        with patch("ipyexplain.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            generate_code(
                "add a bar chart from the loaded data",
                "import pandas as pd\ndf = pd.read_csv('data.csv')"
            )

            call_kwargs = client.chat.completions.create.call_args
            messages = call_kwargs.kwargs.get("messages") or call_kwargs.kwargs["messages"]
            user_msg = next(m["content"] for m in messages if m["role"] == "user")
            assert "add a bar chart from the loaded data" in user_msg
            assert "import pandas as pd" in user_msg
            assert "df = pd.read_csv('data.csv')" in user_msg


# ---------------------------------------------------------------------------
# _extract_code_block helper
# ---------------------------------------------------------------------------

class TestExtractCodeBlock:
    def test_extracts_python_block(self):
        from ipyexplain.handlers import _extract_code_block

        text = "Here is code:\n```python\nx = 1\n```\nDone."
        assert _extract_code_block(text) == "x = 1"

    def test_extracts_plain_block(self):
        from ipyexplain.handlers import _extract_code_block

        text = "```\ny = 2\n```"
        assert _extract_code_block(text) == "y = 2"

    def test_falls_back_to_stripped_text(self):
        from ipyexplain.handlers import _extract_code_block

        text = "  x = 42  "
        assert _extract_code_block(text) == "x = 42"


# ---------------------------------------------------------------------------
# _get_openai_client raises when key missing
# ---------------------------------------------------------------------------

class TestGetOpenAIClient:
    def test_raises_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            from ipyexplain.handlers import _get_openai_client
            _get_openai_client()
