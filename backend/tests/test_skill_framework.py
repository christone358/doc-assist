"""
集成测试 - Skill 框架
"""

import tempfile
import textwrap

import pytest


@pytest.fixture
def skills_dir(tmp_path):
    """创建一个包含有效 Skill 的临时目录"""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    templates_dir = skill_dir / "templates"
    templates_dir.mkdir()
    references_dir = skill_dir / "references"
    references_dir.mkdir()

    skill_md = skill_dir / "skill.md"
    skill_md.write_text(textwrap.dedent("""
        ---
        name: test-skill
        description: 用于单元测试的示例Skill
        type: test
        version: 1.0.0
        tags:
          - 测试
          - 示例
        capabilities:
          - 自动化测试文档编写
          - 测试用例生成
        ---

        # 测试Skill

        ## 概述
        这是一个测试用的Skill。
    """).strip())

    (scripts_dir / "main.py").write_text("def handle_request(context): return {}")
    (templates_dir / "template.md").write_text("# template")
    (references_dir / "guide.md").write_text("# guide")
    (skill_dir / "notes.txt").write_text("note")
    (skill_dir / ".hidden.txt").write_text("hidden")

    return tmp_path


@pytest.mark.asyncio
async def test_skill_discovery(skills_dir):
    """测试 Skill 自动发现"""
    from skill.manager import SkillManager

    mgr = SkillManager(skills_dir=str(skills_dir))
    await mgr.discover_and_load()

    skills = await mgr.get_all_skills()
    assert len(skills) == 1
    assert skills[0].name == "test-skill"


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
    assert skill.skill_md_path is not None
    assert not hasattr(skill, "tags")


@pytest.mark.asyncio
async def test_skill_resources_scanned_and_tags_ignored(skills_dir):
    """测试 Skill 资源扫描和 legacy tags 忽略。"""
    from skill.manager import SkillManager

    mgr = SkillManager(skills_dir=str(skills_dir))
    await mgr.discover_and_load()

    skill = await mgr.get_skill("test-skill")
    assert skill is not None
    assert [(resource.category, resource.path) for resource in skill.resources] == [
        ("other", "notes.txt"),
        ("reference", "references/guide.md"),
        ("script", "scripts/main.py"),
        ("template", "templates/template.md"),
    ]


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

    new_skill = skills_dir / "new-skill"
    new_skill.mkdir()
    (new_skill / "skill.md").write_text(textwrap.dedent("""
        ---
        name: 新Skill
        description: 新增的Skill
        type: new
        ---
    """).strip())

    await mgr.reload()
    skills = await mgr.get_all_skills()
    assert any(s.name == "新Skill" for s in skills)


@pytest.mark.asyncio
async def test_skill_without_resources_returns_empty_list(tmp_path):
    """测试无资源 Skill 返回空资源列表。"""
    skill_dir = tmp_path / "plain-skill"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text(textwrap.dedent("""
        ---
        name: plain-skill
        description: 无资源 Skill
        type: general
        ---
    """).strip())

    from skill.manager import SkillManager

    mgr = SkillManager(skills_dir=str(tmp_path))
    await mgr.discover_and_load()

    skill = await mgr.get_skill("plain-skill")
    assert skill is not None
    assert skill.resources == []
