# -*- coding: utf-8 -*-
# 专属全网聚合 Python版
# 适配常见 Cat/TVBox Python Spider
# 本地py适配

import json
import requests
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from base.spider import Spider


class Spider(Spider):
    sources = {
        'key_360': {'name': '📺360', 'api': 'https://360zy.com/api.php/provide/vod'},
        'key_baidu': {'name': '📺百度', 'api': 'https://api.apibdzy.com/api.php/provide/vod'},
        'key_baofeng': {'name': '📺暴風', 'api': 'https://bfzyapi.com/api.php/provide/vod'},
        'key_dazhong': {'name': '📺大眾', 'api': 'https://cdn.dzzyapi.com/api.php/provide/vod'},
        'key_dianyingtiantang': {'name': '📺電影天堂', 'api': 'http://caiji.dyttzyapi.com/api.php/provide/vod'},
        'key_douban': {'name': '📺豆瓣', 'api': 'https://dbzy.tv/api.php/provide/vod'},
        'key_feifan': {'name': '📺非凡', 'api': 'http://api.ffzyapi.com/api.php/provide/vod'},
        'key_feifan2': {'name': '📺非凡(備)', 'api': 'https://cj.ffzyapi.com/api.php/provide/vod'},
        'key_guangsu': {'name': '📺光速', 'api': 'https://api.guangsuapi.com/api.php/provide/vod'},
        'key_haohua': {'name': '📺豪華', 'api': 'https://hhzyapi.com/api.php/provide/vod'},
        'key_huya': {'name': '📺虎牙', 'api': 'https://www.huyaapi.com/api.php/provide/vod'},
        'key_hongniu': {'name': '📺红牛', 'api': 'https://www.hongniuzy2.com/api.php/provide/vod'},
        'key_ikun': {'name': '📺ikun', 'api': 'https://ikunzyapi.com/api.php/provide/vod'},
        'key_ikun2': {'name': '📺ikun(備)', 'api': 'https://ikunzy.com/api.php/provide/vod'},
        'key_iqiyi': {'name': '📺愛奇藝', 'api': 'https://iqiyizyapi.com/api.php/provide/vod'},
        'key_jianan': {'name': '📺建安', 'api': 'http://154.219.117.232:9981/jacloudapi.php/provide/vod'},
        'key_jinying': {'name': '📺金鷹', 'api': 'https://jinyingzy.com/api.php/provide/vod'},
        'key_jisu': {'name': '📺極速', 'api': 'https://jszyapi.com/api.php/provide/vod'},
        'key_juliang': {'name': '📺巨量', 'api': 'https://api.juliang.live/api/provide/vod'},
        'key_kuaiche': {'name': '📺快車', 'api': 'https://caiji.kuaichezy.org/api.php/provide/vod'},
        'key_liangzi': {'name': '📺量子', 'api': 'https://cj.lziapi.com/api.php/provide/vod'},
        'key_maotai': {'name': '📺茅臺', 'api': 'https://caiji.maotaizy.cc/api.php/provide/vod'},
        'key_maotai2': {'name': '📺茅臺(備)', 'api': 'https://caiji.maotai999.vip/api.php/provide/vod'},
        'key_maoyan': {'name': '📺貓眼', 'api': 'https://api.maoyanapi.top/api.php/provide/vod'},
        'key_modu': {'name': '📺魔都', 'api': 'https://www.mdzyapi.com/api.php/provide/vod'},
        'key_modu2': {'name': '📺魔都(備)', 'api': 'https://caiji.moduapi.cc/api.php/provide/vod'},
        'key_niuniu': {'name': '📺牛牛', 'api': 'https://api.niuniuzy.me/api.php/provide/vod'},
        'key_ok': {'name': '📺OK', 'api': 'https://api.okzyw.net/api.php/provide/vod'},
        'key_piaoling': {'name': '📺飄零', 'api': 'https://p2100.net/api.php/provide/vod'},
        'key_ruyi': {'name': '📺如意', 'api': 'https://cj.rytvapi.com/api.php/provide/vod'},
        'key_shandian': {'name': '📺閃電', 'api': 'https://sdzyapi.com/api.php/provide/vod'},
        'key_shandian2': {'name': '📺閃電(備)', 'api': 'https://xsd.sdzyapi.com/api.php/provide/vod'},
        'key_subo': {'name': '📺速播', 'api': 'https://subocaiji.com/api.php/provide/vod'},
        'key_subo2': {'name': '📺速播(備)', 'api': 'https://subocj.com/api.php/provide/vod'},
        'key_suoni': {'name': '📺索尼', 'api': 'https://suoniapi.com/api.php/provide/vod'},
        'key_taopian': {'name': '📺淘片', 'api': 'https://taopianapi.com/cjapi/mc/vod/json.html'},
        'key_tianyayingshi': {'name': '📺天涯', 'api': 'https://tyyszyapi.com/api.php/provide/vod'},
        'key_tianyayingshi2': {'name': '📺天涯(備)', 'api': 'https://tyyszy.com/api.php/provide/vod'},
        'key_uku': {'name': '📺U酷', 'api': 'https://api.ukuapi88.com/api.php/provide/vod'},
        'key_uu': {'name': '📺UU', 'api': 'https://uuzy.me/api.php/provide/vod'},
        'key_wujin': {'name': '📺無盡', 'api': 'https://api.wujinapi.me/api.php/provide/vod'},
        'key_wujin2': {'name': '📺無盡(備)', 'api': 'https://api.wujinapi.cc/api.php/provide/vod'},
        'key_wushuiyin': {'name': '📺無水印', 'api': 'https://api.wsyzy.net/api.php/provide/vod'},
        'key_xigua': {'name': '📺西瓜', 'api': 'https://caiji.xgzyapi.com/api.php/provide/vod'},
        'key_xinlang': {'name': '📺新浪', 'api': 'https://api.xinlangapi.com/xinlangapi.php/provide/vod'},
        'key_yaya': {'name': '📺鴨鴨(丫丫)', 'api': 'https://cj.yayazy.net/api.php/provide/vod'},
        'key_yinghua': {'name': '📺樱花', 'api': 'https://m3u8.apiyhzy.com/api.php/provide/vod'},
        'key_youzhi': {'name': '📺優質', 'api': 'https://api.yyzy-tv.vip/inc/apijson.php'},
        'key_yunjiexi': {'name': '📺雲解釋', 'api': 'https://api.yparse.com/api/json'},
        'key_zuida': {'name': '📺最大', 'api': 'https://api.zuidapi.com/api.php/provide/vod'},
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 16; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Mobile Safari/537.36"
    }

    def getName(self):
        return "采集聚合"

    def init(self, extend=""):
        pass

    def fetch(self, url, timeout=4):
        try:
            r = requests.get(url, headers=self.headers, timeout=timeout, verify=False)
            return r.text
        except Exception:
            return ""

    def clean_item(self, item, source_key, source_name, is_detail=False):
        item = dict(item)

        if not is_detail:
            item["vod_id"] = f"{source_key}@@{item.get('vod_id', '')}"

        remarks = item.get("vod_remarks", "")
        item["vod_remarks"] = f"{source_name} | {remarks}"

        if item.get("vod_play_from"):
            froms = item["vod_play_from"].split("$$$")
            froms = [f"{source_name}-{x}" for x in froms]
            item["vod_play_from"] = "$$$".join(froms)

        item.pop("vod_down_from", None)
        item.pop("vod_down_url", None)

        return item

    def homeContent(self, filter):
        classes = []
        filters = {}

        def load_class(key, source):
            url = f"{source['api']}?ac=list"
            html = self.fetch(url, 2)

            try:
                data = json.loads(html)
            except:
                data = {}

            vals = [{"n": "全部(最新)", "v": ""}]

            for c in data.get("class", []):
                vals.append({
                    "n": c.get("type_name", ""),
                    "v": c.get("type_id", "")
                })

            return key, vals

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = []

            for key, source in self.sources.items():
                classes.append({
                    "type_id": key,
                    "type_name": source["name"]
                })

                futures.append(executor.submit(load_class, key, source))

            for future in as_completed(futures):
                try:
                    key, vals = future.result()

                    filters[key] = [{
                        "key": "cateId",
                        "name": "分类",
                        "value": vals
                    }]
                except:
                    pass

        return {
            "class": classes,
            "filters": filters,
            "list": []
        }

    def categoryContent(self, tid, pg, filter, extend):
        if tid not in self.sources:
            return {"list": []}

        source = self.sources[tid]

        cate_id = ""
        if isinstance(extend, dict):
            cate_id = extend.get("cateId", "")

        url = f"{source['api']}?ac=detail&pg={pg}"

        if cate_id:
            url += f"&t={cate_id}"

        html = self.fetch(url)

        try:
            data = json.loads(html)
        except:
            data = {}

        result = []

        for item in data.get("list", []):
            result.append(
                self.clean_item(
                    item,
                    tid,
                    source["name"],
                    False
                )
            )

        return {
            "list": result,
            "page": data.get("page", pg),
            "pagecount": data.get("pagecount", 1),
            "limit": data.get("limit", 20),
            "total": data.get("total", len(result))
        }

    def detailContent(self, ids):
        if isinstance(ids, list):
            ids = ids[0]

        if "@@" not in ids:
            return {"list": []}

        source_key, real_id = ids.split("@@", 1)

        if source_key not in self.sources:
            return {"list": []}

        source = self.sources[source_key]

        url = f"{source['api']}?ac=detail&ids={real_id}"

        html = self.fetch(url)

        try:
            data = json.loads(html)
        except:
            data = {}

        result = []

        for item in data.get("list", []):
            cleaned = self.clean_item(
                item,
                source_key,
                source["name"],
                True
            )

            cleaned["vod_id"] = ids

            result.append(cleaned)

        return {"list": result}

    def search_one(self, source_key, source, keyword, pg):
        url = f"{source['api']}?ac=detail&wd={keyword}&pg={pg}"

        html = self.fetch(url, 3)

        try:
            data = json.loads(html)
        except:
            data = {}

        result = []

        for item in data.get("list", []):
            result.append(
                self.clean_item(
                    item,
                    source_key,
                    source["name"],
                    False
                )
            )

        return {
            "list": result,
            "pagecount": data.get("pagecount", 1)
        }

    def searchContent(self, key, quick=False, pg=1):
        result = []
        max_page = 1

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []

            for source_key, source in self.sources.items():
                futures.append(
                    executor.submit(
                        self.search_one,
                        source_key,
                        source,
                        key,
                        pg
                    )
                )

            for future in as_completed(futures):
                try:
                    data = future.result()

                    result.extend(data["list"])

                    if data["pagecount"] > max_page:
                        max_page = data["pagecount"]

                except:
                    pass

        return {
            "list": result,
            "page": pg,
            "pagecount": max_page,
            "limit": 40,
            "total": 9999
        }

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": self.headers
        }

    def localProxy(self, param):
        return [200, "text/plain", "ok"]


if __name__ == "__main__":
    Spider().run()

