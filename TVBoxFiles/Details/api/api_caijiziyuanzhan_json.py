# -*- coding: utf-8 -*-
# 专属全网聚合 Python版
# 适配常见 Cat/TVBox Python Spider
# 本地py适配

import json
import base64
import requests
import os
from requests.adapters import HTTPAdapter
from urllib3.util import Retry    #
from concurrent.futures import ThreadPoolExecutor, as_completed
from base.spider import Spider


class Spider(Spider):
    sources = {}
    mode = "1"          # 篩選模式：0-全部站點，1-非成人內容(非成人站點的倫理內容也剔除)，2非成人站點(倫理內容不剔除)，3-僅成人站點
    exclude_ClassNames = (
            "福利", "伦理", "伦理片", "倫理片", "理论片", "里番动漫", "港台三级", "韩国伦理", "西方伦理", "日本伦理", "两性课堂", "写真热舞", "擦边短剧",
        "擦边剧","公告", "头条", "子类12", "子类113"
        )
    default_path = "https://git.yylx.win/https://github.com/GarkyGod/ListFiles/raw/main/TVBoxFiles/Details/json/api_ziyuanzhan.json"    # 默認站點地址
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 16; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Mobile Safari/537.36"
    }
    
    def getName(self):
        return "采集聚合"

    def init(self, extend=""):

        self.session = requests.Session() # 創建統一的 HTTP 會話
        # 定義重試策略：總共重試 1 次，且包含連線與讀取超時
        retries = Retry(
            total = 1,               # 總重試次數
            connect = 1,             # 連線超時重試次數
            read = 1,                # 讀取超時重試次數
            backoff_factor = 2 ,     # 重試前隨機暫停 2 秒左右【設定退避因子。公式為：backoff_factor * (2 ** (retry_count - 1))】
            status_forcelist = [500, 502, 503, 504],    #伺服器回傳這些錯誤碼時，也強制重試 1 次
            raise_on_status = False
        )
        
        # [核心優化1] 極速連接池：預加載 TCP 連接，大幅降低握手延遲
        # pool_connections=100 保證了高並發搜索時每個站點都有獨立連接
#        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=1)
        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=retries)
        self.session.mount('http://', adapter)   # 為 HTTP 協議掛載自定義連接池
        self.session.mount('https://', adapter)  # 為 HTTPS 協議掛載自定義連接池

        # 設置全域通用請求頭，模擬常規瀏覽器並保持長連接
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
            "Connection": "keep-alive"
        })

        json_path = self.default_path
        # 解析擴展參數 extend
        if extend:
            if "|" in extend:
                # 若包含分隔符 '|'，則拆分為配置路徑與模式
                parts = extend.split("|")
                json_path = parts[0] if parts[0] else self.default_path
                self.mode = parts[1] if len(parts) > 1 else "1"
            elif len(extend) == 1 and extend in ["0", "1", "2", "3"]:
                # 若長度為 1 且是特定數字，則僅視為模式變更
                self.mode = extend
            else:
                # 其餘情況視為自定義配置路徑 (可能是本地路徑或自定義 URL)
                json_path = extend

        try:
            # 判斷配置路徑是否為網路 URL
            if json_path.startswith(('http://', 'https://')):
                # 發起網路請求從遠端獲取 JSON 配置，設置 10 秒超時，跳過 SSL 驗證
                res = self.session.get(json_path, timeout=10, verify=False)
                if res.status_code == 200:
                    data = res.json()
                    all_sites = data.get("api_sites", [])
                    self.sources = self._filter_sites(all_sites, self.mode) # 根據模式篩選並保存站點
            else:
                # 兼容本地文件讀取路徑
                if os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        all_sites = data.get("api_sites", [])
                        self.sources = self._filter_sites(all_sites, self.mode)
        except Exception as e:
            print(f"加載配置失敗: {e}")
            pass

    def _filter_sites(self, sites, mode):
        """
        依據所選模式對站點名進行關鍵字過濾
        :param sites: 原始站點清單
        :param mode: 過濾模式 ("0", "1", "2", "3")
        :return: 過濾後的站點清單
        """
        new_sites = {}
        for i,s in enumerate(sites):
            site_key = str(s.get("key", "")).strip()
            site_name = str(s.get("name", "")).strip()
            site_api = str(s.get("api", "")).strip()
            if site_key and site_api:
                new_sites[site_key] = {
                    "name": site_name if site_name else f"未改名資源站{i}",
                    "api": site_api,
                    "searchable": "0" if str(s.get("searchable", 1)).strip() == "0" else "1"
                }
        if mode == "0": return new_sites # 模式0：返回全部站點
        
        # 定義成人站點名稱中敏感詞集合
        adult_kws = {"🔞","AV","18+"}
        
        def is_adult(name):
            """內部函數：判斷單個站點名是否包含敏感詞"""
            if not name: return False
            name_upper = name.upper()
            if name_upper.startswith("🔞"): return True
            return any(k in name_upper for k in adult_kws)

        # 模式1or2：過濾掉成人站點；模式3：僅保留成人站點
        temp_sites = {}
        if mode == "1" or mode == "2":
            for k, v in new_sites.items():
                if not is_adult(v.get("name", "")): temp_sites[k] = v
            return temp_sites
        elif mode == "3":
            for k, v in new_sites.items():
                if is_adult(v.get("name", "")): temp_sites[k] = v
            return temp_sites
        return new_sites

    def fetch(self, url, timeout=4):
        try:
            r = self.session.get(url, timeout=timeout, verify=False)
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
                html = self.fetch(url, 4)
                try:
                    data = json.loads(html)
                except:
                    html = self.fetch(url, 8)
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

        with ThreadPoolExecutor(max_workers=20) as executor:        # max_workers=16
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
                    if self.mode == "1":
                        vals = [item for item in vals if item["n"] not in self.exclude_ClassNames]
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
        if source["searchable"] == "0": return {}

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

        with ThreadPoolExecutor(max_workers=30) as executor:        # max_workers=20
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

