# 文锋知识口播剪辑 Skill

将真人口播剪辑成带知识图解的视频。每次只显示一行对白字幕，并突出关键词。

## 功能

- 章节条、逐层关键词、浅色信息卡和深色知识板。
- 毛玻璃底色、白色立体圆形真人窗、开场顶部标题、步骤清单、前后对比、关系箭头和真实录屏。
- 基于真实语音时间戳生成单行字幕，长句拆分并校验宽度、重叠和有效时长。
- 保留原声与自然语速；输出MP4、SRT、ASS和可复用计划。

## 辅助素材编排

可同时提供图片、截图、录屏和辅助视频。调用技能的AI先查看素材并匹配实际讲话，再决定插入时间、展示尺寸、重点框选和人物窗是否显示。无关或重复素材不强行使用，视频默认静音，口播原声持续。

脚本支持图片/视频、明确素材入出点、等比展示、指定裁切、重点框、人物窗换角或隐藏。素材语义分析与语音转写由调用环境完成；脚本不内置自动语义分析。复杂遮罩转场、辅助原声混音需另写合成步骤。

## 使用

下载仓库，将完整文件夹放入支持SKILL.md的AI工具的技能目录，保留scripts、references、agents的目录结构。

示例：

> 使用文锋知识口播剪辑处理这个视频：单行字幕，突出关键词，采用毛玻璃背景和白色立体圆形真人窗，根据内容编排辅助图片与视频。

运行脚本需要Python、FFmpeg/ffprobe，以及Pillow、NumPy、PyAV。中文字体需自行提供。语音转写需由使用环境中的转写工具完成，本项目不内置语音识别模型。

```bash
pip install pillow numpy av
python scripts/captions.py --transcript transcript.json --font /path/chinese.otf --keywords 'IP,个人价值,专业' --out work/captions
python scripts/render.py --source input.mp4 --plan plan.json --captions work/captions.json --font /path/chinese.otf --output work/final.mp4
```

计划格式见references/plan-format.md；完整工作流程见SKILL.md。

## 范围与检查

样式来自对公开视频的画面分析；未打包参考作者视频、Logo或用户原始素材。不是任何博主的官方工具，也不保证逐帧复现原片效果。

字幕经过自动转写后仍需核对姓名、数字、否定词和专业术语。脚本自带单行和时间校验，但技术校验不能替代视听审看。
