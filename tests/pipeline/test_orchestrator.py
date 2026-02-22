"""Tests for orchestrator token-usage persistence."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_stack.pipeline.orchestrator import PipelineOrchestrator

if TYPE_CHECKING:
    from collections.abc import Callable

    from agent_stack.models.agent_run import AgentRun
    from agent_stack.models.link import Link


@pytest.fixture
def mock_repos() -> tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    """Return (links, editions, feedback, agent_runs) mock repos."""
    return AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()


@pytest.fixture
def orchestrator(
    mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
) -> PipelineOrchestrator:
    """Create a PipelineOrchestrator with all external deps mocked."""
    links, editions, feedback, runs = mock_repos
    client = MagicMock()
    with (
        patch("agent_stack.pipeline.orchestrator.Agent"),
        patch("agent_stack.pipeline.orchestrator.FetchAgent"),
        patch("agent_stack.pipeline.orchestrator.ReviewAgent"),
        patch("agent_stack.pipeline.orchestrator.DraftAgent"),
        patch("agent_stack.pipeline.orchestrator.EditAgent"),
        patch("agent_stack.pipeline.orchestrator.PublishAgent"),
        patch("agent_stack.pipeline.orchestrator.load_prompt", return_value=""),
    ):
        return PipelineOrchestrator(client, links, editions, feedback, runs)


class TestNormalizeUsage:
    """Tests for _normalize_usage static helper."""

    def test_none_returns_none(self) -> None:
        """Return None when input is None."""
        assert PipelineOrchestrator._normalize_usage(None) is None  # noqa: SLF001

    def test_empty_dict_returns_none(self) -> None:
        """Return None for an empty dict (all zeros)."""
        assert PipelineOrchestrator._normalize_usage({}) is None  # noqa: SLF001

    def test_normalizes_framework_keys(self) -> None:
        """Translate framework key names to the app schema."""
        raw = {
            "input_token_count": 100,
            "output_token_count": 50,
            "total_token_count": 150,
        }
        expected = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        result = PipelineOrchestrator._normalize_usage(raw)  # noqa: SLF001
        assert result == expected

    def test_computes_total_when_missing(self) -> None:
        """Derive total_tokens from input + output when not provided."""
        raw = {"input_token_count": 80, "output_token_count": 20}
        result = PipelineOrchestrator._normalize_usage(raw)  # noqa: SLF001
        assert result is not None
        expected_total = 100
        assert result["total_tokens"] == expected_total


class TestHandleLinkChangeUsage:
    """Verify handle_link_change persists token usage on the orchestrator run."""

    async def test_usage_persisted_on_success(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
        make_link: Callable[..., Link],
    ) -> None:
        """Orchestrator run stores normalized usage from the LLM response."""
        links, _editions, _feedback, runs = mock_repos
        link = make_link(id="l-1", status="submitted")
        links.get.return_value = link

        response = MagicMock()
        response.text = "done"
        response.usage_details = {
            "input_token_count": 200,
            "output_token_count": 80,
            "total_token_count": 280,
        }
        orchestrator._agent.run = AsyncMock(return_value=response)  # noqa: SLF001

        await orchestrator.handle_link_change(
            {"id": "l-1", "edition_id": "ed-1", "status": "submitted"}
        )

        saved_run = runs.update.call_args[0][0]
        assert saved_run.usage is not None
        expected = {"input_tokens": 200, "output_tokens": 80, "total_tokens": 280}
        assert saved_run.usage == expected

    async def test_usage_none_when_response_has_no_details(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
        make_link: Callable[..., Link],
    ) -> None:
        """Usage stays None when the LLM response has no usage_details."""
        links, _editions, _feedback, runs = mock_repos
        link = make_link(id="l-2", status="submitted")
        links.get.return_value = link

        response = MagicMock()
        response.text = "done"
        response.usage_details = None
        orchestrator._agent.run = AsyncMock(return_value=response)  # noqa: SLF001

        await orchestrator.handle_link_change(
            {"id": "l-2", "edition_id": "ed-1", "status": "submitted"}
        )

        saved_run = runs.update.call_args[0][0]
        assert saved_run.usage is None


class TestRecordStageCompleteUsage:
    """Verify record_stage_complete persists token usage when provided."""

    async def test_usage_set_when_tokens_provided(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
        make_agent_run: Callable[..., AgentRun],
    ) -> None:
        """Stage run stores usage dict when token counts are non-zero."""
        links, _editions, _feedback, runs = mock_repos
        run = make_agent_run(id="run-1", trigger_id="l-1")
        runs.get.return_value = run
        links.get.return_value = None

        result = json.loads(
            await orchestrator.record_stage_complete(
                run_id="run-1",
                trigger_id="l-1",
                status="completed",
                input_tokens=500,
                output_tokens=120,
                total_tokens=620,
            )
        )

        assert result["status"] == "completed"
        expected = {"input_tokens": 500, "output_tokens": 120, "total_tokens": 620}
        assert run.usage == expected

    async def test_usage_none_when_no_tokens_provided(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
        make_agent_run: Callable[..., AgentRun],
    ) -> None:
        """Stage run leaves usage as None when no tokens are passed."""
        links, _editions, _feedback, runs = mock_repos
        run = make_agent_run(id="run-2", trigger_id="l-1")
        runs.get.return_value = run
        links.get.return_value = None

        await orchestrator.record_stage_complete(
            run_id="run-2",
            trigger_id="l-1",
            status="completed",
        )

        assert run.usage is None

    async def test_total_tokens_computed_when_omitted(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
        make_agent_run: Callable[..., AgentRun],
    ) -> None:
        """Total tokens is computed from input + output when not provided."""
        links, _editions, _feedback, runs = mock_repos
        run = make_agent_run(id="run-3", trigger_id="l-1")
        runs.get.return_value = run
        links.get.return_value = None

        await orchestrator.record_stage_complete(
            run_id="run-3",
            trigger_id="l-1",
            status="completed",
            input_tokens=300,
            output_tokens=100,
        )

        assert run.usage is not None
        expected_total = 400
        assert run.usage["total_tokens"] == expected_total
