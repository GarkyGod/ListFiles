# -*- coding: utf-8 -*-
# 专属資源站聚合 Python版
# 适配常见 Cat/TVBox Python Spider
# 本地py适配

import json
import base64
import requests
import os
import random
import time
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from base.spider import Spider


class Spider(Spider):
    sources = {}
    mode = "1"          # 篩選模式：0-全部站點，1-非成人內容(非成人站點的倫理內容也剔除)，2-非成人站點(倫理內容不剔除)，3-僅成人站點
    
    # 用 set 提高 in 運算子的查詢效能（O(1) 複雜度）
    exclude_ClassNames = {
        "福利", "伦理", "伦理片", "倫理片", "理论片", "里番动漫", "港台三级", "韩国伦理", "西方伦理", "日本伦理", "两性课堂", "写真热舞", "擦边短剧",
        "擦边剧", "公告", "头条", "子类12", "子类113"
    }

    default_path = "https://gh-proxy.org/https://github.com/GarkyGod/ListFiles/raw/main/TVBoxFiles/Details/json/api_ziyuanzhan_lite.json"    # 默認站點地址
    ua = "Mozilla/5.0 (Linux; Android 16; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Mobile Safari/537.36"
    
    def getName(self):
        return "採集聚合"

    def init(self, extend=""):
        # 顯式抽取超時配置與連接池複用，並最佳化重試策略
        self.session = requests.Session()
        
        retries = Retry(
            total=1,               # 總重試次數
            connect=1,             # 連線超時重試次數
            read=1,                # 讀取超時重試次數
            backoff_factor=1,      # 適當縮短退避時間，提升 TVBox 的加載靈敏度 【設定退避因子。公式為：backoff_factor * (2 ** (retry_count - 1))】
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        
        # 提高 pool_connections 和 maxsize 匹配高併發，避免 ConnectionPool 被打滿
        adapter = HTTPAdapter(pool_connections=120, pool_maxsize=120, max_retries=retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        # 設置全域通用請求頭，模擬常規瀏覽器並保持長連接
        self.session.headers.update({
            "User-Agent": self.ua,
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
            if json_path.startswith(('http://', 'https://')):
                # 將高風險的全域性網路請求增加健壯的錯誤擷取與超時遞增機制
                data = {}
                for timeout in [3, 5, 7]:  # 微調超時區間
                    try:
                        # 只在非第一輪嘗試時才 sleep 避讓，第一輪時直接發起請求，提高速度
                        if timeout > 3:
                            time.sleep(random.uniform(0.3, 0.8))
                        res = self.session.get(json_path, timeout=timeout, verify=False)
                        if res.status_code == 200:
                            data = res.json()  # 優化：直接使用 requests 的內建 json() 解析方法
                            break
                    except Exception:
                        continue
                all_sites = data.get("api_sites", [])
                self.sources = self._filter_sites(all_sites, self.mode)
            else:
                if os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        all_sites = data.get("api_sites", [])
                        self.sources = self._filter_sites(all_sites, self.mode)
        except Exception as e:
            print(f"加載配置失敗: {e}")

    def _filter_sites(self, sites, mode):
        new_sites = {}
        for i, s in enumerate(sites):
            # 減少多餘的 string 轉換與 strip 重複呼叫
            site_key = str(s.get("key", "")).strip()
            site_api = str(s.get("api", "")).strip()
            ping_api = 0
            # 對site_api做三次連通性測試，只保留可用站點
            for timeout in [3, 5, 7]:
                try:
                    if timeout > 3: time.sleep(random.uniform(0.3, 0.8))
                    res = self.session.get(json_path, timeout=timeout, verify=False)
                    if res.status_code == 200:
                        ping_api = 1
                        break
                except Exception:
                    continue
            if site_key and site_api and ping_api:
                site_name = str(s.get("name", "")).strip()
                searchable = str(s.get("searchable", "1")).strip()
                new_sites[site_key] = {
                    "name": site_name if site_name else f"未改名資源站{i}",
                    "api": site_api,
                    "searchable": "0" if searchable == "0" else "1"
                }
        
        if mode == "0": 
            return new_sites
        
        # 成人站點關鍵字改用 frozenset 全域快取，避免重複初始化
        adult_kws = frozenset({"🔞", "AV", "18+"})
        
        def is_adult(name):
            if not name: 
                return False
            name_upper = name.upper()
            if name_upper.startswith("🔞"): 
                return True
            return any(k in name_upper for k in adult_kws)

        # 優化：合併條件判斷與更簡潔的字典生成式
        if mode in ("1", "2"):
            return {k: v for k, v in new_sites.items() if not is_adult(v.get("name", ""))}
        elif mode == "3":
            return {k: v for k, v in new_sites.items() if is_adult(v.get("name", ""))}
            
        return new_sites

    def fetch(self, url, timeout=4):
        try:
            # 統一處理全域 requests 會話調用，簡化例外回傳
            r = self.session.get(url, timeout=timeout, verify=False)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        return ""

    def clean_item(self, item, source_key, source_name, is_detail=False):
        # 直接淺拷貝或避免在不必要時重新轉換為 dict
        item = dict(item)

        if not is_detail:
            item["vod_id"] = f"{source_key}@@{item.get('vod_id', '')}"

        remarks = item.get("vod_remarks", "")
        item["vod_remarks"] = f"{source_name} | {remarks}" if remarks else source_name

        if item.get("vod_play_from"):
            froms = item["vod_play_from"].split("$$$")
            item["vod_play_from"] = "$$$".join(f"{source_name}-{x}" for x in froms)

        # 移除不需要的欄位
        item.pop("vod_down_from", None)
        item.pop("vod_down_url", None)
        return item

    def homeContent(self, filter):
        classes = []
        filters = {}

        def load_class(key, source):
            url = f"{source['api']}?ac=list"
            data = {}
            for timeout in [3, 5]:
                try:
                    # 降低背景阻斷時間
                    html = self.fetch(url, timeout)
                    if html:
                        data = json.loads(html)
                        break
                except Exception:
                    continue

            vals = [{"n": "全部(最新)", "v": ""}]
            for c in data.get("class", []):
                t_name = c.get("type_name", "")
                t_id = c.get("type_id", "")
                if t_name:
                    vals.append({"n": t_name, "v": t_id})
            return key, vals

        # 這裡 max_workers 優化維持在 20，兼顧資源站高併發與輕量設備穩定性
        with ThreadPoolExecutor(max_workers=20) as executor:
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
                        # 利用 set 集合進行過濾，效能提升明顯
                        vals = [item for item in vals if item["n"] not in self.exclude_ClassNames]
                    filters[key] = [{
                        "key": "cateId",
                        "name": "分类",
                        "value": vals
                    }]
                except Exception:
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
        cate_id = extend.get("cateId", "") if isinstance(extend, dict) else ""
        url = f"{source['api']}?ac=detail&pg={pg}"
        if cate_id:
            url += f"&t={cate_id}"

        html = self.fetch(url)
        try:
            data = json.loads(html) if html else {}
        except Exception:
            data = {}

        result = [
            self.clean_item(item, tid, source["name"], False)
            for item in data.get("list", [])
        ]

        return {
            "list": result,
            "page": data.get("page", pg),
            "pagecount": data.get("pagecount", 1),
            "limit": data.get("limit", 20),
            "total": data.get("total", len(result))
        }

    def detailContent(self, ids):
        if isinstance(ids, list):
            ids = ids[0] if ids else ""

        if not ids or "@@" not in ids:
            return {"list": []}

        source_key, real_id = ids.split("@@", 1)
        if source_key not in self.sources:
            return {"list": []}

        source = self.sources[source_key]
        url = f"{source['api']}?ac=detail&ids={real_id}"
        html = self.fetch(url)
        try:
            data = json.loads(html) if html else {}
        except Exception:
            data = {}

        result = []
        for item in data.get("list", []):
            cleaned = self.clean_item(item, source_key, source["name"], True)
            cleaned["vod_id"] = ids
            result.append(cleaned)

        return {"list": result}

    def search_one(self, source_key, source, keyword, pg):
        if source.get("searchable", "1") == "0":
            return {"list": [], "pagecount": 1}

        url = f"{source['api']}?ac=detail&wd={keyword}&pg={pg}"
        html = self.fetch(url, timeout=5)  # 調高搜索超時，防止漏站
        try:
            data = json.loads(html) if html else {}
        except Exception:
            data = {}

        result = [
            self.clean_item(item, source_key, source["name"], False)
            for item in data.get("list", [])
        ]
        return {
            "list": result,
            "pagecount": data.get("pagecount", 1)
        }

    def searchContent(self, key, quick=False, pg=1):
        result = []
        max_page = 1

        # 多執行緒上限維持在合理範圍 25-30，避免部分核心較差的 TVBox 設備發生崩潰
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = {
                executor.submit(self.search_one, sk, s, key, pg): sk 
                for sk, s in self.sources.items()
            }

            for future in as_completed(futures):
                try:
                    data = future.result()
                    if "list" in data:
                        result.extend(data["list"])
                    if data.get("pagecount", 1) > max_page:
                        max_page = data["pagecount"]
                except Exception:
                    pass

        return {
            "list": result,
            "page": pg,
            "pagecount": max_page,
            "limit": 40,
            "total": len(result) if result else 0
        }

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": {"User-Agent": self.ua}
        }

    def localProxy(self, param):
        return [200, "text/plain", "ok"]


if __name__ == "__main__":
    Spider().run()
