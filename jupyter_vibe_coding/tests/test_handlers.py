"""
Unit tests for the jupyter-vibe-coding Python backend.

These tests mock the OpenAI client so that no real API calls are made.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from jupyter_vibe_coding.handlers import (
    _get_runtime_config,
    explain_error,
    fix_code,
    generate_code,
    summarize_fix,
)


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

        with patch("jupyter_vibe_coding.handlers._get_openai_client") as mock_client_factory:
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

        with patch("jupyter_vibe_coding.handlers._get_openai_client") as mock_client_factory:
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

        with patch("jupyter_vibe_coding.handlers._get_openai_client") as mock_client_factory:
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

        with patch("jupyter_vibe_coding.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            result = fix_code("x = 1 +", "SyntaxError", "invalid syntax", "...")

        assert result == "x = 1 + 1"

    def test_passes_code_and_error_to_prompt(self):
        mock_response = _make_mock_response("```python\nfixed\n```")

        with patch("jupyter_vibe_coding.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            fix_code("original_code()", "RuntimeError", "something went wrong", "traceback")

            call_kwargs = client.chat.completions.create.call_args
            messages = call_kwargs.kwargs.get("messages") or call_kwargs.kwargs["messages"]
            user_msg = next(m["content"] for m in messages if m["role"] == "user")
            assert "original_code()" in user_msg
            assert "RuntimeError" in user_msg


class TestSummarizeFix:
    def test_returns_summary_text(self):
        mock_response = _make_mock_response("Renamed pritn to print to fix a NameError.")

        with patch("jupyter_vibe_coding.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            result = summarize_fix(
                original_code="pritn('hello')",
                fixed_code="print('hello')",
                ename="NameError",
                evalue="name 'pritn' is not defined",
                traceback="...",
            )

        assert result == "Renamed pritn to print to fix a NameError."

    def test_returns_no_change_message_when_code_unchanged(self):
        result = summarize_fix(
            original_code="x = 1",
            fixed_code="x = 1",
            ename="ValueError",
            evalue="bad value",
            traceback="...",
        )

        assert result == "No code changes were needed."

    def test_falls_back_when_summary_generation_fails(self):
        with patch("jupyter_vibe_coding.handlers._chat", side_effect=RuntimeError("boom")):
            result = summarize_fix(
                original_code="x = 1 +",
                fixed_code="x = 1 + 1",
                ename="SyntaxError",
                evalue="invalid syntax",
                traceback="...",
            )

        assert result == "Updated the code to address SyntaxError: invalid syntax."


# ---------------------------------------------------------------------------
# generate_code
# ---------------------------------------------------------------------------

class TestGenerateCode:
    def test_extracts_code_block(self):
        raw = "```python\nimport pandas as pd\n```"
        mock_response = _make_mock_response(raw)

        with patch("jupyter_vibe_coding.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            result = generate_code("import pandas")

        assert result == "import pandas as pd"

    def test_passes_prompt_to_messages(self):
        mock_response = _make_mock_response("```python\npass\n```")

        with patch("jupyter_vibe_coding.handlers._get_openai_client") as mock_client_factory:
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

    def test_uses_configured_model(self, monkeypatch):
        monkeypatch.setenv("JUPYTER_VIBE_CODING_MODEL", "gpt-4.1-mini")
        mock_response = _make_mock_response("```python\npass\n```")

        with patch("jupyter_vibe_coding.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            generate_code("write a no-op")

            call_kwargs = client.chat.completions.create.call_args
            model = call_kwargs.kwargs.get("model")
            assert model == "gpt-4.1-mini"

    def test_runtime_config_model_overrides_environment(self, monkeypatch):
        monkeypatch.setenv("JUPYTER_VIBE_CODING_MODEL", "gpt-4.1-mini")
        mock_response = _make_mock_response("```python\npass\n```")

        with patch("jupyter_vibe_coding.handlers._get_openai_client") as mock_client_factory:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_response
            mock_client_factory.return_value = client

            generate_code(
                "write a no-op",
                runtime_config={"enabled": True, "model": "gpt-5-mini"},
            )

            call_kwargs = client.chat.completions.create.call_args
            model = call_kwargs.kwargs.get("model")
            assert model == "gpt-5-mini"


# ---------------------------------------------------------------------------
# _extract_code_block helper
# ---------------------------------------------------------------------------

class TestExtractCodeBlock:
    def test_extracts_python_block(self):
        from jupyter_vibe_coding.handlers import _extract_code_block

        text = "Here is code:\n```python\nx = 1\n```\nDone."
        assert _extract_code_block(text) == "x = 1"

    def test_extracts_plain_block(self):
        from jupyter_vibe_coding.handlers import _extract_code_block

        text = "```\ny = 2\n```"
        assert _extract_code_block(text) == "y = 2"

    def test_falls_back_to_stripped_text(self):
        from jupyter_vibe_coding.handlers import _extract_code_block

        text = "  x = 42  "
        assert _extract_code_block(text) == "x = 42"


# ---------------------------------------------------------------------------
# _get_openai_client raises when key missing
# ---------------------------------------------------------------------------

class TestGetOpenAIClient:
    def test_raises_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("JUPYTER_VIBE_CODING_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="JUPYTER_VIBE_CODING_API_KEY"):
            from jupyter_vibe_coding.handlers import _get_openai_client
            _get_openai_client()

    def test_prefers_jupyter_vibe_coding_api_key(self, monkeypatch):
        monkeypatch.setenv("JUPYTER_VIBE_CODING_API_KEY", "jvc-key")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

        with patch("openai.OpenAI") as mock_openai:
            from jupyter_vibe_coding.handlers import _get_openai_client
            _get_openai_client()

            kwargs = mock_openai.call_args.kwargs
            assert kwargs["api_key"] == "jvc-key"

    def test_passes_base_url_when_configured(self, monkeypatch):
        monkeypatch.setenv("JUPYTER_VIBE_CODING_API_KEY", "jvc-key")
        monkeypatch.setenv("JUPYTER_VIBE_CODING_BASE_URL", "https://example.test/v1")

        with patch("openai.OpenAI") as mock_openai:
            from jupyter_vibe_coding.handlers import _get_openai_client
            _get_openai_client()

            kwargs = mock_openai.call_args.kwargs
            assert kwargs["api_key"] == "jvc-key"
            assert kwargs["base_url"] == "https://example.test/v1"

    def test_runtime_config_overrides_env_key_and_base_url(self, monkeypatch):
        monkeypatch.setenv("JUPYTER_VIBE_CODING_API_KEY", "env-key")
        monkeypatch.setenv("JUPYTER_VIBE_CODING_BASE_URL", "https://env.test/v1")

        with patch("openai.OpenAI") as mock_openai:
            from jupyter_vibe_coding.handlers import _get_openai_client

            _get_openai_client(
                runtime_config={
                    "enabled": True,
                    "api_key": "runtime-key",
                    "base_url": "https://runtime.test/v1",
                }
            )

            kwargs = mock_openai.call_args.kwargs
            assert kwargs["api_key"] == "runtime-key"
            assert kwargs["base_url"] == "https://runtime.test/v1"


# ---------------------------------------------------------------------------
# runtime config parser
# ---------------------------------------------------------------------------


class TestRuntimeConfig:
    def test_returns_none_when_missing(self):
        assert _get_runtime_config({}) is None
        assert _get_runtime_config(None) is None

    def test_returns_disabled_when_checkbox_not_enabled(self):
        config = _get_runtime_config({"config": {"enabled": False, "api_key": "x"}})
        assert config == {"enabled": False}

    def test_sanitizes_runtime_values(self):
        config = _get_runtime_config(
            {
                "config": {
                    "enabled": True,
                    "base_url": "  https://example.test/v1  ",
                    "api_key": "  sk-test  ",
                    "model": "  gpt-4.1-mini  ",
                }
            }
        )
        assert config == {
            "enabled": True,
            "base_url": "https://example.test/v1",
            "api_key": "sk-test",
            "model": "gpt-4.1-mini",
        }
