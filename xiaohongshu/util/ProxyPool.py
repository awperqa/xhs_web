import requests
import time
import threading
from queue import Queue
from datetime import datetime, timedelta
from collections import defaultdict

class ProxyPool:
    def __init__(self, api_url, pool_size=50, max_retry=3):
        self.api_url = api_url
        self.pool_size = pool_size  # 队列容量
        self.max_retry = max_retry
        self.proxy_queue = Queue()
        self.ip_expiry = {}  # {ip: expiry_time}
        self.ip_usage = defaultdict(int)  # {ip: usage_count}
        self.lock = threading.Lock()
        self.running = True
        self._preload_proxies()
        self._start_refresh_thread()

    def _call_api(self):
        """调用 API 获取一批 IP（假设每次返回 10 个）"""
        try:
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [
                    f"{item['ip']}:{item['port']}"
                    for item in data.get("data", [])
                ]
            return []
        except:
            return []

    def _validate_proxy(self, proxy):
        """验证代理是否可用"""
        try:
            test_url = "http://httpbin.org/ip"
            response = requests.get(
                test_url,
                proxies={"http": proxy, "https": proxy},
                timeout=15
            )
            return response.status_code == 200
        except:
            return False

    def _preload_proxies(self):
        """初始加载代理"""
        proxies = self._call_api()
        valid_proxies = [p for p in proxies if self._validate_proxy(p)]
        with self.lock:
            for proxy in valid_proxies:
                self.proxy_queue.put(proxy)
                self.ip_expiry[proxy] = datetime.now() + timedelta(minutes=9)

    def _start_refresh_thread(self):
        """后台刷新线程"""
        def refresh_task():
            while self.running:
                # 动态调整刷新频率：队列剩余量 < 20% 时触发
                if self.proxy_queue.qsize() < 0.2 * self.pool_size:
                    self._refresh_proxies()
                time.sleep(60)  # 每 60 秒检查一次
        threading.Thread(target=refresh_task, daemon=True).start()

    def _refresh_proxies(self):
        """刷新代理池"""
        new_proxies = self._call_api()
        valid_proxies = [p for p in new_proxies if self._validate_proxy(p)]
        with self.lock:
            # 清理过期 IP
            current_time = datetime.now()
            expired_ips = [ip for ip, expiry in self.ip_expiry.items() if expiry < current_time]
            for ip in expired_ips:
                self.ip_expiry.pop(ip, None)
                self.ip_usage.pop(ip, None)
            # 添加新 IP（不超过队列容量）
            for proxy in valid_proxies:
                if self.proxy_queue.qsize() < self.pool_size:
                    self.proxy_queue.put(proxy)
                    self.ip_expiry[proxy] = datetime.now() + timedelta(minutes=9)

    def get_proxy(self):
        """获取一个可用代理（优先使用次数较少的 IP）"""
        with self.lock:
            if not self.proxy_queue.empty():
                proxy = self.proxy_queue.get()
                self.ip_usage[proxy] += 1
                self.proxy_queue.put(proxy)
                return proxy
            return None


    def mark_bad_proxy(self, proxy):
        """标记失效代理"""
        with self.lock:
            if proxy in self.ip_expiry:
                self.ip_expiry.pop(proxy)
                self.ip_usage.pop(proxy)
                print(f"移除失效代理: {proxy}")

    def close(self):
        """关闭代理池"""
        self.running = False