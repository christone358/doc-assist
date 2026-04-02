"""
单元测试 - Agent 核心功能
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def agent():
    from agent.core import AgentCore
    AgentCore._instance = None  # Reset singleton for each test
    return AgentCore.get_instance()


@pytest.mark.asyncio
async def test_identify_intent_new_document(agent):
    """测试新增文档意图识别"""
    intent = await agent._identify_intent("帮我编写一份需求规格文档", None)
    assert intent["intent_type"] == "new_document"
    assert intent["document_type"] == "requirements"


@pytest.mark.asyncio
async def test_identify_intent_modify(agent):
    """测试修改意图识别"""
    intent = await agent._identify_intent("修改第三章的设计方案", None)
    assert intent["intent_type"] == "modify_document"


@pytest.mark.asyncio
async def test_identify_intent_query(agent):
    """测试查询意图识别"""
    intent = await agent._identify_intent("列出所有已有的文档", None)
    assert intent["intent_type"] == "query"


@pytest.mark.asyncio
async def test_identify_intent_default(agent):
    """测试默认意图（无明确关键词）"""
    intent = await agent._identify_intent("用户登录功能", None)
    assert intent["intent_type"] == "new_document"


@pytest.mark.asyncio
async def test_identify_intent_with_context(agent):
    """测试带历史的意图识别"""
    mock_conv = MagicMock()
    mock_conv.rounds = [MagicMock()]  # 有历史记录
    intent = await agent._identify_intent("好的继续", mock_conv)
    assert intent["intent_type"] in ("new_document", "modify_document", "query", "other")


@pytest.mark.asyncio
async def test_recommend_facts_no_service(agent):
    """测试事实服务未初始化时返回空列表"""
    agent._fact_service = None
    results = await agent._recommend_facts("测试消息", {})
    assert results == []


@pytest.mark.asyncio
async def test_select_skill_no_skills(agent):
    """测试无 Skill 时返回 None"""
    agent._skill_manager = MagicMock()
    agent._skill_manager.get_all_skills = AsyncMock(return_value=[])
    result = await agent._select_skill("帮我写文档", {"intent_type": "new_document"})
    assert result is None


@pytest.mark.asyncio
async def test_select_skill_matches_capability(agent):
    """测试 Skill 能力关键词匹配"""
    from agent.models import SkillInfo
    mock_skill = SkillInfo(
        id="write-requirements",
        name="需求文档Skill",
        description="编写需求规格文档",
        type="requirements",
        capabilities=["需求", "规格", "用例"],
    )
    agent._skill_manager = MagicMock()
    agent._skill_manager.get_all_skills = AsyncMock(return_value=[mock_skill])

    result = await agent._select_skill("帮我写一份需求文档", {"intent_type": "new_document", "document_type": "requirements"})
    assert result is not None
    assert result.id == "write-requirements"


def test_build_system_prompt_basic(agent):
    """测试基础系统提示词构建"""
    prompt = agent._build_system_prompt(skill=None, facts_context=[])
    assert "NextAgent Doc Assistant" in prompt
    assert "中文" in prompt


def test_build_system_prompt_with_skill(agent):
    """测试带 Skill 的系统提示词"""
    from agent.models import SkillInfo
    skill = SkillInfo(
        id="test",
        name="测试Skill",
        description="测试描述",
        type="test",
        capabilities=["测试能力"],
    )
    prompt = agent._build_system_prompt(skill=skill, facts_context=[])
    assert "测试Skill" in prompt
    assert "测试能力" in prompt
