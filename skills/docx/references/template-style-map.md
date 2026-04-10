# Software Design Template Style Map

Source template: `/Users/chris/Documents/dev/nextAgent/skill-design/软件设计模板.docx`

This reference records the actual embedded Word styles that the local `docx` skill must follow.

## Page Setup

- Paper size: A4
- Width: `11906` DXA
- Height: `16838` DXA
- Margins:
  - Top: `1440`
  - Right: `1800`
  - Bottom: `1440`
  - Left: `1800`
- Header distance: `851`
- Footer distance: `992`
- Content width: `8306`

## Style Mapping

| Requested Name | Actual styleId | Embedded name / alias |
|---|---:|---|
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

## Notes

- The template's level-2 alias is embedded as `002AXQ 标题2`. The skill normalizes it to `002QAX标题2`.
- Levels 5-9 do not carry explicit `QAX` aliases in `styles.xml`, but they are the actual embedded heading styles used for levels 5-9 and are treated as `005QAX标题5` through `009QAX标题9`.
- Body paragraphs should prefer `077-0`.
- Table cell paragraphs should prefer `077-`.
- Image container paragraphs should prefer `007-`.
- Figure and table captions should prefer `001QAX`.
