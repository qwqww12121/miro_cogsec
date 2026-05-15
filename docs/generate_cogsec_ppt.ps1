Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

$docsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$assetsRoot = Join-Path $docsRoot 'ppt_assets'
$outputPath = Join-Path $docsRoot 'COGSEC_COMPETITION_SUPPORT_DECK.pptx'

$msoFalse = 0
$msoTrue = -1
$msoTextOrientationHorizontal = 1
$ppLayoutBlank = 12
$ppSaveAsOpenXMLPresentation = 24
$ppSlideSizeOnScreen16x9 = 15

function Connect-PresentationApp {
    try {
        return New-Object -ComObject KWPP.Application
    } catch {
        return New-Object -ComObject PowerPoint.Application
    }
}

function Get-OleColor {
    param(
        [Parameter(Mandatory = $true)][int]$R,
        [Parameter(Mandatory = $true)][int]$G,
        [Parameter(Mandatory = $true)][int]$B
    )
    return [System.Drawing.ColorTranslator]::ToOle([System.Drawing.Color]::FromArgb($R, $G, $B))
}

function Add-Textbox {
    param(
        [Parameter(Mandatory = $true)]$Slide,
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][double]$Left,
        [Parameter(Mandatory = $true)][double]$Top,
        [Parameter(Mandatory = $true)][double]$Width,
        [Parameter(Mandatory = $true)][double]$Height,
        [string]$FontName = 'Microsoft YaHei',
        [double]$FontSize = 20,
        [int]$FontColor = 0,
        [switch]$Bold,
        [Nullable[int]]$FillColor = $null,
        [Nullable[int]]$LineColor = $null,
        [double]$Margin = 8,
        [int]$ParagraphAlignment = 1
    )

    $shape = $Slide.Shapes.AddTextbox($msoTextOrientationHorizontal, $Left, $Top, $Width, $Height)
    $shape.TextFrame.MarginLeft = $Margin
    $shape.TextFrame.MarginRight = $Margin
    $shape.TextFrame.MarginTop = $Margin
    $shape.TextFrame.MarginBottom = $Margin
    $shape.TextFrame.WordWrap = $msoTrue
    $shape.TextFrame.AutoSize = 0
    $shape.TextFrame.TextRange.Text = $Text
    $shape.TextFrame.TextRange.Font.Name = $FontName
    $shape.TextFrame.TextRange.Font.Size = $FontSize
    $shape.TextFrame.TextRange.Font.Color.RGB = $FontColor
    $shape.TextFrame.TextRange.ParagraphFormat.Alignment = $ParagraphAlignment
    if ($Bold) {
        $shape.TextFrame.TextRange.Font.Bold = $msoTrue
    }

    if ($FillColor -ne $null) {
        $shape.Fill.Visible = $msoTrue
        $shape.Fill.ForeColor.RGB = $FillColor
    } else {
        $shape.Fill.Visible = $msoFalse
    }

    if ($LineColor -ne $null) {
        $shape.Line.Visible = $msoTrue
        $shape.Line.ForeColor.RGB = $LineColor
    } else {
        $shape.Line.Visible = $msoFalse
    }

    return $shape
}

function Add-Title {
    param(
        [Parameter(Mandatory = $true)]$Slide,
        [Parameter(Mandatory = $true)][string]$Text
    )

    Add-Textbox -Slide $Slide -Text $Text -Left 36 -Top 18 -Width 1180 -Height 42 `
        -FontName 'Microsoft YaHei UI' -FontSize 26 -FontColor (Get-OleColor 15 23 42) -Bold
}

function Add-SourceBox {
    param(
        [Parameter(Mandatory = $true)]$Slide,
        [Parameter(Mandatory = $true)][string]$Text
    )

    Add-Textbox -Slide $Slide -Text ("资料来源：" + $Text) -Left 36 -Top 672 -Width 1180 -Height 28 `
        -FontName 'Microsoft YaHei' -FontSize 8.5 -FontColor (Get-OleColor 71 85 105)
}

