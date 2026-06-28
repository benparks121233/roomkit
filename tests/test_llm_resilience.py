"""Tests for sub-phase 5: LLM retry + shared client singletons."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, call

import pytest

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-fake")


# ---------------------------------------------------------------------------
# Style service: retry + singleton
# ---------------------------------------------------------------------------

class TestStyleRetry:
    """style_service._call_llm retries on RateLimitError."""

    def test_succeeds_on_first_try(self):
        import anthropic
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="ok")]
        mock_client.messages.create.return_value = mock_msg

        with patch("services.style_service._get_anthropic_client", return_value=mock_client):
            from services.style_service import _call_llm
            result = _call_llm("sys", "usr")

        assert result == "ok"
        assert mock_client.messages.create.call_count == 1

    def test_retries_on_rate_limit(self):
        import anthropic
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="retry-ok")]

        rate_err = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_client.messages.create.side_effect = [rate_err, mock_msg]

        with patch("services.style_service._get_anthropic_client", return_value=mock_client), \
             patch("services.style_service.time.sleep") as mock_sleep:
            from services.style_service import _call_llm
            result = _call_llm("sys", "usr")

        assert result == "retry-ok"
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] == 1.0  # first backoff

    def test_exhausts_retries_raises(self):
        import anthropic
        mock_client = MagicMock()
        rate_err = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_client.messages.create.side_effect = [rate_err, rate_err, rate_err]

        with patch("services.style_service._get_anthropic_client", return_value=mock_client), \
             patch("services.style_service.time.sleep"):
            from services.style_service import _call_llm
            with pytest.raises(anthropic.RateLimitError):
                _call_llm("sys", "usr")

        assert mock_client.messages.create.call_count == 3

    def test_retries_on_529_overloaded(self):
        import anthropic
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="529-ok")]

        err_529 = anthropic.InternalServerError(
            message="overloaded",
            response=MagicMock(status_code=529),
            body=None,
        )
        mock_client.messages.create.side_effect = [err_529, mock_msg]

        with patch("services.style_service._get_anthropic_client", return_value=mock_client), \
             patch("services.style_service.time.sleep") as mock_sleep:
            from services.style_service import _call_llm
            result = _call_llm("sys", "usr")

        assert result == "529-ok"
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once()

    def test_retries_on_timeout(self):
        import anthropic
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="timeout-ok")]

        timeout_err = anthropic.APITimeoutError(request=MagicMock())
        mock_client.messages.create.side_effect = [timeout_err, mock_msg]

        with patch("services.style_service._get_anthropic_client", return_value=mock_client), \
             patch("services.style_service.time.sleep") as mock_sleep:
            from services.style_service import _call_llm
            result = _call_llm("sys", "usr")

        assert result == "timeout-ok"
        assert mock_client.messages.create.call_count == 2

    def test_non_retryable_error_not_retried(self):
        import anthropic
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.BadRequestError(
            message="bad request",
            response=MagicMock(status_code=400),
            body=None,
        )

        with patch("services.style_service._get_anthropic_client", return_value=mock_client):
            from services.style_service import _call_llm
            with pytest.raises(anthropic.BadRequestError):
                _call_llm("sys", "usr")

        assert mock_client.messages.create.call_count == 1


class TestStyleSingleton:
    """style_service uses a module-level Anthropic client singleton."""

    def test_singleton_created_once(self):
        import services.style_service as ss
        ss._anthropic_client = None

        with patch("services.style_service.anthropic.Anthropic") as MockAnthro:
            mock_instance = MagicMock()
            MockAnthro.return_value = mock_instance

            c1 = ss._get_anthropic_client()
            c2 = ss._get_anthropic_client()

        assert c1 is c2
        MockAnthro.assert_called_once()
        ss._anthropic_client = None  # cleanup


# ---------------------------------------------------------------------------
# Composition service: retry + singleton
# ---------------------------------------------------------------------------

class TestCompositionRetry:
    """composition_service._call_composition_llm retries on RateLimitError."""

    def test_succeeds_on_first_try(self):
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="comp-ok")]
        mock_client.messages.create.return_value = mock_msg

        with patch("services.composition_service._get_anthropic_client", return_value=mock_client):
            from services.composition_service import _call_composition_llm
            result = _call_composition_llm("sys", "usr")

        assert result == "comp-ok"
        assert mock_client.messages.create.call_count == 1

    def test_retries_on_rate_limit(self):
        import anthropic
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="comp-retry-ok")]

        rate_err = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_client.messages.create.side_effect = [rate_err, mock_msg]

        with patch("services.composition_service._get_anthropic_client", return_value=mock_client), \
             patch("services.composition_service.time.sleep") as mock_sleep:
            from services.composition_service import _call_composition_llm
            result = _call_composition_llm("sys", "usr")

        assert result == "comp-retry-ok"
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once()

    def test_exhausts_retries_raises(self):
        import anthropic
        mock_client = MagicMock()
        rate_err = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_client.messages.create.side_effect = [rate_err, rate_err, rate_err]

        with patch("services.composition_service._get_anthropic_client", return_value=mock_client), \
             patch("services.composition_service.time.sleep"):
            from services.composition_service import _call_composition_llm
            with pytest.raises(anthropic.RateLimitError):
                _call_composition_llm("sys", "usr")

        assert mock_client.messages.create.call_count == 3

    def test_retries_on_529_overloaded(self):
        import anthropic
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="529-ok")]

        err_529 = anthropic.InternalServerError(
            message="overloaded",
            response=MagicMock(status_code=529),
            body=None,
        )
        mock_client.messages.create.side_effect = [err_529, mock_msg]

        with patch("services.composition_service._get_anthropic_client", return_value=mock_client), \
             patch("services.composition_service.time.sleep"):
            from services.composition_service import _call_composition_llm
            result = _call_composition_llm("sys", "usr")

        assert result == "529-ok"
        assert mock_client.messages.create.call_count == 2

    def test_retries_on_timeout(self):
        import anthropic
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="timeout-ok")]

        timeout_err = anthropic.APITimeoutError(request=MagicMock())
        mock_client.messages.create.side_effect = [timeout_err, mock_msg]

        with patch("services.composition_service._get_anthropic_client", return_value=mock_client), \
             patch("services.composition_service.time.sleep"):
            from services.composition_service import _call_composition_llm
            result = _call_composition_llm("sys", "usr")

        assert result == "timeout-ok"
        assert mock_client.messages.create.call_count == 2


class TestCompositionSingleton:
    """composition_service uses a module-level Anthropic client singleton."""

    def test_singleton_created_once(self):
        import services.composition_service as cs
        cs._anthropic_client = None

        with patch("services.composition_service.anthropic.Anthropic") as MockAnthro:
            mock_instance = MagicMock()
            MockAnthro.return_value = mock_instance

            c1 = cs._get_anthropic_client()
            c2 = cs._get_anthropic_client()

        assert c1 is c2
        MockAnthro.assert_called_once()
        cs._anthropic_client = None


# ---------------------------------------------------------------------------
# Selection service: singleton (retry already existed)
# ---------------------------------------------------------------------------

class TestSelectionRetry:
    """selection_service._call_selection_llm retries on 429, 529, timeout."""

    def test_retries_on_529_overloaded(self):
        import anthropic
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="sel-529-ok")]

        err_529 = anthropic.InternalServerError(
            message="overloaded",
            response=MagicMock(status_code=529),
            body=None,
        )
        mock_client.messages.create.side_effect = [err_529, mock_msg]

        with patch("services.selection_service._get_anthropic_client", return_value=mock_client), \
             patch("services.selection_service.time.sleep"):
            from services.selection_service import _call_selection_llm
            result = _call_selection_llm("sys", "usr")

        assert result == "sel-529-ok"
        assert mock_client.messages.create.call_count == 2

    def test_retries_on_timeout(self):
        import anthropic
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="sel-timeout-ok")]

        timeout_err = anthropic.APITimeoutError(request=MagicMock())
        mock_client.messages.create.side_effect = [timeout_err, mock_msg]

        with patch("services.selection_service._get_anthropic_client", return_value=mock_client), \
             patch("services.selection_service.time.sleep"):
            from services.selection_service import _call_selection_llm
            result = _call_selection_llm("sys", "usr")

        assert result == "sel-timeout-ok"
        assert mock_client.messages.create.call_count == 2

    def test_non_retryable_error_not_retried(self):
        import anthropic
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.BadRequestError(
            message="bad",
            response=MagicMock(status_code=400),
            body=None,
        )

        with patch("services.selection_service._get_anthropic_client", return_value=mock_client):
            from services.selection_service import _call_selection_llm
            with pytest.raises(anthropic.BadRequestError):
                _call_selection_llm("sys", "usr")

        assert mock_client.messages.create.call_count == 1


class TestSelectionSingleton:
    """selection_service uses a module-level Anthropic client singleton."""

    def test_singleton_created_once(self):
        import services.selection_service as sel
        sel._anthropic_client = None

        with patch("services.selection_service.anthropic.Anthropic") as MockAnthro:
            mock_instance = MagicMock()
            MockAnthro.return_value = mock_instance

            c1 = sel._get_anthropic_client()
            c2 = sel._get_anthropic_client()

        assert c1 is c2
        MockAnthro.assert_called_once()
        sel._anthropic_client = None


# ---------------------------------------------------------------------------
# Render service: OpenAI singleton + 2x retry
# ---------------------------------------------------------------------------

class TestRenderSingleton:
    """render_service uses a module-level OpenAI client singleton."""

    def test_retry_constants(self):
        import services.render_service as rs
        assert rs._RENDER_RETRY_MAX == 2
        assert rs._RENDER_RETRY_BACKOFF == 5.0

    def test_singleton_starts_none(self):
        import services.render_service as rs
        saved = rs._openai_client
        rs._openai_client = None
        assert rs._openai_client is None
        rs._openai_client = saved

    def test_singleton_reused(self):
        import services.render_service as rs
        saved = rs._openai_client
        mock_client = MagicMock()
        rs._openai_client = mock_client
        assert rs._openai_client is mock_client
        rs._openai_client = saved
