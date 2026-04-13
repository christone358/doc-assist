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
from agent.adk.runner_adapter import stream_message as adk_stream, get_active_context, remove_session
from pydantic import BaseModel
from agent.models import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    DocumentOutputInfo,
    SkillDetail,
    SkillListResponse,
    HealthResponse,
    WritingState,
)
from llm.service import LLMService
from fact_info_service import get_fact_service
from llm.routes import router as llm_router
from doc_version_service import get_doc_version_service
from project_fact_modules import ModuleArchiveRepository, ensure_generated_views

REPO_ROOT = Path(__file__).resolve().parents[1]
FACTS_ROOT = REPO_ROOT / "project-facts"


def _extract_doc_content(text: str) -> str:
    """Extract clean document content from LLM response.

    Strips any preamble explanation before the first H1 heading,
    removes known process-summary appendix sections,
    and removes trailing <!-- doc_type: ... --> metadata comments.
    Falls back to the full text if no H1 is found.
    """
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('# ') or line == '#':
            doc = '\n'.join(lines[i:]).strip()
            appendix_heading = re.search(
                r'(?m)^(##+\s*(?:事实来源说明(?:与质量检查)?|事实来源说明|事实来源|质量检查结论|手册编写说明与待确认项|主要待确认项)\s*)$',
                doc,
            )
            if appendix_heading:
                doc = doc[:appendix_heading.start()].rstrip()
            # Strip trailing doc_type comment — not needed in stored draft
            doc = re.sub(r'\s*<!--\s*doc_type:\s*[\w-]+\s*-->\s*$', '', doc).strip()
            return doc
    return text.strip()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Third-party SDKs can emit very noisy DEBUG logs for local OpenAI-compatible
# models (for example LiteLLM cost estimation on unknown model ids). Keep our
# backend logs verbose, but quiet these libraries unless they log warnings.
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.INFO)

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
    remove_session(conversation_id)
    return {"message": "Conversation deleted"}


class ConversationUpdate(BaseModel):
    name: str


@app.patch("/api/v1/conversations/{conversation_id}", tags=["Conversations"])
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    manager: ConversationManager = Depends(get_conversation_manager),
):
    """Update conversation name."""
    conversation = await manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.name = body.name.strip() or conversation.name
    from agent.conversation import _now
    conversation.updated_at = _now()
    await manager._save(conversation)
    return {"conversation_id": conversation.id, "name": conversation.name}


async def _try_auto_name(conversation_id: str, manager: ConversationManager) -> None:
    """Auto-generate a conversation title if it still has a default timestamp name."""
    try:
        conversation = await manager.get_conversation(conversation_id)
        if not conversation:
            logger.warning(f"auto_name: conversation {conversation_id} not found")
            return
        if not conversation.rounds:
            logger.warning(f"auto_name: conversation {conversation_id} has no rounds")
            return
        if not conversation.name.startswith("对话 "):
            logger.info(f"auto_name: skipped, name already set: {conversation.name!r}")
            return

        first_round = conversation.rounds[0]
        user_input = first_round.user_input[:300]
        response_summary = (first_round.agent_response or "")[:200]

        logger.info(f"auto_name: generating title for {conversation_id}, input={user_input[:50]!r}")

        llm = LLMService()
        title, _ = await llm.complete(
            system_prompt="你是一个对话标题生成助手，根据用户输入和AI回复生成简短的中文标题。只返回标题文本，不超过15个字，不加引号。",
            messages=[],
            user_message=f"用户：{user_input}\nAI：{response_summary}",
        )
        title = title.strip().strip('"').strip("'")[:20]
        logger.info(f"auto_name: got title={title!r}")

        if title and not title.startswith("⚠️"):
            conversation.name = title
            from agent.conversation import _now
            conversation.updated_at = _now()
            await manager._save(conversation)
            logger.info(f"auto_name: saved title={title!r} for {conversation_id}")
        else:
            logger.warning(f"auto_name: title rejected: {title!r}")
    except Exception as e:
        logger.error(f"auto_name: failed for {conversation_id}: {e}", exc_info=True)


