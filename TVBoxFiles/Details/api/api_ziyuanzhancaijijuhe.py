# -*- coding: utf-8 -*-
# @Author  : AI Assistant
# @Desc    : 全鏈路無感版 (搜索/分類/詳情全緩存 + 異步並發 + 連接池預熱)

import json
import os
import time
import hashlib
import requests
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        """返回當前爬蟲組件的名稱"""
        return "資源站採集聚合"

    def init(self, extend):
        """
        初始化爬蟲組件，配置連接池、緩存系統、加載站點配置
        :param extend: 擴展參數，可用於指定配置路徑、篩選模式或兩者的組合
        """
        self.sources = {}         # 存儲解析後的站點信息
        self.exclude_ClassNames = (
            "福利", "伦理", "伦理片", "倫理片", "理论片", "里番动漫", "港台三级", "韩国伦理", "西方伦理", "日本伦理", "两性课堂", "写真热舞", "擦边短剧", "擦边剧","公告", "头条", "未分类", "子类12", "子类113"
        )
        self.session = requests.Session() # 創建統一的 HTTP 會話
        
        # [核心優化1] 極速連接池：預加載 TCP 連接，大幅降低握手延遲
        # pool_connections=100 保證了高並發搜索時每個站點都有獨立連接
        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=1)
        self.session.mount('http://', adapter)   # 為 HTTP 協議掛載自定義連接池
        self.session.mount('https://', adapter)  # 為 HTTPS 協議掛載自定義連接池
        
        # 設置全域通用請求頭，模擬常規瀏覽器並保持長連接
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
            "Connection": "keep-alive"
        })

        # [核心優化2] 緩存系統初始化
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".lz/cache/")  # 跨平台緩存路徑(用戶主目錄下)
        self.memory_cache = {} # 內存緩存字典 (用於詳情頁，應用關閉即銷毀)
        self.disk_ttl = 3600   # 磁碟緩存有效期，單位為秒，預設 1 小時
        
        # 如果緩存目錄不存在，則自動創建
        if not os.path.exists(self.cache_dir):
            try: 
                os.makedirs(self.cache_dir, exist_ok=True)
            except: 
                pass

        # 加載站點配置（支持GitHub等遠端URL）
        default_path = "https://git.yylx.win/https://github.com/GarkyGod/ListFiles/raw/main/TVBoxFiles/Details/json/api_ziyuanzhan.json"  # 默認GitHub地址
        self.mode = "1"             # 篩選模式：0-全部站點，1-非成人內容(非成人站點的倫理內容也剔除)，2非成人站點(倫理內容不剔除)，3-僅成人站點
        json_path = default_path

        # 解析擴展參數 extend
        if extend:
            if "|" in extend:
                # 若包含分隔符 '|'，則拆分為配置路徑與模式
                parts = extend.split("|")
                json_path = parts[0] if parts[0] else default_path
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

    # --- 緩存核心邏輯 ---
    
    def _get_disk_cache(self, key):
        """
        讀取磁碟緩存 (主要用於搜索和分類內容)
        :param key: 緩存的原始識別鍵
        :return: 快照 JSON 數據或 None
        """
        try:
            # 使用 MD5 算法將 Key 轉化為固定長度的文件名，避免特殊字符影響
            md5_key = hashlib.md5(key.encode('utf-8')).hexdigest()
            path = os.path.join(self.cache_dir, f"{md5_key}.json")
            
            # 判斷緩存文件是否存在
            if os.path.exists(path):
                # 檢查文件修改時間，判斷是否在過期時間內
                if time.time() - os.path.getmtime(path) < self.disk_ttl:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                else:
                    os.remove(path) # 超出有效期則進行過期刪除
        except:
            pass
        return None

    def _set_disk_cache(self, key, data):
        """
        寫入磁碟緩存
        :param key: 緩存的原始識別鍵
        :param data: 待快照的字典數據
        """
        try:
            # 空數據或不包含列表數據時，不進行緩存
            if not data or not data.get("list"): return 
            md5_key = hashlib.md5(key.encode('utf-8')).hexdigest()
            path = os.path.join(self.cache_dir, f"{md5_key}.json")
            # 寫入本地 JSON 文件，確保不將中文轉義為 Unicode 碼
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except:
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
                    "searchable": "0" if str(s.get("searchable", 1)).strip() == "0" else "1",
                    "exclude_id": s.get("exclude_id", ""),
                    "exclude_name": s.get("exclude_name", "")
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

    def _fetch(self, api_url, params=None):
        """
        內部統一數據網絡請求核心方法
        :param api_url: 接口網址
        :param params: 字典形式的 URL 參數
        :return: 解析後的 JSON 數據字典
        """
        try:
            # 動態拼接 URL 參數，判斷原網址是否已帶有問號
            sep = "&" if "?" in api_url else "?"
            qs = "&".join([f'{k}={v}' for k, v in params.items()]) if params else ""
            full_url = f"{api_url}{sep}{qs}" if qs else api_url
            
            # 超時控制策略：搜索需要極速響應(2s)，詳情讀取可以稍慢(4s)
            timeout = 2.0 if params and "wd" in params else 4.0
            res = self.session.get(full_url, timeout=timeout, verify=False)
            
            if res.status_code == 200:
                try: 
                    return res.json()
                except: 
                    # 若返回的 json 開頭含有 UTF-8 BOM 字符，則清理後用 json.loads 解析
                    return json.loads(res.text.strip().lstrip('﻿'))
        except:
            pass
        return {}

    def homeContent(self, filter):
        """
        獲取主頁分類及篩選配置
        :param filter: 是否啟用篩選
        :return: 包含所有站點映射分類的字典數據
        """
        classes = []
        filters = {}
        # 獲取站點影視類別
        def load_class(key, source):
            params = {"ac": "list"}
            data = self._fetch(source["api"], params)

