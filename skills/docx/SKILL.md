---
name: docx
description: "当用户想要创建、读取、编辑或处理 Word 文档（.docx 文件）时使用本 skill。触发场景包括：任何提到“Word 文档”“word 文件”“.docx”，或要求生成带目录、标题、页码、信头等格式的专业文档。也适用于从 .docx 中提取或重组内容、在文档中插入或替换图片、对 Word 文件执行查找替换、处理修订痕迹或批注，或将内容整理成排版完善的 Word 文档。如果用户要求交付“报告”“备忘录”“信函”“模板”或类似成果，且目标是 Word / .docx 文件，也使用本 skill。不要用于 PDF、电子表格、Google Docs，或与文档生成无关的一般编码任务。"
type: general
---

# DOCX 创建、编辑与分析

## 概览

`.docx` 文件本质上是一个包含 XML 文件的 ZIP 压缩包。

## 快速参考

| 任务 | 方法 |
|------|------|
| 读取 / 分析内容 | `pandoc`，或解包后直接看原始 XML |
| 新建文档 | 使用 `docx-js`，见下方“创建新文档” |
| 编辑现有文档 | 解包 → 编辑 XML → 回包，见下方“编辑现有文档” |

### 将 `.doc` 转换为 `.docx`

旧版 `.doc` 文件在编辑前必须先转换：

```bash
python scripts/office/soffice.py --headless --convert-to docx document.doc
```

### 读取内容

```bash
# 提取文本，并保留修订痕迹
pandoc --track-changes=all document.docx -o output.md

# 访问原始 XML
python scripts/office/unpack.py document.docx unpacked/
```

### 转换为图片

```bash
python scripts/office/soffice.py --headless --convert-to pdf document.docx
pdftoppm -jpeg -r 150 document.pdf page
```

### 接受全部修订

如果要输出一个“已接受全部修订”的干净文档：

```bash
python scripts/accept_changes.py input.docx output.docx
```

本地脚本优先顺序：

- Windows：优先走 Microsoft Word COM 自动化
- macOS：优先走 Microsoft Word AppleScript 自动化
- Windows / Linux / macOS：若原生 Office 自动化不可用，则回退为纯 OpenXML 接受修订

---

## 创建新文档

先用 JavaScript 生成 `.docx`，再做校验。安装：`npm install -g docx`

### 基础准备

```javascript
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
        Header, Footer, AlignmentType, PageOrientation, LevelFormat, ExternalHyperlink,
        InternalHyperlink, Bookmark, FootnoteReferenceRun, PositionalTab,
        PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader,
        TabStopType, TabStopPosition, Column, SectionType,
        TableOfContents, HeadingLevel, BorderStyle, WidthType, ShadingType,
        VerticalAlign, PageNumber, PageBreak } = require('docx');

const doc = new Document({ sections: [{ children: [/* content */] }] });
Packer.toBuffer(doc).then(buffer => fs.writeFileSync("doc.docx", buffer));
```

### 校验

创建文件后必须校验。如果校验失败，就解包、修复 XML、再重新回包。

```bash
python scripts/office/validate.py doc.docx
```

### 页面尺寸

本项目不要使用官方示例中的 US Letter 默认值，而要显式对齐根目录模板 [软件设计模板.docx](/Users/chris/Documents/dev/nextAgent/skill-design/软件设计模板.docx) 的页面设置。

```javascript
// 关键：不要依赖 docx-js 的默认纸张
// 当前模板内嵌版式为 A4，并带指定页边距 / 页眉页脚距离
sections: [{
  properties: {
    page: {
      size: {
        width: 11906,   // A4 短边（DXA）
        height: 16838   // A4 长边（DXA）
      },
      margin: {
        top: 1440,
        right: 1800,
        bottom: 1440,
        left: 1800,
        header: 851,
        footer: 992
      }
    }
  },
  children: [/* content */]
}]
```

