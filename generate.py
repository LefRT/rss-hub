#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rss-hub 生成器：把没有 RSS 的网站数据源转成标准 RSS 2.0。
- 配置在 sources.json，每个源一个条目；新增网站时按现有 type 扩展 fetcher。
- 输出到 rss/<id>.xml，另生成 rss/all.xml 汇总流。
- 只用标准库，GitHub Actions 上无需 pip install。
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "rss")
UA = {"User-Agent": "Mozilla/5.0 (compatible; rss-hub generator)"}
CST = timezone(timedelta(hours=8))  # 米哈游中国官网数据用北京时间

FALLBACK_DT = datetime(1970, 1, 1, tzinfo=timezone.utc)


def http_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_dt(s):
    if not s:
        return None
    s = str(s).split(".")[0].strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=CST)
        except ValueError:
            pass
    return None


def strip_html(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def make_item(title, link, guid, dt, description, src_title):
    return {
        "title": strip_html(title) or "(无标题)",
        "link": link,
        "guid": guid,
        "pubDate": format_datetime(dt or FALLBACK_DT),
        "description": (description or "")[:800],
        "_dt": dt or FALLBACK_DT,
        "_src": src_title,
    }


# ---------------- fetcher: 米哈游官网 content_v2 API ----------------

def fetch_mihoyo_content_v2(src):
    api = src["api_base"].rstrip("/")
    url = (api + "/getContentList?iChanId=%s&iPageSize=25&iPage=1&sLangKey=%s"
           % (src["chan_id"], src.get("lang", "zh-cn")))
    d = http_json(url)
    if d.get("retcode") != 0:
        raise RuntimeError("retcode %s: %s" % (d.get("retcode"), d.get("message")))
    detail_base = (src.get("detail_base") or src.get("site")).rstrip("/")
    items = []
    for it in d["data"].get("list", []):
        ident = it.get("iInfoId") or it.get("iId") or ""
        link = it.get("sUrl") if it.get("sUrl", "").startswith("http") \
            else detail_base + "/" + str(ident)
        raw = it.get("sIntro") or it.get("sContent") or ""
        desc = strip_html(str(raw)) if isinstance(raw, str) else ""
        # sExt 里可能带封面图，附在描述头部当摘要
        if isinstance(it.get("sExt"), dict):
            cover = None
            for v in it["sExt"].values():
                cand = v[0] if isinstance(v, list) and v and isinstance(v[0], dict) else None
                if cand and cand.get("url"):
                    cover = cand["url"]
                    break
            if cover:
                desc = ('<img src="%s"/><br/>' % cover) + desc
        items.append(make_item(
            it.get("sTitle"), link,
            "mihoyo-%s" % ident,
            parse_dt(it.get("dtCreateTime")),
            desc, src["title"]))
    return items


FETCHERS = {"mihoyo_content_v2": fetch_mihoyo_content_v2}


# ---------------- 生成 RSS 2.0 ----------------

def rss_xml(title, link, desc, items):
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        "<title>%s</title>" % escape(title),
        "<link>%s</link>" % escape(link),
        "<description>%s</description>" % escape(desc),
    ]
    for it in items:
        parts += [
            "<item>",
            "<title>%s</title>" % escape(it["title"]),
            "<link>%s</link>" % escape(it["link"]),
            '<guid isPermaLink="false">%s</guid>' % escape(it["guid"]),
            "<pubDate>%s</pubDate>" % it["pubDate"],
            "<description>%s</description>" % escape(it["description"]),
            "<source>%s</source>" % escape(it["_src"]),
            "</item>",
        ]
    parts.append("</channel></rss>")
    return "\n".join(parts)


def main():
    with open(os.path.join(ROOT, "sources.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    if not os.path.isdir(OUT):
        os.makedirs(OUT)

    all_items = []
    failures = []
    for src in cfg["sources"]:
        try:
            items = FETCHERS[src["type"]](src)
            items.sort(key=lambda x: x["_dt"], reverse=True)
            xml = rss_xml(src["title"], src.get("site", ""), src.get("intro", ""), items)
            with open(os.path.join(OUT, src["id"] + ".xml"), "w", encoding="utf-8") as f:
                f.write(xml)
            print("[OK] %s -> rss/%s.xml (%d items)" % (src["title"], src["id"], len(items)))
            all_items.extend(items)
        except Exception as e:
            print("[FAIL] %s: %s" % (src["title"], e))
            failures.append(src["title"])

    all_items.sort(key=lambda x: x["_dt"], reverse=True)
    xml = rss_xml("rss-hub · 全部源", cfg.get("site", "https://github.com/LefRT/rss-hub"),
                  "聚合所有来源的最新条目", all_items[:80])
    with open(os.path.join(OUT, "all.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    print("[OK] 汇总 -> rss/all.xml (%d items)" % min(len(all_items), 80))

    if failures and len(failures) == len(cfg["sources"]):
        print("全部源失败，退出码 1")
        sys.exit(1)


if __name__ == "__main__":
    main()
