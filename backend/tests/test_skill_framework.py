"""
集成测试 - Skill 框架
"""
import pytest
from pathlib import Path
import tempfile, os, textwrap


@pytest.fixture
def skills_dir(tmp_path):
    """创建一个包含有效 Skill 的临时目录"""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()

    skill_md = skill_dir / "skill.md"
    skill_md.write_text(textwrap.dedent("""
        # 测试Skill

        ```yaml
        Skill Name: 测试文档Skill
        Description: 用于单元测试的示例Skill
        Type: test
        Version: 1.0.0
        Tags:
          - 测试
          - 示例
        Capabilities:
          - 自动化测试文档编写
          - 测试用例生成
        ```

        ## 概述
        这是一个测试用的Skill。
    """).strip())

    (scripts_dir / "main.py").write_text("def handle_request(context): return {}")

    return tmp_path


@pytest.mark.asyncio
async def test_skill_discovery(skills_dir):
    """测试 Skill 自动发现"""
    from skill.manager import SkillManager
    mgr = SkillManager(skills_dir=str(skills_dir))
    await mgr.discover_and_load()

    skills = await mgr.get_all_skills()
    assert len(skills) == 1
    assert skills[0].name == "测试文档Skill"


@pytest.mark.asyncio
async def test_skill_metadata_parsed(skills_dir):
    """测试 Skill 元数据解析"""
    from skill.manager import SkillManager
    mgr = SkillManager(skills_dir=str(skills_dir))
    await mgr.discover_and_load()

    skill = await mgr.get_skill("test-skill")
    assert skill is not None
    assert skill.type == "test"
    assert "自动化测试文档编写" in skill.capabilities


@pytest.mark.asyncio
async def test_invalid_skill_skipped(skills_dir):
    """测试无效 Skill 被跳过（缺少 skill.md）"""
    bad_skill = skills_dir / "no-skill-md"
    bad_skill.mkdir()

    from skill.manager import SkillManager
    mgr = SkillManager(skills_dir=str(skills_dir))
    await mgr.discover_and_load()

    skills = await mgr.get_all_skills()
    assert all(s.id != "no-skill-md" for s in skills)


@pytest.mark.asyncio
async def test_empty_skills_dir():
    """测试空 Skill 目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        from skill.manager import SkillManager
        mgr = SkillManager(skills_dir=tmpdir)
        await mgr.discover_and_load()
        skills = await mgr.get_all_skills()
        assert skills == []


@pytest.mark.asyncio
async def test_skill_reload(skills_dir):
    """测试 Skill 重新加载"""
    from skill.manager import SkillManager
    mgr = SkillManager(skills_dir=str(skills_dir))
    await mgr.discover_and_load()

    # 添加一个新 Skill
    new_skill = skills_dir / "new-skill"
    new_skill.mkdir()
    (new_skill / "skill.md").write_text(textwrap.dedent("""
        ```yaml
        Skill Name: 新Skill
        Description: 新增的Skill
        Type: new
        ```
    """).strip())

    await mgr.reload()
    skills = await mgr.get_all_skills()
    assert any(s.name == "新Skill" for s in skills)
