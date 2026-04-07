from prototype_parser.axure_enricher import enrich_axure_interactions
from prototype_parser.dom_extractor import extract_dom_facts
from prototype_parser.package_scanner import scan_prototype_packages
from prototype_parser.repository import PrototypeRepository, build_generated_prototypes
from prototype_parser.summary_builder import build_llm_summary


def test_scan_prototype_packages_detects_root_and_subdir_exports(tmp_path):
    facts_root = tmp_path / "project-facts"
    prototypes_root = facts_root / "prototypes"
    nested_root = prototypes_root / "axure-export"
    nested_root.mkdir(parents=True)

    (prototypes_root / "landing.html").write_text("<html><body>root</body></html>", encoding="utf-8")
    (nested_root / "index.html").write_text("<html><body>index</body></html>", encoding="utf-8")
    (nested_root / "列表页.html").write_text("<html><body>list</body></html>", encoding="utf-8")

    packages = scan_prototype_packages(prototypes_root)

    assert len(packages) == 2
    root_package = next(item for item in packages if item.package_id == "root-package")
    nested_package = next(item for item in packages if item.package_id == "axure-export")
    assert root_package.root_path == "prototypes"
    assert root_package.page_count == 1
    assert nested_package.root_path == "prototypes/axure-export"
    assert nested_package.entry_page == "index.html"
    assert nested_package.page_count == 1
    assert root_package.fingerprint.startswith("sha1:")
    assert nested_package.fingerprint.startswith("sha1:")


def test_dom_extraction_axure_enrichment_and_summary_builder_work_together():
    html = """
    <html>
      <head><title>资产管理</title></head>
      <body>
        <section aria-label="查询区域">
          <input placeholder="资产名称" />
          <button>查询</button>
          <button>导出</button>
        </section>
        <div role="dialog" aria-label="导出结果"></div>
        <div role="alert">导出成功</div>
        <table>
          <tr><th>资产编码</th><th>资产名称</th></tr>
        </table>
        <a href="detail.html">查看详情</a>
      </body>
    </html>
    """

    dom = extract_dom_facts(html)
    enriched = enrich_axure_interactions(dom)
    summary = build_llm_summary(
        "资产管理页面",
        dom["title"],
        "axure-export/资产管理页面.html",
        {
            "layout_sections": dom["layout_sections"],
            "elements": {
                "buttons": dom["buttons"],
                "inputs": dom["inputs"],
                "tables": dom["tables"],
                "tabs": dom["tabs"],
                "dialogs": dom["dialogs"],
                "links": [item["label"] for item in dom["links"]],
            },
            "visible_texts": dom["visible_texts"],
            "messages": dom["messages"],
            "interactions": enriched["interactions"],
        },
    )

    assert dom["title"] == "资产管理"
    assert dom["buttons"] == ["查询", "导出"]
    assert dom["inputs"] == ["资产名称"]
    assert dom["dialogs"] == ["导出结果"]
    assert "导出成功" in dom["messages"]
    assert dom["tables"][0]["columns"] == ["资产编码", "资产名称"]
    assert dom["links"] == [{"label": "查看详情", "href": "detail.html"}]
    assert "点击【查看详情】跳转到 detail.html" in enriched["interactions"]
    assert "点击【查询】触发对应操作" in enriched["interactions"]
    assert "标题：资产管理" in summary
    assert "按钮：查询、导出" in summary


def test_build_generated_prototypes_refreshes_only_when_fingerprint_changes(tmp_path):
    facts_root = tmp_path / "project-facts"
    prototypes_dir = facts_root / "prototypes" / "axure-export"
    prototypes_dir.mkdir(parents=True)

    (prototypes_dir / "index.html").write_text("<html><body>index</body></html>", encoding="utf-8")
    page_path = prototypes_dir / "资产管理页面.html"
    page_path.write_text(
        "<html><head><title>资产管理</title></head><body><button>查询</button></body></html>",
        encoding="utf-8",
    )

    first = build_generated_prototypes(facts_root)
    page_index_path = facts_root / "generated" / "prototypes" / "page-index.json"
    first_mtime = page_index_path.stat().st_mtime_ns

    second = build_generated_prototypes(facts_root)
    second_mtime = page_index_path.stat().st_mtime_ns

    assert first["packages"] == second["packages"]
    assert first["page_index"] == second["page_index"]
    assert first_mtime == second_mtime

    page_path.write_text(
        "<html><head><title>资产管理</title></head><body><button>查询</button><button>导出</button></body></html>",
        encoding="utf-8",
    )

    third = build_generated_prototypes(facts_root)
    third_mtime = page_index_path.stat().st_mtime_ns
    repo = PrototypeRepository(facts_root)
    page = repo.get_page("资产管理页面")

    assert third_mtime >= second_mtime
    assert third["packages"] != second["packages"]
    assert page is not None
    assert "导出" in page["elements"]["buttons"]
