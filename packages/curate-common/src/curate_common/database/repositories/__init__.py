"""Repository modules for each Cosmos DB container."""

from curate_common.database.repositories.agent_runs import AgentRunRepository
from curate_common.database.repositories.editions import EditionRepository
from curate_common.database.repositories.feedback import FeedbackRepository
from curate_common.database.repositories.links import LinkRepository
from curate_common.database.repositories.revisions import RevisionRepository

__all__ = [
    "AgentRunRepository",
    "EditionRepository",
    "FeedbackRepository",
    "LinkRepository",
    "RevisionRepository",
]
