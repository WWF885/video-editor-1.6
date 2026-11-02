# 计划格式

所有字幕与scenes均使用剪辑后的时间，不是源片时间。输出帧率为显式整数，默认30；对特殊帧率先使用时间保持的转码，不通过改标签变速。

```json
{
 "width":512,"height":902,"fps":30,"theme":"light",
 "cuts":[{"in":1.0,"out":26.2},{"in":36.8,"out":53.9}],
 "scenes":[
  {"start":0,"end":3,"mode":"overlay","title":"做值钱的IP","items":[{"at":0,"text":"不做短暂的网红"}]},
  {"start":17,"end":25,"mode":"steps","title":"01  让业务和价值被看见","items":[{"at":17.3,"text":"低成本流量"},{"at":21.2,"text":"业务被看见"},{"at":23.4,"text":"自己更值钱"}]}
 ]
}
```

- 省略cuts表示保留整片。保留cuts必须in<out且在源片内；不变速。
- 场景不交叠，end不超过成片，字幕也不得超长。mode包括`overlay`（真人全屏＋顶部摘要），`card`（白/深知识卡＋人物窗），`steps`（编号清单＋人物窗），`flow`（逐步箭头＋人物窗），`compare`（左右对比＋人物窗），`media`（真实辅助图片/视频＋人物窗）。
- compare的items每项需加`column`为0或1；可以先用items第一行放侧名，后续作为具体差异。
- `media`提供`asset`文件路径（相对plan.json）；`asset_in`为辅助视频源入点，默认为0。图片静态展示，视频在原速连续解码，长度不足就报错，不偷偷循环。字幕和原片音轨仍连续。
- items的`at`是元素开始可读的讲话时刻，后续渐进出现；`text`是一行图解短语。普通场景最多4行（视觉上优先不超过3个核心元素），compare每侧最多4行；超过则拆场景。过长文字缩短图解概括而不改变对白。
- theme只能light或dark；默认配色在脚本中统一。输出保持原比例，尺寸比例不匹配时使用等比contain，圆形窗使用逐段确认的正方形取景；其他布局默认不裁人物。
- `caption_y`可设置0—1之间的字幕基线位置；默认约0.925，需按人物位置检查。标题/图解不要落到字幕区域。

转写输入为句子列表，每句包含`start,end,text`；需要拆分的句子还需`words:[{start,end,word}]`。若word的时间均为0或交叠，先补对齐。已校正短cue可直接交给渲染器，包含`start,end,text,highlights`。

## 毛玻璃与白色圆框
默认`background: "frosted"`、`presenter_shape: "circle"`、`caption_y: 0.925`。保留旧矩形窗可显式设置`presenter_shape: "rounded"`。
`presenter`为全局配置，场景同名字段可覆盖：`{"x":0.56,"y":0.67,"diameter":0.36,"crop":[0,0.0776,1,0.6452]}`。
x/y分别按成片宽/高归一化，diameter按画宽归一化；crop为源片归一化left,top,right,bottom，必须正方形且在源片内。示例crop仅适合512×902示例素材，不得套用其他视频。未填crop时中心裁切仅作技术回退，正式交付必须逐段验收并填写合适取景。
开场场景的`title`填写内容相关标题；标题宽度校验失败时精简标题，不能硬塞。

## 辅助素材场景
先读material-direction.md完成素材盘点与语义匹配，再填写实际时间。示例：
```json
{
 "start": 8, "end": 12, "mode": "media", "title": "看这个真实案例",
 "asset": "assets/case.mp4", "asset_in": 2, "asset_out": 6,
 "reason": "展示当前讲到的操作结果", "asset_audio": "mute",
 "media_box": [0.06,0.14,0.88,0.70], "show_presenter": false,
 "focus": [{"at":9,"box":[0.1,0.2,0.8,0.4]}]
}
```
- asset接受本地图片/视频，均相对plan.json解析；图片无须asset_in/out。每个片段单独场景，重复使用同一文件也明确新的入点。
- media_box是成片归一化[x,y,width,height]；素材等比contain，不拉伸。asset_crop可选，是源素材归一化[left,top,right,bottom]，裁切后再等比适配。
- focus为可选重点框，at使用成片绝对时间，box为裁切后显示素材内部归一化[left,top,right,bottom]；不伪造原图内容。
- show_presenter默认true；素材关键区域会被挡时false或用场景presenter换角。圆窗绘制在素材上方，字幕最后绘制。标题在媒体框之外，必要时为标题增加顶部空间。
- asset_audio当前仅支持mute，主口播原声持续。asset_out默认文件末尾；视频可用长度必须覆盖场景，失败应调整计划，不取消检查。
- asset_manifest.json是调用者维护的素材决策表，非渲染器输入；reason仅记录理由，不执行语义匹配。
