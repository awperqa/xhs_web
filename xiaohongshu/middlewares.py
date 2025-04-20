import json
import random

import requests
from scrapy import signals
from xhs import XiaohongshuClient
from scrapy import signals
from scrapy.exceptions import NotConfigured, IgnoreRequest

from xiaohongshu.util.ProxyManager import ProxyManager
from xiaohongshu.util.ProxyPool import ProxyPool



# class RetryMiddleware:
#     def process_response(self, request, response, spider):
#         if response.status in [403, 429]:
#             spider.logger.warning(f"请求被拦截: {response.url}")
#             # 移除失效的 Cookie 或 IP
#             self.remove_failed_resource(request)
#             return request  # 重新调度请求
#         return response
#
#     def remove_failed_resource(self, request):
#         if 'proxy' in request.meta:
#             proxy = request.meta['proxy']
#             if proxy in self.proxies:
#                 self.proxies.remove(proxy)
#         # 类似处理失效 Cookie

class DynamicProxyMiddleware:
    def __init__(self, proxy_api, cookie_pool):
        self.proxy_manager = ProxyManager(proxy_api, cookie_pool)
        for i in range(len(cookie_pool)):
            self.proxy_manager.get_proxy()
        print("ip cookie初始化成功")


    @classmethod
    def from_crawler(cls, crawler):
        proxy_api = crawler.settings.get("PROXY_API")
        cookie_pool = crawler.settings.get("COOKIE_POOL", [])
        middleware = cls(proxy_api, cookie_pool)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def process_request(self, request, spider):
        if "proxy" not in request.meta and request.meta.get('isApi'):
            proxy_item = self.proxy_manager.get_proxy()
            if proxy_item:
                # 设置代理和 Cookie
                request.meta["proxy"] = f"http://{proxy_item.ip}:{proxy_item.port}"
                request.cookies['web_session'] = proxy_item.cookie
                spider.logger.debug(f"使用代理: {proxy_item.ip}, Cookie: {proxy_item.cookie}...")
            else:
                spider.logger.error("代理池枯竭")
                raise IgnoreRequest

    def process_response(self, request, response, spider):
        if response.status in [104]:
            # 未登录,重新发起请求
            return request  # 重新调度

        if response.status in [461]:
            spider.logger.warning(f"出现验证码!")
            spider.logger.warning(f"{response.text}!")
            return response

        if response.status in [403, 429, 503, 416]:
            # 获取当前代理并标记失效
            proxy = request.meta.get("proxy", "").replace("http://", "")
            if proxy:
                ip_port = proxy.split(":")
                proxy_item = next(
                    (p for p in self.proxy_manager.proxy_pool
                     if p.ip == ip_port[0] and p.port == ip_port[1]),
                    None
                )
                if proxy_item:
                    self.proxy_manager.mark_invalid(proxy_item)
                    spider.logger.warning(f"标记失效代理: {proxy}")
            return request  # 重新调度
        return response

    def process_exception(self, request, exception, spider):
        # 标记代理失效
        proxy = request.meta.get("proxy", "").replace("http://", "")
        if proxy:
            ip_port = proxy.split(":")
            proxy_item = next(
                (p for p in self.proxy_manager.proxy_pool
                 if self.proxy_manager.proxy_pool[p].ip == ip_port[0] and self.proxy_manager.proxy_pool[p].port == ip_port[1]),
                None
            )
            if proxy_item:
                self.proxy_manager.mark_invalid(proxy_item)
        return request

    def spider_closed(self, spider):
        spider.logger.info("动态代理中间件关闭")