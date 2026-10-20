"""Pydantic schemas for AI Assistant module."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    """Request to create a new chat session."""
    title: Optional[str] = "New Chat"
    project_id: Optional[UUID] = None
    initial_context: Optional[dict] = None


class ChatSessionOut(BaseModel):
    """Chat session response."""
    id: UUID
    organization_id: UUID
    user_id: UUID
    title: str
    project_id: Optional[UUID]
    context: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageBase(BaseModel):
    """Base chat message schema."""
    session_id: UUID
    role: str
    content: str
    tool_calls: Optional[List[dict]] = None
    tool_call_id: Optional[str] = None


class ChatMessageCreate(ChatMessageBase):
    """Message creation schema."""
    pass


class ChatMessageOut(ChatMessageBase):
    """Chat message response."""
    id: UUID
    metadata: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    session_id: UUID
    message: str


class ChatResponse(BaseModel):
    """Response to a chat message."""
    message: ChatMessageOut
    tool_calls: Optional[List[dict]] = None
    session_id: UUID


class ChatSearch(BaseModel):
    """Search chat messages."""
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[UUID] = None
    organization_id: UUID


class ToolCallRequest(BaseModel):
    """Execute a tool call."""
    tool_name: str
    arguments: dict
    session_id: UUID


class ToolCallResponse(BaseModel):
    """Result of a tool call."""
    tool_name: str
    result: dict
    error: Optional[str] = None