**当前模板版式参数（DXA，1440 DXA = 1 英寸）：**

| 项目 | 数值 |
|------|------|
| 纸张 | A4 |
| 宽 | 11,906 |
| 高 | 16,838 |
| 上边距 | 1,440 |
| 下边距 | 1,440 |
| 左边距 | 1,800 |
| 右边距 | 1,800 |
| 页眉距离 | 851 |
| 页脚距离 | 992 |
| 正文可用宽度 | 8,306 |

**横向页面：** 仍按 `docx-js` 的规则传入纵向尺寸，再让库内部交换宽高：

```javascript
size: {
  width: 11906,   // 传短边
  height: 16838,  // 传长边
  orientation: PageOrientation.LANDSCAPE
},
```

### 样式

本项目不要再用官方示例里的 Arial 通用样式覆盖方案。所有页面、标题、正文、图表、表格文本都要以 [软件设计模板.docx](/Users/chris/Documents/dev/nextAgent/skill-design/软件设计模板.docx) 中已经嵌入的样式为准。

**优先规则：**

1. 优先复制 / 编辑模板文档，不要从空白文档重新造一套“看起来差不多”的样式。
2. 新增段落时优先使用模板真实 `styleId`，不要自创同名样式。
3. 标题层级必须沿用模板里的 1 到 9 级编号与 `outlineLevel`。
4. 正文、表格文字、图片、图表名，必须分别使用模板中的专用样式。

```javascript
// 关键：这里不要再使用通用 Arial + Heading1/Heading2 方案
// 本模板中应直接使用真实 styleId
new Paragraph({ style: "1", children: [new TextRun("一级标题")] })      // 001QAX标题1
new Paragraph({ style: "2", children: [new TextRun("二级标题")] })      // 002QAX标题2
new Paragraph({ style: "3", children: [new TextRun("三级标题")] })      // 003QAX标题3
new Paragraph({ style: "4", children: [new TextRun("四级标题")] })      // 004QAX标题4
new Paragraph({ style: "5", children: [new TextRun("五级标题")] })      // 005QAX标题5
new Paragraph({ style: "6", children: [new TextRun("六级标题")] })      // 006QAX标题6
new Paragraph({ style: "7", children: [new TextRun("七级标题")] })      // 007QAX标题7
new Paragraph({ style: "8", children: [new TextRun("八级标题")] })      // 008QAX标题8
new Paragraph({ style: "9", children: [new TextRun("九级标题")] })      // 009QAX标题9
new Paragraph({ style: "077-0", children: [new TextRun("正文内容")] })  // 077-正文格式
new Paragraph({ style: "077-", children: [new TextRun("表格文字")] })   // 077-表格文字
new Paragraph({ style: "007-", children: [new TextRun("图像段落")] })   // 007-图片
new Paragraph({ style: "001QAX", children: [new TextRun("图 1 标题")] }) // 001QAX图表名
```

#### 模板样式映射

| 业务名称 | 模板真实 styleId | 模板 name / alias |
|----------|------------------|-------------------|
| 001QAX标题1 | `1` | `heading 1` / `001QAX标题 1` |
| 002QAX标题2 | `2` | `heading 2` / `002AXQ 标题2` |
| 003QAX标题3 | `3` | `heading 3` / `003QAX标题3` |
| 004QAX标题4 | `4` | `heading 4` / `004QAX标题 4` |
| 005QAX标题5 | `5` | `heading 5` |
| 006QAX标题6 | `6` | `heading 6` |
| 007QAX标题7 | `7` | `heading 7` |
| 008QAX标题8 | `8` | `heading 8` |
| 009QAX标题9 | `9` | `heading 9` |
| 007-图片 | `007-` | `007-图片` |
| 001QAX图表名 | `001QAX` | `001QAX图表名` |
| 077-正文格式 | `077-0` | `077-正文格式` |
| 077-表格文字 | `077-` | `077-表格文字` |