@app.post("/api/v1/conversations/{conversation_id}/auto-name", tags=["Conversations"])
async def auto_name_conversation(
    conversation_id: str,
    manager: ConversationManager = Depends(get_conversation_manager),
):
    """Generate a semantic title for the conversation using LLM."""
    conversation = await manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if not conversation.rounds:
        raise HTTPException(status_code=400, detail="No rounds yet")

    await _try_auto_name(conversation_id, manager)
    conversation = await manager.get_conversation(conversation_id)
    return {"conversation_id": conversation.id, "name": conversation.name}


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
    ws.module_name = ref.doc_name
    ws.doc_type = ref.doc_type
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
    return SkillListResponse(skills=[skill.to_summary() for skill in skills])


@app.get("/api/v1/skills/{skill_id}", response_model=SkillDetail, tags=["Skills"])
async def get_skill(
    skill_id: str,
    agent: AgentCore = Depends(get_agent),
):
    """Get details of a specific skill."""
    skill = await agent.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill.to_detail()


# =============================================================================
# Project Fact Information API (REST)
# =============================================================================

@app.get("/api/v1/fact-info", tags=["Project Facts"])
async def get_fact_info(
    layer: Optional[str] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    system: Optional[str] = None,
    subsystem: Optional[str] = None,
    status: Optional[str] = None,
):
    """Query project fact information."""
    repo = ModuleArchiveRepository(FACTS_ROOT)
    module_items = repo.list_modules(
        keyword=keyword or "",
        system=system or "",
        subsystem=subsystem or "",
        status=status or "",
    )
    if module_items:
        return {"items": module_items}

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


@app.post("/api/v1/fact-info/refresh", tags=["Project Facts"])
async def refresh_fact_info():
    """Rebuild derived project fact views from the latest module archives."""
    generated = ensure_generated_views(FACTS_ROOT)
    archives = generated.get("archives", [])
    return {
        "message": "项目事实信息已更新",
        "modules": len(archives),
        "generated_views": len(archives),
    }


@app.get("/api/v1/fact-info/{fact_id}", tags=["Project Facts"])
async def get_fact_by_id(fact_id: str):
    """Get a specific fact information item by ID."""
    repo = ModuleArchiveRepository(FACTS_ROOT)
    module = repo.get_module(fact_id)
    if module:
        return module

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
async def list_documents(
    doc_type: Optional[str] = None,
    query: Optional[str] = None,
    module_query: Optional[str] = None,
):
    """List all documents, optionally filtered by type and document name query."""
    svc = get_doc_version_service()
    docs = await svc.list_documents(doc_type=doc_type, query=query or module_query)
    return {"documents": docs}


