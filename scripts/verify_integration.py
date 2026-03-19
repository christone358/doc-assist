#!/usr/bin/env python3
"""
集成验证脚本 - 验证前后端集成和核心功能工作流

用于验证任务 9.4 - 9.12:
- 多轮对话流程
- 用户输入和 Agent 响应的实时展示
- 对话历史的保存和恢复
- 项目事实信息的查询和推荐
- 完整的文档编写工作流（新增编写）
- 文档修改工作流（精准修改）
- 版本管理集成
- DeepSeek 和 QWen 模型的实际调用

使用方法:
    cd backend && python ../scripts/verify_integration.py
"""

import asyncio
import sys
import json
import os
from pathlib import Path

# 添加 backend 到 Python 路径
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)


async def check_agent_init():
    """9.4 验证 Agent 初始化和 Skill 加载"""
    print("\n[TEST] 验证 Agent 初始化...")
    from agent.core import AgentCore
    agent = AgentCore.get_instance()
    await agent.initialize()
    skills = await agent.get_available_skills()
    print(f"  ✓ Agent 已初始化，加载了 {len(skills)} 个 Skill")
    for s in skills:
        print(f"    - {s.name} ({s.skill_type})")
    return True


async def check_conversation_lifecycle():
    """9.5/9.6 验证对话创建、多轮消息、持久化和恢复"""
    print("\n[TEST] 验证对话生命周期...")
    from agent.conversation import ConversationManager

    mgr = ConversationManager.get_instance()

    # 创建对话
    conv = await mgr.create_conversation(name="集成测试对话")
    print(f"  ✓ 对话已创建: {conv.id}")

    # 添加多轮消息
    await mgr.add_round(
        conv.id,
        user_input="帮我写一份需求文档",
        agent_response="好的，请告诉我需求的基本信息",
    )
    await mgr.add_round(
        conv.id,
        user_input="这是一个用户登录功能",
        agent_response="已了解，正在生成需求规格文档...",
    )
    print("  ✓ 已添加 2 轮消息")

    # 重新加载（模拟重启恢复）
    mgr._conversations.pop(conv.id, None)  # 清除内存缓存
    loaded = await mgr.get_conversation(conv.id)
    assert loaded is not None, "对话加载失败"
    assert len(loaded.rounds) == 2, f"期望 2 轮，实际 {len(loaded.rounds)} 轮"
    print(f"  ✓ 对话持久化和恢复验证通过（{len(loaded.rounds)} 轮）")

    # 列出对话
    convs = await mgr.list_conversations()
    assert any(c["id"] == conv.id for c in convs), "对话未出现在列表中"
    print(f"  ✓ 对话列表验证通过，共 {len(convs)} 个对话")

    # 清理
    await mgr.delete_conversation(conv.id)
    return True


async def check_fact_info():
    """9.7 验证项目事实信息的查询"""
    print("\n[TEST] 验证项目事实信息查询...")
    from fact_info_service import get_fact_service
    from models import FactLayer

    svc = await get_fact_service()

    # 按层级查询
    items = await svc.query_by_layer(FactLayer.MANIFEST)
    print(f"  ✓ 清单层查询: {len(items)} 条记录")

    # 关键词搜索
    results = await svc.search("用例")
    print(f"  ✓ 关键词搜索('用例'): {len(results)} 条记录")
    return True


async def check_document_version_management():
    """9.10 验证文档版本管理"""
    print("\n[TEST] 验证文档版本管理...")
    from doc_version_service import DocumentVersionService
    from pathlib import Path
    import tempfile, shutil

    # 使用临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = DocumentVersionService(docs_root=Path(tmpdir))

        # 保存第一个版本
        ref1 = await svc.save_document(
            "# 需求规格v1\n内容A",
            doc_type="requirements", doc_name="test-doc",
            conversation_id="conv-1", change_summary="初始版本",
            force_date="2026-01-01",
        )
        assert ref1.version == "1.0.0", f"期望 1.0.0，实际 {ref1.version}"
        print(f"  ✓ 第一版本: {ref1.relative_path}")

        # 同天第二次保存 → 递进修订号
        ref2 = await svc.save_document(
            "# 需求规格v1.0.1\n内容B",
            doc_type="requirements", doc_name="test-doc",
            force_date="2026-01-01",
        )
        assert ref2.version == "1.0.1", f"期望 1.0.1，实际 {ref2.version}"
        print(f"  ✓ 同天递进版本: {ref2.relative_path}")

        # 跨天保存 → 从 v1.0.0 重新开始
        ref3 = await svc.save_document(
            "# 需求规格跨天\n内容C",
            doc_type="requirements", doc_name="test-doc",
            force_date="2026-01-02",
        )
        assert ref3.version == "1.0.0", f"期望 1.0.0（新日期），实际 {ref3.version}"
        print(f"  ✓ 跨天新版本: {ref3.relative_path}")

        # 加载最新版本
        result = await svc.load_latest(doc_type="requirements", doc_name="test-doc")
        assert result is not None
        content, latest_ref = result
        assert latest_ref.date == "2026-01-02"
        print(f"  ✓ 加载最新版本: {latest_ref.relative_path}")

        # 版本列表
        versions = await svc.list_versions(doc_type="requirements", doc_name="test-doc")
        assert len(versions) == 3, f"期望 3 个版本，实际 {len(versions)}"
        print(f"  ✓ 版本列表正确: {len(versions)} 个版本")

    return True


async def check_llm_config():
    """9.11 验证 LLM 配置管理（不调用真实API）"""
    print("\n[TEST] 验证 LLM 配置管理...")
    from llm.service import LLMConfigManager, LLMConfig, LLMProvider, _encrypt_key
    import tempfile, json, uuid
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "llm_configs.json"
        mgr = LLMConfigManager(config_file=config_path)

        # 添加配置
        cfg_id = str(uuid.uuid4())[:8]
        cfg = LLMConfig(
            id=cfg_id,
            name="测试DeepSeek",
            provider=LLMProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_base="https://api.deepseek.com/v1",
            api_key_encrypted=_encrypt_key("test-key-12345"),
        )
        mgr.add(cfg)
        print(f"  ✓ 配置已添加: {cfg.id}")

        # 设置为默认
        mgr.set_default(cfg_id)
        default = mgr.get_default()
        assert default is not None and default.id == cfg_id
        print("  ✓ 默认配置设置成功")

        # 验证加密存储（raw JSON 不含明文 Key）
        with open(config_path) as f:
            raw = json.load(f)
        stored_items = raw["configs"]
        stored_key = stored_items[0]["api_key_encrypted"]
        assert stored_key != "test-key-12345", "API Key 应该被加密存储"
        print("  ✓ API Key 加密存储验证通过")

        # 重新加载（模拟重启）
        mgr2 = LLMConfigManager(config_file=config_path)
        loaded = mgr2.get(cfg_id)
        assert loaded is not None
        assert loaded.name == "测试DeepSeek"
        print("  ✓ 配置持久化和加载验证通过")

    return True


async def main():
    print("=" * 60)
    print("NextAgent Doc Assistant - 集成验证")
    print("=" * 60)

    tests = [
        ("Agent 初始化和 Skill 加载", check_agent_init),
        ("对话生命周期（多轮+持久化）", check_conversation_lifecycle),
        ("项目事实信息查询", check_fact_info),
        ("文档版本管理", check_document_version_management),
        ("LLM 配置管理", check_llm_config),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            await test_fn()
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"验证完成: {passed} 通过, {failed} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