说明：

- 模板里第 2 级标题的 alias 原文是 `002AXQ 标题2`，存在字母顺序差异；本 skill 按你的要求把它规范映射为 `002QAX标题2` 使用。
- 模板中第 5 到 9 级标题没有单独写入 `QAX` alias，但对应的真实嵌入样式就是 `heading 5` 到 `heading 9`，本 skill 固定把它们映射为 `005QAX标题5` 到 `009QAX标题9`。

#### 样式细节

**基准样式 `Normal`（styleId=`a`）**

- 段落属性：
  - `widowControl=0`
  - `adjustRightInd=0`
  - `line=360`
  - `lineRule=atLeast`
  - `textAlignment=baseline`
- 字体属性：
  - `ascii=Times New Roman`
  - `eastAsia=宋体`
  - `hAnsi=Times New Roman`
  - `cs=Times New Roman`
  - `spacing=-4`
  - `kern=0`
  - `sz=24`
  - `szCs=20`

**001QAX标题1（styleId=`1`）**

- `basedOn=a`
- `next=2`
- `link=10`
- 标题编号：`numId=1`
- 段落属性：
  - `spacing before=50 after=50 line=240 lineRule=auto`
  - `ind left=0 firstLine=0`
  - `outlineLevel=0`
- 字体属性：
  - 段落样式中显式指定 `ascii=黑体`、`eastAsia=黑体`
  - `kern=21`
  - 关联字符样式 `10`：`sz=24`、`szCs=20`

**002QAX标题2（styleId=`2`）**

- `basedOn=a`
- `next=a`
- `link=20`
- 标题编号：`numId=1 ilvl=1`
- 段落属性：
  - `snapToGrid=0`
  - `spacing before=50 after=50 line=240 lineRule=auto`
  - `jc=both`
  - `outlineLevel=1`
- 字体属性：
  - 段落样式中显式指定 `eastAsia=黑体`
  - `snapToGrid=0`
  - `spacing=0`
  - `kern=24`
  - `szCs=24`
  - 关联字符样式 `20`：`ascii=Times New Roman`、`eastAsia=黑体`、`sz=24`、`szCs=24`

**003QAX标题3（styleId=`3`）**

- `basedOn=a`
- `next=a`
- `link=30`
- 标题编号：`numId=1 ilvl=2`
- 段落属性：
  - `autoSpaceDE=0`
  - `autoSpaceDN=0`
  - `snapToGrid=0`
  - `spacing before=50 after=50 line=240 lineRule=auto`
  - `textAlignment=bottom`
  - `outlineLevel=2`
- 字体属性：
  - 段落样式中显式指定 `snapToGrid=0`
  - `spacing=0`
  - `kern=24`
  - `szCs=24`
  - 关联字符样式 `30`：`ascii=Times New Roman`、`eastAsia=宋体`、`sz=24`、`szCs=24`

**004QAX标题4（styleId=`4`）**

- `basedOn=a`
- `next=a`
- `link=40`
- 标题编号：`numId=1 ilvl=3`
- 段落属性：
  - `spacing before=50 after=50 line=240 lineRule=auto`
  - `outlineLevel=3`
- 字体属性：
  - 段落样式中显式指定 `eastAsia=黑体`
  - 关联字符样式 `40`：`ascii=Times New Roman`、`eastAsia=黑体`、`spacing=-4`、`kern=0`、`sz=24`、`szCs=20`

**005QAX标题5（styleId=`5`）**

- `basedOn=a`
- `next=a`
- `link=50`
- 标题编号：`numId=1 ilvl=4`
- 段落属性：
  - `topLinePunct`
  - `spacing line=240 lineRule=auto`
  - `outlineLevel=4`
- 关联字符样式 `50`：
  - `ascii=Times New Roman`
  - `eastAsia=宋体`
  - `spacing=-4`
  - `kern=0`
  - `sz=24`
  - `szCs=20`

