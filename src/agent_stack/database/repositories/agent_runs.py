"""Repository for the agent_runs container (partitioned by /trigger_id)."""

from __future__ import annotations

from agent_stack.database.repositories.base import BaseRepository
from agent_stack.models.agent_run import AgentRun, AgentStage


class AgentRunRepository(BaseRepository[AgentRun]):
    container_name = "agent_runs"
    model_class = AgentRun

    async def get_by_trigger(self, trigger_id: str) -> list[AgentRun]:
        """Fetch all runs triggered by a specific document."""
        return await self.query(
            "SELECT * FROM c WHERE c.trigger_id = @trigger_id AND NOT IS_DEFINED(c.deleted_at)",
            [{"name": "@trigger_id", "value": trigger_id}],
        )

    async def get_by_stage(self, trigger_id: str, stage: AgentStage) -> list[AgentRun]:
        """Fetch runs for a specific stage and trigger."""
        return await self.query(
            "SELECT * FROM c WHERE c.trigger_id = @trigger_id AND c.stage = @stage AND NOT IS_DEFINED(c.deleted_at)",
            [
                {"name": "@trigger_id", "value": trigger_id},
                {"name": "@stage", "value": stage.value},
            ],
        )
