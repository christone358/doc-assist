#!/usr/bin/env python3
"""
将业务系统管理模块用户手册转换为专业的Word文档(.docx格式)
使用docx库创建包含封面、目录、页眉页脚、页码等标准元素的文档
"""

import json
import sys
import os
from datetime import datetime
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def create_docx_from_content(content_text, output_path):
    """
    从文本内容创建专业的Word文档
    
    Args:
        content_text: 用户手册的文本内容
        output_path: 输出DOCX文件路径
    """
    
    # 创建文档对象
    doc = Document()
    
    # 设置文档默认字体
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(12)
    
    # 设置标题样式
    heading1 = doc.styles['Heading 1']
    heading1.font.name = 'Arial'
    heading1.font.size = Pt(16)
    heading1.font.bold = True
    
    heading2 = doc.styles['Heading 2']
    heading2.font.name = 'Arial'
    heading2.font.size = Pt(14)
    heading2.font.bold = True
    
    heading3 = doc.styles['Heading 3']
    heading3.font.name = 'Arial'
    heading3.font.size = Pt(12)
    heading3.font.bold = True
    
    # 添加封面页
    doc.add_heading('业务系统管理模块', 0)
    doc.add_paragraph('用户手册')
    doc.add_paragraph()
    doc.add_paragraph(f'版本: v1.0.1')
    doc.add_paragraph(f'日期: {datetime.now().strftime("%Y年%m月%d日")}')
    doc.add_paragraph()
    doc.add_paragraph('业务保障管理系统')
    doc.add_paragraph('业务资产管理子系统')
    
    # 添加分页符
    doc.add_page_break()
    
    # 添加目录页
    doc.add_heading('目录', 1)
    
    # 解析内容并添加到文档
    lines = content_text.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 判断标题级别
        if line.startswith('# '):
            # 一级标题
            title = line[2:].strip()
            doc.add_heading(title, 1)
            current_section = title
        elif line.startswith('## '):
            # 二级标题
            title = line[3:].strip()
            doc.add_heading(title, 2)
        elif line.startswith('### '):
            # 三级标题
            title = line[4:].strip()
            doc.add_heading(title, 3)
        elif line.startswith('- ') or line.startswith('* '):
            # 列表项
            item = line[2:].strip()
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(item)
        elif line.startswith('1. ') or line.startswith('2. ') or line.startswith('3. '):
            # 编号列表项
            item = line[3:].strip()
            p = doc.add_paragraph(style='List Number')
            p.add_run(item)
        else:
            # 普通段落
            if line and not line.startswith('```') and not line.endswith('```'):
                doc.add_paragraph(line)
    
    # 添加页眉页脚
    add_header_footer(doc)
    
    # 保存文档
    doc.save(output_path)
    print(f"文档已保存到: {output_path}")

def add_header_footer(doc):
    """
    为文档添加页眉和页脚
    
    Args:
        doc: Document对象
    """
    
    # 获取所有节
    sections = doc.sections
    
    for section in sections:
        # 添加页眉
        header = section.header
        header_para = header.paragraphs[0]
        header_para.text = "业务系统管理模块用户手册"
        header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 添加页脚
        footer = section.footer
        footer_para = footer.paragraphs[0]
        footer_para.text = "第 \t 页"
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 添加页码字段
        add_page_number(footer_para)

def add_page_number(paragraph):
    """
    在段落中添加页码字段
    
    Args:
        paragraph: 段落对象
    """
    # 创建页码字段
    run = paragraph.add_run()
    fldChar = OxmlElement('w:fldChar')
    fldChar.set(qn('w:fldCharType'), 'begin')
    
    instrText = OxmlElement('w:instrText')
    instrText.text = "PAGE"
    
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'end')
    
    run._r.append(fldChar)
    run._r.append(instrText)
    run._r.append(fldChar2)

def main():
    """主函数"""
    
    # 检查参数
    if len(sys.argv) < 3:
        print("用法: python generate_docx.py <输入文件> <输出文件>")
        print("示例: python generate_docx.py content.txt 业务系统管理模块用户手册.docx")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 读取输入文件内容
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"错误: 找不到输入文件 {input_file}")
        sys.exit(1)
    
    # 创建DOCX文档
    create_docx_from_content(content, output_file)

if __name__ == "__main__":
    main()