**006QAX标题6（styleId=`6`）**

- `basedOn=a`
- `next=a`
- `link=60`
- 标题编号：`numId=1 ilvl=5`
- 段落属性：
  - `outlineLevel=5`
- 关联字符样式 `60`：
  - `ascii=Times New Roman`
  - `eastAsia=宋体`
  - `spacing=-4`
  - `kern=0`
  - `sz=24`
  - `szCs=20`

**007QAX标题7（styleId=`7`）**

- `basedOn=3`
- `next=a`
- `link=70`
- 标题编号：`ilvl=6`
- 段落属性：
  - `outlineLevel=6`
- 关联字符样式 `70`：
  - `ascii=Times New Roman`
  - `eastAsia=宋体`
  - `snapToGrid=0`
  - `kern=24`
  - `sz=24`
  - `szCs=24`

**008QAX标题8（styleId=`8`）**

- `basedOn=3`
- `next=a`
- `link=80`
- 标题编号：`ilvl=7`
- 段落属性：
  - `keepNext`
  - `keepLines`
  - `suppressLineNumbers`
  - `spacing before=240 after=64 line=320 lineRule=atLeast`
  - `outlineLevel=7`
- 字体属性：
  - 段落样式中显式指定 `eastAsia=黑体`
  - `b`
  - 关联字符样式 `80`：`ascii=Times New Roman`、`eastAsia=黑体`、`b`、`snapToGrid=0`、`kern=24`、`sz=24`、`szCs=24`

**009QAX标题9（styleId=`9`）**

- `basedOn=3`
- `next=a`
- `link=90`
- 标题编号：`ilvl=8`
- 段落属性：
  - `keepNext`
  - `keepLines`
  - `outlineLevel=8`
- 字体属性：
  - 段落样式中显式指定 `ascii=Arial`、`eastAsia=黑体`、`hAnsi=Arial`
  - `b`
  - 关联字符样式 `90`：`ascii=Arial`、`eastAsia=黑体`、`hAnsi=Arial`、`b`、`snapToGrid=0`、`kern=24`、`sz=24`、`szCs=24`

**001QAX图表名（styleId=`001QAX`）**

- `customStyle=1`
- `basedOn=a`
- 段落属性：
  - `jc=center`
- 字体属性：
  - `ascii=黑体`
  - `eastAsia=黑体`

**007-图片（styleId=`007-`）**

- `customStyle=1`
- `basedOn=a`
- 段落属性：
  - `spacing line=240 lineRule=auto`
  - `jc=center`
- 字体属性：
  - `cs=宋体`

**077-正文格式（styleId=`077-0`）**

- `customStyle=1`
- `basedOn=a`
- `link=077-Char`
- 段落属性：
  - `adjustRightInd`
  - `spacing line=300 lineRule=auto`
  - `ind firstLine=482`
- 关联字符样式 `077-Char`：
  - `ascii=Times New Roman`
  - `eastAsia=宋体`
  - `hAnsi=Times New Roman`
  - `cs=Times New Roman`
  - `spacing=-4`
  - `kern=0`
  - `sz=24`
  - `szCs=20`

**077-表格文字（styleId=`077-`）**

- `customStyle=1`
- `basedOn=a`
- 段落属性：
  - `spacing line=240 lineRule=auto`
- 字体属性：
  - `sz=20`
  - `szCs=21`
  - 其余字体族默认继承 `Normal`

#### 标题编号体系

模板中的标题 1 到 9 级使用同一套多级编号 `numId=1`。规则如下：

