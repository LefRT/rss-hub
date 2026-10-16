# rss-hub

把没有 RSS 的网站转化为标准 RSS feed，GitHub Actions 每 30 分钟自动重建。

- `sources.json` — 数据源登记表（加新网站就在这里加一段）
- `generate.py` — 生成器（只用 Python 标准库），支持 `mihoyo_content_v2` 类型（米哈游官网新闻），按需扩类型
- `rss/*.xml` — 生成的 feed；`rss/all.xml` 为全源聚合流

Feed 地址（GitHub Pages）：`https://leftrt.github.io/rss-hub/rss/<源id>.xml`

当前收录：
| 源 | id | 说明 |
|---|---|---|
| 绝区零·官网新闻 | `zzz-news` | 米哈游 content_v2 API，iChanId=273 |
