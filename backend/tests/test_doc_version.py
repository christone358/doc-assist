"""
单元测试 - 文档版本管理
"""

import asyncio
import json
from pathlib import Path

import pytest

from doc_version_service import DocumentVersionService, VersionRef


@pytest.fixture
def svc(tmp_path):
    return DocumentVersionService(
        docs_root=tmp_path / "doc_output",
        legacy_docs_roots=[tmp_path / "backend" / "docs"],
    )


def test_save_first_version_under_doc_output(svc):
    """第一次保存应落到 doc_output 并得到 v1.0.0"""
    ref = asyncio.run(
        svc.save_document(
            "# 文档内容",
            doc_type="requirements",
            doc_name="LLM集成管理模块需求规格说明书",
            force_date="2026-01-01",
        )
    )
    assert ref.version == "1.0.0"
    assert ref.date == "2026-01-01"
    assert ref.relative_path.endswith("requirements/LLM集成管理模块/2026-01-01/v1.0.0.md")
    assert ref.doc_name == "LLM集成管理模块"


def test_same_day_increments_patch(svc):
    """同天第二次保存应递增修订号"""
    asyncio.run(svc.save_document("v1", doc_type="req", doc_name="文档A需求规格说明书", force_date="2026-01-01"))
    ref = asyncio.run(svc.save_document("v2", doc_type="requirements", doc_name="文档A", force_date="2026-01-01"))
    assert ref.version == "1.0.1"
    assert ref.doc_type == "requirements"


def test_cross_day_resets_to_v1(svc):
    """跨天保存应从 v1.0.0 重新开始"""
    asyncio.run(svc.save_document("day1", doc_type="req", doc_name="文档A", force_date="2026-01-01"))
    asyncio.run(svc.save_document("day1b", doc_type="req", doc_name="文档A", force_date="2026-01-01"))
    ref = asyncio.run(svc.save_document("day2", doc_type="req", doc_name="文档A", force_date="2026-01-02"))
    assert ref.version == "1.0.0"
    assert ref.date == "2026-01-02"


def test_load_latest_uses_alias_resolution(svc):
    """load_latest 应能识别同一对象的不同描述"""
    asyncio.run(
        svc.save_document(
            "v1",
            doc_type="requirements",
            doc_name="LLM 集成管理模块需求规格说明书",
            force_date="2026-01-01",
        )
    )
    asyncio.run(
        svc.save_document(
            "v2",
            doc_type="requirements",
            doc_name="LLM集成管理模块",
            force_date="2026-01-01",
        )
    )

    result = asyncio.run(svc.load_latest(doc_type="requirements", doc_name="LLM集成模块需求文档"))
    assert result is not None
    content, ref = result
    assert content == "v2"
    assert ref.version == "1.0.1"
    assert ref.doc_name == "LLM集成管理模块"


def test_load_specific_version(svc):
    """load_version 应返回指定版本"""
    asyncio.run(svc.save_document("内容A", doc_type="req", doc_name="文档A", force_date="2026-01-01"))
    asyncio.run(svc.save_document("内容B", doc_type="req", doc_name="文档A", force_date="2026-01-01"))

    result = asyncio.run(
        svc.load_version(doc_type="requirements", doc_name="文档A需求规格说明书", date="2026-01-01", version="1.0.0")
    )
    assert result is not None
    content, ref = result
    assert content == "内容A"
    assert ref.doc_name == "文档A"


def test_load_nonexistent_returns_none(svc):
    """加载不存在的文档应返回 None"""
    result = asyncio.run(svc.load_latest(doc_type="req", doc_name="nonexistent"))
    assert result is None


def test_list_versions_reads_legacy_and_new_roots(svc, tmp_path):
    """版本历史应兼容 legacy 根目录并与新目录合并展示"""
    legacy_root = tmp_path / "backend" / "docs"
    legacy_file = legacy_root / "requirements" / "LLM集成管理模块需求规格说明书" / "2026-01-01" / "v1.0.0.md"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_text("legacy", encoding="utf-8")

    asyncio.run(
        svc.save_document(
            "new",
            doc_type="requirements",
            doc_name="LLM集成管理模块",
            force_date="2026-01-02",
        )
    )

    versions = asyncio.run(svc.list_versions(doc_type="requirements", doc_name="LLM集成模块需求规格说明书"))
    assert len(versions) == 2
    assert versions[0].version == "1.0.0"
    assert versions[-1].date == "2026-01-02"


def test_list_documents_returns_canonical_doc_type_labels(svc):
    """list_documents 应返回归一后的类型和展示标签"""
    asyncio.run(svc.save_document("A", doc_type="req", doc_name="模块A需求规格说明书", force_date="2026-01-01"))
    asyncio.run(svc.save_document("B", doc_type="test", doc_name="模块A测试方案", force_date="2026-01-01"))
    asyncio.run(svc.save_document("C", doc_type="user-guide", doc_name="模块A用户手册", force_date="2026-01-01"))

    docs = asyncio.run(svc.list_documents())
    doc_types = {d["doc_type"] for d in docs}
    assert {"requirements", "test-plan", "user-manual"}.issubset(doc_types)

    req_doc = next(d for d in docs if d["doc_type"] == "requirements")
    assert req_doc["doc_type_label"] == "需求规格"
    assert req_doc["doc_name"] == "模块A"


def test_meta_file_created_with_aliases(svc):
    """保存文档时应创建包含 aliases 的 .meta.json 文件"""
    ref = asyncio.run(
        svc.save_document(
            "内容",
            doc_type="req",
            doc_name="文档A需求规格说明书",
            conversation_id="conv-123",
            force_date="2026-01-01",
        )
    )
    meta_path = ref.file_path.with_suffix(".meta.json")
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["conversation_id"] == "conv-123"
    assert meta["version"] == "1.0.0"
    assert "文档A" in meta["aliases"]


def test_relative_path_prefers_project_relative(tmp_path):
    """relative_path 应优先返回 project 相对路径，测试路径下回退到 docs_root 相对路径"""
    ref = VersionRef(
        docs_root=tmp_path / "doc_output",
        doc_type="req",
        doc_name="doc",
        date="2026-01-01",
        version="1.0.0",
        file_path=tmp_path / "doc_output" / "req" / "doc" / "2026-01-01" / "v1.0.0.md",
    )
    assert "req/doc/2026-01-01/v1.0.0.md" in ref.relative_path