| 层级 | styleId | 编号文本 |
|------|---------|----------|
| 1 | `1` | `%1` |
| 2 | `2` | `%1.%2` |
| 3 | `3` | `%1.%2.%3` |
| 4 | `4` | `%1.%2.%3.%4.` |
| 5 | `5` | `%1.%2.%3.%4.%5.` |
| 6 | `6` | `%1.%2.%3.%4.%5.%6.` |
| 7 | `7` | `%1.%2.%3.%4.%5.%6.%7.` |
| 8 | `8` | `%1.%2.%3.%4.%5.%6.%7.%8.` |
| 9 | `9` | `%1.%2.%3.%4.%5.%6.%7.%8.%9.` |

对应缩进：

- H1: `left=432 hanging=432`
- H2: `left=575 hanging=575`
- H3: `left=720 hanging=720`
- H4: `left=864 hanging=864`
- H5: `left=1008 hanging=1008`
- H6: `left=1151 hanging=1151`
- H7: `left=1296 hanging=1296`
- H8: `left=1440 hanging=1440`
- H9: `left=1583 hanging=1583`

### 列表（绝不要手写 Unicode 项目符号）

```javascript
// ❌ 错误：不要手工插入项目符号字符
new Paragraph({ children: [new TextRun("• Item")] })
new Paragraph({ children: [new TextRun("\u2022 Item")] })

// ✅ 正确：使用 numbering 配置和 LevelFormat.BULLET
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    children: [
      new Paragraph({ numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Bullet item")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Numbered item")] }),
    ]
  }]
});
```

**注意：** 每个 `reference` 都是独立编号序列。

- 同一个 `reference`：继续编号
- 不同 `reference`：重新从 1 开始

### 表格

**关键：表格宽度要双重设置**。既要在表上设置 `columnWidths`，也要在每个单元格上设置 `width`。否则不同平台渲染不一致。

同时，本项目表格中的文字段落默认使用模板样式 `077-表格文字`。

```javascript
// 关键：表格宽度必须显式设置
// 关键：底纹使用 ShadingType.CLEAR，不要用 SOLID
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

new Table({
  width: { size: 8306, type: WidthType.DXA }, // A4 模板正文满宽
  columnWidths: [4153, 4153],
  rows: [
    new TableRow({
      children: [
        new TableCell({
          borders,
          width: { size: 4153, type: WidthType.DXA },
          shading: { fill: "D5E8F0", type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [
            new Paragraph({ style: "077-", children: [new TextRun("单元格")] })
          ]
        })
      ]
    })
  ]
})
```

**表格宽度计算：**

始终使用 `WidthType.DXA`。不要用 `WidthType.PERCENTAGE`，它在 Google Docs 中会出问题。

```javascript
// 当前模板正文可用宽度 = 11906 - 1800 - 1800 = 8306 DXA
width: { size: 8306, type: WidthType.DXA },
columnWidths: [6000, 2306]  // 总和必须等于表格宽度
```

**宽度规则：**

- 始终使用 `WidthType.DXA`
- 表格总宽度必须等于 `columnWidths` 之和
- 单元格 `width` 必须与对应列宽一致
- 单元格 `margins` 是内部留白，不额外增加单元格宽度
- 如果是满宽表格，就用当前模板正文满宽 `8306`

### 图片

```javascript
// 关键：type 参数必填
new Paragraph({
  style: "007-",
  children: [new ImageRun({
    type: "png",
    data: fs.readFileSync("image.png"),
    transformation: { width: 200, height: 150 },
    altText: { title: "Title", description: "Desc", name: "Name" }
  })]
})

// 图片标题 / 图表名
new Paragraph({
  style: "001QAX",
  children: [new TextRun("图 1  系统架构图")]
})
```

### 分页

```javascript
// 关键：PageBreak 必须放在 Paragraph 内部
new Paragraph({ children: [new PageBreak()] })

// 或者使用 pageBreakBefore
new Paragraph({ pageBreakBefore: true, children: [new TextRun("新页开始")] })
```

### 超链接

