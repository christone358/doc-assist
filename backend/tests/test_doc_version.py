"""
单元测试 - 文档版本管理
"""
import pytest
from pathlib import Path
from doc_version_service import DocumentVersionService


@pytest.fixture
def svc(tmp_path):
    return DocumentVersionService(docs_root=tmp_path)


@pytest.mark.asyncio
async def test_save_first_version(svc):
    """第一次保存应得到 v1.0.0"""
    ref = await svc.save_document(
        "# 文档内容",
        doc_type="requirements", doc_name="test",
        force_date="2026-01-01",
    )
    assert ref.version == "1.0.0"
    assert ref.date == "2026-01-01"


@pytest.mark.asyncio
async def test_same_day_increments_patch(svc):
    """同天第二次保存应递增修订号"""
    await svc.save_document("v1", doc_type="req", doc_name="doc", force_date="2026-01-01")
    ref = await svc.save_document("v2", doc_type="req", doc_name="doc", force_date="2026-01-01")
    assert ref.version == "1.0.1"


@pytest.mark.asyncio
async def test_cross_day_resets_to_v1(svc):
    """跨天保存应从 v1.0.0 重新开始"""
    await svc.save_document("day1", doc_type="req", doc_name="doc", force_date="2026-01-01")
    await svc.save_document("day1b", doc_type="req", doc_name="doc", force_date="2026-01-01")
    ref = await svc.save_document("day2", doc_type="req", doc_name="doc", force_date="2026-01-02")
    assert ref.version == "1.0.0"
    assert ref.date == "2026-01-02"


@pytest.mark.asyncio
async def test_load_latest(svc):
    """load_latest 应返回最新版本"""
    await svc.save_document("v1", doc_type="req", doc_name="doc", force_date="2026-01-01")
    await svc.save_document("v2", doc_type="req", doc_name="doc", force_date="2026-01-01")
    result = await svc.load_latest(doc_type="req", doc_name="doc")
    assert result is not None
    content, ref = result
    assert content == "v2"
    assert ref.version == "1.0.1"


@pytest.mark.asyncio
async def test_load_specific_version(svc):
    """load_version 应返回指定版本"""
    await svc.save_document("内容A", doc_type="req", doc_name="doc", force_date="2026-01-01")
    await svc.save_document("内容B", doc_type="req", doc_name="doc", force_date="2026-01-01")

    result = await svc.load_version(doc_type="req", doc_name="doc", date="2026-01-01", version="1.0.0")
    assert result is not None
    content, ref = result
    assert content == "内容A"


@pytest.mark.asyncio
async def test_load_nonexistent_returns_none(svc):
    """加载不存在的文档应返回 None"""
    result = await svc.load_latest(doc_type="req", doc_name="nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_list_versions(svc):
    """list_versions 应按时间顺序返回所有版本"""
    await svc.save_document("v1", doc_type="req", doc_name="doc", force_date="2026-01-01")
    await svc.save_document("v2", doc_type="req", doc_name="doc", force_date="2026-01-01")
    await svc.save_document("v3", doc_type="req", doc_name="doc", force_date="2026-01-02")

    versions = await svc.list_versions(doc_type="req", doc_name="doc")
    assert len(versions) == 3
    assert versions[0].version == "1.0.0"
    assert versions[-1].date == "2026-01-02"


@pytest.mark.asyncio
async def test_list_documents(svc):
    """list_documents 应返回文档摘要列表"""
    await svc.save_document("A", doc_type="req", doc_name="doc1", force_date="2026-01-01")
    await svc.save_document("B", doc_type="design", doc_name="doc2", force_date="2026-01-01")

    docs = await svc.list_documents()
    assert len(docs) == 2
    doc_types = {d["doc_type"] for d in docs}
    assert "req" in doc_types
    assert "design" in doc_types


@pytest.mark.asyncio
async def test_meta_file_created(svc, tmp_path):
    """保存文档时应创建 .meta.json 文件"""
    ref = await svc.save_document(
        "内容",
        doc_type="req", doc_name="doc",
        conversation_id="conv-123",
        force_date="2026-01-01",
    )
    meta_path = ref.file_path.with_suffix(".meta.json")
    assert meta_path.exists()

    import json
    meta = json.loads(meta_path.read_text())
    assert meta["conversation_id"] == "conv-123"
    assert meta["version"] == "1.0.0"


def test_relative_path(svc, tmp_path):
    """relative_path 应相对于 docs_root"""
    from doc_version_service import VersionRef
    ref = VersionRef(
        doc_type="req", doc_name="doc",
        date="2026-01-01", version="1.0.0",
        file_path=tmp_path / "req" / "doc" / "2026-01-01" / "v1.0.0.md",
    )
    assert "req/doc/2026-01-01/v1.0.0.md" in ref.relative_path