@app.get("/api/v1/documents/{doc_type}/{doc_name}/versions", tags=["Documents"])
async def list_versions(doc_type: str, doc_name: str):
    """List all versions of a document."""
    svc = get_doc_version_service()
    versions = await svc.list_versions(doc_type=doc_type, doc_name=doc_name)
    return {
        "versions": [
            {
                "date": v.date,
                "version": v.version,
                "path": v.relative_path,
                "updated_at": svc.ref_updated_at(v),
            }
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
    return {
        "path": ref.relative_path,
        "version": ref.version,
        "updated_at": svc.ref_updated_at(ref),
        "content": content,
    }


@app.get("/api/v1/documents/{doc_type}/{doc_name}/{date}/{version}", tags=["Documents"])
async def get_document_version(doc_type: str, doc_name: str, date: str, version: str):
    """Get a specific version of a document."""
    svc = get_doc_version_service()
    result = await svc.load_version(doc_type=doc_type, doc_name=doc_name, date=date, version=version)
    if result is None:
        raise HTTPException(status_code=404, detail="Version not found")
    content, ref = result
    return {
        "path": ref.relative_path,
        "version": ref.version,
        "updated_at": svc.ref_updated_at(ref),
        "content": content,
    }


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


async def _run_agent_stream(
    conversation_id: str,
    message: str,
    ws_manager_ref: "ConnectionManager",
    manager: "ConversationManager",
    skill_manager,
    ws_sender,
) -> dict:
    """在独立协程中运行 ADK Agent 流，收集 done 数据后返回。

    与 WebSocket 接收循环并发运行，使 ask_user 的用户回复可以实时送达。
    """
    skill_id = None
    skill_name = None
    skill_reason = None
    llm_usage = None
    done_data = None
    text_response = ""  # 累积非草稿的对话回复文本（用于持久化到 agent_response）

    async for chunk in adk_stream(
        conversation_id=conversation_id,
        message=message,
        ws_sender=ws_sender,
        conversation_manager=manager,
        skill_manager=skill_manager,
    ):
        chunk_type = chunk.get("type")
        if chunk_type in (
            "text",
            "status",
            "error",
            "question",
            "thinking",
            "skill_start",
            "execution_event",
            "trace_node",
            "reflection",
            "summary",
        ):
            await ws_manager_ref.send_message(conversation_id, chunk)
            if chunk_type == "text":
                text_response += chunk.get("content", "")
        elif chunk_type == "done":
            skill_id = chunk.get("skill_id") or skill_id
            skill_name = chunk.get("skill_name")
            skill_reason = chunk.get("skill_reason")
            llm_usage = chunk.get("usage")
            done_data = chunk
            await ws_manager_ref.send_message(conversation_id, chunk)

    return {
        "done_data": done_data,
        "skill_id": skill_id,
        "skill_name": skill_name,
        "skill_reason": skill_reason,
        "llm_usage": llm_usage,
        "text_response": text_response,
    }


@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for real-time chat."""
    await ws_manager.connect(websocket, conversation_id)
    agent = AgentCore.get_instance()
    manager = ConversationManager.get_instance()

    async def ws_sender(msg: dict):
        """直接向 WebSocket 发送消息（供工具侧信道流式输出使用）。"""
        await ws_manager.send_message(conversation_id, msg)

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")

            if not message:
                continue

            # 检查是否有等待用户回复的活跃上下文（ask_user 场景）
            active_ctx = get_active_context(conversation_id)
            if active_ctx and active_ctx.waiting_for_user:
                # 将用户回复投入等待队列，不启动新的 Agent 运行
                await active_ctx.user_input_queue.put(message)
                continue

            # Send acknowledgment
            await ws_manager.send_message(conversation_id, {
                "type": "ack",
                "conversation_id": conversation_id,
            })

            # 将 Agent 运行放入独立任务，保持 WebSocket 接收循环活跃
            # 这样 ask_user 等待用户回复时，接收循环可以继续接收消息并路由到队列
            agent_task = asyncio.create_task(
                _run_agent_stream(
                    conversation_id=conversation_id,
                    message=message,
                    ws_manager_ref=ws_manager,
                    manager=manager,
                    skill_manager=agent._skill_manager,
                    ws_sender=ws_sender,
                )
            )

            # 等待 Agent 完成，同时保持接收循环活跃以处理 ask_user 回复
            while not agent_task.done():
                try:
                    incoming = await asyncio.wait_for(
                        websocket.receive_json(), timeout=0.5
                    )
                    inc_message = incoming.get("message", "")
                    if inc_message:
                        inc_ctx = get_active_context(conversation_id)
                        if inc_ctx and inc_ctx.waiting_for_user:
                            await inc_ctx.user_input_queue.put(inc_message)
                        # else: 忽略 Agent 运行期间收到的其他消息
                except asyncio.TimeoutError:
                    pass  # 正常：无新消息，继续等待
                except WebSocketDisconnect:
                    agent_task.cancel()
                    raise

            result = await agent_task
            done_data = result.get("done_data")
            skill_id = result.get("skill_id")
            skill_reason = result.get("skill_reason")
            llm_usage = result.get("llm_usage")

            # 持久化 agent_response：草稿场景用 draft_content，普通对话用累积的 text_response
            has_draft_this_round = bool(done_data and done_data.get("has_draft"))
            draft_content = done_data.get("draft_content", "") if (done_data and has_draft_this_round) else ""
            response_text = draft_content or result.get("text_response", "")
            documents = []

            # Save round to conversation history
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
                skill_execution=done_data.get("skill_execution") if done_data else None,
                execution_events=done_data.get("execution_events") if done_data else None,
                execution_nodes=done_data.get("execution_nodes") if done_data else None,
                state_snapshot=done_data.get("state_snapshot") if done_data else None,
            )

            # Auto-name: generate semantic title on the first round (fire-and-forget)
            asyncio.create_task(_try_auto_name(conversation_id, manager))

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

    svc = get_doc_version_service()
    migration = svc.migrate_legacy_outputs(cleanup=True)
    logger.info("Legacy document migration summary: %s", migration)

    # Initialize Agent (loads skills)
    agent = AgentCore.get_instance()
    await agent.initialize()

    logger.info("NextAgent Doc Assistant started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down NextAgent Doc Assistant...")


# Serve static frontend files if built
static_dir = Path(__file__).parent.parent / "frontend" / "build"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
