"""
Agent Core Service - Main entry point for the FastAPI backend.

Provides REST API and WebSocket endpoints for the NextAgent Doc Assistant.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import re
import json
import logging
import asyncio
from typing import Optional

from agent.core import AgentCore
from agent.conversation import ConversationManager
from agent.models import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    DocumentOutputInfo,
    SkillListResponse,
    HealthResponse,
    WritingState,
)
from fact_info_service import get_fact_service
from llm.routes import router as llm_router
from doc_version_service import get_doc_version_service


def _extract_doc_content(text: str) -> str:
    """Extract clean document content from LLM response.

    Strips any preamble explanation before the first H1 heading,
    and removes trailing <!-- doc_type: ... --> metadata comments.
    Falls back to the full text if no H1 is found.
    """
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('# ') or line == '#':
            doc = '\n'.join(lines[i:]).strip()
            # Strip trailing doc_type comment — not needed in stored draft
            doc = re.sub(r'\s*<!--\s*doc_type:\s*[\w-]+\s*-->\s*$', '', doc).strip()
            return doc
    return text.strip()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="NextAgent Doc Assistant API",
    description="AI Agent for intelligent document writing",
    version="0.1.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(llm_router)

# Dependency injection
async def get_agent() -> AgentCore:
    """Get the Agent instance."""
    return AgentCore.get_instance()


async def get_conversation_manager() -> ConversationManager:
    """Get the ConversationManager instance."""
    return ConversationManager.get_instance()


# =============================================================================
# Health Check
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check system health."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        components={
            "agent": "ready",
            "fact_info": "ready",
            "skills": "ready",
        }
    )


# =============================================================================
# Conversation API (REST)
# =============================================================================

@app.post("/api/v1/conversations", tags=["Conversations"])
async def create_conversation(
    body: ConversationCreate,
    manager: ConversationManager = Depends(get_conversation_manager)
):
    """Create a new conversation session."""
    conversation = await manager.create_conversation(
        name=body.name,
        description=body.description,
        document_type=body.document_type,
    )
    return {"conversation_id": conversation.id, "name": conversation.name}


@app.get("/api/v1/conversations", tags=["Conversations"])
async def list_conversations(
    manager: ConversationManager = Depends(get_conversation_manager)
):
    """List all conversations."""
    conversations = await manager.list_conversations()
    return {"conversations": conversations}


@app.get("/api/v1/conversations/{conversation_id}", tags=["Conversations"])
async def get_conversation(
    conversation_id: str,
    manager: ConversationManager = Depends(get_conversation_manager)
):
    """Get a specific conversation."""
    conversation = await manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/v1/conversations/{conversation_id}", tags=["Conversations"])
async def delete_conversation(
    conversation_id: str,
    manager: ConversationManager = Depends(get_conversation_manager)
):
    """Delete a conversation."""
    success = await manager.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted"}


@app.post("/api/v1/conversations/{conversation_id}/save-draft", tags=["Conversations"])
async def save_draft(
    conversation_id: str,
    manager: ConversationManager = Depends(get_conversation_manager),
):
    """Save the current draft in writing_state as a versioned document file."""
    conversation = await manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    ws = conversation.writing_state
    if not ws or not ws.draft_content:
        raise HTTPException(status_code=400, detail="No draft content to save")

    svc = get_doc_version_service()
    try:
        ref = await svc.save_document(
            content=ws.draft_content,
            doc_type=ws.doc_type or "document",
            doc_name=ws.module_name,
            conversation_id=conversation_id,
        )
    except Exception as e:
        logger.error(f"Failed to save draft: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败：{str(e)}")

    ws.saved_version = ref.version
    ws.saved_path = ref.relative_path
    await manager._save(conversation)

    return {
        "version": ref.version,
        "file_path": ref.relative_path,
    }


# =============================================================================
# Chat API (REST)
# =============================================================================

@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(
    body: ChatRequest,
    agent: AgentCore = Depends(get_agent),
):
    """Send a message to the Agent and get a response (non-streaming)."""
    try:
        response = await agent.process_message(
            conversation_id=body.conversation_id,
            message=body.message,
        )
        return response
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Skills API (REST)
# =============================================================================

@app.get("/api/v1/skills", response_model=SkillListResponse, tags=["Skills"])
async def list_skills(
    agent: AgentCore = Depends(get_agent),
):
    """Get list of available skills."""
    skills = await agent.get_available_skills()
    return SkillListResponse(skills=skills)


@app.get("/api/v1/skills/{skill_id}", tags=["Skills"])
async def get_skill(
    skill_id: str,
    agent: AgentCore = Depends(get_agent),
):
    """Get details of a specific skill."""
    skill = await agent.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


# =============================================================================
# Project Fact Information API (REST)
# =============================================================================

@app.get("/api/v1/fact-info", tags=["Project Facts"])
async def get_fact_info(
    layer: Optional[str] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
):
    """Query project fact information."""
    service = await get_fact_service()

    if keyword:
        items = await service.search(keyword)
    elif layer:
        from models import FactLayer
        items = await service.query_by_layer(FactLayer(layer))
    elif category:
        from models import FactCategory
        items = await service.query_by_category(FactCategory(category))
    else:
        # Return top-level summary
        from models import FactLayer
        items = await service.query_by_layer(FactLayer.MANIFEST)

    return {"items": [{"id": i.metadata.id, "name": i.metadata.name, "layer": i.metadata.layer} for i in items]}


@app.get("/api/v1/fact-info/{fact_id}", tags=["Project Facts"])
async def get_fact_by_id(fact_id: str):
    """Get a specific fact information item by ID."""
    service = await get_fact_service()
    item = await service.get_by_id(fact_id)
    if not item:
        raise HTTPException(status_code=404, detail="Fact not found")
    return {
        "id": item.metadata.id,
        "name": item.metadata.name,
        "layer": item.metadata.layer,
        "content": item.content,
    }


# =============================================================================
# Document Version Management API (REST)
# =============================================================================

@app.get("/api/v1/documents", tags=["Documents"])
async def list_documents(doc_type: Optional[str] = None):
    """List all documents, optionally filtered by type."""
    svc = get_doc_version_service()
    docs = await svc.list_documents(doc_type=doc_type)
    return {"documents": docs}


@app.get("/api/v1/documents/{doc_type}/{doc_name}/versions", tags=["Documents"])
async def list_versions(doc_type: str, doc_name: str):
    """List all versions of a document."""
    svc = get_doc_version_service()
    versions = await svc.list_versions(doc_type=doc_type, doc_name=doc_name)
    return {
        "versions": [
            {"date": v.date, "version": v.version, "path": v.relative_path}
            for v in versions
        ]
    }


@app.get("/api/v1/documents/{doc_type}/{doc_name}/latest", tags=["Documents"])
async def get_latest_document(doc_type: str, doc_name: str):
    """Get the latest version of a document."""
    svc = get_doc_version_service()
    result = await svc.load_latest(doc_type=doc_type, doc_name=doc_name)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    content, ref = result
    return {"path": ref.relative_path, "version": ref.version, "content": content}


@app.get("/api/v1/documents/{doc_type}/{doc_name}/{date}/{version}", tags=["Documents"])
async def get_document_version(doc_type: str, doc_name: str, date: str, version: str):
    """Get a specific version of a document."""
    svc = get_doc_version_service()
    result = await svc.load_version(doc_type=doc_type, doc_name=doc_name, date=date, version=version)
    if result is None:
        raise HTTPException(status_code=404, detail="Version not found")
    content, ref = result
    return {"path": ref.relative_path, "version": ref.version, "content": content}


# =============================================================================
# WebSocket Chat (Streaming)
# =============================================================================

class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        self.active_connections[conversation_id] = websocket

    def disconnect(self, conversation_id: str):
        self.active_connections.pop(conversation_id, None)

    async def send_message(self, conversation_id: str, message: dict):
        ws = self.active_connections.get(conversation_id)
        if ws:
            await ws.send_json(message)


ws_manager = ConnectionManager()


@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for real-time chat."""
    await ws_manager.connect(websocket, conversation_id)
    agent = AgentCore.get_instance()
    manager = ConversationManager.get_instance()

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")

            if not message:
                continue

            # Send acknowledgment
            await ws_manager.send_message(conversation_id, {
                "type": "ack",
                "conversation_id": conversation_id,
            })

            # Collect full response while streaming
            full_response = []
            skill_id = None
            skill_name = None
            skill_reason = None
            llm_usage = None
            done_data = None
            async for chunk in agent.stream_message(
                conversation_id=conversation_id,
                message=message,
            ):
                await ws_manager.send_message(conversation_id, chunk)
                if chunk.get("type") == "text":
                    full_response.append(chunk.get("content", ""))
                elif chunk.get("type") == "skill_start":
                    skill_id = chunk.get("skill_id")
                elif chunk.get("type") == "done":
                    skill_id = chunk.get("skill_id") or skill_id
                    skill_name = chunk.get("skill_name")
                    skill_reason = chunk.get("skill_reason")
                    llm_usage = chunk.get("usage")
                    done_data = chunk

            # Collect response text (no auto-save; user explicitly saves via save-draft)
            response_text = "".join(full_response)
            documents = []

            # Save round to conversation history
            if response_text:
                llm_info = None
                if llm_usage or skill_reason:
                    llm_info = {**(llm_usage or {}), "skill_reason": skill_reason}
                await manager.add_round(
                    conversation_id=conversation_id,
                    user_input=message,
                    agent_response=response_text,
                    skill_invoked=skill_id,
                    documents_generated=documents,
                    llm_info=llm_info,
                )

            # Update writing_state if this round produced a draft
            if done_data and done_data.get("has_draft") and response_text:
                conv = await manager.get_conversation(conversation_id)
                if conv:
                    ws_data = done_data.get("writing_state_data")
                    ws_update = done_data.get("writing_state_update")
                    if ws_data:
                        # New module: create/replace writing_state
                        conv.writing_state = WritingState(
                            module_id=ws_data.get("module_id", ""),
                            module_name=ws_data.get("module_name", ""),
                            skill_id=ws_data.get("skill_id", ""),
                            doc_type=ws_data.get("doc_type", ""),
                            draft_content=_extract_doc_content(response_text),
                        )
                        logger.info(f"Writing state created for module={ws_data.get('module_id')}")
                    elif ws_update == "draft_only" and conv.writing_state:
                        # Modify flow: update draft content only
                        conv.writing_state.draft_content = _extract_doc_content(response_text)
                        logger.info(f"Writing state draft updated for module={conv.writing_state.module_id}")
                    await manager._save(conv)

    except WebSocketDisconnect:
        ws_manager.disconnect(conversation_id)
        logger.info(f"WebSocket disconnected: {conversation_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(conversation_id)


# =============================================================================
# Startup / Shutdown
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting NextAgent Doc Assistant...")

    # Initialize Agent (loads skills)
    agent = AgentCore.get_instance()
    await agent.initialize()

    # Initialize Fact Information Service
    await get_fact_service()

    logger.info("NextAgent Doc Assistant started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down NextAgent Doc Assistant...")


# Serve static frontend files if built
static_dir = Path(__file__).parent.parent / "frontend" / "build"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
