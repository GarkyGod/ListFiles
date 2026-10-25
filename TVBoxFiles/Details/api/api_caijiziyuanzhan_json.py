# -*- coding: utf-8 -*-
# 資源站聚合 Python版
# 適配常見 Cat/TVBox Python Spider
# 本地py適配

import json
import requests
import os
import random
import time
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from base.spider import Spider

# 爬蟲主體類別
class Spider(Spider):
	def __init__(self):
		super().__init__()
		self.sources = {}
		self.mode = "1"	 # 篩選模式：0-全部站點，1-非成人內容(非成人站點的倫理內容也剔除)，2-非成人站點(倫理內容不剔除)，3-僅成人站點
		self.adult_kws = frozenset({"🔞", "AV", "18+"})
		self.exclude_ClassNames = frozenset({
			"福利", "伦理", "伦理片", "倫理片", "理论片", "里番动漫", "港台三级", "韩国伦理", "西方伦理", "日本伦理", "两性课堂", "写真热舞", "擦边短剧",
			"擦边剧", "公告", "头条", "子类12", "子类113"
		})	   # 需剔除的類別名稱
		self.default_path = "https://gh-proxy.org/https://github.com/GarkyGod/ListFiles/raw/main/TVBoxFiles/Details/json/api_ziyuanzhan_lite.json"	# 默認站點地址
		self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
		self.session = requests.Session()
		retries = Retry(
			total=False,		# 全局重試次數 (False關閉,對應數值為重試次數)
			connect=False,	  # 連線失敗重試次數 (False關閉,對應數值為重試次數)
			read=False,		 # 讀取逾時重試次數 (False關閉,對應數值為重試次數)
			status=0,		   # 狀態碼錯誤（如502/503）不重試
			raise_on_status=False
		)
		adapter = HTTPAdapter(pool_connections=30, pool_maxsize=30, max_retries=retries)
		self.session.mount('http://', adapter)
		self.session.mount('https://', adapter)
		self.session.headers.update({
			"User-Agent": self.ua,
			"Connection": "keep-alive"
		})
		self.class_cache = {}
		self.filter_cache = {}

	def getName(self):
		return "採集聚合"

	def init(self, extend=""):
		json_path = self.default_path
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
				# 若以http://或https://開頭則為URL地址
				data = {}
				for timeout in [3, 5, 7]:  # 微調超時區間
					try:
						# 只在非第一輪嘗試時才 sleep 避讓，第一輪時直接發起請求，提高速度
						if timeout > 3:
							time.sleep(random.uniform(0.3, 0.8))
						res = self.session.get(json_path, timeout=timeout, verify=False, headers={"Connection": "close"})
						if res.status_code == 200:
							data = res.json()  # 優化：直接使用 requests 的內建 json() 解析方法
							break
					except Exception:
						continue
				all_sites = data.get("api_sites", [])
				self.sources = self._filter_sites(all_sites, self.mode)
			else:
				# 否則為本地路徑
				if os.path.exists(json_path):
					with open(json_path, "r", encoding="utf-8") as f:
						data = json.load(f)
						all_sites = data.get("api_sites", [])
						self.sources = self._filter_sites(all_sites, self.mode)
		except Exception:
			pass

	def _filter_sites(self, sites, mode):
		new_sites = {}
		for i, s in enumerate(sites):
			site_key = str(s.get("key", "")).strip()
			site_api = str(s.get("api", "")).strip()
			if site_api and site_api.startswith(('http://', 'https://')):
				ping_api = 0
				# 對site_api做三次連通性測試，只保留可用站點
				for timeout in [0.5, 1, 1.5]:
					try:
						if timeout > 0.5: time.sleep(random.uniform(0.3, 0.8))
						res = self.session.get(site_api, timeout=timeout, verify=False, headers={"Connection": "close"})
						if res.status_code == 200:
							try:
								html_json = res.json()
							except:
								html_json = json.loads(res.text.strip().lstrip('﻿'))
							ping_api = 1
							break
					except Exception:
						continue
				if site_key and ping_api:
					site_name = str(s.get("name", "")).strip()
					site_name = site_name if site_name else f"未改名資源站{i}"
					searchable = str(s.get("searchable", "1")).strip()
					new_sites[site_key] = {
						"name": site_name,
						"api": site_api,
						"searchable": "0" if searchable == "0" else "1"
					}
					filter = html_json.get("class",[])
					self.class_cache[site_key] = {"type_id": site_key, "type_name": site_name}
					self.filter_cache[site_key] = filter
		if mode == "0": 
			return new_sites
		# 判斷sites名稱是否含成人站點標識
		def is_adult(name):
			if not name:
				return False
			name_upper = name.upper()
			if name_upper.startswith("🔞"): 
				return True
			return any(k in name_upper for k in self.adult_kws)
		if mode in ("1", "2"):
			return {k: v for k, v in new_sites.items() if not is_adult(v.get("name", ""))}
		elif mode == "3":
			return {k: v for k, v in new_sites.items() if is_adult(v.get("name", ""))}
		return new_sites

	def _fetch(self, api_url, params=None):
		try:
			api_url = api_url.rstrip("/")
			sep = "&" if "?" in api_url else "?"
			qs = "&".join([f'{k}={v}' for k, v in params.items()]) if params else ""
			full_url = f"{api_url}/{sep}{qs}" if qs else api_url
			# 超時控制：搜索(2s)，詳情(4s)
			timeout = 2.0 if params and "wd" in params else 4.0
			res = self.session.get(full_url, timeout=timeout, verify=False)
			if res.status_code == 200:
				try: return res.json()
				except: return json.loads(res.text.strip().lstrip('﻿'))
		except Exception:
			pass
		return {}

	def homeContent(self, filter):
		"""獲取首頁分類清單與篩選條件"""
		classes = self._classes()
		result = {
#			"class": classes,
			"class":[{"type_id": "1", "type_name": "影視"}, {"type_id": "2", "type_name": "電視"}],
#			"filters": {},
			"list": []  # 首頁推薦影片，可留空
		}
		return result

	def _classes(self):
		if self.class_cache:
			for k,v in self.sources.items():
				classes.append(self.class_cache[k])
			return classes
		for k,v in self.sources.items():
			classes.append({
				"type_id": k,
				"type_name": v["name"]
			})
		return classes

	def categoryContent(self, tid, pg, filter, extend):
		"""獲取分類頁面的影片列表"""
		result = {"list": []}
		url = f"{self.api_url}?ac=detail&cid={tid}&pg={pg}"
		
		html = self.fetch(url)
		if not html: return result
		
		try:
			# 💡 提示：如果網站有加密，在此處使用 _AESCBC.decrypt 解密 html
			data = json.loads(html)
			for item in data.get("list", []):
				result["list"].append({
					"vod_id": item.get("id"),
					"vod_name": item.get("name"),
					"vod_pic": item.get("pic"),
					"vod_remarks": item.get("remarks")
				})
		except Exception:
			pass
			
		return result

	def detailContent(self, ids):
		"""獲取影片詳情與播放列表"""
		if isinstance(ids, list): ids = ids[0]
		result = {"list": []}
		url = f"{self.api_url}?ac=detail&id={ids}"
		
		html = self.fetch(url)
		if not html: return result
		
		try:
			data = json.loads(html)
			item = data.get("data", {})
			result["list"].append({
				"vod_id": item.get("id"),
				"vod_name": item.get("name"),
				"vod_pic": item.get("pic"),
				"vod_type": item.get("type"),
				"vod_year": item.get("year"),
				"vod_area": item.get("area"),
				"vod_actor": item.get("actor"),
				"vod_director": item.get("director"),
				"vod_content": item.get("content"),
				# 播放源名稱與播放網址，多集用 # 分隔，多源用 $$$ 分隔
				"vod_play_from": "優質播放源",
				"vod_play_url": "第1集$https://video.mp4#第2集$https://video2.mp4"
			})
		except Exception:
			pass
			
		return result

	def searchContent(self, key, quick=False, pg=1):
		"""關鍵字搜尋功能"""
		result = {"list": []}
		url = f"{self.api_url}?wd={key}&pg={pg}"
		
		html = self.fetch(url)
		if not html: return result
		
		try:
			data = json.loads(html)
			for item in data.get("list", []):
				result["list"].append({
					"vod_id": item.get("id"),
					"vod_name": item.get("name"),
					"vod_pic": item.get("pic"),
					"vod_remarks": item.get("remarks")
				})
		except Exception:
			pass
			
		return result

	def playerContent(self, flag, id, vipFlags):
		"""解析播放網址並返回給 TVBox 播放器"""
		return {
			"parse": 0,		  # 0 代表直接播放，1 代表需要調用解析
			"playUrl": "",
			"url": id,		   # 直接返回影片的真實播放網址
			"header": self.session.headers
		}

	def localProxy(self, param):
		"""本地代理接口 (通常用於 M3U8 P2P 解析或文字轉換，非必用)"""
		return [200, "text/plain", "ok"]

	def destroy(self):
		"""自訂釋放機制：當 TVBox 卸載爬蟲或程式結束時，手動關閉 Session"""
		if self.session:
			self.session.close()
