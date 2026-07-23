"""A3/A4 专业试卷排版 HTML 模板引擎"""
import json
from typing import Optional


def render_exam_paper(
    title: str,
    questions: list[dict],
    total_score: float,
    duration: int,
    template_type: str = "midterm",
    subject: str = "math",
    knowledge_points: Optional[list[str]] = None,
) -> str:
    is_a3 = template_type in ("midterm", "final")
    page_size_css = _page_size_style(is_a3)
    kp_str = "、".join(knowledge_points or [])
    header_html = _render_header(title, total_score, duration, kp_str)
    sections_html = _render_all_sections(questions, subject)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body,{{delimiters:[{{left:'$$',right:'$$',display:true}},{{left:'$',right:'$',display:false}}]}});"></script>
<style>
{page_size_css}
{_global_styles(is_a3)}
{_subject_styles(subject)}
</style>
</head>
<body>
{header_html}
<div class="exam-body">
{sections_html}
</div>
{_footer_html()}
</body>
</html>"""


def _page_size_style(is_a3: bool) -> str:
    if is_a3:
        return """@page { size: A3 landscape; margin: 25mm 20mm 20mm 25mm; }"""
    return """@page { size: A4; margin: 20mm 18mm 18mm 20mm; }"""


def _global_styles(is_a3: bool) -> str:
    body_width = "420mm" if is_a3 else "210mm"
    return f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: 'Times New Roman', '宋体', serif;
  width: {body_width};
  margin: 0 auto;
  padding: 0;
  color: #1a1a1a;
  line-height: 1.8;
}}
.exam-header {{
  text-align: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #333;
}}
.confidential {{ font-size: 14px; font-weight: bold; letter-spacing: 4px; margin-bottom: 8px; color: #c00; }}
.exam-title {{ font-family: '黑体', 'SimHei', sans-serif; font-size: 22px; font-weight: bold; margin-bottom: 12px; }}
.exam-meta {{ font-family: '黑体', 'SimHei', sans-serif; font-size: 14px; margin-bottom: 8px; }}
.exam-meta span {{ margin: 0 16px; }}
.student-info {{ display: flex; justify-content: center; gap: 40px; font-size: 14px; margin: 12px 0; }}
.student-info u {{ letter-spacing: 2px; }}
.section {{ margin-bottom: 28px; }}
.section-header {{
  font-family: '黑体', 'SimHei', sans-serif;
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 12px;
}}
.section-instruction {{
  font-family: '宋体', 'SimSun', serif;
  font-size: 13px;
  color: #555;
  margin-bottom: 10px;
  margin-left: 0;
}}
.question {{
  margin-bottom: 18px;
  padding-left: 0;
  page-break-inside: avoid;
}}
.q-content {{ font-family: '宋体', 'SimSun', serif; font-size: 14px; margin-bottom: 8px; }}
.q-options {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 20px;
  padding-left: 24px;
  margin: 6px 0;
  font-size: 14px;
}}
.fill-blank {{ display: inline-block; width: 100px; border-bottom: 1px solid #333; margin: 0 4px; }}
.answer-area {{ min-height: 100px; margin: 8px 0 8px 24px; border-bottom: 1px solid #ccc; }}
.sub-question {{ margin: 6px 0 6px 24px; font-size: 14px; }}
.page-footer {{
  text-align: center;
  font-size: 12px;
  color: #999;
  margin-top: 40px;
  padding-top: 8px;
  border-top: 1px solid #ddd;
}}
.latex-inline {{ font-family: 'Times New Roman', serif; font-style: italic; }}
@media print {{
  body {{ width: auto; }}
  .no-print {{ display: none; }}
}}
"""


def _subject_styles(subject: str) -> str:
    styles = ""
    if subject == "chinese":
        styles += """
.essay-grid {{
  width: 100%;
  height: 800px;
  background-image: linear-gradient(#ccc 1px, transparent 1px);
  background-size: 22px 22px;
  margin: 16px 0;
  border: 1px solid #999;
}}
.paragraph {{ text-indent: 2em; margin: 8px 0; }}
"""
    if subject in ("math", "physics", "chemistry", "biology"):
        styles += """
.formula-center {{ text-align: center; margin: 12px 0; font-family: 'Times New Roman', serif; }}
"""
    if subject == "english":
        styles += """
.reading-passage {{ margin: 12px 0; padding: 8px 16px; border-left: 2px solid #ccc; }}
.listening-section {{ margin: 16px 0; padding: 12px; border: 1px dashed #999; }}
"""
    return styles


