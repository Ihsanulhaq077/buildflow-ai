"""
AI Assistant API routes.

Endpoints:
- POST /ai/chat              - Send a chat message
- GET  /ai/sessions          - List chat sessions
- POST /ai/sessions          - Create a new chat session
- GET  /ai/sessions/{id}     - Get session details
- GET  /ai/sessions/{id}/messages - Get session messages
- DELETE /ai/sessions/{id}   - Delete a session
- POST /ai/tools/execute     - Execute a tool call
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_assistant.models import ChatMessage, ChatSession
from app.ai_assistant.schemas import (
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ChatSessionCreate,
    ChatSessionOut,
    ToolCallRequest,
    ToolCallResponse,
)
from app.ai_assistant.service import AIService
from app.db import get_db
from app.deps import get_current_user, require_permission
from app.models import User

log = logging.getLogger("buildflow.ai_assistant.routes")
router = APIRouter(tags=["ai-assistant"])

PERM_READ = require_permission("ai_assistant.read")
PERM_WRITE = require_permission("ai_assistant.write")


@router.post("/ai/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: ChatSessionCreate,
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Create a new chat session."""
    ai_service = AIService(db, user)
    session = ai_service.create_session(
        title=body.title,
        project_id=str(body.project_id) if body.project_id else None,
        context=body.initial_context,
    )
    return session


@router.get("/ai/sessions", response_model=List[ChatSessionOut])
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(PERM_READ),
    db: Session = Depends(get_db),
):
    """List chat sessions for the organization."""
    ai_service = AIService(db, user)
    sessions = ai_service.list_sessions(limit=limit, offset=offset)
    return sessions


@router.get("/ai/sessions/{session_id}", response_model=ChatSessionOut)
async def get_session(
    session_id: UUID,
    user: User = Depends(PERM_READ),
    db: Session = Depends(get_db),
):
    """Get a chat session by ID."""
    ai_service = AIService(db, user)
    session = ai_service.get_session(str(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/ai/sessions/{session_id}/messages", response_model=List[ChatMessageOut])
async def get_messages(
    session_id: UUID,
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(PERM_READ),
    db: Session = Depends(get_db),
):
    """Get messages for a chat session."""
    ai_service = AIService(db, user)
    session = ai_service.get_session(str(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get messages with pagination
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    messages = db.scalars(stmt).all()
    return messages


@router.delete("/ai/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Delete a chat session."""
    ai_service = AIService(db, user)
    deleted = ai_service.delete_session(str(session_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/ai/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Send a chat message and get a response."""
    ai_service = AIService(db, user)
    session = ai_service.get_session(str(body.session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Process the message
    response_msg = ai_service.chat(str(body.session_id), body.message)

    return ChatResponse(
        message=response_msg,
        tool_calls=None,
        session_id=body.session_id,
    )


@router.post("/ai/tools/execute", response_model=ToolCallResponse)
async def execute_tool(
    body: ToolCallRequest,
    user: User = Depends(PERM_WRITE),
    db: Session = Depends(get_db),
):
    """Execute a tool call."""
    ai_service = AIService(db, user)
    result = ai_service.execute_tool(body.tool_name, body.arguments)
    return ToolCallResponse(
        tool_name=body.tool_name,
        result=result.get("result", {}),
        error=result.get("error"),
    )