function Add-PictureBox {
    param(
        [Parameter(Mandatory = $true)]$Slide,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][double]$Left,
        [Parameter(Mandatory = $true)][double]$Top,
        [Parameter(Mandatory = $true)][double]$Width,
        [Parameter(Mandatory = $true)][double]$Height,
        [string]$Caption = ''
    )

    $Slide.Shapes.AddPicture($Path, $msoFalse, $msoTrue, $Left, $Top, $Width, $Height) | Out-Null
    if ($Caption) {
        Add-Textbox -Slide $Slide -Text $Caption -Left $Left -Top ($Top + $Height + 4) -Width $Width -Height 20 `
            -FontName 'Microsoft YaHei' -FontSize 9 -FontColor (Get-OleColor 71 85 105)
    }
}

function Add-Card {
    param(
        [Parameter(Mandatory = $true)]$Slide,
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$Body,
        [Parameter(Mandatory = $true)][double]$Left,
        [Parameter(Mandatory = $true)][double]$Top,
        [Parameter(Mandatory = $true)][double]$Width,
        [Parameter(Mandatory = $true)][double]$Height,
        [int]$FillColor,
        [int]$LineColor
    )

    Add-Textbox -Slide $Slide -Text '' -Left $Left -Top $Top -Width $Width -Height $Height `
        -FillColor $FillColor -LineColor $LineColor | Out-Null
    Add-Textbox -Slide $Slide -Text $Title -Left ($Left + 12) -Top ($Top + 10) -Width ($Width - 24) -Height 26 `
        -FontName 'Microsoft YaHei UI' -FontSize 18 -FontColor (Get-OleColor 15 23 42) -Bold
    Add-Textbox -Slide $Slide -Text $Body -Left ($Left + 12) -Top ($Top + 42) -Width ($Width - 24) -Height ($Height - 52) `
        -FontName 'Microsoft YaHei' -FontSize 15 -FontColor (Get-OleColor 51 65 85)
}

