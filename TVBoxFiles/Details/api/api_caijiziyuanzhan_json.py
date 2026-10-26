import threading
import time

# ==============================================================================
# 1. 全域快取與執行緒安全鎖
# ==============================================================================
# 提供一組最基本的初始分類，確保 APP 剛打開時首頁絕對不會是一片空白
current_classes = [
    {"type_id": "movie", "type_name": "電影（載入中...）"},
    {"type_id": "drama", "type_name": "連續劇（載入中...）"}
]
current_filters = {}

# 快取更新時間戳，避免短時間內重疊觸發遠端請求
last_update_time = 0
CACHE_EXPIRE_SECONDS = 300  # 5分鐘內不重複請求遠端

# 執行緒鎖，確保讀寫安全
data_lock = threading.Lock()


# ==============================================================================
# 2. 資料抓取核心邏輯
# ==============================================================================
def fetch_latest_data_from_remote():
    """
    在這裡編寫你原本去解析網站、抓取最新分類與篩選的邏輯。
    """
    try:
        # 模擬遠端抓取到的最新分類與篩選
        new_classes = [
            {"type_id": "movie", "type_name": "電影專區"},
            {"type_id": "drama", "type_name": "連續劇"},
            {"type_id": "anime", "type_name": "熱血動漫"} 
        ]
        new_filters = {
            "movie": [{"key": "year", "name": "年份", "value": [{"n": "2026", "v": "2026"}]}]
        }
        return new_classes, new_filters
    except Exception as e:
        print(f"[Fongmi Python] 遠端抓取失敗: {e}")
        return None, None


def try_refresh_cache(force=False):
    """
    安全地嘗試刷新快取變數。
    force: 是否無視5分鐘限制強制刷新
    """
    global current_classes, current_filters, last_update_time
    
    current_now = time.time()
    # 檢查是否超過5分鐘，或是否強制刷新
    if not force and (current_now - last_update_time < CACHE_EXPIRE_SECONDS):
        return # 時間還沒到，直接跳過

    new_classes, new_filters = fetch_latest_data_from_remote()
    if new_classes and new_filters:
        with data_lock:
            current_classes = new_classes
            current_filters = new_filters
            last_update_time = current_now
            print("[Fongmi Python] Class 與 Filters 變數已成功重新整理！")


def async_refresh_task():
    """ 用於異步非同步開執行緒跑的任務，完全不卡住 UI 渲染 """
    try_refresh_cache(force=False)


# ==============================================================================
# 3. 背景定時器（雙保險）
# ==============================================================================
def background_timer_loop():
    """ 背景死循環：每5分鐘主動醒來刷新一次變數 """
    while True:
        time.sleep(300)
        try_refresh_cache(force=True)

# 啟動背景守護執行緒
threading.Thread(target=background_timer_loop, daemon=True).start()


# ==============================================================================
# 4. Fongmi TVBox 標準擴充介面
# ==============================================================================

def homeContent(filter):
    """
    Fongmi 首頁入口：
    當使用者重啟 APP、更換站點、手動下拉刷新時，Fongmi 會來呼叫這個函式。
    """
    result = {}
    
    # 1. 嘗試同步刷新一次（如果剛好過期，且在剛開 APP 時）
    try_refresh_cache(force=False)
    
    # 2. 安全讀取快取值直接回傳給 Fongmi，速度極快
    with data_lock:
        result['class'] = current_classes
        if filter:
            result['filters'] = current_filters
            
    # 首頁推薦影片列表（依照你原本的邏輯填寫）
    result['list'] = [] 
    return result


def categoryContent(tid, pg, filter, extend):
    """
    Fongmi 分類頁入口：
    使用者點擊各個分類分頁、滑動切換標籤、使用篩選條件時觸發。
    """
    # 【關鍵點】只要使用者有在操作分類頁，就順便丟一個非同步執行緒去後台檢查/刷新變數
    # 這樣完全不會卡到使用者目前載入分類影片的速度，同時又能維持資料最新
    threading.Thread(target=async_refresh_task, daemon=True).start()
    
    # ---- 這裡放你原本 categoryContent 要回傳的影片清單邏輯 ----
    result = {}
    result['page'] = int(pg)
    result['pagecount'] = 10
    result['limit'] = 20
    result['total'] = 200
    result['list'] = [] # 塞入該分類下的影片物件
    
    return result
