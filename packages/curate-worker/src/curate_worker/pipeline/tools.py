"""Orchestrator tool definitions (mixed into PipelineOrchestrator)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from agent_framework import tool

from curate_common.models.agent_run import AgentRun, AgentRunStatus, AgentStage
from curate_worker.pipeline.rendering import render_link_row
from curate_worker.pipeline.runs import RunManager

if TYPE_CHECKING:
    from curate_common.database.repositories.agent_runs import AgentRunRepository
    from curate_common.database.repositories.editions import EditionRepository
    from curate_common.database.repositories.links import LinkRepository
    from curate_common.events import EventPublisher
    from curate_worker.agents.draft import DraftAgent
    from curate_worker.agents.edit import EditAgent
    from curate_worker.agents.fetch import FetchAgent
    from curate_worker.agents.publish import PublishAgent
    from curate_worker.agents.review import ReviewAgent

logger = logging.getLogger(__name__)


class OrchestratorToolsMixin:
    """Mixin providing @tool-decorated methods for the orchestrator agent."""

    _links_repo: LinkRepository
    _editions_repo: EditionRepository
    _agent_runs_repo: AgentRunRepository
    _events: EventPublisher
    _last_stage_usage: dict | None

    fetch: FetchAgent
    review: ReviewAgent
    draft: DraftAgent
    edit: EditAgent
    publish: PublishAgent

    def _capture_usage(self, response: object) -> str:
        """Extract token usage from a sub-agent response and return its text."""
        usage_details = getattr(response, "usage_details", None) if response else None
        self._last_stage_usage = RunManager.normalize_usage(
            dict(usage_details) if usage_details else None
        )
        text = getattr(response, "text", None)
        return text or ""

    @tool(name="fetch")
    async def _fetch_tool(
        self,
        task: Annotated[str, "Instructions including the URL, link ID, and edition ID"],
    ) -> str:
        """Fetch and extract content from a submitted URL."""
        response = await self.fetch.agent.run(task)
        return self._capture_usage(response)

    @tool(name="review")
    async def _review_tool(
        self,
        task: Annotated[str, "Instructions including the link ID and edition ID"],
    ) -> str:
        """Evaluate relevance, extract insights, categorize content."""
        response = await self.review.agent.run(task)
        return self._capture_usage(response)

    @tool(name="draft")
    async def _draft_tool(
        self,
        task: Annotated[str, "Instructions including the link ID and edition ID"],
    ) -> str:
        """Compose newsletter content from reviewed material."""
        self.draft._draft_saved = False  # noqa: SLF001
        session = self.draft.agent.create_session()
        response = await self.draft.agent.run(task, session=session)
        if not self.draft._draft_saved:  # noqa: SLF001
            logger.warning("Draft agent did not call save_draft — retrying")
            response = await self.draft.agent.run(
                "You must call the save_draft tool now with the full edition "
                "content JSON to persist your work. Content in your text "
                "response is NOT saved to the database.",
                session=session,
            )
        return self._capture_usage(response)

    @tool(name="edit")
    async def _edit_tool(
        self,
        task: Annotated[str, "Instructions including the edition ID"],
    ) -> str:
        """Refine edition content and address editor feedback."""
        response = await self.edit.agent.run(task)
        return self._capture_usage(response)

    @tool(name="publish")
    async def _publish_tool(
        self,
        task: Annotated[str, "Instructions including the edition ID"],
    ) -> str:
        """Render HTML and upload to storage."""
        response = await self.publish.agent.run(task)
        return self._capture_usage(response)

    @tool
    async def get_link_status(
        self,
        link_id: Annotated[str, "The link document ID"],
        edition_id: Annotated[str, "The edition partition key"],  # noqa: ARG002
    ) -> str:
        """Get the current status and metadata of a link."""
        link = await self._links_repo.get(link_id, link_id)
        if not link:
            return json.dumps({"error": "Link not found"})
        return json.dumps(
            {
                "id": link.id,
                "url": link.url,
                "title": link.title,
                "status": link.status,
                "has_content": link.content is not None,
                "has_review": link.review is not None,
                "edition_id": link.edition_id,
            }
        )

    @tool
    async def get_edition_status(
        self,
        edition_id: Annotated[str, "The edition document ID"],
    ) -> str:
        """Get the current status of an edition."""
        edition = await self._editions_repo.get(edition_id, edition_id)
        if not edition:
            return json.dumps({"error": "Edition not found"})
        return json.dumps(
            {
                "id": edition.id,
                "status": edition.status,
                "link_count": len(edition.link_ids),
                "has_content": bool(edition.content),
            }
        )

    @tool
    async def record_stage_start(
        self,
        stage: Annotated[str, "Pipeline stage: fetch, review, draft, edit, or publish"],
        trigger_id: Annotated[str, "ID of the document that triggered this run"],
        edition_id: Annotated[str, "ID of the edition this run belongs to"],
    ) -> str:
        """Record the start of a pipeline stage. Call before invoking a sub-agent."""
        run = AgentRun(
            stage=AgentStage(stage),
            edition_id=edition_id,
            trigger_id=trigger_id,
            input={"stage": stage},
            started_at=datetime.now(UTC),
        )
        await self._agent_runs_repo.create(run)
        await self._events.publish(
            "agent-run-start",
            {
                "id": run.id,
                "stage": run.stage,
                "trigger_id": run.trigger_id,
                "edition_id": run.edition_id,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
            },
        )
        return json.dumps({"run_id": run.id, "stage": stage, "status": "running"})

    @tool
    async def record_stage_complete(
        self,
        run_id: Annotated[str, "The run ID returned by record_stage_start"],
        trigger_id: Annotated[str, "ID of the document that triggered this run"],
        edition_id: Annotated[str, "ID of the edition this run belongs to"],
        status: Annotated[str, "Completion status: completed or failed"],
        error: Annotated[str, "Error message if failed, empty if completed"] = "",
        input_tokens: Annotated[int, "Input tokens consumed by this stage"] = 0,
        output_tokens: Annotated[int, "Output tokens consumed by this stage"] = 0,
        total_tokens: Annotated[int, "Total tokens consumed by this stage"] = 0,
    ) -> str:
        """Record the completion of a pipeline stage."""
        run = await self._agent_runs_repo.get(run_id, edition_id)
        if not run:
            return json.dumps({"error": "Run not found"})
        run.status = (
            AgentRunStatus.COMPLETED if status == "completed" else AgentRunStatus.FAILED
        )
        run.completed_at = datetime.now(UTC)
        if error:
            run.output = {"error": error}
        if input_tokens or output_tokens or total_tokens:
            run.usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens or input_tokens + output_tokens,
            }
        elif self._last_stage_usage:
            run.usage = self._last_stage_usage
        self._last_stage_usage = None
        await self._agent_runs_repo.update(run, edition_id)
        await self._events.publish(
            "agent-run-complete",
            {
                "id": run.id,
                "stage": run.stage,
                "trigger_id": run.trigger_id,
                "edition_id": run.edition_id,
                "status": run.status,
                "output": run.output,
                "usage": run.usage,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat()
                if run.completed_at
                else None,
            },
        )

        link = await self._links_repo.get(trigger_id, trigger_id)
        if link:
            runs = await self._agent_runs_repo.get_by_trigger(trigger_id)
            await self._events.publish("link-update", render_link_row(link, runs))

        return json.dumps(
            {
                "run_id": run_id,
                "status": status,
                "completed": True,
            }
        )