```javascript
// 外部链接
new Paragraph({
  children: [new ExternalHyperlink({
    children: [new TextRun({ text: "点击这里", style: "Hyperlink" })],
    link: "https://example.com",
  })]
})

// 内部链接（书签 + 引用）
new Paragraph({ heading: HeadingLevel.HEADING_1, children: [
  new Bookmark({ id: "chapter1", children: [new TextRun("第一章")] }),
]})

new Paragraph({ children: [new InternalHyperlink({
  children: [new TextRun({ text: "参见第一章", style: "Hyperlink" })],
  anchor: "chapter1",
})]})
```

### 脚注

```javascript
const doc = new Document({
  footnotes: {
    1: { children: [new Paragraph("来源：2024 年报")] },
    2: { children: [new Paragraph("方法见附录")] },
  },
  sections: [{
    children: [new Paragraph({
      children: [
        new TextRun("收入增长了 15%"),
        new FootnoteReferenceRun(1),
        new TextRun("，采用了调整口径"),
        new FootnoteReferenceRun(2),
      ],
    })]
  }]
});
```

### 制表位

```javascript
// 同一行左右对齐，例如标题和日期
new Paragraph({
  children: [
    new TextRun("公司名称"),
    new TextRun("\t2025 年 1 月"),
  ],
  tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
})

// 点状引导线，例如目录
new Paragraph({
  children: [
    new TextRun("引言"),
    new TextRun({ children: [
      new PositionalTab({
        alignment: PositionalTabAlignment.RIGHT,
        relativeTo: PositionalTabRelativeTo.MARGIN,
        leader: PositionalTabLeader.DOT,
      }),
      "3",
    ]}),
  ],
})
```

### 多栏布局

```javascript
// 等宽分栏
sections: [{
  properties: {
    column: {
      count: 2,
      space: 720,
      equalWidth: true,
      separate: true,
    },
  },
  children: [/* 内容会自然流入各栏 */]
}]

// 自定义栏宽
sections: [{
  properties: {
    column: {
      equalWidth: false,
      children: [
        new Column({ width: 5400, space: 720 }),
        new Column({ width: 3240 }),
      ],
    },
  },
  children: [/* content */]
}]
```

如果要强制换栏，使用 `type: SectionType.NEXT_COLUMN` 新开一个 section。

### 目录

对当前模板，目录的前提不是通用 `Heading1 / Heading2 / Heading3`，而是模板标题样式保留自己的 `outlineLevel` 与编号。

```javascript
// 关键：标题必须保留模板中的 outlineLevel 0-8
new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-9" })
```

如果必须从空白文档创建，优先显式使用模板 `styleId=1..9`，不要退回官方示例里的 Arial 标题样式。

### 页眉 / 页脚

当前 [软件设计模板.docx](/Users/chris/Documents/dev/nextAgent/skill-design/软件设计模板.docx) 中未发现独立的 `header*.xml` / `footer*.xml` 部件，因此默认不主动生成页眉页脚。除非用户明确要求，否则保持模板当前状态。

```javascript
sections: [{
  properties: {
    page: {
      margin: {
        top: 1440, right: 1800, bottom: 1440, left: 1800,
        header: 851, footer: 992
      }
    }
  },
  headers: {
    default: new Header({ children: [new Paragraph({ children: [new TextRun("页眉")] })] })
  },
  footers: {
    default: new Footer({ children: [new Paragraph({
      children: [new TextRun("第 "), new TextRun({ children: [PageNumber.CURRENT] }), new TextRun(" 页")]
    })] })
  },
  children: [/* content */]
}]
```

### `docx-js` 的关键规则