#            try:
#                data = json.loads(html)
#            except:
#                data = {}

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
                    if self.mode =="1":
                        vals = [item for item in vals if item["n"] not in self.exclude_ClassNames]
                    filters[key] = [{
                        "key": "cateId",
                        "name": "分类",
                        "value": vals
                    }]
                except:
                    pass

        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        """獲取主頁推薦視頻列表（預設返回空）"""
        return {"list": []}

    # [核心優化3] 分類頁快取：實現“後退”秒開
    def categoryContent(self, tid, pg, filter, ext):
        """
        獲取指定分類分頁的視頻清單
        :param tid: 分類ID（此處對應站點索引）
        :param pg: 頁碼
        :param ext: 篩選字典
        """
        # 獲取篩選器中的具體子分類關鍵字
        cate_id_val = ext.get("cateId", "") if ext else ""
        # 生成唯一的緩存 Key 組合
        cache_key = f"CAT_{tid}_{pg}_{cate_id_val}"
        
        # 1. 先行嘗試讀取本地磁碟緩存
        cached = self._get_disk_cache(cache_key)
        if cached: return cached

        try:
            if tid not in self.sources: return {"list": []}
            site = self.sources[tid]
            
            # 解析站點配置的排除分類清單
            paichu_str = str(site.get("paichu", ""))
            paichu = set(paichu_str.split(",")) if paichu_str else set()
            
            # 組裝 API 請求參數（採集特定頁面的列表詳情）
            params = {"ac": "detail", "pg": pg}
            data = self._fetch(site["api"], params)
            
            video_list = []
            if data and "list" in data:
                for item in data["list"]:
                    # 過濾掉屬於排除 ID 的影片
                    if str(item.get("type_id")) in paichu: continue
                    # 本地自定義子分類關鍵字過濾邏輯
                    if cate_id_val:
                        type_name = item.get("type_name", "")
                        if cate_id_val not in type_name: continue
                    
                    # 關鍵：重寫影片的 vod_id，在前面加上"站點索引@@"以區分多站同ID
                    item["vod_id"] = f"{tid}@@{item['vod_id']}"
                    video_list.append(item)
            
            # 標準化回傳的結構數據
            result = {
                "page": int(data.get("page", 1)) if data else 1,
                "pagecount": int(data.get("pagecount", 1)) if data else 1,
                "limit": 20,
                "total": int(data.get("total", 0)) if data else 0,
                "list": video_list
            }
            
            # 2. 回寫磁碟緩存，便於下次秒開
            self._set_disk_cache(cache_key, result)
            return result
        except:
            return {"list": []}

    # [核心優化4] 詳情頁內存緩存：防止誤觸返回後的重複加載
    def detailContent(self, array):
        """
        獲取特定影片的詳細資訊
        :param array: 包含唯一 vod_id 的列表集合
        """
        if not array: return {"list": []}
        vod_id_full = str(array[0])
        
        # 1. 內存快取 (RamCache) 檢索 - 達到極速網頁響應
        if vod_id_full in self.memory_cache:
            return self.memory_cache[vod_id_full]

        # 驗證 ID 的合法性是否包含站點分割標識
        if "@@" not in vod_id_full: return {"list": []}
        try:
            # 拆分出原本的站點索引與影片真實 ID
            idx, vid = vod_id_full.split("@@")
            idx = int(idx)
            site = self.sources[idx]
            
            # 調用站點 API 查詢詳情
            data = self._fetch(site["api"], {"ac": "detail", "ids": vid})
            if data and "list" in data:
                item = data["list"][0]
                item["vod_id"] = vod_id_full # 還原為複合 ID 供後續流程追蹤
                result = {"list": [item]}
                
                # 2. 寫入高速運行內存，避免同進同出重複拉取數據
                self.memory_cache[vod_id_full] = result
                return result
        except: pass
        return {"list": []}

    # [核心優化5] 異步並發 + 磁碟緩存搜索
    def searchContent(self, key, quick, pg="1"):
        """
        全站多線程異步並發聚合檢索
        :param key: 搜索關鍵字
        :param quick: 是否快速模式
        :param pg: 頁碼
        """
        if not key: return {"list": []}
        
        # 1. 檢查是否存在同名本地搜索快取
        cache_key = f"SEARCH_{key}"
        cached = self._get_disk_cache(cache_key)
        if cached: return cached

        # 2. 篩選出所有支援並發檢索的有效目標站點
        search_targets = []
        for i, s in enumerate(self.sources):
            bz_val = str(s.get("bz", "1")).strip()
            if bz_val != "0" and s.get("api"): # bz 為 0 通常代表關閉或不參與搜索
                search_targets.append((i, s))

        def search_one_site(target):
            """線程池任務函數：負責單個站點的搜索與數據清洗"""
            idx, site = target
            try:
                paichu_str = str(site.get("paichu", ""))
                paichu = set(paichu_str.split(",")) if paichu_str else set()
                # 發起網頁請求，搜索任務給予較緊湊的 2.5s 超時限制
                data = self._fetch(site["api"], {"ac": "detail", "wd": key})
                local_res = []
                if data and "list" in data:
                    for item in data["list"]:
                        if str(item.get("type_id")) in paichu: continue
                        
                        # 清洗站點名並在影片標題前加上站點標籤，便於用戶識別來源
                        site_name = site.get("name", "").replace("TV-", "").replace("AV-", "")
                        item["vod_name"] = f"[{site_name}] {item['vod_name']}"
                        item["vod_id"] = f"{idx}@@{item['vod_id']}" # 加上複合標籤
                        local_res.append(item)
                return idx, local_res 
            except:
                return idx, []

        # 3. 啟動線程池執行並發調用 (設置最大工作線程為 60)
        temp_results = {}
        with ThreadPoolExecutor(max_workers=60) as executor:
            futures = [executor.submit(search_one_site, target) for target in search_targets]
            # 依線程完成的先後順序及時採集結果
            for future in as_completed(futures):
                try:
                    idx, res = future.result()
                    if res: temp_results[idx] = res # 緩存非空的站點結果
                except: pass

        # 4. 按原始站點順序進行結果聚合，保障展現的有序性
        final_list = []
        sorted_indices = sorted(temp_results.keys())
        for idx in sorted_indices:
            final_list.extend(temp_results[idx])

        result_data = {"list": final_list}
        # 5. 將整合完畢的搜索結果寫入磁碟緩存
        self._set_disk_cache(cache_key, result_data)
        
        return result_data

    def playerContent(self, flag, id, vipFlags):
        """
        獲取播放解析鏈接
        :param flag: 播放源標識
        :param id: 播放媒體鏈接或ID
        """
        # 播放連結通常具有時效性，因此不進行緩存
        # 判斷是否為直鏈格式（.m3u8 或 .mp4），若是則直接返回不進行二次解析 (parse: 0)
        if ".m3u8" in id or ".mp4" in id:
            return {"url": id, "header": {"User-Agent": "Mozilla/5.0"}, "parse": 0, "jx": 0}
        # 非直鏈需要依賴核心進行網頁解析 (parse: 1)
        return {"url": id, "header": {"User-Agent": "Mozilla/5.0"}, "parse": 1, "jx": 0}

    def localProxy(self, params):
        """本地代理邏輯（返回預設的媒體流格式響應狀態碼）"""
        return [200, "video/MP2T", "", ""]
