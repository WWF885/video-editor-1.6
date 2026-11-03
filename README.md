# 文锋同款口播剪辑·标准版

固定模板、内置字体与画面校验，让不同用户使用同一套画面生成程序。默认 `wenfeng-standard-v1`；AI只填写内容、选择模板和匹配素材，不临时改写样式。

## 固定效果

毛玻璃底色、白色立体圆形真人窗、原视频首帧顶部艺术字标题、单行重点字幕、渐进图解、0.24秒固定转场。8种模板（含原视频开场）覆盖真人、路径、观点对照、价值放大、双栏比较、步骤和图片/视频素材。

## 下载与运行

点击 **Code → Download ZIP** 并完整解压；不能只复制SKILL.md。运行环境为Python3.12.14、FFmpeg与ffprobe。依赖及字体版本已固定：

```bash
python -m pip install -r requirements.txt
python scripts/run.py --check
python scripts/run.py --demo --demo-dir work/demo
python scripts/verify_standard.py
```

标准演示无需真人素材或API密钥，使用明确标注的非真人、无口播校准画面；演示字幕仅为排版测试。所有40个画面采样点必须通过，环境不合格会停止，不偷偷换字体或模板。Dockerfile提供隔离构建方式，但没有发布不可变镜像；严格跨机器复现需使用同一构建镜像摘要及CPU架构。

## 剪辑自己的素材

把主口播、可选图片/录屏/辅助视频和逐字稿交给支持Skill的AI：

> 使用文锋知识口播剪辑，默认标准模式。先理解口播和素材，按实际语音建立plan.json与captions.json，选择固定模板，用scripts/run.py渲染，不重写样式。

```bash
python scripts/run.py --source input.mp4 --plan plan.json --captions captions.json --output work/final.mp4
```

输出MP4、SRT、画面与输入校验报告和环境报告。标准计划格式见 [references/standard-mode.md](references/standard-mode.md)，完整示例见 [assets/standard-demo.json](assets/standard-demo.json)。素材编排见 [references/material-direction.md](references/material-direction.md)。语音转写与语义分析由调用环境完成，不内置ASR或自动语义分析模型。辅助视频默认静音，原口播持续、原速；视频不足不循环。中文字体附OFL许可。

## 一致性的范围

相同素材、相同剪辑计划、合格环境可复现同一套画面；已在原目录和全新拷贝完成480帧演示并得到相同栅格SHA。不同口播统一视觉风格，分镜根据内容变化。MP4字节不保证跨编码器一致；FFmpeg解码、音频及平台差异需记录环境并复核。历史手工样片不是逐像素基准，本版本内置校准图和可执行模板是后续统一标准。

安装旧版的人请用完整新版替换旧文件，运行检查后再生成；不要混合旧版mode/theme计划与标准template计划。

未打包用户真人原始视频、私人项目、账号信息或参考博主素材。技术检查不代替字幕核对和听审。字体许可见assets/fonts/OFL.txt。

技能调用名：`wwf-video-editor`。英文技能及项目命名统一使用 `wwf` 前缀。

## 1.1 默认剪辑规则

- 开始前先推荐3个候选爆款标题，由用户选择或自定后才渲染。
- 首段使用原视频全画面，顶部艺术字呈现选定标题；不以毛玻璃卡片或缩小人物窗替代首帧。
- 圆形头像完整展示头发和肩膀，矩形原片取景等比适配，保留白边和立体阴影。取景确认需逐段查看，不是自动人脸检测。
- 按完整语义段划分paragraphs，每段一场景，相邻模板必须不同。
- 左上角为当前段落概述，右上角不显示序号。
- plan需使用standard_version=1.1，并填写opening_title、paragraphs、presenter.framing_confirmed；旧计划需重新检查和编排，不能仅改版本号。