- **页面尺寸必须显式设置**：本项目使用模板中的 A4 `11906 x 16838 DXA`
- **横向页面传纵向宽高**：让 `docx-js` 自己交换
- **不要使用 `\n`**：改用多个 `Paragraph`
- **不要手写 Unicode 项目符号**
- **PageBreak 必须在 Paragraph 里**
- **ImageRun 必须带 `type`**
- **表格宽度始终使用 DXA**
- **表格必须双重设宽**
- **表格宽度必须精确等于列宽总和**
- **单元格要有 margins**
- **底纹使用 `ShadingType.CLEAR`**
- **不要拿表格当分隔线**
- **目录依赖标题 `outlineLevel`**
- **不要再使用通用 `Heading1` / `Heading2` 样式覆盖方案**
- **新增标题必须使用模板标题样式 `1..9`**
- **正文、表格文字、图片、图表名必须分别使用 `077-0`、`077-`、`007-`、`001QAX`**

---

## 编辑现有文档

**严格按顺序执行这 3 步。**

### 第 1 步：解包

```bash
python scripts/office/unpack.py document.docx unpacked/
```

这一步会提取 XML、做 pretty-print、合并相邻 runs，并把智能引号转成 XML 实体（如 `&#x201C;`），确保编辑后不会丢失。

如果不想合并 runs，可用 `--merge-runs false`。

### 第 2 步：编辑 XML

编辑 `unpacked/word/` 下的文件。常见模式见下方“XML 参考”。

**除非用户明确要求其他名字，否则修订痕迹和批注作者统一写 `"Claude"`。**

**优先直接用 Edit 工具做字符串替换。不要额外写 Python 脚本。** 脚本会引入不必要的复杂度，而 Edit 工具能清楚显示替换了什么。

**关键：新增内容要用智能引号。** 添加带引号或撇号的文本时，使用 XML 实体：

```xml
<w:t>Here&#x2019;s a quote: &#x201C;Hello&#x201D;</w:t>
```

| 实体 | 字符 |
|------|------|
| `&#x2018;` | ‘ |
| `&#x2019;` | ’ |
| `&#x201C;` | “ |
| `&#x201D;` | ” |

**关键：如果当前文档基于 `软件设计模板.docx`，不要随意改 `styles.xml`。** 新增内容优先复用下列 `styleId`：

- 标题：`1` 到 `9`
- 图像段落：`007-`
- 图表名：`001QAX`
- 正文：`077-0`
- 表格文字：`077-`

**添加批注：** 使用 `comment.py` 处理多文件样板代码（文本内容要先转义为 XML）：

```bash
python scripts/comment.py unpacked/ 0 "Comment text with &amp; and &#x2019;"
python scripts/comment.py unpacked/ 1 "Reply text" --parent 0
python scripts/comment.py unpacked/ 0 "Text" --author "Custom Author"
```

然后在 `document.xml` 中加标记，见“XML 参考”里的 Comments。

### 第 3 步：回包

```bash
python scripts/office/pack.py unpacked/ output.docx --original document.docx
```

这一步会做自动修复、压缩 XML 并生成 DOCX。如需跳过校验，可加 `--validate false`。

**自动修复能处理：**

- `durableId >= 0x7FFFFFFF`
- `<w:t>` 缺少 `xml:space="preserve"` 而文本带空格

**自动修复不能处理：**

- XML 格式损坏
- 非法元素嵌套
- 关系文件缺失
- Schema 级违规

### 常见陷阱

- **替换整个 `<w:r>` 元素**：添加修订痕迹时，要把整块 `<w:r>...</w:r>` 替换成并列的 `<w:del>...` 和 `<w:ins>...`，不要把修订标记塞进 run 里面。
- **保留 `<w:rPr>` 格式**：给修订内容加 `<w:ins>` / `<w:del>` 时，要把原 run 的 `<w:rPr>` 一并复制进去，避免粗体、字号、字体丢失。

---

## XML 参考

### Schema 合规

- **`<w:pPr>` 中元素顺序**：`<w:pStyle>`、`<w:numPr>`、`<w:spacing>`、`<w:ind>`、`<w:jc>`，最后才是 `<w:rPr>`
- **空白字符**：如果 `<w:t>` 有前后空格，加上 `xml:space="preserve"`
- **RSID**：必须是 8 位十六进制，例如 `00AB1234`