function Add-CodePanel {
    param(
        [Parameter(Mandatory = $true)]$Slide,
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$Code,
        [Parameter(Mandatory = $true)][double]$Left,
        [Parameter(Mandatory = $true)][double]$Top,
        [Parameter(Mandatory = $true)][double]$Width,
        [Parameter(Mandatory = $true)][double]$Height
    )

    Add-Textbox -Slide $Slide -Text '' -Left $Left -Top $Top -Width $Width -Height $Height `
        -FillColor (Get-OleColor 248 250 252) -LineColor (Get-OleColor 226 232 240) | Out-Null
    Add-Textbox -Slide $Slide -Text $Title -Left ($Left + 12) -Top ($Top + 8) -Width ($Width - 24) -Height 20 `
        -FontName 'Microsoft YaHei UI' -FontSize 15 -FontColor (Get-OleColor 30 41 59) -Bold
    Add-Textbox -Slide $Slide -Text $Code -Left ($Left + 12) -Top ($Top + 34) -Width ($Width - 24) -Height ($Height - 44) `
        -FontName 'Consolas' -FontSize 11 -FontColor (Get-OleColor 15 23 42)
}

$ppt = $null
$presentation = $null

try {
    $ppt = Connect-PresentationApp
    $ppt.Visible = $msoFalse
    $presentation = $ppt.Presentations.Add()
    $presentation.PageSetup.SlideSize = $ppSlideSizeOnScreen16x9

    $slideW = [double]$presentation.PageSetup.SlideWidth
    $slideH = [double]$presentation.PageSetup.SlideHeight

    # Slide 1
    $slide = $presentation.Slides.Add(1, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 248 250 252
    Add-Textbox -Slide $slide -Text 'MiroFish / CogSec' -Left 48 -Top 88 -Width 620 -Height 58 `
        -FontName 'Microsoft YaHei UI' -FontSize 30 -FontColor (Get-OleColor 15 23 42) -Bold | Out-Null
    Add-Textbox -Slide $slide -Text '基于反事实推演的个人决策图谱' -Left 48 -Top 148 -Width 700 -Height 56 `
        -FontName 'Microsoft YaHei UI' -FontSize 24 -FontColor (Get-OleColor 12 74 110) -Bold | Out-Null
    Add-Textbox -Slide $slide -Text "配套报告：COGSEC_COMPETITION_SUMMARY_REPOSITIONED.tex`n版本：v3.2`n日期：2026-04-22" `
        -Left 48 -Top 240 -Width 420 -Height 96 -FontName 'Microsoft YaHei' -FontSize 18 -FontColor (Get-OleColor 51 65 85) | Out-Null
    Add-Textbox -Slide $slide -Text '面向诈骗、钓鱼和社会工程场景，在用户执行高风险动作前给出路径比较、可逆性窗口和干预建议。' `
        -Left 48 -Top 370 -Width 620 -Height 90 -FontName 'Microsoft YaHei' -FontSize 19 -FontColor (Get-OleColor 30 41 59) `
        -FillColor (Get-OleColor 239 246 255) -LineColor (Get-OleColor 186 230 253) | Out-Null
    Add-PictureBox -Slide $slide -Path (Join-Path $assetsRoot 'mirofish_logo.jpeg') -Left 760 -Top 110 -Width 400 -Height 260 `
        -Caption '项目 logo / 本地开源仓库资产'
    Add-SourceBox -Slide $slide -Text '本地素材：static/image/MiroFish_logo_compressed.jpeg；报告正文：docs/COGSEC_COMPETITION_SUMMARY_REPOSITIONED.tex'

    # Slide 2
    $slide = $presentation.Slides.Add(2, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 255 255 255
    Add-Title -Slide $slide -Text '1. 这个系统是做什么的'
    Add-Textbox -Slide $slide -Text "它不是只判断像不像诈骗，而是帮助用户在危险动作发生前做决定：`n`n• 识别当前场景中的高危动作与诱导线索`n• 比较继续执行与暂停核验两条路径`n• 输出风险差异、可逆性窗口和个性化干预建议" `
        -Left 52 -Top 96 -Width 520 -Height 280 -FontName 'Microsoft YaHei' -FontSize 20 -FontColor (Get-OleColor 30 41 59) | Out-Null
    Add-Card -Slide $slide -Title '输入' -Body '文本 / 聊天记录 / 截图 / 场景描述' -Left 640 -Top 120 -Width 170 -Height 120 `
        -FillColor (Get-OleColor 239 246 255) -LineColor (Get-OleColor 186 230 253)
    Add-Card -Slide $slide -Title '识别' -Body 'T0 护栏 + 风险因子 + ThreatKnowledgeRAG' -Left 835 -Top 120 -Width 170 -Height 120 `
        -FillColor (Get-OleColor 240 253 244) -LineColor (Get-OleColor 187 247 208)
    Add-Card -Slide $slide -Title 'Fork' -Body 'Branch A / Branch B 反事实推演' -Left 1030 -Top 120 -Width 170 -Height 120 `
        -FillColor (Get-OleColor 255 247 237) -LineColor (Get-OleColor 254 215 170)
    Add-Card -Slide $slide -Title '输出' -Body '风险差异 / 可逆性 / 干预处方' -Left 835 -Top 270 -Width 170 -Height 120 `
        -FillColor (Get-OleColor 250 245 255) -LineColor (Get-OleColor 221 214 254)
    Add-Textbox -Slide $slide -Text '一句话：把模糊风险转换成可比较、可解释、可干预的决策图谱。' `
        -Left 640 -Top 430 -Width 560 -Height 70 -FontName 'Microsoft YaHei UI' -FontSize 21 -FontColor (Get-OleColor 15 23 42) -Bold `
        -FillColor (Get-OleColor 248 250 252) -LineColor (Get-OleColor 226 232 240) | Out-Null
    Add-SourceBox -Slide $slide -Text '报告正文：执行摘要 / 它是做什么的'

    # Slide 3
    $slide = $presentation.Slides.Add(3, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 255 255 255
    Add-Title -Slide $slide -Text '2. 为什么基于 MiroFish 可以构建个人决策图谱'
    Add-Textbox -Slide $slide -Text "MiroFish 原始强项不是某个单场景功能，而是复杂情境建模闭环：`n`n• 非结构化输入 -> 图谱/状态对象`n• 多角色、多因素约束下的环境构造`n• 状态演化与关键分叉跟踪`n• 报告输出与交互解释`n`n这正好可以从世界排演缩放到个体关键动作前的局部平行路径。" `
        -Left 52 -Top 92 -Width 470 -Height 370 -FontName 'Microsoft YaHei' -FontSize 19 -FontColor (Get-OleColor 30 41 59) | Out-Null
    Add-PictureBox -Slide $slide -Path (Join-Path $assetsRoot 'run_1.png') -Left 560 -Top 96 -Width 620 -Height 430 `
        -Caption '本地运行截图：原始 MiroFish 首页与输入入口'
    Add-Textbox -Slide $slide -Text '方法迁移逻辑：平行世界 -> 局部平行路径；群体演化 -> 个体决策分叉。' `
        -Left 52 -Top 500 -Width 1128 -Height 60 -FontName 'Microsoft YaHei UI' -FontSize 20 -FontColor (Get-OleColor 12 74 110) -Bold `
        -FillColor (Get-OleColor 239 246 255) -LineColor (Get-OleColor 186 230 253) | Out-Null
    Add-SourceBox -Slide $slide -Text 'MiroFish GitHub：https://github.com/666ghj/MiroFish；MiroFish-Offline：https://github.com/nikmcfly/MiroFish-Offline'

    # Slide 4
    $slide = $presentation.Slides.Add(4, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 255 255 255
    Add-Title -Slide $slide -Text '3. 原版 MiroFish 与当前项目的关键差异'
    Add-Card -Slide $slide -Title '原版 MiroFish' -Body "• 群体/环境的未来排演`n• 输入是报告、新闻、政策、故事等现实种子`n• 输出是预测报告与交互式数字世界`n• 重心是图谱构建、环境搭建与大规模 Agent 模拟" `
        -Left 52 -Top 96 -Width 520 -Height 360 -FillColor (Get-OleColor 248 250 252) -LineColor (Get-OleColor 226 232 240)
    Add-Card -Slide $slide -Title '当前 CogSec 项目' -Body "• 个体在诈骗场景中的关键决策路径`n• 输入是对话、文本、截图、问卷与上下文`n• 输出是个人决策图谱、双分支对照、可逆性与处方`n• 重心是 T0/T1、风险因子、RAG、Fork 与 Reporter" `
        -Left 628 -Top 96 -Width 552 -Height 360 -FillColor (Get-OleColor 239 246 255) -LineColor (Get-OleColor 186 230 253)
    Add-Textbox -Slide $slide -Text '准确说法：以 MiroFish 为情境建模底座，以 CogSec 为认知安全主线。' `
        -Left 52 -Top 500 -Width 1128 -Height 64 -FontName 'Microsoft YaHei UI' -FontSize 21 -FontColor (Get-OleColor 15 23 42) -Bold `
        -FillColor (Get-OleColor 255 247 237) -LineColor (Get-OleColor 254 215 170) | Out-Null
    Add-SourceBox -Slide $slide -Text '对照来源：本地 README、README-EN 与报告正文 为什么基于 MiroFish 可以构建个人决策图谱'

    # Slide 5
    $slide = $presentation.Slides.Add(5, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 255 255 255
    Add-Title -Slide $slide -Text '4. 同类竞品与开源调研'
    Add-Card -Slide $slide -Title '消费者 AI 反诈' -Body "Bitdefender Scamio`nNorton Genie`n`n特点：更像内容层第二意见，强在快筛与低门槛。" `
        -Left 52 -Top 96 -Width 260 -Height 220 -FillColor (Get-OleColor 239 246 255) -LineColor (Get-OleColor 186 230 253)
    Add-Card -Slide $slide -Title '企业人因风险平台' -Body "SoSafe`nKnowBe4 AIDA`nAdaptive Security`n`n特点：重培训闭环与组织长期风险下降。" `
        -Left 332 -Top 96 -Width 260 -Height 220 -FillColor (Get-OleColor 240 253 244) -LineColor (Get-OleColor 187 247 208)
    Add-Card -Slide $slide -Title 'SOC / Triage Agent' -Body "Microsoft Defender Phishing Triage Agent`n`n特点：服务分析师工作流，而非普通用户的即时决策辅助。" `
        -Left 612 -Top 96 -Width 260 -Height 220 -FillColor (Get-OleColor 255 247 237) -LineColor (Get-OleColor 254 215 170)
    Add-Card -Slide $slide -Title '训练 / 开源 / 研究' -Body "Pretexta`nAXIS`n`n特点：前者偏训练与复盘，后者偏多智能体反事实解释研究。" `
        -Left 892 -Top 96 -Width 288 -Height 220 -FillColor (Get-OleColor 250 245 255) -LineColor (Get-OleColor 221 214 254)
    Add-Textbox -Slide $slide -Text '结论：已存在大量检测、训练、triage 与研究解释方案，但个人关键动作前的反事实决策图谱仍有明显空位。' `
        -Left 52 -Top 360 -Width 1128 -Height 110 -FontName 'Microsoft YaHei UI' -FontSize 21 -FontColor (Get-OleColor 15 23 42) -Bold `
        -FillColor (Get-OleColor 248 250 252) -LineColor (Get-OleColor 226 232 240) | Out-Null
    Add-Textbox -Slide $slide -Text "代表链接：`nBitdefender Scamio / Norton Genie / SoSafe / KnowBe4 AIDA / Adaptive Security / Microsoft Defender / Pretexta / AXIS" `
        -Left 52 -Top 500 -Width 1128 -Height 80 -FontName 'Microsoft YaHei' -FontSize 16 -FontColor (Get-OleColor 51 65 85) | Out-Null
    Add-SourceBox -Slide $slide -Text '产品与开源入口见 PPT_MATERIALS.md；报告正文 同类竞品与 GitHub 开源调研'

    # Slide 6
    $slide = $presentation.Slides.Add(6, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 255 255 255
    Add-Title -Slide $slide -Text '5. 为什么系统要这样设计：理论与方法依据'
    Add-Card -Slide $slide -Title '双系统理论' -Body "高压力、高不确定性下，System 1 更容易接管决策。`n=> 支持 T0 / T1 双层结构。" `
        -Left 52 -Top 96 -Width 260 -Height 220 -FillColor (Get-OleColor 239 246 255) -LineColor (Get-OleColor 186 230 253)
    Add-Card -Slide $slide -Title '用户情境与个体差异' -Body "同样内容对不同人、不同上下文的风险并不一样。`n=> 支持 persona_state_vector。" `
        -Left 332 -Top 96 -Width 260 -Height 220 -FillColor (Get-OleColor 240 253 244) -LineColor (Get-OleColor 187 247 208)
    Add-Card -Slide $slide -Title '说服原则' -Body "权威、紧迫、社会认同、承诺一致性、互惠、喜好。`n=> 支持攻击-人-环境图谱。" `
        -Left 612 -Top 96 -Width 260 -Height 220 -FillColor (Get-OleColor 255 247 237) -LineColor (Get-OleColor 254 215 170)
    Add-Card -Slide $slide -Title '反事实解释' -Body "不只说明发生了什么，更说明换一条路径会怎样。`n=> 支持 Branch A / Branch B。" `
        -Left 892 -Top 96 -Width 288 -Height 220 -FillColor (Get-OleColor 250 245 255) -LineColor (Get-OleColor 221 214 254)
    Add-Textbox -Slide $slide -Text '因此，T0 + 风险向量 + ThreatKnowledgeRAG + Fork + Reporter 不是堆模块，而是从问题本质、竞品边界与理论依据共同推导出的组合。' `
        -Left 52 -Top 360 -Width 1128 -Height 120 -FontName 'Microsoft YaHei UI' -FontSize 21 -FontColor (Get-OleColor 15 23 42) -Bold `
        -FillColor (Get-OleColor 248 250 252) -LineColor (Get-OleColor 226 232 240) | Out-Null
    Add-SourceBox -Slide $slide -Text 'Frontiers 2025 / NIST Phish Scale / PMC social engineering cognition / persuasion survey / AXIS'

    # Slide 7
    $slide = $presentation.Slides.Add(7, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 255 255 255
    Add-Title -Slide $slide -Text '6. 系统总体架构与主链工作流'
    Add-Card -Slide $slide -Title '输入治理层' -Body '文本 / 聊天记录 / 截图 OCR / 问卷 / 上下文 + 隐私脱敏' `
        -Left 52 -Top 104 -Width 250 -Height 140 -FillColor (Get-OleColor 239 246 255) -LineColor (Get-OleColor 186 230 253)
    Add-Card -Slide $slide -Title '分析理解层' -Body '风险因子提取、场景识别、ThreatKnowledgeRAG、攻击-人-环境图谱' `
        -Left 332 -Top 104 -Width 250 -Height 140 -FillColor (Get-OleColor 240 253 244) -LineColor (Get-OleColor 187 247 208)
    Add-Card -Slide $slide -Title '反事实推演层' -Body 'WorldState、Fork、Branch A / B、风险差值与可逆性' `
        -Left 612 -Top 104 -Width 250 -Height 140 -FillColor (Get-OleColor 255 247 237) -LineColor (Get-OleColor 254 215 170)
    Add-Card -Slide $slide -Title '报告与干预层' -Body '数字孪生摘要、路径对照、干预窗口、个性化处方' `
        -Left 892 -Top 104 -Width 288 -Height 140 -FillColor (Get-OleColor 250 245 255) -LineColor (Get-OleColor 221 214 254)
    Add-Textbox -Slide $slide -Text 'Input -> PrivacySanitizer -> PersonaStateVector -> RiskGraphBundle -> WorldState -> Fork A/B -> Counterfactual Risk -> Intervention' `
        -Left 52 -Top 300 -Width 1128 -Height 70 -FontName 'Consolas' -FontSize 18 -FontColor (Get-OleColor 15 23 42) `
        -FillColor (Get-OleColor 248 250 252) -LineColor (Get-OleColor 226 232 240) | Out-Null
    Add-Textbox -Slide $slide -Text "T0：验证码 / 转账 / 屏幕共享 / 安全账户等红旗的毫秒级护栏`nT1：画像、图谱、Fork 比较和反事实报告生成" `
        -Left 52 -Top 410 -Width 1128 -Height 110 -FontName 'Microsoft YaHei' -FontSize 20 -FontColor (Get-OleColor 30 41 59) | Out-Null
    Add-SourceBox -Slide $slide -Text '本地 README、docs/COGSEC_MIROFISH_MAINLINE_REFACTOR.md、报告正文 系统总体架构'

    # Slide 8
    $slide = $presentation.Slides.Add(8, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 255 255 255
    Add-Title -Slide $slide -Text '7. 现有界面与产品形态证据'
    Add-PictureBox -Slide $slide -Path (Join-Path $assetsRoot 'run_3.png') -Left 44 -Top 78 -Width 720 -Height 405 `
        -Caption '本地运行截图：图谱可视化 + 环境搭建 / 双栏工作流'
    Add-PictureBox -Slide $slide -Path (Join-Path $assetsRoot 'run_6.png') -Left 790 -Top 78 -Width 390 -Height 405 `
        -Caption '本地运行截图：复杂图谱与节点详情'
    Add-Textbox -Slide $slide -Text "前端当前最有价值的证据不是概念稿，而是已经存在的工作流与工作台结构：`n`n• 首页 / 主流程 / 报告页 / 交互页`n• CogSecWorkbench 五屏：用户数字孪生、攻击-人-环境图谱、双分支反事实推演、风险 / 可逆性曲线、个性化干预处方" `
        -Left 52 -Top 520 -Width 1128 -Height 120 -FontName 'Microsoft YaHei' -FontSize 19 -FontColor (Get-OleColor 30 41 59) | Out-Null
    Add-SourceBox -Slide $slide -Text '本地截图：static/image/Screenshot/运行截图3.png、运行截图6.png；组件：frontend/src/components/cogsec/CogSecWorkbench.vue'

    # Slide 9
    $slide = $presentation.Slides.Add(9, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 255 255 255
    Add-Title -Slide $slide -Text '8. 关键代码证据'
    $code1 = @'
self.profile_extractor = CognitiveProfileExtractor(...)
self.threat_rag = ThreatKnowledgeRAG(Config.CHROMA_PATH)
self.runtime = MiroFishRuntime()
self.reporter = CounterfactualReporter()
self.t0_responder = T0FastResponder(...)
self.privacy_sanitizer = PrivacySanitizer(...)

runtime_result = self.runtime.run(...)
report = self.reporter.generate_report(...)
'@
    $code2 = @'
@app.get("/health")
@app.get("/api/cogsec/sample")
@app.post("/api/cogsec/analyze")

const screens = [
  { key: "twin", label: "1. 用户数字孪生" },
  { key: "graph", label: "2. 攻击-人-环境图谱" },
  { key: "fork", label: "3. 双分支反事实推演" },
  { key: "curve", label: "4. 风险 / 可逆性曲线" },
  { key: "prescription", label: "5. 个性化干预处方" }
]
'@
    Add-CodePanel -Slide $slide -Title '后端主链编排：backend/app/services/cogsec_service.py' -Code $code1 `
        -Left 52 -Top 98 -Width 548 -Height 330
    Add-CodePanel -Slide $slide -Title '最小 Demo 与五屏工作台：run_cogsec_demo.py / CogSecWorkbench.vue' -Code $code2 `
        -Left 632 -Top 98 -Width 548 -Height 330
    Add-Textbox -Slide $slide -Text "结论：项目已经不是 PPT 先行 的概念稿，后端主链对象、最小 Demo 入口与五屏工作台都已有明确代码落点。" `
        -Left 52 -Top 470 -Width 1128 -Height 90 -FontName 'Microsoft YaHei UI' -FontSize 21 -FontColor (Get-OleColor 15 23 42) -Bold `
        -FillColor (Get-OleColor 248 250 252) -LineColor (Get-OleColor 226 232 240) | Out-Null
    Add-SourceBox -Slide $slide -Text 'backend/app/services/cogsec_service.py；backend/run_cogsec_demo.py；frontend/src/components/cogsec/CogSecWorkbench.vue'

    # Slide 10
    $slide = $presentation.Slides.Add(10, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 255 255 255
    Add-Title -Slide $slide -Text '9. 创新点与差异化价值'
    Add-Card -Slide $slide -Title '从内容识别转向决策建模' -Body '最小分析单位不是消息文本，而是用户下一步的高危动作。' `
        -Left 52 -Top 96 -Width 260 -Height 210 -FillColor (Get-OleColor 239 246 255) -LineColor (Get-OleColor 186 230 253)
    Add-Card -Slide $slide -Title '个体风险因子进入路径推演' -Body '风险向量用于解释为什么同样刺激对不同人作用不同。' `
        -Left 332 -Top 96 -Width 260 -Height 210 -FillColor (Get-OleColor 240 253 244) -LineColor (Get-OleColor 187 247 208)
    Add-Card -Slide $slide -Title '反事实报告作为主输出' -Body '系统主打的是 Branch A / B 差异，而不是单一风险分。' `
        -Left 612 -Top 96 -Width 260 -Height 210 -FillColor (Get-OleColor 255 247 237) -LineColor (Get-OleColor 254 215 170)
    Add-Card -Slide $slide -Title 'T0 / T1 双层防御结构' -Body '把毫秒级护栏与深度解释结合起来，兼顾阻断与说明。' `
        -Left 892 -Top 96 -Width 288 -Height 210 -FillColor (Get-OleColor 250 245 255) -LineColor (Get-OleColor 221 214 254)
    Add-Textbox -Slide $slide -Text "创新点成立的前提：`n• 页面里真的看得到关键节点、双分支和可逆性`n• 风险因子服务于解释，而不是夸张的人格诊断`n• 用样例、测试和 benchmark 证明链路稳定" `
        -Left 52 -Top 360 -Width 1128 -Height 150 -FontName 'Microsoft YaHei' -FontSize 20 -FontColor (Get-OleColor 30 41 59) | Out-Null
    Add-SourceBox -Slide $slide -Text '报告正文 创新点与差异化价值'

    # Slide 11
    $slide = $presentation.Slides.Add(11, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 255 255 255
    Add-Title -Slide $slide -Text '10. 风险治理与迭代路线'
    Add-Card -Slide $slide -Title '治理边界' -Body "• 仅用于防御与决策辅助`n• 优先本地/前置脱敏`n• 个体风险因子不形成惩罚性标签`n• 证据不足时允许返回需要人工核验" `
        -Left 52 -Top 98 -Width 520 -Height 270 -FillColor (Get-OleColor 248 250 252) -LineColor (Get-OleColor 226 232 240)
    Add-Card -Slide $slide -Title '比赛版近期优先级' -Body "• 稳定个人决策 DAG 可视化`n• 强化 Branch A / Branch B 报告与可逆性曲线`n• 补标准场景样例与截图`n• 用 benchmark/测试结果支撑性能表述`n• 统一首页与答辩主叙事口径" `
        -Left 612 -Top 98 -Width 568 -Height 270 -FillColor (Get-OleColor 239 246 255) -LineColor (Get-OleColor 186 230 253)
    Add-Textbox -Slide $slide -Text "中长期可扩展：更丰富的风险因子动态更新、更强多模态输入、更完整知识库与标注体系，以及复杂关系链/长期演化场景下的多智能体环境建模。" `
        -Left 52 -Top 430 -Width 1128 -Height 90 -FontName 'Microsoft YaHei' -FontSize 19 -FontColor (Get-OleColor 30 41 59) | Out-Null
    Add-SourceBox -Slide $slide -Text '报告正文 风险治理、隐私与伦理边界；当前局限与迭代路线'

    # Slide 12
    $slide = $presentation.Slides.Add(12, $ppLayoutBlank)
    $slide.Background.Fill.ForeColor.RGB = Get-OleColor 248 250 252
    Add-Title -Slide $slide -Text '11. 资料入口与结束页'
    Add-Textbox -Slide $slide -Text "配套文件：`n• COGSEC_COMPETITION_SUMMARY_REPOSITIONED.tex`n• PPT_MATERIALS.md`n• ppt_assets/`n`n关键公开链接：`n• MiroFish: https://github.com/666ghj/MiroFish`n• Pretexta: https://github.com/dalpan/Pretexta`n• AXIS: https://arxiv.org/abs/2505.17801`n• NIST Phish Scale: https://www.nist.gov/publications/phishing-user-context-understanding-nist-phish-scale" `
        -Left 52 -Top 110 -Width 760 -Height 360 -FontName 'Microsoft YaHei' -FontSize 18 -FontColor (Get-OleColor 30 41 59) | Out-Null
    Add-Textbox -Slide $slide -Text '一句话收束：在损失真正发生前，为个体提供一张可解释、可比较、可干预的决策图谱。' `
        -Left 52 -Top 510 -Width 760 -Height 90 -FontName 'Microsoft YaHei UI' -FontSize 23 -FontColor (Get-OleColor 15 23 42) -Bold `
        -FillColor (Get-OleColor 255 255 255) -LineColor (Get-OleColor 226 232 240) | Out-Null
    Add-PictureBox -Slide $slide -Path (Join-Path $assetsRoot 'mirofish_logo.jpeg') -Left 860 -Top 150 -Width 280 -Height 190 `
        -Caption '项目本地素材'
    Add-SourceBox -Slide $slide -Text '更多资料见 PPT_MATERIALS.md'

    if (Test-Path $outputPath) {
        Remove-Item -LiteralPath $outputPath -Force
    }
    $presentation.SaveAs($outputPath, $ppSaveAsOpenXMLPresentation)
}
finally {
    if ($presentation -ne $null) {
        $presentation.Close()
    }
    if ($ppt -ne $null) {
        $ppt.Quit()
    }
}

Write-Output "PPT generated: $outputPath"
