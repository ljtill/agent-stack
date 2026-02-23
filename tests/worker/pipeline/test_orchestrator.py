"""Tests for orchestrator token-usage persistence and pipeline logic."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from curate_common.models.link import LinkStatus
from curate_worker.pipeline.orchestrator import PipelineOrchestrator
from curate_worker.pipeline.runs import RunManager

if TYPE_CHECKING:
    from collections.abc import Callable

    from curate_common.models.agent_run import AgentRun
    from curate_common.models.link import Link


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
        patch("curate_worker.pipeline.orchestrator.Agent"),
        patch("curate_worker.pipeline.orchestrator.FetchAgent"),
        patch("curate_worker.pipeline.orchestrator.ReviewAgent"),
        patch("curate_worker.pipeline.orchestrator.DraftAgent"),
        patch("curate_worker.pipeline.orchestrator.EditAgent"),
        patch("curate_worker.pipeline.orchestrator.PublishAgent"),
        patch("curate_worker.pipeline.orchestrator.load_prompt", return_value=""),
    ):
        mock_publisher = MagicMock()
        mock_publisher.publish = AsyncMock()
        orch = PipelineOrchestrator(
            client,
            links,
            editions,
            feedback,
            runs,
            event_publisher=mock_publisher,
        )
        orch._runs = MagicMock()  # noqa: SLF001
        orch._runs.create_orchestrator_run = AsyncMock()  # noqa: SLF001
        orch._runs.publish_run_event = AsyncMock()  # noqa: SLF001
        return orch


_START_EVENT_KEYS = {"id", "stage", "trigger_id", "edition_id", "status", "started_at"}


class TestNormalizeUsage:
    """Tests for RunManager.normalize_usage static helper."""

    def test_none_returns_none(self) -> None:
        """Return None when input is None."""
        assert RunManager.normalize_usage(None) is None

    def test_empty_dict_returns_none(self) -> None:
        """Return None for an empty dict (all zeros)."""
        assert RunManager.normalize_usage({}) is None

    def test_normalizes_framework_keys(self) -> None:
        """Translate framework key names to the app schema."""
        raw = {
            "input_token_count": 100,
            "output_token_count": 50,
            "total_token_count": 150,
        }
        expected = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        result = RunManager.normalize_usage(raw)
        assert result == expected

    def test_computes_total_when_missing(self) -> None:
        """Derive total_tokens from input + output when not provided."""
        raw = {"input_token_count": 80, "output_token_count": 20}
        result = RunManager.normalize_usage(raw)
        assert result is not None
        expected_total = 100
        assert result["total_tokens"] == expected_total


class TestStartEventPayloads:
    """Verify start-event payload schema for all emitters."""

    async def test_run_manager_includes_edition_id(self) -> None:
        """RunManager start events include edition_id and the shared schema."""
        runs_repo = AsyncMock()
        events = MagicMock()
        events.publish = AsyncMock()
        manager = RunManager(runs_repo, events)

        run = await manager.create_orchestrator_run(
            "ed-1", "l-1", {"status": "submitted"}
        )

        event_name, payload = events.publish.call_args.args
        assert event_name == "agent-run-start"
        assert set(payload) == _START_EVENT_KEYS
        assert payload["id"] == run.id
        assert payload["stage"] == run.stage
        assert payload["trigger_id"] == run.trigger_id
        assert payload["edition_id"] == run.edition_id
        assert payload["status"] == run.status

    async def test_record_stage_start_emits_same_schema(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
    ) -> None:
        """record_stage_start emits the same schema as RunManager start events."""
        _links, _editions, _feedback, runs = mock_repos

        await orchestrator.record_stage_start("fetch", "l-1", "ed-1")

        created_run = runs.create.call_args.args[0]
        event_name, payload = orchestrator._events.publish.call_args.args  # noqa: SLF001
        assert event_name == "agent-run-start"
        assert set(payload) == _START_EVENT_KEYS
        assert payload["id"] == created_run.id
        assert payload["stage"] == created_run.stage
        assert payload["trigger_id"] == created_run.trigger_id
        assert payload["edition_id"] == created_run.edition_id
        assert payload["status"] == created_run.status


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
        links.claim_submitted.return_value = link
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
        links.claim_submitted.return_value = link
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
                edition_id="ed-1",
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
            edition_id="ed-1",
            status="completed",
        )

        assert run.usage is None

    async def test_usage_auto_populated_from_last_stage(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
        make_agent_run: Callable[..., AgentRun],
    ) -> None:
        """Usage is auto-populated from sub-agent when no explicit tokens passed."""
        links, _editions, _feedback, runs = mock_repos
        run = make_agent_run(id="run-auto", trigger_id="l-1")
        runs.get.return_value = run
        links.get.return_value = None

        orchestrator._last_stage_usage = {  # noqa: SLF001
            "input_tokens": 150,
            "output_tokens": 60,
            "total_tokens": 210,
        }

        await orchestrator.record_stage_complete(
            run_id="run-auto",
            trigger_id="l-1",
            edition_id="ed-1",
            status="completed",
        )

        expected = {"input_tokens": 150, "output_tokens": 60, "total_tokens": 210}
        assert run.usage == expected
        assert orchestrator._last_stage_usage is None  # noqa: SLF001

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
            edition_id="ed-1",
            status="completed",
            input_tokens=300,
            output_tokens=100,
        )

        assert run.usage is not None
        expected_total = 400
        assert run.usage["total_tokens"] == expected_total


class TestClaimLink:
    """Tests for _claim_link guard logic."""

    async def test_returns_none_when_status_not_submitted(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
    ) -> None:
        """Return None when the event status is not SUBMITTED."""
        links, *_ = mock_repos

        result = await orchestrator._claim_link("l-1", "reviewed")  # noqa: SLF001
        assert result is None
        links.claim_submitted.assert_not_called()

    async def test_returns_none_when_claim_rejected(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
    ) -> None:
        """Return None when the repository claim path rejects the link."""
        links, *_ = mock_repos
        links.claim_submitted.return_value = None

        result = await orchestrator._claim_link("l-1", "submitted")  # noqa: SLF001
        assert result is None

    async def test_returns_claimed_link(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
        make_link: Callable[..., Link],
    ) -> None:
        """Return the claimed link when durable claim succeeds."""
        links, *_ = mock_repos
        claimed_link = make_link(id="l-1", status=LinkStatus.SUBMITTED)
        links.claim_submitted.return_value = claimed_link

        result = await orchestrator._claim_link("l-1", "submitted")  # noqa: SLF001
        assert result == claimed_link


class TestHandleLinkChangeRetry:
    """Tests for handle_link_change retry logic."""

    async def test_retries_on_failure_succeeds_on_second_attempt(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
        make_link: Callable[..., Link],
    ) -> None:
        """Verify retry succeeds on second attempt after first failure."""
        links, _editions, _feedback, runs = mock_repos
        link = make_link(id="l-retry", status="submitted")
        links.claim_submitted.return_value = link
        links.get.return_value = link

        response = MagicMock()
        response.text = "ok"
        response.usage_details = None
        orchestrator._agent.run = AsyncMock(  # noqa: SLF001
            side_effect=[RuntimeError("transient"), response],
        )

        sleep_patch = "curate_worker.pipeline.orchestrator.asyncio.sleep"
        with patch(sleep_patch, new_callable=AsyncMock):
            await orchestrator.handle_link_change(
                {"id": "l-retry", "edition_id": "ed-1", "status": "submitted"}
            )

        saved_run = runs.update.call_args[0][0]
        assert saved_run.status == "completed"

    async def test_marks_failed_after_max_retries(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
        make_link: Callable[..., Link],
    ) -> None:
        """Verify the run is marked FAILED after all retries are exhausted."""
        links, _editions, _feedback, runs = mock_repos
        link = make_link(id="l-fail", status="submitted")
        links.claim_submitted.return_value = link
        links.get.return_value = link

        orchestrator._agent.run = AsyncMock(  # noqa: SLF001
            side_effect=RuntimeError("persistent error"),
        )

        sleep_patch = "curate_worker.pipeline.orchestrator.asyncio.sleep"
        with patch(sleep_patch, new_callable=AsyncMock):
            await orchestrator.handle_link_change(
                {"id": "l-fail", "edition_id": "ed-1", "status": "submitted"}
            )

        saved_run = runs.update.call_args[0][0]
        assert saved_run.status == "failed"


class TestGetEditionLock:
    """Tests for _get_edition_lock."""

    async def test_returns_same_lock_for_same_edition(
        self,
        orchestrator: PipelineOrchestrator,
    ) -> None:
        """The same lock object is returned for the same edition_id."""
        lock1 = await orchestrator._get_edition_lock("ed-1")  # noqa: SLF001
        lock2 = await orchestrator._get_edition_lock("ed-1")  # noqa: SLF001
        assert lock1 is lock2


class TestHandleFeedbackChangeLock:
    """Tests for handle_feedback_change edition lock serialization."""

    async def test_serializes_concurrent_feedback(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
    ) -> None:
        """Concurrent calls for the same edition are serialized by the lock."""
        *_, _runs = mock_repos
        order: list[str] = []

        async def _slow_run(_msg: str, **_kwargs: object) -> MagicMock:
            order.append("start")
            await asyncio.sleep(0.05)
            order.append("end")
            resp = MagicMock()
            resp.text = "done"
            resp.usage_details = None
            return resp

        orchestrator._agent.run = AsyncMock(side_effect=_slow_run)  # noqa: SLF001

        await asyncio.gather(
            orchestrator.handle_feedback_change(
                {"id": "fb-1", "edition_id": "ed-1", "resolved": False}
            ),
            orchestrator.handle_feedback_change(
                {"id": "fb-2", "edition_id": "ed-1", "resolved": False}
            ),
        )

        assert order == ["start", "end", "start", "end"]


class TestHandlePublishFailure:
    """Tests for handle_publish error handling."""

    async def test_records_run_and_handles_failure(
        self,
        orchestrator: PipelineOrchestrator,
        mock_repos: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
    ) -> None:
        """Verify handle_publish records the run and sets FAILED on error."""
        _links, _editions, _feedback, runs = mock_repos
        orchestrator._agent.run = AsyncMock(  # noqa: SLF001
            side_effect=RuntimeError("publish boom"),
        )

        await orchestrator.handle_publish("ed-1")

        saved_run = runs.update.call_args[0][0]
        assert saved_run.status == "failed"
        assert saved_run.output == {"error": "Orchestrator failed"}


class TestSubAgentUsageCapture:
    """Verify custom tool wrappers capture sub-agent token usage."""

    async def test_fetch_tool_captures_usage(
        self,
        orchestrator: PipelineOrchestrator,
    ) -> None:
        """The _fetch_tool wrapper captures usage from the sub-agent response."""
        response = MagicMock()
        response.text = "fetched content"
        response.usage_details = {
            "input_token_count": 100,
            "output_token_count": 40,
            "total_token_count": 140,
        }
        orchestrator.fetch.agent.run = AsyncMock(return_value=response)

        result = await orchestrator._fetch_tool(task="fetch this url")  # noqa: SLF001

        assert result == "fetched content"
        expected = {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140}
        assert orchestrator._last_stage_usage == expected  # noqa: SLF001

    async def test_review_tool_captures_usage(
        self,
        orchestrator: PipelineOrchestrator,
    ) -> None:
        """The _review_tool wrapper captures usage from the sub-agent response."""
        response = MagicMock()
        response.text = "reviewed"
        response.usage_details = {
            "input_token_count": 200,
            "output_token_count": 80,
            "total_token_count": 280,
        }
        orchestrator.review.agent.run = AsyncMock(return_value=response)

        result = await orchestrator._review_tool(task="review this")  # noqa: SLF001

        assert result == "reviewed"
        expected = {"input_tokens": 200, "output_tokens": 80, "total_tokens": 280}
        assert orchestrator._last_stage_usage == expected  # noqa: SLF001

    async def test_draft_tool_uses_guardrailed_api(
        self,
        orchestrator: PipelineOrchestrator,
    ) -> None:
        """The _draft_tool wrapper delegates to DraftAgent's public guardrail API."""
        response = MagicMock()
        response.text = "drafted"
        response.usage_details = {
            "input_token_count": 120,
            "output_token_count": 30,
            "total_token_count": 150,
        }
        orchestrator.draft.run_guardrailed = AsyncMock(return_value=response)

        result = await orchestrator._draft_tool(task="draft this")  # noqa: SLF001

        assert result == "drafted"
        expected = {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}
        assert orchestrator._last_stage_usage == expected  # noqa: SLF001
        orchestrator.draft.run_guardrailed.assert_called_once_with("draft this")
        orchestrator.draft.agent.run.assert_not_called()

    async def test_tool_sets_none_when_no_usage(
        self,
        orchestrator: PipelineOrchestrator,
    ) -> None:
        """Usage is None when the sub-agent response has no usage_details."""
        response = MagicMock()
        response.text = "done"
        response.usage_details = None
        orchestrator.fetch.agent.run = AsyncMock(return_value=response)

        await orchestrator._fetch_tool(task="fetch this")  # noqa: SLF001

        assert orchestrator._last_stage_usage is None  # noqa: SLF001