### 修订痕迹

**插入：**

```xml
<w:ins w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:t>inserted text</w:t></w:r>
</w:ins>
```

**删除：**

```xml
<w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
```

**在 `<w:del>` 里面**：文本要用 `<w:delText>`，字段文本要用 `<w:delInstrText>`，不要用普通 `<w:t>` / `<w:instrText>`。

**最小化修改，只标记变动部分：**

```xml
<w:r><w:t>The term is </w:t></w:r>
<w:del w:id="1" w:author="Claude" w:date="...">
  <w:r><w:delText>30</w:delText></w:r>
</w:del>
<w:ins w:id="2" w:author="Claude" w:date="...">
  <w:r><w:t>60</w:t></w:r>
</w:ins>
<w:r><w:t> days.</w:t></w:r>
```

**删除整段 / 整个列表项**：如果段落全部内容都删掉，还必须把段落标记也标记为删除，这样接受修订后才会与下一段合并：

```xml
<w:p>
  <w:pPr>
    <w:numPr>...</w:numPr>
    <w:rPr>
      <w:del w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z"/>
    </w:rPr>
  </w:pPr>
  <w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
    <w:r><w:delText>Entire paragraph content being deleted...</w:delText></w:r>
  </w:del>
</w:p>
```

如果缺少 `<w:pPr><w:rPr>` 里的 `<w:del/>`，接受修订后会留下空段落或空列表项。

**拒绝别人插入的内容**：在对方的 `<w:ins>` 内嵌套你的 `<w:del>`：

```xml
<w:ins w:author="Jane" w:id="5">
  <w:del w:author="Claude" w:id="10">
    <w:r><w:delText>their inserted text</w:delText></w:r>
  </w:del>
</w:ins>
```

**恢复别人删除的内容**：在他们的删除后面再插入一份，不要去改原删除块：

```xml
<w:del w:author="Jane" w:id="5">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
<w:ins w:author="Claude" w:id="10">
  <w:r><w:t>deleted text</w:t></w:r>
</w:ins>
```

### 批注

运行 `comment.py` 之后，把批注标记加回 `document.xml`。回复批注时，使用 `--parent` 并把回复范围嵌套在父批注范围内。

**关键：`<w:commentRangeStart>` 和 `<w:commentRangeEnd>` 必须是 `<w:p>` 的直接子节点，绝不能放到 `<w:r>` 里面。**

```xml
<w:commentRangeStart w:id="0"/>
<w:del w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted</w:delText></w:r>
</w:del>
<w:r><w:t> more text</w:t></w:r>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>

<w:commentRangeStart w:id="0"/>
  <w:commentRangeStart w:id="1"/>
  <w:r><w:t>text</w:t></w:r>
  <w:commentRangeEnd w:id="1"/>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="1"/></w:r>
```

### 图片

1. 把图片文件放进 `word/media/`
2. 在 `word/_rels/document.xml.rels` 增加关系：

```xml
<Relationship Id="rId5" Type=".../image" Target="media/image1.png"/>
```

3. 在 `[Content_Types].xml` 增加内容类型：

```xml
<Default Extension="png" ContentType="image/png"/>
```

4. 在 `document.xml` 中引用：

```xml
<w:drawing>
  <wp:inline>
    <wp:extent cx="914400" cy="914400"/>
    <a:graphic>
      <a:graphicData uri=".../picture">
        <pic:pic>
          <pic:blipFill><a:blip r:embed="rId5"/></pic:blipFill>
        </pic:pic>
      </a:graphicData>
    </a:graphic>
  </wp:inline>
</w:drawing>
```

---

## 依赖

- **pandoc**：提取文本
- **docx**：`npm install -g docx`（新建文档）
- **LibreOffice**：可选，用于文档格式转换
- **Poppler**：`pdftoppm` 用于输出图片
