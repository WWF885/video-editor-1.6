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
- items的`at`是元素开始可读的讲话时刻，后续渐进出现；`text`是一行图解短语。超过8个items应拆场景。过长文字缩短图解概括而不改变对白。
- theme只能light或dark；默认配色在脚本中统一。输出保持原比例，尺寸比例不匹配时使用等比contain，默认不裁人物。
- `caption_y`可设置0—1之间的字幕基线位置；默认约0.71，需按人物位置检查。标题/图解不要落到字幕区域。

转写输入为句子列表，每句包含`start,end,text`；需要拆分的句子还需`words:[{start,end,word}]`。若word的时间均为0或交叠，先补对齐。已校正短cue可直接交给渲染器，包含`start,end,text,highlights`。
