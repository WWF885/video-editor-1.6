# 标准运行与计划

## 运行
使用Python 3.12.14，先执行`python -m pip install -r requirements.txt`；FFmpeg和ffprobe需已安装并在PATH中。Windows用`py -3.12`代替python。所有命令在完整技能文件夹内执行，不能只复制SKILL.md。

```bash
python scripts/run.py --check
python scripts/run.py --demo --demo-dir work/demo
python scripts/verify_standard.py
python scripts/run.py --source input.mp4 --plan plan.json --captions captions.json --output work/final.mp4
```

字体已内置，标准模式禁止替代字体。自检输出必须通过；每次标准入口都会复核40个栅格采样点。输出同时附带SRT与环境报告。首次生成演示无需真人素材或API密钥，演示中的字幕是明确标注的排版测试，不代表语音转写。

Dockerfile提供隔离安装入口，构建`docker build -t wenfeng-editor .`，Windows/macOS/Linux可以挂载工作目录后运行。Docker构建使用固定Python与Python依赖；操作系统包仓库会变化，不能把同一Dockerfile当作不可变镜像。严格跨机器复现需使用同一已构建镜像摘要与CPU架构；当前包不宣称已发布或测试这样的镜像。

## 锁定与可填写字段
必须给出`style_profile: "wenfeng-standard-v1"`，必须给出`standard_version: "1.6"`；width512、height902、fps30固定。未知字段、其他颜色/字体/尺寸/字幕位置会报错。cuts记录主口播源入出点；必须明确提供cuts且第一段in=0。scenes从0开始连续覆盖完整成片。字幕使用最终成片真实时刻。

开场必须用opening模板，直接显示原视频全画面，艺术字标题第一帧可见。渲染前必须提供3个候选标题供用户选择，或采用用户自定标题。plan.opening_title记录`{"text":"用AI做生意","lines":["用AI","做生意"],"highlights":["AI","生意"],"approved":true,"source":"user"}`；此为字段示例，实际须用户确认；source=chosen时还必须保存3个候选标题candidates，禁止伪造approved。
paragraphs是完整语义段列表，每项`{"start":0,"end":3,"summary":"本段概述"}`，与scenes在时间、数量上一一对应且覆盖全片。相邻scene的template必须不同；首段opening，后段可在7种模板中轮换。首帧纯封面；后续左上角显示summary，右上角不显示编号。标题、图解超宽时精简概括；字幕超宽时按真实语音分句，禁止缩字或均分时间。对白cue为`start,end,text,highlights`，highlights最多2个，必须存在于文字中。字幕单行固定26px及底部深色底条。

所有场景共同字段：start,end,template,title,subtitle,show_presenter,presenter_position,presenter_size,presenter_space,reason,presenter。presenter接受crop、head_box和framing_confirmed:true，表示源视频视觉方向归一化[left,top,right,bottom]矩形或正方形取景；圆窗等比cover铺满，禁止留白和拉伸。framing_confirmed必须依据逐段抽帧，确认完整头发和整张脸；肩部仅在不影响头脸完整时保留，不是自动检测。presenter_position默认bottom_center，可top并配presenter_space。人物圆框、白边阴影由程序固定，不能重新生成头像。优先头发与整张脸，肩部可少露；原片本身缺失头脸范围时报告素材限制。

| template | 内容字段 | 固定呈现 |
| --- | --- | --- |
| opening | 已确认title,subtitle | 原视频全屏、中央超大艺术字封面 |
| presenter | title,subtitle | 顶部标题、大人物窗、毛玻璃底色 |
| path | nodes恰好2项，takeaway | 双节点与动态箭头、圆形人物 |
| statement | before,after | 对照词、下行箭头、放大结论 |
| amplifier | traits最多3项+center，或metric+metric_note | 价值汇聚连线或大数字，不同论点拆场 |
| compare | columns恰好2列，每列title/items最多3项 | 等宽双栏与递进要点 |
| list | items最多3项 | 按实际讲话逐条出现 |
| media | asset,asset_in/out,asset_crop,media_box,focus,asset_audio | 真实图片/视频卡片与可隐藏圆窗 |

nodes、traits、items均为`[{"at":2.0,"text":"重点"}]`，at是成片绝对时间，须在场景内。compare columns为`[{"title":"方案A","items":[...]},{"title":"方案B","items":[...]}]`。每个标题/图解都需符合实际讲话，不凭模板新增结论。

media的asset相对plan.json解析；辅助视频静音、原速；asset_out不足覆盖场景即报错，不循环。asset_crop是源素材归一化left/top/right/bottom；media_box是成片归一化x/y/width/height，默认[.06,.28,.88,.58]，顶部不早于.27H，底部不超过.89H。focus=[{"at":12.5,"box":[.1,.2,.8,.4]}]，box相对裁切后素材。圆窗挡内容就换角或show_presenter=false。

