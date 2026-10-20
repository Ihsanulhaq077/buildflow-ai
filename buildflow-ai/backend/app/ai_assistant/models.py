"""
AI Assistant models: chat sessions, messages, and tool calls.

Models:
- ChatSession: a conversation thread
- ChatMessage: a single message in a session
- ToolCall: record of a tool invocation during chat
- ToolResult: result of a tool call
"""
import json
import uuid
from datetime import datetime
from typing import Optional, Any, Dict, List

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, BaseMixin


class MessageRole(str, Enum):
    """Role of a message in the conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ToolStatus(str, Enum):
    """Status of a tool call."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class ChatSession(BaseMixin, Base):
    """
    A conversation session between a user and the AI assistant.

    Sessions are organization-scoped and can have optional context
    (e.g., project_id for project-specific conversations).
    """
    __tablename__ = "chat_sessions"
    __table_args__ = ({"comment": "AI Assistant chat sessions"},)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), default="New Chat")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)  # Additional context (project, filters, etc.)

    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )

    def __repr__(self) -> str:
        return f"<ChatSession {self.title} (org={self.organization_id})>"


class ChatMessage(BaseMixin, Base):
    """
    A single message in a chat session.

    Messages can be from user, assistant, system, or tool results.
    Tool calls and their results are stored as separate messages.
    """
    __tablename__ = "chat_messages"
    __table_args__ = ({"comment": "Chat messages in a session"},)

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), default=MessageRole.USER)
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)  # Tool calls made by assistant
    tool_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # For tool result messages
    message_metadata: Mapped[dict] = mapped_column(JSON, default=dict)  # Extra info (model, tokens, etc.)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage role={self.role} session={self.session_id}>"


class ToolCall(BaseMixin, Base):
    """
    Record of a tool invocation by the AI assistant.

    Links to the message that initiated it and stores the result.
    """
    __tablename__ = "tool_calls"
    __table_args__ = ({"comment": "AI Assistant tool invocations"},)

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(100))
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ToolStatus.PENDING)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<ToolCall {self.tool_name} ({self.status})>"