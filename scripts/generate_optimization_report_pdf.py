"""Generate the final Miro-CogSec optimization report PDF.

The report is intentionally generated from audited, fixed values produced by
the 2026-08-08 formal_v3 run. It contains no credentials.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "Miro-CogSec_Optimization_and_Blind_Evaluation_Report_2026-08-08.pdf"

NAVY = colors.HexColor("#172554")
BLUE = colors.HexColor("#2563EB")
CYAN = colors.HexColor("#0891B2")
TEAL = colors.HexColor("#0F766E")
GREEN = colors.HexColor("#16A34A")
AMBER = colors.HexColor("#D97706")
RED = colors.HexColor("#DC2626")
INK = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#D9E2EC")
PALE = colors.HexColor("#F4F7FB")
PALE_BLUE = colors.HexColor("#EAF2FF")
PALE_GREEN = colors.HexColor("#EAF8F1")


def register_fonts() -> tuple[str, str]:
    regular = Path(r"C:\Windows\Fonts\msyh.ttc")
    bold = Path(r"C:\Windows\Fonts\msyhbd.ttc")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("MiroYaHei", str(regular), subfontIndex=0))
        pdfmetrics.registerFont(TTFont("MiroYaHeiBold", str(bold), subfontIndex=0))
        pdfmetrics.registerFontFamily(
            "MiroYaHei",
            normal="MiroYaHei",
            bold="MiroYaHeiBold",
            italic="MiroYaHei",
            boldItalic="MiroYaHeiBold",
        )
        return "MiroYaHei", "MiroYaHeiBold"
    pdfmetrics.registerFont(TTFont("MiroHei", r"C:\Windows\Fonts\simhei.ttf"))
    return "MiroHei", "MiroHei"


FONT, FONT_BOLD = register_fonts()


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_kicker": ParagraphStyle(
            "cover_kicker", parent=base["Normal"], fontName=FONT_BOLD,
            fontSize=10, leading=15, textColor=CYAN, spaceAfter=8,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontName=FONT_BOLD,
            fontSize=27, leading=38, textColor=NAVY, spaceAfter=14,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle", parent=base["Normal"], fontName=FONT,
            fontSize=12, leading=20, textColor=MUTED, spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName=FONT_BOLD,
            fontSize=18, leading=25, textColor=NAVY, spaceBefore=3, spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName=FONT_BOLD,
            fontSize=12.5, leading=18, textColor=BLUE, spaceBefore=9, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName=FONT,
            fontSize=9.3, leading=15.5, textColor=INK, spaceAfter=7,
            wordWrap="CJK", alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName=FONT,
            fontSize=7.8, leading=12.3, textColor=MUTED, wordWrap="CJK",
        ),
        "callout": ParagraphStyle(
            "callout", parent=base["BodyText"], fontName=FONT_BOLD,
            fontSize=10.3, leading=17, textColor=NAVY, wordWrap="CJK",
        ),
        "metric": ParagraphStyle(
            "metric", parent=base["Normal"], fontName=FONT_BOLD,
            fontSize=19, leading=22, textColor=BLUE, alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "metric_label", parent=base["Normal"], fontName=FONT,
            fontSize=7.5, leading=11, textColor=MUTED, alignment=TA_CENTER,
        ),
        "table": ParagraphStyle(
            "table", parent=base["BodyText"], fontName=FONT,
            fontSize=7.6, leading=11.5, textColor=INK, wordWrap="CJK",
        ),
        "table_head": ParagraphStyle(
            "table_head", parent=base["BodyText"], fontName=FONT_BOLD,
            fontSize=7.7, leading=11, textColor=colors.white, wordWrap="CJK",
        ),
        "quote": ParagraphStyle(
            "quote", parent=base["BodyText"], fontName=FONT,
            fontSize=9, leading=15, leftIndent=10, rightIndent=10,
            borderColor=CYAN, borderWidth=0, borderPadding=8,
            backColor=colors.HexColor("#ECFEFF"), textColor=INK, wordWrap="CJK",
        ),
    }


S = styles()


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def bullet(text: str) -> Paragraph:
    return Paragraph(f"<font color='#2563EB'>●</font>&nbsp;&nbsp;{text}", S["body"])


def section(title: str) -> list:
    return [P(title, "h1")]


def h2(title: str) -> Paragraph:
    return P(title, "h2")


def table(data, widths, header=True, row_colors=True) -> Table:
    converted = []
    for r_idx, row in enumerate(data):
        converted.append([
            item if isinstance(item, Paragraph) else P(str(item), "table_head" if header and r_idx == 0 else "table")
            for item in row
        ])
    t = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    if row_colors:
        start = 1 if header else 0
        for idx in range(start, len(converted)):
            if (idx - start) % 2:
                commands.append(("BACKGROUND", (0, idx), (-1, idx), PALE))
    t.setStyle(TableStyle(commands))
    return t


def metric_cards(items) -> Table:
    cells = []
    for value, label, color in items:
        cells.append(Table(
            [[P(value, "metric")], [P(label, "metric_label")]],
            colWidths=[38 * mm], rowHeights=[12 * mm, 10 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), color),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]),
        ))
    return Table([cells], colWidths=[40 * mm] * len(cells), hAlign="LEFT",
                 style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))


def progress_chart() -> Drawing:
    d = Drawing(465, 145)
    labels = ["历史证据版", "首轮重构", "保护 v2", "最终 v3"]
    values = [16.67, 83.33, 93.33, 100.0]
    colors_ = [RED, CYAN, BLUE, GREEN]
    x0, width = 92, 330
    for idx, (label, value, color) in enumerate(zip(labels, values, colors_)):
        y = 114 - idx * 31
        d.add(String(0, y + 3, label, fontName=FONT, fontSize=8, fillColor=INK))
        d.add(Rect(x0, y, width, 12, fillColor=colors.HexColor("#E8EEF5"), strokeColor=None))
        d.add(Rect(x0, y, width * value / 100, 12, fillColor=color, strokeColor=None))
        d.add(String(x0 + width + 8, y + 2, f"{value:.2f}%", fontName=FONT_BOLD, fontSize=8, fillColor=color))
    d.add(String(0, 136, "无 Gold 盲评：Miro-CogSec 胜率演进", fontName=FONT_BOLD, fontSize=10, fillColor=NAVY))
    return d


def score_chart() -> Drawing:
    d = Drawing(465, 165)
    labels = ["问题定位", "行动性", "证据支撑", "机制洞察", "输出可靠性"]
    miro = [8.533, 8.500, 8.600, 7.933, 8.267]
    llm = [6.500, 5.000, 6.500, 4.333, 6.867]
    x0, unit = 96, 29
    for idx, label in enumerate(labels):
        y = 130 - idx * 25
        d.add(String(0, y + 2, label, fontName=FONT, fontSize=8, fillColor=INK))
        d.add(Rect(x0, y + 6, miro[idx] * unit, 6, fillColor=BLUE, strokeColor=None))
        d.add(Rect(x0, y - 2, llm[idx] * unit, 6, fillColor=colors.HexColor("#94A3B8"), strokeColor=None))
        d.add(String(x0 + miro[idx] * unit + 5, y + 4, f"{miro[idx]:.2f}", fontName=FONT_BOLD, fontSize=7, fillColor=BLUE))
    d.add(String(0, 154, "最终主轮五维均分（蓝：Miro；灰：LLM-only）", fontName=FONT_BOLD, fontSize=10, fillColor=NAVY))
    return d


def draw_page(canvas, doc):
    canvas.saveState()
    page = canvas.getPageNumber()
    width, height = A4
    if page > 1:
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, height - 15 * mm, width - 20 * mm, height - 15 * mm)
        canvas.setFont(FONT_BOLD, 7.5)
        canvas.setFillColor(NAVY)
        canvas.drawString(20 * mm, height - 11 * mm, "MIRO-COGSEC · OUTPUT PIPELINE OPTIMIZATION")
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(width - 20 * mm, height - 11 * mm, "2026-08-08")
        canvas.line(20 * mm, 14 * mm, width - 20 * mm, 14 * mm)
        canvas.drawString(20 * mm, 9 * mm, "内部工程报告 · 不含任何 API 密钥")
        canvas.drawRightString(width - 20 * mm, 9 * mm, f"{page - 1}")
    canvas.restoreState()


def build_story() -> list:
    story = []
    story += [Spacer(1, 20 * mm), P("第十九届全国大学生信息安全竞赛 · 作品赛", "cover_kicker")]
    story += [P("Miro-CogSec<br/>输出链优化与盲评复验报告", "cover_title")]
    story += [P("面向认知安全的多场景决策防护系统", "cover_subtitle")]
    story += [Spacer(1, 9 * mm)]
    story += [metric_cards([
        ("357", "自动化测试通过", PALE_BLUE),
        ("30 / 30", "双种子盲评获胜", PALE_GREEN),
        ("1.68 s", "平均端到端耗时", PALE_BLUE),
        ("0", "截断 / 泄漏 / 异常兜底", PALE_GREEN),
    ])]
    story += [Spacer(1, 16 * mm)]
    story += [P("核心结论", "h2")]
    story += [P(
        "本轮完成了组长路线中的第一优先级：恢复真实、无参考答案的盲评，并把最终输出与 Benchmark、"
        "合成传播轨迹和固定模板真正隔离。PPO 接口保留，但因缺少完整 OASIS、稳定多步状态转移和足量轨迹，"
        "没有伪造训练结论。", "callout"
    )]
    story += [Spacer(1, 25 * mm), P("工程日期：2026-08-08　｜　版本：Reporter v3 / formal_v3", "small")]
    story += [PageBreak()]

    story += section("1　现状判断与本轮目标")
    story += [P(
        "组长的新版本已经完成主干架构重构：Runtime 产出事实和候选动作，ReportState 汇总统一状态，Reporter 负责最终自然语言，"
        "Benchmark 只做旁路导出和离线评分。同时保留本地 Reporter、SFT、DPO 与 PPO 的接口。真正的问题不再是“代码有没有接口”，"
        "而是输出端是否仍被内部结构和测评先验污染，以及外部 API 是否能稳定完成真实盲评。"
    )]
    story += [P(
        "本轮目标被限定为四项：恢复独立 Reporter API；阻断合成节点与代理数值泄漏；对正常内容和边界风险做比例性判断；"
        "使用实际用户可见回答运行无 Gold 双盲。", "quote"
    )]
    story += [h2("与组长报告的路线对齐")]
    story += [table([
        ["组长路线", "本轮状态", "说明"],
        ["真实盲评", "已完成", "两种 A/B 随机种子，各 30 条，无 Gold"],
        ["Semantic Scorer v2", "待建设", "当前词法 RES 仅用于诊断，不能替代语义/矛盾判断"],
        ["单步干预 Ranker", "接口存在", "learned 权重缺失，按设计回退固定权重"],
        ["完整 OASIS", "未完成", "public/event 仍含轻量 proxy，provenance 如实标记"],
        ["SFT / DPO", "未训练", "缺少成体系语料与独立偏好数据"],
        ["PPO", "未训练", "缺少稳定多步环境、可靠 reward 和足量轨迹"],
    ], [35 * mm, 25 * mm, 107 * mm])]
    story += [h2("为什么不立即做 PPO")]
    story += [P(
        "PPO 应优化“何时、对谁、做什么、做多强”的多步干预策略，而不是最终一句话是否自然。当前代理环境会生成合成节点和人为轨迹；"
        "若现在训练，策略极可能学会代理器偏差。先证明 Reporter、冻结回归集、建设隐藏集和真实 OASIS，是更可靠的顺序。"
    )]
    story += [PageBreak()]

    story += section("2　根因审计")
    root_rows = [
        ["失败表现", "根因", "风险"],
        ["正常公告、寻人启事被定性为诈骗", "Reporter 被 fraud 场景标签和固定安全话术诱导", "误报、过度处置、降低可信度"],
        ["天气预警明示无误传，却声称严重失真", "完整 proxy mutation trace 覆盖了原文证据", "把仿真当现实，结论自相矛盾"],
        ["输出 SYNTH_*/INFERRED_* 与 0.912→0.136", "内部节点和模拟数值直接进入 Reporter payload", "无法面向真实用户解释或执行"],
        ["办卡广告先收费却被低风险保护", "只依赖汇总风险分，没有检查原文攻击转折", "漏报明确财产风险"],
        ["裁判汇总误标 with_gold", "工具默认值与请求生成器默认值不一致", "评测口径不可审计"],
    ]
    story += [table(root_rows, [47 * mm, 65 * mm, 55 * mm])]
    story += [Spacer(1, 5 * mm)]
    story += [h2("核心修复原则")]
    story += [bullet("原文可观察证据高于 proxy/heuristic；代理数据只能提出监测方向。")]
    story += [bullet("内部风险分只能辅助，不能覆盖原文中明确的付款、验证码、远程控制等攻击转折。")]
    story += [bullet("Reporter 输入采用最小白名单，不再把全量运行时对象交给输出模型自行筛选。")]
    story += [bullet("输出端做格式与事实边界校验；失败时使用可解释保护，而不是静默模板。")]
    story += [PageBreak()]

    story += section("3　实现改造")
    implementation = [
        ["模块", "改造内容"],
        ["独立 Reporter", "新增独立 key/base/model、连接/读取超时、重试、最大 Token 与 thinking 开关；支持远端、本地、训练后与确定性后端。"],
        ["Reporter v3", "证据白名单；隐藏 mutation trace、节点 ID、候选编号和代理评分；提示词强调原文优先、禁止虚构、禁止不具备能力的承诺。"],
        ["输出校验", "拒绝截断、JSON/代码块、内部字段、内部动作 Token、合成节点、代理小数冒充观测、与明确否定证据相冲突。"],
        ["比例性保护", "正常/稳定材料走可解释保护；原文明示先交费用、保证下卡等信号时绕过低风险保护。"],
        ["Fraud Agents", "提示只返回允许动作 Token；默认确定性 policy；LLM policy 保留并提供 provenance。"],
        ["画像与性能", "auto 模式下 fraud 可用 LLM，public/event 使用启发式画像，减少无关外部调用。"],
        ["盲评脚本", "严格校验 winner、五维分数和理由；显式 no_gold；thinking 关闭；保存位置映射、裁判模型和逐条理由。"],
    ]
    story += [table(implementation, [38 * mm, 129 * mm])]
    story += [h2("最终输出分流")]
    story += [P(
        "30 条最终结果中，22 条由 Qwen3.7-Flash 独立 Reporter 生成；8 条触发证据保护：6 条低风险正常材料、"
        "1 条稳定舆情、1 条明确无失真的事件传播。保护分支有独立 provenance，不伪装成模型输出，也不计作异常兜底。"
    )]
    story += [PageBreak()]

    story += section("4　自动化测试与运行质量")
    story += [metric_cards([
        ("357", "Pytest 通过", PALE_BLUE),
        ("30 / 30", "正式输出成功", PALE_GREEN),
        ("22 + 8", "远端 Reporter + 保护", PALE_BLUE),
        ("0", "异常兜底", PALE_GREEN),
    ])]
    story += [Spacer(1, 7 * mm)]
    story += [table([
        ["运行指标", "最终值", "审计结论"],
        ["截断", "0", "finish_reason 未出现 length/max_tokens"],
        ["内部节点泄漏", "0", "未出现 SYNTH/INFERRED/ACTOR/CLAIM 编号"],
        ["不受支持的后续承诺", "0", "未出现“我们将持续关注/继续跟进”"],
        ["平均端到端耗时", "1,677.1 ms", "可用于现场演示；低风险保护约 45–152 ms"],
        ["最大端到端耗时", "3,546.1 ms", "30 条批次内无长尾超时"],
        ["唯一测试 warning", "1", "learned ranker 权重缺失，固定权重回退符合设计"],
        ["前端生产构建", "通过", "Vite 转换 920 模块；主 JS 约 706 KB，后续可代码分割"],
        ["HTTP 可达性", "通过", "前端 200 + React root；后端 /health status=ok"],
    ], [48 * mm, 34 * mm, 85 * mm])]
    story += [h2("测试覆盖新增")]
    story += [bullet("Reporter 截断自动重试并增加 Token 预算。")]
    story += [bullet("正常文本误报、明确收费信号漏报、稳定舆情过度推断。")]
    story += [bullet("代理节点/数值泄漏与原文否定证据冲突。")]
    story += [bullet("裁判缺字段、非法分数、理由过短时拒绝并重试。")]
    story += [P(
        "当前环境没有可用的交互式浏览器会话，因此未声称完成点击式 UI 巡检；前端验证范围是依赖安装、生产构建与 HTTP 可达性。",
        "small",
    )]
    story += [PageBreak()]

    story += section("5　无 Gold 双盲评测")
    story += [P(
        "评测输入仅包含原始用户输入和随机化的 Answer A/B。Miro 与 LLM-only 均使用实际用户可见文本；"
        "不提供 Gold 或系统身份。Reporter/基线为 Qwen3.7-Flash，裁判为不同模型族 GLM-5.2，temperature=0，thinking 关闭。"
    )]
    story += [progress_chart(), Spacer(1, 3 * mm)]
    story += [table([
        ["评测阶段", "Miro", "LLM-only", "平局", "Miro 胜率"],
        ["历史保守原文证据版", "5", "22", "3", "16.67%"],
        ["本轮首轮重构", "25", "5", "0", "83.33%"],
        ["证据白名单 + 第一轮保护", "28", "2", "0", "93.33%"],
        ["最终主轮 · seed 20260808", "30", "0", "0", "100.00%"],
        ["位置复核 · seed 20260809", "30", "0", "0", "100.00%"],
    ], [70 * mm, 22 * mm, 26 * mm, 20 * mm, 29 * mm])]
    story += [P(
        "注意：历史与最终轮的模型、脚本和输出策略不同，只反映工程趋势。最终 30 条已经参与迭代，100% 不能解释为未见数据泛化率。", "small"
    )]
    story += [PageBreak()]

    story += section("6　盲评得分与稳定性复核")
    story += [score_chart()]
    story += [table([
        ["维度", "Miro-CogSec", "LLM-only", "差值"],
        ["问题定位", "8.533", "6.500", "+2.033"],
        ["行动性", "8.500", "5.000", "+3.500"],
        ["证据支撑", "8.600", "6.500", "+2.100"],
        ["机制洞察", "7.933", "4.333", "+3.600"],
        ["输出可靠性", "8.267", "6.867", "+1.400"],
    ], [54 * mm, 38 * mm, 38 * mm, 37 * mm])]
    story += [h2("位置复核")]
    story += [P(
        "主轮中 Miro 位于 A/B 的数量为 11/19；第二随机种子为 14/16。两轮均为 30/30，且均无裁判解析警告。"
        "这降低了简单位置偏差的可能性，但两轮使用同一裁判模型和同一 30 条答案，仍不能替代多模型、人类与隐藏集验证。"
    )]
    story += [PageBreak()]

    story += section("7　限制、风险与密钥处理")
    limitations = [
        ["限制", "当前事实", "应对"],
        ["OASIS 未完整运行", "public/event 仍含 proxy", "禁止引用内部轨迹为现实；下一阶段接独立分支与多 seed"],
        ["小模型未接入", "只有接口，无 checkpoint 实测", "优先 1.5B LoRA/QLoRA Reporter 对比"],
        ["SFT/DPO 数据不足", "无 500–2,000 条 SFT 与 1k–5k 偏好对", "先扩数据并冻结当前回归集"],
        ["PPO 条件不足", "无稳定多步环境与真实轨迹", "先做 Ranker、OASIS 和 reward 验证"],
        ["迭代集偏差", "30 条已用于错误分析", "新增 150–300 条隐藏样本，至少 20% 人工复核"],
        ["单裁判模型", "两种子仍是 GLM-5.2", "至少增加一个异构裁判和人工争议复核"],
    ]
    story += [table(limitations, [38 * mm, 55 * mm, 74 * mm])]
    story += [h2("API 与密钥")]
    story += [P(
        "百炼 OpenAI-compatible 接口已用于 Qwen Reporter 与 GLM 裁判；关闭 thinking 后延迟稳定。DeepSeek 单次调用可用，"
        "但批量调用曾出现长等待，因此正式可复现评测未依赖 DeepSeek 主分析链。所有密钥仅注入进程，没有写入源码、报告、示例配置或压缩包。"
    )]
    story += [P(
        "安全提醒：密钥曾通过聊天明文发送，交付后应在对应控制台轮换。", "quote"
    )]
    story += [PageBreak()]

    story += section("8　下一步路线")
    roadmap = [
        ["优先级", "任务", "完成标准"],
        ["P0", "冻结 30 条回归集；新建 150–300 条隐藏集", "覆盖正常/边界/隐含攻击/否定/多轮/误路由；开发者不看 Gold"],
        ["P1", "Semantic Scorer v2", "Embedding + NLI + 事实一致性 + 行动性 + 过度处置惩罚；全链路 provenance"],
        ["P2", "单步干预 Ranker", "pairwise preference 足量；held-out 稳定优于固定权重"],
        ["P3", "完整 OASIS + 本地 Reporter", "独立 candidate branch、多 seed、共享初态；1.5B SFT 与远端模型对比"],
        ["P4", "DPO", "约 1k–5k 独立偏好对；自然度、具体性、机制与行动性稳定改善"],
        ["P5", "PPO", "稳定多步环境、可靠 reward、独立测试集、数百/数千真实或高质量轨迹"],
    ]
    story += [table(roadmap, [20 * mm, 55 * mm, 92 * mm])]
    story += [Spacer(1, 7 * mm)]
    story += [P(
        "推荐顺序：先证明 Reporter 的泛化收益，再训练偏好；先证明单步 Ranker，再进入多步强化学习。"
        "PPO 不应被用来掩盖环境和数据尚未成熟的问题。", "callout"
    )]
    story += [PageBreak()]

    story += section("9　交付与复现索引")
    story += [table([
        ["产物", "位置"],
        ["最终运行结果", "benchmark/outputs/refactor_2026-08-08/formal_v3/"],
        ["主轮盲评", "judge_requests.jsonl / judge_results.jsonl / judge_summary.json"],
        ["位置复核", "judge_requests_seed_20260809.jsonl / judge_results_seed_20260809.jsonl / judge_summary_seed_20260809.json"],
        ["Reporter 实现", "backend/app/modules/reporter_policy.py"],
        ["运行与配置", "backend/app/runtime.py / backend/app/config.py / .env.example"],
        ["评测脚本", "scripts/run_scenario_api_benchmark.py / make_closed_model_judge_input.py / run_closed_model_judge.py"],
        ["报告源文档", "docs/MODEL_REPORTER_OPTIMIZATION_REPORT_2026-08-08.md"],
    ], [43 * mm, 124 * mm])]
    story += [Spacer(1, 9 * mm)]
    story += [P("最终结论", "h2")]
    story += [P(
        "当前版本已经从架构、输入白名单、输出校验和评测工具四个层面，隔离了“结构化测评逻辑污染用户回答”的核心问题。"
        "它在现有回归集上实现了稳定双种子盲评胜出和明显延迟改善。下一步应转向隐藏集、Semantic Scorer v2、真实 OASIS 与数据建设，"
        "而不是立即开启缺乏环境与轨迹支撑的 PPO。", "quote"
    )]
    return story


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    width, height = A4
    frame = Frame(20 * mm, 18 * mm, width - 40 * mm, height - 37 * mm, id="normal")
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=19 * mm, bottomMargin=18 * mm,
        title="Miro-CogSec 输出链优化与盲评复验报告",
        author="Miro-CogSec Project Team",
        subject="Reporter v3 optimization and no-gold blind evaluation",
    )
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=draw_page)])
    doc.build(build_story())
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
