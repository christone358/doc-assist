"""
Agent Core - Main agent class handling conversation and skill dispatch.
"""

import logging
import asyncio
from typing import Optional, List, Dict, Any, AsyncIterator
from pathlib import Path
import json

from agent.context_loader import load_context, resolve_module_id

from agent.models import (
    ChatResponse,
    ConversationInfo,
    ConversationRound,
    DocumentOutputInfo,
    MessageRole,
    SkillInfo,
    StreamChunk,
    WritingState,
)

logger = logging.getLogger(__name__)


class AgentCore:
    """Core Agent that handles conversation and skill orchestration."""

    _instance: Optional["AgentCore"] = None

    def __init__(self):
        self._initialized = False
        self._skill_manager = None
        self._llm_service = None
        self._conversation_manager = None
        self._fact_service = None

    @classmethod
    def get_instance(cls) -> "AgentCore":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self):
        """Initialize the agent and all sub-components."""
        if self._initialized:
            return

        logger.info("Initializing Agent Core...")

        # Import here to avoid circular imports
        from skill.manager import SkillManager
        from llm.service import LLMService
        from agent.conversation import ConversationManager
        from fact_info_service import get_fact_service

        # Initialize skill manager and load skills
        self._skill_manager = SkillManager(skills_dir=str(Path(__file__).parent.parent.parent / "skills"))
        await self._skill_manager.discover_and_load()

        # Initialize LLM service
        self._llm_service = LLMService()
        await self._llm_service.initialize()

        # Initialize conversation manager
        self._conversation_manager = ConversationManager.get_instance()

        # Initialize fact information service
        self._fact_service = await get_fact_service()

        self._initialized = True
        loaded = len(await self.get_available_skills())
        logger.info(f"Agent Core initialized. Loaded {loaded} skills.")

    async def process_message(
        self,
        conversation_id: str,
        message: str,
    ) -> ChatResponse:
        """Process a user message and return a response.

        Args:
            conversation_id: The conversation to continue
            message: The user's message

        Returns:
            ChatResponse with Agent's reply
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Load conversation history
            conversation = await self._conversation_manager.get_conversation(
                conversation_id
            )

            # Identify what the user wants (new doc vs. modification)
            intent = await self._identify_intent(message, conversation)

            # Select appropriate skill
            selected_skill, skill_reason = await self._select_skill(message, intent)

            # Infer context needs, resolve module, load context
            vocab_list = await self._infer_context_needs(selected_skill)
            module_id, _, _reasoning = await self._resolve_module(message)
            facts_context = await self._load_project_context(vocab_list, module_id)

            # Generate response with LLM
            agent_response, documents, usage = await self._execute_with_llm(
                message=message,
                conversation=conversation,
                intent=intent,
                skill=selected_skill,
                facts_context=facts_context,
            )

            # Save round to conversation
            await self._conversation_manager.add_round(
                conversation_id=conversation_id,
                user_input=message,
                agent_response=agent_response,
                skill_invoked=selected_skill.id if selected_skill else None,
                documents_generated=documents,
            )

            return ChatResponse(
                conversation_id=conversation_id,
                message=agent_response,
                skill_invoked=selected_skill.id if selected_skill else None,
                documents_generated=documents,
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return ChatResponse(
                conversation_id=conversation_id,
                message=f"抱歉，处理您的请求时遇到了错误。请重新描述您的需求，或联系管理员。\n\n错误信息：{str(e)}",
                metadata={"error": str(e)},
            )

    async def stream_message(
        self,
        conversation_id: str,
        message: str,
    ) -> AsyncIterator[dict]:
        """Stream a response to a user message.

        Yields chunks as they become available.
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Load conversation and writing_state at the start
            conversation = await self._conversation_manager.get_conversation(
                conversation_id
            )
            writing_state = conversation.writing_state if conversation else None

            # Determine writing intent
            writing_intent = "new_module"
            if writing_state:
                yield {"type": "status", "content": "识别写作意图..."}
                writing_intent = await self._identify_writing_intent(message, writing_state)

                if writing_intent == "modify":
                    draft_label = f"v{writing_state.saved_version}" if writing_state.saved_version else "草稿"
                    yield {
                        "type": "status",
                        "content": f"当前写作目标：{writing_state.module_name}（{draft_label}）",
                    }
                else:
                    # new_module: clear writing_state for this flow
                    writing_state = None
                    if conversation:
                        conversation.writing_state = None

            if writing_intent == "modify" and writing_state:
                # === MODIFY FLOW: lightweight, skip module resolution and context loading ===
                selected_skill = await self.get_skill(writing_state.skill_id)
                skill_reason = "继续修改当前文档"

                if selected_skill:
                    yield {
                        "type": "skill_start",
                        "skill_id": selected_skill.id,
                        "content": f"使用 Skill: {selected_skill.name}",
                        "reason": skill_reason,
                    }

                yield {"type": "status", "content": "正在生成修改内容..."}

                llm_usage = None
                async for chunk in self._stream_llm_response(
                    message=message,
                    conversation=None,  # skip history; draft is the context
                    intent={"intent_type": "modify_document"},
                    skill=selected_skill,
                    facts_context=[],
                    draft_content=writing_state.draft_content,
                ):
                    if isinstance(chunk, dict):
                        llm_usage = chunk.get("usage")
                    else:
                        yield {"type": "text", "content": chunk}

                if selected_skill:
                    yield {"type": "skill_end", "skill_id": selected_skill.id}

                yield {
                    "type": "done",
                    "skill_id": selected_skill.id if selected_skill else None,
                    "skill_name": selected_skill.name if selected_skill else None,
                    "skill_reason": skill_reason,
                    "usage": llm_usage,
                    "has_draft": True,
                    "writing_state_update": "draft_only",
                }
                return

            # === NEW_MODULE / FULL FLOW ===
            # Identify intent (legacy: new_document / modify_document for skill selection)
            yield {"type": "status", "content": "正在理解您的需求..."}
            intent = await self._identify_intent(message, None)

            # Select skill via LLM
            yield {"type": "status", "content": "LLM 正在分析可用 Skill..."}
            selected_skill, skill_reason = await self._select_skill(message, intent)

            if selected_skill:
                yield {
                    "type": "skill_start",
                    "skill_id": selected_skill.id,
                    "content": f"使用 Skill: {selected_skill.name}",
                    "reason": skill_reason,
                }

            # Step 1: Infer context needs from skill
            yield {"type": "status", "content": "分析上下文需求..."}
            vocab_list = await self._infer_context_needs(selected_skill)

            # Step 2: Locate target module from user message
            yield {"type": "status", "content": "识别目标模块..."}
            module_id, module_name, module_reasoning = await self._resolve_module(message)
            if module_id:
                label = "语义理解" if module_reasoning else "精确匹配"
                yield {
                    "type": "status",
                    "content": f"已定位模块: {module_name}（{module_id}）[{label}]",
                }
                if module_reasoning:
                    yield {"type": "status", "content": f"理解：{module_reasoning}"}
            else:
                yield {"type": "status", "content": "未识别到目标模块"}
                logger.info("Module not resolved, stopping and asking user to clarify")

                module_options = await self._get_available_modules()
                if module_options:
                    options_text = "\n".join(
                        f"- **{name}**" for name, _ in module_options
                    )
                    clarification = (
                        "我无法从您的描述中确定要编写哪个模块的文档。\n\n"
                        "请告诉我具体是哪个模块，可用的模块有：\n\n"
                        f"{options_text}\n\n"
                        "例如：「帮我写 **Agent核心模块** 的需求规格」"
                    )
                else:
                    clarification = (
                        "我无法从您的描述中确定要编写哪个模块的文档。\n\n"
                        "请告诉我具体是哪个模块的名称，例如：「帮我写 **XXX模块** 的需求规格」"
                    )

                yield {"type": "text", "content": clarification}
                yield {
                    "type": "done",
                    "skill_id": selected_skill.id if selected_skill else None,
                    "skill_name": selected_skill.name if selected_skill else None,
                    "skill_reason": skill_reason,
                    "usage": None,
                }
                return

            # Step 3: Load all inferred context
            facts_context = await self._load_project_context(vocab_list, module_id)
            if facts_context:
                parts = []
                for item in facts_context:
                    vocab = item["vocab"]
                    names = item.get("entry_names", [])
                    count = item["entry_count"]
                    if vocab == "modules":
                        parts.append(f"modules（{count}个）: " + "、".join(names[:5]) + ("..." if count > 5 else ""))
                    elif names:
                        preview = "、".join(names[:3])
                        suffix = f" 等{count}条" if count > 3 else f"（{count}条）"
                        parts.append(f"{vocab}: {preview}{suffix}")
                    else:
                        parts.append(f"{vocab}（{count}条）")
                yield {"type": "status", "content": "加载项目上下文：" + " · ".join(parts)}

            # Stream LLM response
            yield {"type": "status", "content": "正在生成响应..."}

            llm_usage = None
            async for chunk in self._stream_llm_response(
                message=message,
                conversation=conversation,
                intent=intent,
                skill=selected_skill,
                facts_context=facts_context,
            ):
                if isinstance(chunk, dict):
                    # Usage data from LLM service
                    llm_usage = chunk.get("usage")
                else:
                    yield {"type": "text", "content": chunk}

            if selected_skill:
                yield {"type": "skill_end", "skill_id": selected_skill.id}

            yield {
                "type": "done",
                "skill_id": selected_skill.id if selected_skill else None,
                "skill_name": selected_skill.name if selected_skill else None,
                "skill_reason": skill_reason,
                "usage": llm_usage,
                "has_draft": True,
                "writing_state_data": {
                    "module_id": module_id,
                    "module_name": module_name,
                    "skill_id": selected_skill.id if selected_skill else "",
                    "doc_type": selected_skill.type if selected_skill else "",
                },
            }

        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": f"处理出错：{str(e)}"
            }

    async def _identify_writing_intent(
        self,
        message: str,
        writing_state: Optional[Any],
    ) -> str:
        """Identify writing intent from user message.

        Returns 'modify' or 'new_module'.
        - modify: user is refining/adding to the current document
        - new_module: user wants to write a different module or start fresh
        """
        if writing_state is None:
            return "new_module"

        # Fast path: explicit rewrite instructions
        rewrite_phrases = ["重新写", "从头开始", "全部重写", "全部重新", "重新生成"]
        if any(phrase in message for phrase in rewrite_phrases):
            return "new_module"

        if not self._llm_service:
            return "modify"  # conservative default

        prompt = (
            f"当前正在编写的模块：「{writing_state.module_name}」\n"
            f"用户新消息：「{message}」\n\n"
            "判断用户意图：\n"
            "- 如果用户是在对当前文档进行修改、补充、调整（如增加内容、改写章节、调整格式），返回：modify\n"
            "- 如果用户要写一个完全不同的模块文档，或明确要求全部重写，返回：new_module\n"
            "只返回一个词（modify 或 new_module），不要其他内容。"
        )
        try:
            text, _ = await self._llm_service.complete(
                system_prompt="你是写作意图分析助手，只返回 modify 或 new_module。",
                messages=[],
                user_message=prompt,
            )
            result = (text or "").strip().lower()
            if result in ("modify", "new_module"):
                logger.info(f"Writing intent identified: {result} for module={writing_state.module_name}")
                return result
        except Exception as e:
            logger.warning(f"Writing intent LLM call failed: {e}")

        return "modify"  # default to modify on failure

    async def _identify_intent(
        self,
        message: str,
        conversation: Optional[ConversationInfo],
    ) -> Dict[str, Any]:
        """Identify user intent from message and conversation context.

        Returns a dict with:
        - intent_type: "new_document" | "modify_document" | "query" | "other"
        - document_type: Optional[str]
        - target_document: Optional[str] (for modifications)
        - key_requirements: List[str]
        """
        message_lower = message.lower()

        # Modification keywords (higher specificity → check first)
        modify_keywords = ["修改", "修正", "更新", "调整", "改动", "变更", "重写",
                           "补充", "增加内容", "删除", "替换", "完善", "优化已有"]
        # New document keywords
        new_doc_keywords = ["编写", "创建", "生成", "新建", "起草", "撰写",
                             "帮我写", "写一份", "写一个", "制作", "输出"]
        # Query keywords
        query_keywords = ["查询", "查看", "显示", "列出", "什么", "如何",
                          "有哪些", "告诉我", "解释", "介绍"]

        # Document type extraction
        doc_type_map = {
            "需求": "requirements",
            "设计": "design",
            "测试": "test",
            "接口": "api",
            "用例": "use-case",
            "架构": "architecture",
        }

        if any(kw in message_lower for kw in modify_keywords):
            intent_type = "modify_document"
        elif any(kw in message_lower for kw in new_doc_keywords):
            intent_type = "new_document"
        elif any(kw in message_lower for kw in query_keywords):
            intent_type = "query"
        elif conversation and len(conversation.rounds) > 0:
            # Continue in same intent direction as previous round
            intent_type = "new_document"
        else:
            intent_type = "new_document"  # Default

        # Extract document type if mentioned
        detected_doc_type = None
        for keyword, dtype in doc_type_map.items():
            if keyword in message_lower:
                detected_doc_type = dtype
                break

        # Extract key requirements from message (simple sentence split)
        key_requirements = [
            seg.strip() for seg in message.split("，")
            if len(seg.strip()) > 4
        ][:5]

        return {
            "intent_type": intent_type,
            "document_type": detected_doc_type,
            "key_requirements": key_requirements,
        }

    async def _infer_context_needs(self, skill: Optional[Any]) -> List[str]:
        """
        Infer which vocabulary types are needed for the given skill via LLM.

        Sends the full skill.md content + vocabulary table to LLM, expects:
          CONTEXT: modules, usecases, prototypes

        Falls back to ["modules", "usecases"] on failure.
        """
        fallback = ["modules", "usecases"]

        if skill is None or not self._llm_service:
            return fallback

        skill_text = skill.content or f"{skill.name}: {skill.description}"

        vocab_table = (
            "系统词汇表（上下文类型）：\n"
            "- modules: 功能模块清单（全量，始终包含）\n"
            "- usecases: 用例清单（按模块过滤）\n"
            "- classes: 类包清单（按模块过滤）\n"
            "- interfaces: 接口清单（按模块过滤）\n"
            "- prototypes: 原型界面（按模块定位文件）"
        )

        prompt = (
            f"{vocab_table}\n\n"
            f"以下是某个文档编写 Skill 的完整内容：\n\n{skill_text}\n\n"
            "请分析该 Skill 在编写文档时需要加载哪些类型的项目上下文信息。\n"
            "只返回一行，格式如下（逗号分隔词汇，不要其他内容）：\n"
            "CONTEXT: modules, usecases"
        )

        try:
            text, _ = await self._llm_service.complete(
                system_prompt="你是上下文需求分析助手，只返回一行 CONTEXT: 格式的结果。",
                messages=[],
                user_message=prompt,
            )
            for line in (text or "").strip().splitlines():
                line = line.strip()
                if line.upper().startswith("CONTEXT:"):
                    raw = line.split(":", 1)[1].strip()
                    vocab_list = [v.strip() for v in raw.split(",") if v.strip()]
                    valid = {"modules", "usecases", "classes", "interfaces", "prototypes"}
                    result = [v for v in vocab_list if v in valid]
                    if "modules" not in result:
                        result.insert(0, "modules")
                    logger.info(
                        f"Context inference for skill={getattr(skill, 'id', '?')}: "
                        f"source=llm, vocab={result}"
                    )
                    return result
        except Exception as e:
            logger.warning(f"Context inference LLM call failed: {e}")

        logger.info(
            f"Context inference fallback for skill={getattr(skill, 'id', '?')}: "
            f"vocab={fallback}"
        )
        return fallback

    async def _resolve_module(
        self, user_message: str
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Resolve the target module ID from user message.

        Strategy:
        1. Exact string match against module names in modules.md
        2. LLM semantic match with reasoning (async)

        Returns (module_id, module_name, reasoning) or (None, None, None).
        reasoning is a brief LLM-generated description of its understanding,
        e.g. "用户想编写 LLM 集成模块的需求规格文档".
        """
        import re as _re
        facts_root = Path(__file__).parent.parent.parent / "project-facts"
        modules_file = facts_root / "modules.md"
        if not modules_file.exists():
            return None, None, None

        modules_content = modules_file.read_text(encoding="utf-8")
        module_id, module_map = resolve_module_id(user_message, modules_content)

        if module_id:
            pattern = rf"^##\s+(.+?)\s+\{{#{_re.escape(module_id)}\}}"
            m = _re.search(pattern, modules_content, _re.MULTILINE)
            module_name = m.group(1).strip() if m else module_id
            return module_id, module_name, None

        # LLM semantic fallback
        if not self._llm_service or not module_map:
            return None, None, None

        module_list = "\n".join(
            f"- {name}（ID: {mid}）" for name, mid in module_map.items()
        )
        prompt = (
            f"项目中所有功能模块：\n{module_list}\n\n"
            f"用户消息：\"{user_message}\"\n\n"
            "请判断用户消息涉及哪个功能模块，按以下格式返回两行（不要其他内容）：\n"
            "MODULE_ID: <模块ID 或 null>\n"
            "REASON: <一句话说明你的理解，例如「用户想编写 LLM 集成模块的需求规格文档」>"
        )
        try:
            text, _ = await self._llm_service.complete(
                system_prompt="你是模块识别助手，严格按格式返回两行结果。",
                messages=[],
                user_message=prompt,
            )
            result_id = None
            reasoning = None
            for line in (text or "").strip().splitlines():
                line = line.strip()
                if line.upper().startswith("MODULE_ID:"):
                    raw = line.split(":", 1)[1].strip()
                    if raw.lower() != "null" and raw in set(module_map.values()):
                        result_id = raw
                elif line.upper().startswith("REASON:"):
                    reasoning = line.split(":", 1)[1].strip()

            if result_id:
                pattern = rf"^##\s+(.+?)\s+\{{#{_re.escape(result_id)}\}}"
                m = _re.search(pattern, modules_content, _re.MULTILINE)
                module_name = m.group(1).strip() if m else result_id
                logger.info(
                    f"Module resolved via LLM: {result_id}, reasoning: {reasoning}"
                )
                return result_id, module_name, reasoning

        except Exception as e:
            logger.error(f"LLM module resolution failed: {e}")

        return None, None, None

    async def _get_available_modules(self) -> List[tuple]:
        """Read modules.md and return list of (name, module_id) tuples."""
        import re
        facts_root = Path(__file__).parent.parent.parent / "project-facts"
        modules_file = facts_root / "modules.md"
        if not modules_file.exists():
            return []
        content = modules_file.read_text(encoding="utf-8")
        modules = []
        for m in re.finditer(r"^##\s+(.+?)\s+\{#([^}]+)\}", content, re.MULTILINE):
            modules.append((m.group(1).strip(), m.group(2).strip()))
        return modules

    async def _load_project_context(
        self, vocab_list: List[str], module_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """
        Load project context for each vocabulary type.

        Returns a list of dicts: {"vocab": str, "content": str, "entry_count": int}
        """
        facts_root = Path(__file__).parent.parent.parent / "project-facts"
        if not facts_root.exists():
            logger.warning(f"project-facts directory not found at {facts_root}")
            return []

        import re

        results = []
        for vocab in vocab_list:
            contents = load_context(vocab, module_id, facts_root)
            if not contents:
                continue
            combined = "\n\n".join(contents)

            # Extract human-readable entry names for status display
            entry_names: List[str] = []
            if vocab == "modules":
                for m in re.finditer(r"^##\s+(.+?)\s+\{#", combined, re.MULTILINE):
                    entry_names.append(m.group(1).strip())
            else:
                # usecases / classes / interfaces / prototypes: ### heading lines
                for m in re.finditer(r"^###\s+(.+?)$", combined, re.MULTILINE):
                    entry_names.append(m.group(1).strip())

            entry_count = len(entry_names) if entry_names else (1 if combined.strip() else 0)
            results.append({
                "vocab": vocab,
                "content": combined,
                "entry_count": entry_count,
                "entry_names": entry_names,
            })
            logger.info(
                f"Loaded context: vocab={vocab}, module_id={module_id}, "
                f"entries={entry_count}, chars={len(combined)}"
            )

        return results

    async def _select_skill(
        self,
        message: str,
        intent: Dict[str, Any],
    ) -> tuple[Optional[SkillInfo], Optional[str]]:
        """Select the most appropriate skill via a dedicated LLM call.

        The LLM reads each skill's name and description, reasons about which
        one best fits the user's request, and returns a structured decision.
        Returns (skill | None, reason | None).
        """
        skills = await self.get_available_skills()
        if not skills or not self._llm_service:
            return None, None

        skill_map = {s.id: s for s in skills}
        skills_desc = "\n".join(
            f"- {s.id}: 【{s.name}】{s.description}"
            for s in skills
        )

        system_prompt = (
            "你是一个文档编写 Skill 选择专家。\n"
            "根据用户的需求描述，从以下可用 Skill 中选择最适合的一个，并用一句话说明选择理由。\n"
            "如果没有任何 Skill 适合该需求，请回复 SKILL_ID: none。\n\n"
            f"可用 Skill：\n{skills_desc}\n\n"
            "请严格按以下格式回复（仅此两行，不要多余内容）：\n"
            "SKILL_ID: <skill_id 或 none>\n"
            "REASON: <简短的中文选择理由>"
        )

        try:
            text, _ = await self._llm_service.complete(
                system_prompt=system_prompt,
                messages=[],
                user_message=f"用户需求：{message}",
            )

            skill_id = None
            reason = None
            for line in (text or "").strip().splitlines():
                line = line.strip()
                if line.startswith("SKILL_ID:"):
                    skill_id = line.split(":", 1)[1].strip()
                elif line.startswith("REASON:"):
                    reason = line.split(":", 1)[1].strip()

            if not skill_id or skill_id.lower() == "none":
                return None, None

            selected = skill_map.get(skill_id)
            if not selected:
                # Fuzzy fallback: LLM may have returned a partial ID
                for s in skills:
                    if skill_id.lower() in s.id.lower() or s.id.lower() in skill_id.lower():
                        selected = s
                        break

            return selected, reason

        except Exception as e:
            logger.warning(f"Skill selection LLM call failed: {e}")
            return None, None

    async def _execute_with_llm(
        self,
        message: str,
        conversation: Optional[ConversationInfo],
        intent: Dict[str, Any],
        skill: Optional[SkillInfo],
        facts_context: List[Any],
    ) -> tuple[str, List[DocumentOutputInfo], Optional[dict]]:
        """Execute the request using LLM and optionally a skill.
        Returns (text, documents, usage).
        """
        if not self._llm_service:
            return "LLM服务未初始化，请检查配置。", [], None

        all_skills = await self.get_available_skills()
        system_prompt = self._build_system_prompt(skill, facts_context, all_skills)
        history = []
        if conversation:
            for r in conversation.rounds[-5:]:  # Last 5 rounds
                history.append({"role": "user", "content": r.user_input})
                history.append({"role": "assistant", "content": r.agent_response})

        # Call LLM
        response_text, usage = await self._llm_service.complete(
            system_prompt=system_prompt,
            messages=history,
            user_message=message,
        )

        documents = []
        return response_text, documents, usage

    async def _stream_llm_response(
        self,
        message: str,
        conversation: Optional[ConversationInfo],
        intent: Dict[str, Any],
        skill: Optional[SkillInfo],
        facts_context: List[Any],
        draft_content: Optional[str] = None,
    ) -> AsyncIterator[str | dict]:
        """Stream LLM response. Yields text strings and a final {"usage": ...} dict."""
        if not self._llm_service:
            yield "LLM服务未初始化，请检查配置。"
            yield {"usage": None}
            return

        all_skills = await self.get_available_skills()
        system_prompt = self._build_system_prompt(skill, facts_context, all_skills, draft_content)
        history = []
        if conversation and not draft_content:
            # Only use conversation history when not in modify (draft) mode
            for r in conversation.rounds[-5:]:
                history.append({"role": "user", "content": r.user_input})
                history.append({"role": "assistant", "content": r.agent_response})

        async for chunk in self._llm_service.stream_complete(
            system_prompt=system_prompt,
            messages=history,
            user_message=message,
        ):
            yield chunk

    def _build_system_prompt(
        self,
        skill: Optional[SkillInfo],
        facts_context: List[Any],
        all_skills: Optional[List[SkillInfo]] = None,
        draft_content: Optional[str] = None,
    ) -> str:
        """Build a high-quality system prompt including skill info and project facts."""
        parts = [
            "你是 NextAgent Doc Assistant，一个专业的智能文档编写助手。",
            "你的职责是帮助软件工程师和产品经理高效地创建和维护项目文档。",
            "",
            "## 工作原则",
            "- 所有输出使用中文，语言专业、清晰、简洁",
            "- 文档内容严格基于用户提供的需求和项目信息",
            "- 不要凭空捏造技术细节，不确定时应向用户询问",
            "- 文档格式遵循 Markdown 规范，层次结构清晰",
            "",
        ]

        # Always list all available skills so LLM knows what it can do
        if all_skills:
            parts += ["## 我具备的 Skill（文档编写能力）"]
            for s in all_skills:
                parts.append(f"- **{s.name}** (`{s.id}`)：{s.description}")
            parts += [
                "",
                "当用户询问你有哪些能力或技能时，必须根据以上 Skill 列表如实回答，不要凭空扩展。",
                "",
            ]
        else:
            parts += [
                "## 当前没有加载任何 Skill",
                "当用户询问技能时，告知暂无可用 Skill，请管理员在 skills 目录中添加。",
                "",
            ]

        if skill:
            parts += [
                "## 当前激活的 Skill",
                f"Skill ID: `{skill.id}`  名称: **{skill.name}**",
                "",
            ]
            if skill.content:
                parts += [
                    "以下是该 Skill 的完整执行指令，请严格遵循：",
                    "",
                    skill.content,
                    "",
                ]
            else:
                parts += [
                    f"描述：{skill.description}",
                    f"能力范围：{', '.join(skill.capabilities)}",
                    "",
                    "请严格按照该 Skill 的规范生成文档内容。",
                    "",
                ]

        if facts_context:
            parts += ["## 项目事实信息（请基于此内容编写文档，不要虚构）"]
            for item in facts_context:
                if isinstance(item, dict):
                    name = item.get("vocab", "")
                    content = item.get("content", "")
                else:
                    name = item.metadata.name if hasattr(item, "metadata") else ""
                    content = item.content if hasattr(item, "content") else str(item)
                parts += [f"### {name}", content[:2000], ""]

        if draft_content:
            parts += [
                "## 当前草稿（修改基准）",
                "",
                draft_content,
                "",
            ]

        if draft_content:
            # Modify mode: explanation visible to user, document extracted as next draft
            parts += [
                "## 响应格式要求（修改模式）",
                "- 先用 1-3 句话简述你对本次修改意图的理解（纯文字，不要使用任何 # 标题）",
                "- 紧接着输出修改后的完整文档正文，文档从 # 一级标题开始",
                "- 严格保留草稿中所有未被本次修改涉及的章节和内容，不得增删未提及的部分",
                "- 不要在文档正文之前插入任何 # 标题或 Markdown 分隔线",
            ]
        else:
            parts += [
                "## 响应格式要求",
                "- 若用户要求编写文档，直接输出完整的 Markdown 文档内容",
                "- 若生成的是完整文档，在文档末尾注明文档类型（如：<!-- doc_type: requirements -->）",
                "- 若需要澄清信息，先提问，再等待用户回复后再生成文档",
            ]

        return "\n".join(parts)

    async def get_available_skills(self) -> List[SkillInfo]:
        """Get all available skills."""
        if not self._skill_manager:
            return []
        return await self._skill_manager.get_all_skills()

    async def get_skill(self, skill_id: str) -> Optional[SkillInfo]:
        """Get a specific skill by ID."""
        if not self._skill_manager:
            return None
        return await self._skill_manager.get_skill(skill_id)
