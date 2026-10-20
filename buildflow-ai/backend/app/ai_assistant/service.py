"""
AI Assistant service.

Provides:
- Chat session management
- Tool calling (RAG search, project info, etc.)
- Permission-aware responses
- Conversation history management
"""
import logging
import time
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import org_scoped
from app.models import User
from app.ai_assistant.models import ChatMessage, ChatSession, ToolCall, MessageRole

log = logging.getLogger("buildflow.ai_assistant")

# Maximum conversation history length
MAX_HISTORY = 50


class ToolExecutor:
    """Execute tools for the AI assistant."""

    # Available tools
    AVAILABLE_TOOLS = [
        "rag.search",
        "project.get",
        "project.list",
        "boq.get",
        "boq.list",
        "budget.get",
        "budget.list",
        "procurement.get",
        "procurement.list",
        "inventory.get",
        "inventory.list",
        "labour.get",
        "labour.list",
        "dailylog.get",
        "dailylog.list",
        "document.list",
        "document.get",
    ]

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.org_id = user.organization_id

    def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool call."""
        if tool_name not in self.AVAILABLE_TOOLS:
            return {"error": f"Unknown tool: {tool_name}"}

        start_time = time.time()

        try:
            if tool_name == "rag.search":
                return self._rag_search(arguments)
            elif tool_name == "project.get":
                return self._project_get(arguments)
            elif tool_name == "project.list":
                return self._project_list(arguments)
            elif tool_name == "boq.get":
                return self._boq_get(arguments)
            elif tool_name == "boq.list":
                return self._boq_list(arguments)
            elif tool_name == "budget.get":
                return self._budget_get(arguments)
            elif tool_name == "budget.list":
                return self._budget_list(arguments)
            elif tool_name == "procurement.get":
                return self._procurement_get(arguments)
            elif tool_name == "procurement.list":
                return self._procurement_list(arguments)
            elif tool_name == "inventory.get":
                return self._inventory_get(arguments)
            elif tool_name == "inventory.list":
                return self._inventory_list(arguments)
            elif tool_name == "labour.get":
                return self._labour_get(arguments)
            elif tool_name == "labour.list":
                return self._labour_list(arguments)
            elif tool_name == "dailylog.get":
                return self._dailylog_get(arguments)
            elif tool_name == "dailylog.list":
                return self._dailylog_list(arguments)
            elif tool_name == "document.list":
                return self._document_list(arguments)
            elif tool_name == "document.get":
                return self._document_get(arguments)
            else:
                return {"error": f"Tool not implemented: {tool_name}"}
        except Exception as e:
            log.error(f"Tool {tool_name} failed: {e}")
            return {"error": str(e)}
        finally:
            duration = int((time.time() - start_time) * 1000)
            log.info(f"Tool {tool_name} executed in {duration}ms")

    def _rag_search(self, args: dict) -> dict:
        """Search documents using RAG."""
        from app.rag.service import RagService

        query = args.get("query", "")
        top_k = args.get("top_k", 5)
        threshold = args.get("similarity_threshold", 0.5)
        doc_ids = args.get("doc_ids")

        service = RagService(self.db, self.org_id)
        results = service.search(query, top_k=top_k, doc_ids=doc_ids, threshold=threshold)

        # Format results for the assistant
        formatted = []
        for r in results.get("results", []):
            chunk = r.get("chunk")
            formatted.append({
                "text": chunk.text if chunk else "",
                "score": r.get("score", 0),
                "distance": r.get("distance", 1),
                "doc_id": str(chunk.doc_id) if chunk else "",
            })

        return {"results": formatted, "query": query, "total_results": results.get("total_results", 0)}

    def _project_get(self, args: dict) -> dict:
        """Get a project by ID."""
        from app.projects.models import Project

        project_id = args.get("project_id")
        if not project_id:
            return {"error": "project_id required"}

        stmt = select(Project).where(
            Project.id == project_id,
            Project.organization_id == self.org_id,
            Project.deleted_at.is_(None)
        )
        project = self.db.scalar(stmt)
        if not project:
            return {"error": "Project not found"}

        return {
            "id": str(project.id),
            "code": project.code,
            "name": project.name,
            "client_id": str(project.client_id) if project.client_id else None,
            "location": project.location,
            "status": project.status.value if project.status else None,
            "contract_value": float(project.contract_value) if project.contract_value else 0,
            "start_date": str(project.start_date) if project.start_date else None,
            "planned_end_date": str(project.planned_end_date) if project.planned_end_date else None,
        }

    def _project_list(self, args: dict) -> dict:
        """List projects."""
        from app.projects.models import Project

        status = args.get("status")
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)

        stmt = select(Project).where(
            Project.organization_id == self.org_id,
            Project.deleted_at.is_(None)
        )
        if status:
            stmt = stmt.where(Project.status == status)
        stmt = stmt.order_by(Project.created_at.desc()).limit(limit).offset(offset)
        projects = self.db.scalars(stmt).all()

        return [
            {
                "id": str(p.id),
                "code": p.code,
                "name": p.name,
                "status": p.status.value if p.status else None,
                "location": p.location,
                "contract_value": float(p.contract_value) if p.contract_value else 0,
            }
            for p in projects
        ]

    def _boq_get(self, args: dict) -> dict:
        """Get BOQ by ID."""
        from app.boq.models import BOQ

        boq_id = args.get("boq_id")
        if not boq_id:
            return {"error": "boq_id required"}

        stmt = select(BOQ).where(BOQ.id == boq_id)
        boq = self.db.scalar(stmt)
        if not boq:
            return {"error": "BOQ not found"}

        return {
            "id": str(boq.id),
            "project_id": str(boq.project_id),
            "name": boq.name,
            "status": boq.status.value if boq.status else None,
            "overhead_pct": float(boq.overhead_pct) if boq.overhead_pct else 0,
            "contingency_pct": float(boq.contingency_pct) if boq.contingency_pct else 0,
            "profit_pct": float(boq.profit_pct) if boq.profit_pct else 0,
        }

    def _boq_list(self, args: dict) -> dict:
        """List BOQs."""
        from app.boq.models import BOQ

        project_id = args.get("project_id")
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)

        stmt = select(BOQ).where(BOQ.organization_id == self.org_id)
        if project_id:
            stmt = stmt.where(BOQ.project_id == project_id)
        stmt = stmt.order_by(BOQ.created_at.desc()).limit(limit).offset(offset)
        boqs = self.db.scalars(stmt).all()

        return [
            {
                "id": str(b.id),
                "name": b.name,
                "project_id": str(b.project_id),
                "status": b.status.value if b.status else None,
            }
            for b in boqs
        ]

    def _budget_get(self, args: dict) -> dict:
        """Get budget by ID."""
        from app.budgets.models import Budget

        budget_id = args.get("budget_id")
        if not budget_id:
            return {"error": "budget_id required"}

        stmt = select(Budget).where(Budget.id == budget_id)
        budget = self.db.scalar(stmt)
        if not budget:
            return {"error": "Budget not found"}

        return {
            "id": str(budget.id),
            "project_id": str(budget.project_id),
            "boq_id": str(budget.boq_id),
            "name": budget.name,
            "status": budget.status.value if budget.status else None,
            "total": float(budget.total) if budget.total else 0,
            "selling_price": float(budget.selling_price) if budget.selling_price else 0,
        }

    def _budget_list(self, args: dict) -> dict:
        """List budgets."""
        from app.budgets.models import Budget

        project_id = args.get("project_id")
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)

        stmt = select(Budget).where(Budget.organization_id == self.org_id)
        if project_id:
            stmt = stmt.where(Budget.project_id == project_id)
        stmt = stmt.order_by(Budget.created_at.desc()).limit(limit).offset(offset)
        budgets = self.db.scalars(stmt).all()

        return [
            {
                "id": str(b.id),
                "name": b.name,
                "project_id": str(b.project_id),
                "status": b.status.value if b.status else None,
                "total": float(b.total) if b.total else 0,
            }
            for b in budgets
        ]

    def _procurement_get(self, args: dict) -> dict:
        """Get procurement requisition by ID."""
        from app.procurement.models import PurchaseRequisition

        req_id = args.get("requisition_id")
        if not req_id:
            return {"error": "requisition_id required"}

        stmt = select(PurchaseRequisition).where(
            PurchaseRequisition.id == req_id,
            PurchaseRequisition.organization_id == self.org_id
        )
        req = self.db.scalar(stmt)
        if not req:
            return {"error": "Requisition not found"}

        return {
            "id": str(req.id),
            "project_id": str(req.project_id),
            "requisition_no": req.requisition_no,
            "status": req.status.value if req.status else None,
            "total_amount": float(req.total_amount) if req.total_amount else 0,
        }

    def _procurement_list(self, args: dict) -> dict:
        """List procurement requisitions."""
        from app.procurement.models import PurchaseRequisition

        project_id = args.get("project_id")
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)

        stmt = select(PurchaseRequisition).where(
            PurchaseRequisition.organization_id == self.org_id
        )
        if project_id:
            stmt = stmt.where(PurchaseRequisition.project_id == project_id)
        stmt = stmt.order_by(PurchaseRequisition.created_at.desc()).limit(limit).offset(offset)
        reqs = self.db.scalars(stmt).all()

        return [
            {
                "id": str(r.id),
                "requisition_no": r.requisition_no,
                "project_id": str(r.project_id),
                "status": r.status.value if r.status else None,
                "total_amount": float(r.total_amount) if r.total_amount else 0,
            }
            for r in reqs
        ]

    def _inventory_get(self, args: dict) -> dict:
        """Get inventory item by ID."""
        from app.inventory.models import InventoryItem

        item_id = args.get("item_id")
        if not item_id:
            return {"error": "item_id required"}

        stmt = select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.organization_id == self.org_id
        )
        item = self.db.scalar(stmt)
        if not item:
            return {"error": "Inventory item not found"}

        return {
            "id": str(item.id),
            "name": item.name,
            "sku": item.sku,
            "unit": item.unit,
            "reorder_level": item.reorder_level if item.reorder_level else 0,
            "is_active": item.is_active,
        }

    def _inventory_list(self, args: dict) -> dict:
        """List inventory items."""
        from app.inventory.models import InventoryItem

        limit = args.get("limit", 100)
        offset = args.get("offset", 0)

        stmt = select(InventoryItem).where(
            InventoryItem.organization_id == self.org_id,
            InventoryItem.is_active == True
        )
        stmt = stmt.order_by(InventoryItem.name).limit(limit).offset(offset)
        items = self.db.scalars(stmt).all()

        return [
            {
                "id": str(i.id),
                "name": i.name,
                "sku": i.sku,
                "unit": i.unit,
                "reorder_level": i.reorder_level if i.reorder_level else 0,
            }
            for i in items
        ]

    def _labour_get(self, args: dict) -> dict:
        """Get labour attendance sheet by ID."""
        from app.labour.models import AttendanceSheet

        sheet_id = args.get("sheet_id")
        if not sheet_id:
            return {"error": "sheet_id required"}

        stmt = select(AttendanceSheet).where(AttendanceSheet.id == sheet_id)
        sheet = self.db.scalar(stmt)
        if not sheet:
            return {"error": "Attendance sheet not found"}

        return {
            "id": str(sheet.id),
            "project_id": str(sheet.project_id),
            "sheet_date": str(sheet.sheet_date),
            "status": sheet.status.value if sheet.status else None,
            "total_entries": len(sheet.entries) if hasattr(sheet, 'entries') else 0,
        }

    def _labour_list(self, args: dict) -> dict:
        """List labour attendance sheets."""
        from app.labour.models import AttendanceSheet

        project_id = args.get("project_id")
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)

        stmt = select(AttendanceSheet).where(
            AttendanceSheet.organization_id == self.org_id
        )
        if project_id:
            stmt = stmt.where(AttendanceSheet.project_id == project_id)
        stmt = stmt.order_by(AttendanceSheet.sheet_date.desc()).limit(limit).offset(offset)
        sheets = self.db.scalars(stmt).all()

        return [
            {
                "id": str(s.id),
                "sheet_date": str(s.sheet_date),
                "project_id": str(s.project_id),
                "status": s.status.value if s.status else None,
            }
            for s in sheets
        ]

    def _dailylog_get(self, args: dict) -> dict:
        """Get daily log by ID."""
        from app.dailylogs.models import DailyLog

        log_id = args.get("log_id")
        if not log_id:
            return {"error": "log_id required"}

        stmt = select(DailyLog).where(
            DailyLog.id == log_id,
            DailyLog.organization_id == self.org_id
        )
        log_ = self.db.scalar(stmt)
        if not log_:
            return {"error": "Daily log not found"}

        return {
            "id": str(log_.id),
            "project_id": str(log_.project_id),
            "log_date": str(log_.log_date),
            "status": log_.status.value if log_.status else None,
            "summary": log_.summary or "",
        }

    def _dailylog_list(self, args: dict) -> dict:
        """List daily logs."""
        from app.dailylogs.models import DailyLog

        project_id = args.get("project_id")
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)

        stmt = select(DailyLog).where(
            DailyLog.organization_id == self.org_id
        )
        if project_id:
            stmt = stmt.where(DailyLog.project_id == project_id)
        stmt = stmt.order_by(DailyLog.log_date.desc()).limit(limit).offset(offset)
        logs = self.db.scalars(stmt).all()

        return [
            {
                "id": str(l.id),
                "log_date": str(l.log_date),
                "project_id": str(l.project_id),
                "status": l.status.value if l.status else None,
                "summary": l.summary or "",
            }
            for l in logs
        ]

    def _document_list(self, args: dict) -> dict:
        """List documents."""
        from app.documents.models import Document

        limit = args.get("limit", 100)
        offset = args.get("offset", 0)

        stmt = select(Document).where(
            Document.organization_id == self.org_id,
            Document.deleted_at.is_(None),
        )
        stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        docs = self.db.scalars(stmt).all()

        return [
            {
                "id": str(d.id),
                "name": d.name,
                "file_name": d.file_name,
                "file_type": d.file_type,
                "version": d.version,
                "status": d.status,
            }
            for d in docs
        ]

    def _document_get(self, args: dict) -> dict:
        """Get document by ID."""
        from app.documents.models import Document

        doc_id = args.get("doc_id")
        if not doc_id:
            return {"error": "doc_id required"}

        stmt = select(Document).where(
            Document.id == doc_id,
            Document.organization_id == self.org_id,
            Document.deleted_at.is_(None),
        )
        doc = self.db.scalar(stmt)
        if not doc:
            return {"error": "Document not found"}

        return {
            "id": str(doc.id),
            "name": doc.name,
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "version": doc.version,
            "status": doc.status,
        }


class AIService:
    """Main AI assistant service."""

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.org_id = user.organization_id

    def create_session(self, title: Optional[str] = None, project_id: Optional[str] = None, context: Optional[dict] = None) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            organization_id=self.org_id,
            user_id=self.user.id,
            title=title or "New Chat",
            project_id=project_id,
            context=context or {},
        )
        self.db.add(session)
        self.db.commit()
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID."""
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.organization_id == self.org_id
        )
        return self.db.scalar(stmt)

    def list_sessions(self, limit: int = 50, offset: int = 0) -> List[ChatSession]:
        """List chat sessions for the organization."""
        stmt = select(ChatSession).where(
            ChatSession.organization_id == self.org_id,
            ChatSession.is_active == True
        ).order_by(ChatSession.updated_at.desc()).limit(limit).offset(offset)
        return self.db.scalars(stmt).all()

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session (soft delete)."""
        session = self.get_session(session_id)
        if session:
            session.is_active = False
            self.db.commit()
            return True
        return False

    def add_message(self, session_id: str, role: str, content: str, tool_calls: Optional[List[dict]] = None) -> ChatMessage:
        """Add a message to a session."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        )
        self.db.add(message)
        self.db.commit()
        return message

    def get_history(self, session_id: str, limit: int = MAX_HISTORY) -> List[ChatMessage]:
        """Get conversation history."""
        stmt = select(ChatMessage).where(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).limit(limit)
        return self.db.scalars(stmt).all()

    def chat(self, session_id: str, user_message: str) -> ChatMessage:
        """Process a chat message and return the assistant's response."""
        # Add user message
        user_msg = self.add_message(session_id, MessageRole.USER, user_message)

        # Get context for the response
        session = self.get_session(session_id)
        context = session.context if session else {}

        # Simple keyword-based response (no LLM in this MVP)
        response = self._generate_response(user_message, context)

        # Add assistant message
        assistant_msg = self.add_message(session_id, MessageRole.ASSISTANT, response)

        return assistant_msg

    def _generate_response(self, message: str, context: dict) -> str:
        """Generate a response based on the message and context."""
        message_lower = message.lower()

        # Check for RAG search intent
        if any(word in message_lower for word in ["document", "rag", "search", "find"]):
            return "I can help you search documents. Please provide a search query."

        # Check for project info intent
        if any(word in message_lower for word in ["project", "status", "progress"]):
            return "I can help you with project information. Please specify a project ID or name."

        # Check for BOQ intent
        if any(word in message_lower for word in ["boq", "quantity", "material"]):
            return "I can help you with BOQ information. Please specify a BOQ ID or project."

        # Check for procurement intent
        if any(word in message_lower for word in ["procurement", "purchase", "order"]):
            return "I can help you with procurement information. Please specify a requisition ID."

        # Check for inventory intent
        if any(word in message_lower for word in ["inventory", "stock", "material issue"]):
            return "I can help you with inventory information. Please specify an item or warehouse."

        # Check for labour intent
        if any(word in message_lower for word in ["labour", "attendance", "worker"]):
            return "I can help you with labour information. Please specify a date or project."

        # Default response
        return "I can help you with the following:\n- Search documents (RAG)\n- Project information\n- BOQ details\n- Procurement status\n- Inventory levels\n- Labour attendance\n\nPlease provide more details about what you need."

    def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool call."""
        executor = ToolExecutor(self.db, self.user)
        return executor.execute(tool_name, arguments)

    def process_tool_calls(self, session_id: str, tool_calls: List[dict]) -> List[ToolCall]:
        """Process multiple tool calls and return results."""
        results = []
        for tc in tool_calls:
            tool_name = tc.get("name")
            arguments = tc.get("arguments", {})
            result = self.execute_tool(tool_name, arguments)
            results.append({"name": tool_name, "result": result})
        return results