示例完整结构见assets/standard-demo.json及assets/demo-captions.json。复制示例后更换素材/真实时间，不能把排版测试句当用户对白。旧references/plan-format.md仅用于显式legacy自由模式；标准模式不要混用mode、theme、caption_y等旧字段。

## 一致性验收
scripts/verify_standard.py通过内置非真人测试画面逐帧验证模板栅格SHA256，覆盖7种模板、3种转场、首帧标题与单行字幕。它同时检查锁定字段被拒绝。该测试与ASR无关，不检验另一台机器上真实素材的音质、转写或分镜合理性。

run.py同时校验standard-manifest.json中的字体和程序文件。渲染review保留raster_sha256与输入哈希：相同输入的两次渲染比较raster_sha256，而非MP4文件SHA。FFmpeg不同版本/CPU可能使真实视频解码与AAC编码有细微差异；要严格复现使用同一镜像和输入。听审需单独完成，未听审不得以技术检查代替。

标准演示的预置标题与approved标记仅用于无口播的合成校准，不代表用户确认过真实作品；剪辑真实口播时必须重新获取用户选定标题。


圆窗位置与缩放：默认下方水平居中（bottom_center），底边固定在790px、避开单行字幕；旧bottom_left/bottom_right计划也统一居中。presenter_size允许120–220px，默认184px。上方使用top，先检查整段文字、图解和素材的占用范围，再填写空白区域presenter_space=[x,y,width,height]（归一化，位于y=.27–.68）；圆窗居中于该区域并自动缩小至容纳范围。不得遮挡信息；若整段没有足够空白，则移到下方居中。位置与大小按场景固定，禁止随每帧检测跳动；缩放后仍须逐段检查完整头发与整张脸。脚本不自动识别空白，空白区域由编排阶段检查后指定。

## v1.6 封面与画板节奏（优先于历史规则）

- 首帧即封面，背景必须为原始主视频第0帧，不能用加工过的旧成片或截图替代。cuts第一个in必须为0；渲染时首段原视频持续正常播放，不冻结、不静音。另存成片第0帧为cover.png供发布。
- 剪辑前给3个候选短标题，每个明确列出两行供选择，用户也可自定。标题必须恰好两行，每行1–4个字符、总计不超过8个字符；标点、空格、符号均禁用。英文和数字也逐字符计数。长题必须重新概括并由用户确认，不能机械截断。每行独立水平居中，固定96px超大描边艺术字，两行组成的文字块在整张画面正中央水平与垂直居中，关键词暖金色加粗；首帧不叠段落角标、对白字幕和进度条，第二场恢复单行对白字幕。字幕cue/SRT仍保留开场实际语音，不删稿。
- 圆窗优先完整头发、头顶、两侧鬓角、脸和下巴，不能只显示五官。填写presenter.head_box（归一化left,top,right,bottom），它是该场景起中末及运动极值帧完整头部范围的并集，不能只标面部检测框。几何检查要求头框四角位于cover圆内且留10%径向安全量，失败就扩大/平移原视频crop，不靠缩小圆窗补救。原片已截掉的头发或脸无法恢复，须索要原片或明确素材限制，禁止人工勾选通过。
- 每个完整语义段更换场景和模板；长段继续按真实分句切分。单个画板场景最长12秒，建议4–8秒，禁止用一个模板撑几十秒。
- 画板最长连续静止不得超过3秒。内置每2.4秒对已出现的知识卡/节点/对比项/素材重点轮换描边追踪，动画约0.65秒；新节点、箭头、重点随讲话时间渐进出现。动态必须作用于知识内容，不能把头像嘴动、字幕变化、底部进度条或背景闪烁当作画板动效。未说到的信息不能提前出现；不要抖动或随机缩放人物。相邻长段轮换路径、对比、观点、清单、素材等展示，避免只换字。
- 交付前检查封面0帧与缩略图可读性；圆窗每场起中末及动作极值抽查；画板以1秒步进检查整个时间线，记录最长静止段。assets/visual-review-template.json新增封面与静止时长项、head_evidence；审核事实与实际成片绑定。几何框来自真实检查，不宣称自动识别完整头发，人工框错仍会导致错误。
- 参考本次外部成片暴露的失败：长标题带标点；缩略图标题不够集中；头发/下巴被圆边裁切；重复图解停留过久；部分清单图解与真人大小关系单一。只拿截图和文字说明并不能证明安装成功，必须执行--check并交付环境、剪辑计划与验收报告。

run.py在实际成片上以5fps检查知识内容区域，排除圆窗、字幕、标题和进度条，超过3秒近似静止即停止。像素变化检查不能判定动效语义，仍需视觉复核。

侧倾头部可用presenter.head_outline补充8–64个归一化外轮廓点，覆盖整段运动的头顶、发际、鬓角、脸颊、下巴及head_box四个极值；在此情况下检查实际轮廓到圆心距离，避免矩形空角造成误拒。没有可靠轮廓时仍按head_box四角保守检查。轮廓点必须来自逐段抽帧，不可只标五官、缩小包围框或任意捏造以通过检查；复核实际圆窗仍必需。