def _render_header(title: str, total_score: float, duration: int, kp_str: str) -> str:
    kp_html = f'<p style="text-align:center;font-size:13px;color:#666;margin-top:4px;">知识点：{kp_str}</p>' if kp_str else ""
    return f"""
<div class="exam-header">
  <div class="confidential">绝密 ★ 启用前</div>
  <h1 class="exam-title">{title}</h1>
  {kp_html}
  <div class="exam-meta">
    <span>总分：<strong>{total_score}</strong> 分</span>
    <span>时长：<strong>{duration}</strong> 分钟</span>
  </div>
  <div class="student-info">
    <span>姓名：<u>&emsp;&emsp;&emsp;&emsp;&emsp;</u></span>
    <span>班级：<u>&emsp;&emsp;&emsp;&emsp;&emsp;</u></span>
  </div>
</div>"""


_type_labels = {
    "choice": "选择题", "fill": "填空题", "essay": "解答题",
    "judge": "判断题", "reading": "阅读理解", "cloze": "完形填空",
    "writing": "写作", "classical": "文言文", "calculate": "计算题",
    "proof": "证明题", "experiment": "实验题", "material": "材料分析",
}


def _render_all_sections(questions: list[dict], subject: str) -> str:
    if not questions:
        return "<p style='color:#999;text-align:center;padding:40px 0;'>暂无题目</p>"

    type_order = ["choice", "fill", "judge", "reading", "cloze", "calculate", "proof", "experiment", "material", "classical", "writing", "essay"]
    sections_dict: dict[str, list[dict]] = {}
    type_labels_seen: dict[str, str] = {}
    for q in questions:
        t = q.get("type", "essay")
        if t not in sections_dict:
            sections_dict[t] = []
            type_labels_seen[t] = _type_labels.get(t, t)
        sections_dict[t].append(q)

    section_index = 1
    q_index = 1
    html = ""
    section_num_cn = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

    for t in type_order:
        if t not in sections_dict:
            continue
        qs = sections_dict[t]
        label = type_labels_seen[t]
        count = len(qs)
        total_sec_score = sum(float(q.get("score", 0)) for q in qs)
        cn = section_num_cn[section_index] if section_index < len(section_num_cn) else str(section_index)

        instructions = {
            "choice": f"（本大题共 {count} 小题，每小题 {total_sec_score / max(count, 1):.0f} 分，共 {total_sec_score:.0f} 分。在每小题给出的选项中，只有一项是符合题目要求的。）",
            "fill": f"（本大题共 {count} 小题，每小题 {total_sec_score / max(count, 1):.0f} 分，共 {total_sec_score:.0f} 分。）",
            "judge": f"（本大题共 {count} 小题，每小题 {total_sec_score / max(count, 1):.0f} 分，共 {total_sec_score:.0f} 分。正确的打\u201c√\u201d，错误的打\u201c×\u201d。）",
        }
        instruction = instructions.get(t, f"（本大题共 {count} 小题，共 {total_sec_score:.0f} 分。）")

        html += '<div class="section">'
        html += f'<div class="section-header">{cn}、{label}</div>'
        html += f'<div class="section-instruction">{instruction}</div>'

        for q in qs:
            qtype = q.get("type", "")
            content = q.get("content", "")
            score = float(q.get("score", 0))
            options = q.get("options")

            html += '<div class="question">'
            html += f'<div class="q-content">{q_index}. {content}（{score:.0f} 分）</div>'

            if qtype == "choice" and options:
                html += '<div class="q-options">'
                if isinstance(options, list):
                    for opt in options:
                        if isinstance(opt, dict):
                            html += f'<div>{opt.get("label", "")}、{opt.get("content", "")}</div>'
                        elif isinstance(opt, str):
                            html += f'<div>{opt}</div>'
                elif isinstance(options, str):
                    try:
                        parsed = json.loads(options)
                        for opt in parsed:
                            label = opt.get("label", "")
                            opt_content = opt.get("content", "")
                            html += f'<div>{label}、{opt_content}</div>'
                    except json.JSONDecodeError:
                        html += f'<div>{options}</div>'
                html += '</div>'

            if qtype == "fill":
                html += '<div class="fill-blank">&nbsp;</div>'

            if qtype in ("essay", "writing", "material", "calculate", "proof", "experiment"):
                html += '<div class="answer-area"></div>'

            if subject == "chinese" and qtype == "writing":
                html += '<div class="essay-grid"></div>'

            html += '</div>'
            q_index += 1

        html += '</div>'
        section_index += 1

    return html


def _footer_html() -> str:
    return """
<div class="page-footer">第 1 页 / 共 1 页</div>
"""
