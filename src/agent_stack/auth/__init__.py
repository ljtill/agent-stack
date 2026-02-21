"""Authentication module — Microsoft Entra ID via MSAL."""

from agent_stack.auth.middleware import require_auth
from agent_stack.auth.msal_auth import MSALAuth

__all__ = ["MSALAuth", "require_auth"]
