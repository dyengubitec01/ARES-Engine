"""Integration Layer - External Service Clients."""

from app.clients.rag_client import (
    Document,
    MockRAGClient,
    RAGClient,
    RAGClientProtocol,
    format_documents_for_context,
    format_documents_to_sources,
    get_rag_client,
)
from app.clients.tool_client import (
    MockToolClient,
    ToolClient,
    ToolClientProtocol,
    ToolDefinition,
    ToolResult,
    get_tool_client,
)

__all__ = [
    # RAG Client
    "Document",
    "MockRAGClient",
    "RAGClient",
    "RAGClientProtocol",
    "format_documents_for_context",
    "format_documents_to_sources",
    "get_rag_client",
    # Tool Client
    "MockToolClient",
    "ToolClient",
    "ToolClientProtocol",
    "ToolDefinition",
    "ToolResult",
    "get_tool_client",
]
