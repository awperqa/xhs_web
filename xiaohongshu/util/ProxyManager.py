# proxy_manager.py
import random
import threading
from datetime import datetime

import requests
import time

from xiaohongshu.items import ProxyItem


class ProxyManager:
    def __init__(self, api_url, cookie_pool, max_retry=3):
        self.api_url = api_url
        self.cookie_pool = cookie_pool  # Cookie 池（列表）
        self.max_retry = max_retry
        self.proxy_pool = {}  # 代理池（存储 ProxyItem）
        self.lock = threading.Lock()

    def _fetch_proxy(self):
        """从 API 获取新代理 IP"""
        try:
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data['data'][0]['ip'], data['data'][0]['port']
            return None, None
        except:
            return None, None

    def _bind_cookie(self, ip, port):
        """为代理 IP 绑定 Cookie"""
        if not self.cookie_pool:
            raise ValueError("Cookie 池为空")
        cookie = self.cookie_pool.pop(0)  # 取出一个 Cookie
        self.cookie_pool.append(cookie)  # 轮转 Cookie
        return ProxyItem(ip, port, cookie)

    def get_proxy(self):
        """获取一个有效代理（IP + Cookie）"""
        with self.lock:
            # 清理过期或无效代理
            current_time = datetime.now()

            for proxy in list(self.proxy_pool.keys()):
                if self.proxy_pool[proxy].expire_time <= current_time and not self.proxy_pool[proxy].is_valid:
                    print("删除不可用代理:%s" % self.proxy_pool[proxy].ip)
                    del self.proxy_pool[proxy]

            # 返回可用代理
            if self.proxy_pool and len(list(self.proxy_pool.keys())) == len(self.cookie_pool):
                a = random.choice(list(self.proxy_pool.keys()))
                print(a)
                return self.proxy_pool[a]

            # 无可用代理时获取新 IP
            for _ in range(self.max_retry):
                ip, port = self._fetch_proxy()
                if ip and port:
                    proxy_item = self._bind_cookie(ip, port)
                    if self._validate_proxy(proxy_item):
                        self.proxy_pool[proxy_item.cookie] = proxy_item
                        return proxy_item
            return None

    def _validate_proxy(self, proxy_item):
        """验证代理 IP 是否可用"""
        try:
            test_url = "http://httpbin.org/ip"
            proxies = {"http": f"http://{proxy_item.ip}:{proxy_item.port}"}
            response = requests.get(test_url, proxies=proxies, timeout=15)
            if response.status_code == 200:
                print(f"代理验证成功: {proxy_item.ip}:{proxy_item.port}")
                return True
            return False
        except:
            print(f"代理验证失败: {proxy_item.ip}:{proxy_item.port}")
            return False

    def mark_invalid(self, proxy_item):
        """标记代理失效"""
        with self.lock:
            proxy_item.is_valid = False