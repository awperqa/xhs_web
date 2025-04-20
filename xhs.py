#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于类封装的小红书接口请求及加密工具

主要功能：
    - 各种加密（AES、DES、RC4）和编码工具
    - 构造请求所需的 x-s、x-t、x-s-common 等参数
    - 接口请求封装（登录、帖子详情、评论、搜索、关注、点赞、收藏等）
"""

import json
import math
import os
import time
import subprocess
import uuid
from http.cookiejar import Cookie

import requests
import base64
import random
import hashlib
import zlib
from datetime import datetime
import pytz
import scrapy
from Crypto.Cipher import AES, DES
from Crypto.Util.Padding import pad
from xiaohongshu.util.x_mns import get_encrypted_signature


class XiaohongshuClient:
    def __init__(self, crawler):
        # 初始化 requests session
        # AES 加密使用的 IV 和 key（均为 bytes 类型）
        self.iv = bytes([52, 117, 122, 106, 114, 55, 109, 98, 115, 105, 98, 99, 97, 108, 100, 112])
        self.key = bytes([55, 99, 99, 52, 97, 100, 108, 97, 53, 97, 121, 48, 55, 48, 49, 118])
        # a1 为本地生成的 id
        self.a1 = self.generateLocalId('Windows')
        self.webId = self.md5_encrypt(self.generate_trace_id())
        self.crawler = crawler
        self.cookie = self.init_cookies()

    @classmethod
    def from_crawler(cls, crawler):
        # 创建实例并传递 crawler
        return cls(crawler)

    # -------------------------------
    # 工具函数（静态方法）
    # -------------------------------
    @staticmethod
    def int_to_base36(num):
        """整数转换为36进制字符串"""
        if num < 0:
            raise ValueError("Negative numbers not supported")
        chars = '0123456789abcdefghijklmnopqrstuvwxyz'
        if num == 0:
            return chars[0]
        result = []
        while num > 0:
            num, rem = divmod(num, 36)
            result.append(chars[rem])
        return ''.join(reversed(result))

    def create_search_id(self):
        """
        生成搜索 id：
            - 当前毫秒级时间戳左移 64 位后加上随机数
            - 转换为36进制字符串
        """
        timestamp_ms = int(time.time() * 1000)
        o = math.ceil(0x7ffffffe * random.random())
        combined = (timestamp_ms << 64) + o
        return self.int_to_base36(combined)

    @staticmethod
    def gen_random_string(length):
        """生成指定长度的随机字符串（由小写字母和数字组成）"""
        return ''.join(random.choices("abcdefghijklmnopqrstuvwxyz1234567890", k=length))

    @staticmethod
    def md5_encrypt(data):
        """MD5 加密，返回32位小写字符串"""
        md5 = hashlib.md5()
        md5.update(data.encode('utf-8'))
        return md5.hexdigest()

    @staticmethod
    def crc32(data):
        """
        计算 CRC32 校验值
        :param data: 字符串或 bytes
        :return: 无符号 32 位整数
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        return zlib.crc32(data) & 0xFFFFFFFF

    # -------------------------------
    # DES、AES、RC4 加密相关
    # -------------------------------
    @staticmethod
    def des_encrypt(plaintext, key_str):
        """
        DES 加密（ECB模式，PKCS7填充）
        :param plaintext: 明文字符串
        :param key_str: 8字节的 DES 密钥（字符串）
        :return: 加密后的 bytes
        """
        key_bytes = key_str.encode('utf-8')
        plaintext_bytes = plaintext.encode('utf-8')
        if len(key_bytes) != 8:
            raise ValueError("DES密钥必须为8字节长度")
        cipher = DES.new(key_bytes, DES.MODE_ECB)
        padded_bytes = pad(plaintext_bytes, DES.block_size)
        return cipher.encrypt(padded_bytes)

    @staticmethod
    def aes_pad(data):
        """PKCS7 填充（AES）"""
        padding_len = 16 - (len(data) % 16)
        return data + bytes([padding_len] * padding_len)

    @staticmethod
    def unpad(data):
        """去除 PKCS7 填充"""
        padding_len = data[-1]
        return data[:-padding_len]

    def aes_encrypt(self, plaintext):
        """
        AES-CBC 加密
        :param plaintext: 明文字符串
        :return: 加密后的 bytes
        """
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        padded_text = self.aes_pad(plaintext.encode())
        return cipher.encrypt(padded_text)

    def aes_decrypt(self, encrypted):
        """
        AES-CBC 解密
        :param encrypted: 加密的 bytes
        :return: 解密后的明文字符串
        """
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        decrypted_padded = cipher.decrypt(encrypted)
        return self.unpad(decrypted_padded).decode()

    @staticmethod
    def custom_b64encode(input_data):
        """
        自定义 Base64 编码：
            1. 使用标准 Base64 编码
            2. 替换标准字母表为自定义字母表
        """
        custom_alphabet = "ZmserbBoHQtNP+wOcza/LpngG8yJq42KWYj0DSfdikx3VT16IlUAFM97hECvuRX5"
        standard_alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        base64_map = {standard_alphabet[i]: custom_alphabet[i] for i in range(64)}

        encoded = base64.b64encode(input_data.encode('utf-8')).decode('utf-8')
        return ''.join([base64_map.get(ch, ch) for ch in encoded])

    @staticmethod
    def string_to_bytes(hex_str):
        """十六进制字符串转字节数组"""
        return bytes.fromhex(hex_str)

    @staticmethod
    def bytes_to_hex(byte_data):
        """字节数组转十六进制字符串"""
        return byte_data.hex()

    # RC4 实现
    @staticmethod
    def KSA(key_bytes):
        """RC4 Key-Scheduling Algorithm (KSA)"""
        S = list(range(256))
        j = 0
        for i in range(256):
            j = (j + S[i] + key_bytes[i % len(key_bytes)]) % 256
            S[i], S[j] = S[j], S[i]
        return S

    @staticmethod
    def PRGA(S):
        """RC4 Pseudo-Random Generation Algorithm (PRGA)"""
        i, j = 0, 0
        while True:
            i = (i + 1) % 256
            j = (j + S[i]) % 256
            S[i], S[j] = S[j], S[i]
            yield S[(S[i] + S[j]) % 256]

    @classmethod
    def RC4(cls, key_bytes, data):
        """
        RC4 加密/解密
        :param key_bytes: bytes 类型的密钥
        :param data: bytes 类型的数据
        :return: 加密/解密后的 bytes
        """
        S = cls.KSA(key_bytes)
        keystream = cls.PRGA(S)
        return bytes([b ^ next(keystream) for b in data])

    # -------------------------------
    # 工具方法（依赖当前实例状态）
    # -------------------------------
    def generateLocalId(self, e):
        """
        生成本地 id
        :param e: 保留参数，目前未使用
        """
        r = 5
        timestamp_hex = hex(int(time.time() * 1000))[2:]
        random_str = self.gen_random_string(30)
        base_str = f"{timestamp_hex}{random_str}{r}0{'000'}"
        crc32_hash = self.crc32(base_str)
        return (base_str + str(crc32_hash))[:52]

    def get_x_xray_traceid(self):
        """
        调用 Node.js 脚本生成 x-xray-traceid
        注意：js 文件路径需要根据项目实际情况调整
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        js_file_path = os.path.join(current_dir, "..", "js_code", "x-xray-traceid.js")
        result = subprocess.run(
            ["node", js_file_path],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()

    def generate_trace_id(self):
        """
        生成 16 位随机 traceId（由 a-f 和 0-9 组成）
        """
        chars = 'abcdef0123456789'
        return ''.join(random.choice(chars) for _ in range(16))

    def get_x_s_x_t(self, p, u):
        """
        构造 x-s 与 x-t 参数
        :param p: 请求 URL
        :param u: 请求数据（JSON 串）
        :return: tuple (x_s, x_t)
        """
        # 处理 url
        p = 'url=/' + p.split('//')[-1].split('/', 1)[-1]
        x_s_data = {
            "signSvn": "56",
            "signType": "x2",
            "appId": "xhs-pc-web",
            "signVersion": "1",
            "payload": ""
        }
        x1 = self.md5_encrypt(p + u)
        x3 = self.a1
        x4 = int(time.time() * 1000)  # 13位时间戳

        payload_data = f'x1={x1};x2=0|0|0|1|0|0|1|0|0|0|1|0|0|0|0|1|0|0|0;x3={x3};x4={x4};'
        base64_pay = base64.b64encode(payload_data.encode('utf-8')).decode('utf-8')
        payload = self.aes_encrypt(base64_pay)
        x_s_data['payload'] = self.bytes_to_hex(payload)
        x_s = 'XYW_' + base64.b64encode(json.dumps(x_s_data).encode("utf-8")).decode('utf-8')
        x_t = x4
        return x_s, x_t

    def get_x_s_common(self, x_s, x_t):
        """
        构造 x-s-common 参数
        """
        b1_params = '{"x33":"0","x34":"0","x35":"0","x36":"1","x37":"0|0|0|0|0|0|0|0|0|1|0|0|0|0|0|0|0|0|1|0|0|0|0|0","x38":"0|0|1|0|1|0|0|0|0|0|1|0|1|0|1|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0","x39":"0 ","x42":"3.3.3","x43":"f72c2d2c","x44":"1740659728620","x45":"connecterror","x46":"false","x48":"","x49":"{list:[],type:}","x50":"","x51":"","x52":"[]"}'
        tend = int(time.time() * 1000)
        b1_params = b1_params.replace('"x44":"1740659728620"', f'"x44":"{tend}"')
        b1_params = b1_params.encode("utf-8")
        # 使用 RC4 加密
        b1_rc4 = self.RC4(b"xhswebmplfbt", b1_params)
        b1_str = ''.join(chr(b) for b in b1_rc4)
        b1 = self.custom_b64encode(b1_str)

        m = {
            "s0": 5,
            "s1": "",
            "x0": '1',
            "x1": "4.1.0",
            "x2": "Windows",
            "x3": "xhs-pc-web",
            "x4": "4.58.0",   # 如需更新版本请调整
            "x5": self.a1,
            "x6": x_t,
            "x7": x_s,
            "x8": b1,
            "x9": self.crc32(str(x_t) + x_s + b1),
            "x10": 150
        }
        return self.custom_b64encode(json.dumps(m, separators=(',', ':')))

    def get_headers(self, x_s, x_t, x_s_common, x_mns):
        """
        构造请求 headers
        """
        headers = {
            'accept': 'application/json,text/plain,*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'cache-control': 'no-cache',
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://www.xiaohongshu.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://www.xiaohongshu.com/',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Microsoft Edge";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0',
            'x-b3-traceid': self.generate_trace_id(),
            'x-mns': x_mns,
            'x-s': x_s,
            'x-s-common': x_s_common,
            'x-t': str(x_t),
            'x-xray-traceid': self.get_x_xray_traceid()
        }
        return headers

    def xhs_request(self, url, method, data=None, callback=None, meta=None, cookie=None):
        """
        小红书请求封装（生成 scrapy.Request 对象）：
            1. 根据 URL 与数据生成 x-s, x-t, x-s-common 参数
            2. 构造 headers 后生成 scrapy.Request 对象，并附加 cookies
        :param url: 请求 URL
        :param method: GET 或 POST
        :param data: 请求数据（字典），POST 时会转换为 JSON 字符串作为 body
        :param callback: 请求回调函数，用于处理响应
        :return: scrapy.Request 对象
        """
        data_str = json.dumps(data) if data is not None else ''
        x_s, x_t = self.get_x_s_x_t(url, data_str)
        x_s_common = self.get_x_s_common(x_s, x_t)
        x_mns = get_encrypted_signature('mns_' + url + json.dumps(data,separators=(',', ':'), ensure_ascii=False),
                                        self.md5_encrypt(url + json.dumps(data,separators=(',', ':'), ensure_ascii=False)),
                                        self.a1)
        headers = self.get_headers(x_s, x_t, x_s_common, x_mns)

        if method.upper() == "GET":
            req = scrapy.Request(
                url=url,
                method="GET",
                headers=headers,
                callback=callback,
                dont_filter=True,
                meta=meta,
                cookies=cookie
            )
        elif method.upper() == "POST":
            req = scrapy.Request(
                url=url,
                method="POST",
                headers=headers,
                body=json.dumps(data) if data is not None else '',
                callback=callback,
                dont_filter=True,
                meta=meta,
                cookies=cookie
            )
        else:
            raise ValueError("仅支持 GET 和 POST 请求")
        return req

    # -------------------------------
    # Session Cookie 设置
    # -------------------------------
    def init_cookies(self):
        """
        初始化固定的 cookies 参数，并返回一个字典，
        该字典可以直接作为 scrapy.Request 的 cookies 参数使用
        """
        # 如果需要预先访问某个 URL 获取 cookies，可以通过生成一个 Request 来完成，
        # 但这里我们直接构造固定的 cookies 数据
        cookies = {
            "webBuild": "4.58.0",
            "xsecappid": "xhs-pc-web",
            "loadts": str(int(time.time() * 1000)),
            "a1": self.a1,
            "webId": self.webId,
        }
        return cookies

    # -------------------------------
    # 接口请求方法
    # -------------------------------
    def login(self, phone, callback=None):
        """
        登录流程：
            1. 发送验证码
            2. 校验验证码（此处固定验证码为 "104912"，实际使用时需修改）
            3. 获取登录 session
        """
        send_code_url = f'https://edith.xiaohongshu.com/api/sns/web/v2/login/send_code?phone={phone}&zone=86&type=login'
        self.xhs_request(send_code_url, 'GET', callback)

        code = "104912"  # 测试验证码，实际情况需替换
        check_code_url = f'https://edith.xiaohongshu.com/api/sns/web/v1/login/check_code?phone={phone}&zone=86&code={code}'
        result = self.xhs_request(check_code_url, 'GET',callback=callback)
        mobile_token = result['data']["mobile_token"]

        code_url = 'https://edith.xiaohongshu.com/api/sns/web/v2/login/code'
        data = {"mobile_token": mobile_token, "zone": "86", "phone": phone}
        return self.xhs_request(code_url, 'POST', data, callback)

    def get_note(self, source_note_id, xsec_token, callback=None, meta=None):
        """获取帖子详情"""
        feed_url = 'https://edith.xiaohongshu.com/api/sns/web/v1/feed'
        data = {
            "source_note_id": source_note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": "1"},
            "xsec_source": "pc_feed",
            "xsec_token": xsec_token
        }
        return self.xhs_request(feed_url, 'POST', data, callback, meta, self.cookie)

    def get_comment(self, note_id, xsec_token, cursor="", callback=None, meta=None):
        """
        获取评论（递归获取全部评论）
        """
        comment_url = (f'https://edith.xiaohongshu.com/api/sns/web/v2/comment/page?note_id={note_id}'
                       f'&cursor={cursor}&top_comment_id=&image_formats=jpg,webp,avif&xsec_token={xsec_token}')
        return self.xhs_request(comment_url, 'GET', callback=callback, meta=meta, cookie=self.cookie)

    def search_notes(self, keyword, page, page_size, callback, meta=None):
        """
        搜索帖子（需要登录）
        """
        search_url = 'https://edith.xiaohongshu.com/api/sns/web/v1/search/notes'
        data = {
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "search_id": self.create_search_id(),
            "sort": "general",
            "note_type": 0,
            "ext_flags": [],
            "image_formats": ["jpg", "webp", "avif"]
        }
        return self.xhs_request(search_url, 'POST', data, callback, meta=meta, cookie=self.cookie)

    def get_user_notes(self, user_id, xsec_token, cursor='', callback=None, meta=None):
        """获取用户帖子"""
        user_url = f'https://edith.xiaohongshu.com/api/sns/web/v1/user_posted?num=30&cursor='+cursor+'&user_id='+user_id+'&image_formats=jpg,webp,avif&xsec_token='+xsec_token+'&xsec_source=pc_search'
        self.xhs_request(user_url, "GET",callback=callback)

    def follow_user(self, target_user_id, callback=None):
        """关注用户接口"""
        follow_url = 'https://edith.xiaohongshu.com/api/sns/web/v1/user/follow'
        data = {"target_user_id": target_user_id}
        self.xhs_request(follow_url, 'POST', data, callback)

    def like_note(self, note_oid, callback=None):
        """点赞帖子接口"""
        like_url = 'https://edith.xiaohongshu.com/api/sns/web/v1/note/like'
        data = {"note_oid": note_oid}
        self.xhs_request(like_url, 'POST', data, callback)

    def collect_note(self, note_id, callback=None):
        """收藏帖子接口（取消收藏可参考）"""
        collect_url = 'https://edith.xiaohongshu.com/api/sns/web/v1/note/collect'
        data = {"note_id": note_id}
        self.xhs_request(collect_url, 'POST', data, callback)

    # -------------------------------
    # 示例业务流程
    # -------------------------------

    def parse_explore(self, response):

        # 2. 探索页请求完成后，再请求激活接口
        activate_url = 'https://edith.xiaohongshu.com/api/sns/web/v1/login/activate'
        yield self.xhs_request(
            url=activate_url,
            method="POST",
            data={},
            callback=self.parse_activate,  # 指定回调函数
            meta={'final_callback': response.meta['final_callback']},
            cookie=self.cookie
        )


    def parse_activate(self, response):
        # 获取当前 Cookie
        cookies_str = response.request.headers.getlist('Cookie')
        cookies_str = cookies_str[0].decode('utf-8')
        cookies_dict = {}
        for item in cookies_str.split('; '):
            # 处理可能存在多个等号的情况（例如：key=value=123）
            key, value = item.split('=', 1)  # 只分割第一个等号
            cookies_dict[key] = value

        print("当前 Cookies:", cookies_dict)
        formatted_cookies = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
        print("格式化后的 Cookie 字符串:", formatted_cookies)

        # 构造 profileData 数据   注意有些数据需要随机替换
        profileData = {
            "x1": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0",
            "x2": "false",
            "x3": "zh-CN",
            "x4": "24",
            "x5": "8",
            "x6": "24",
            "x7": "Google Inc. (NVIDIA),ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Laptop GPU (0x00002520) Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "x8": "16",
            "x9": "1920;1080",
            "x10": "1920;1032",
            "x11": "-480",
            "x12": "Asia/Shanghai",
            "x13": "true",
            "x14": "true",
            "x15": "true",
            "x16": "false",
            "x17": "false",
            "x18": "un",
            "x19": "Win32",
            "x20": "un",
            "x21": "PDF Viewer,Chrome PDF Viewer,Chromium PDF Viewer,Microsoft Edge PDF Viewer,WebKit built-in PDF",
            "x22": "d730a91a255004ea76a4f70879c221b6",
            "x23": "false",
            "x24": "false",
            "x25": "false",
            "x26": "false",
            "x27": "false",
            "x28": "0,false,false",
            "x29": "4,7,8",
            "x30": "swf object not loaded",
            "x33": "0",
            "x34": "0",
            "x35": "0",
            "x36": "1",
            "x37": "0|0|0|0|0|0|0|0|0|1|0|0|0|0|0|0|0|0|1|0|0|0|0|0",
            "x38": "0|0|1|0|1|0|0|0|0|0|1|0|1|0|1|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0",
            "x39": "2",
            "x40": "0",
            "x41": "0",
            "x42": "3.3.3",
            "x43": "f72c2d2c",
            "x44": str(int(time.time() * 1000)),
            "x45": "connecterror",
            "x46": "false",
            "x47": "0|0|0|0|0|1",
            "x48": "",
            "x49": "{list:[],type:}",
            "x50": "",
            "x51": "",
            "x52": "[]",
            "x55": "500,500,560,520,500,520,500,1120,500,480,480,520,480,580",
            "x56": "Google Inc. (NVIDIA)|ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Laptop GPU (0x00002520) Direct3D11 vs_5_0 ps_5_0, D3D11)|0ebc53d03ea89d69525d81de558e2544|35",
            "x57": formatted_cookies,  # 填入格式化后的 Cookie 字符串
            "x58": "157",
            "x59": "18",
            "x60": "63",
            "x61": "1277",
            "x62": "2047",
            "x63": "0",
            "x64": "0",
            "x65": "0",
            "x66": {"referer": "", "location": "https://www.xiaohongshu.com/explore", "frame": 0},
            "x67": "1|0",
            "x68": "0",
            "x69": "337|1278",
            "x70": ["location"],
            "x71": "true",
            "x72": "complete",
            "x73": "1210",
            "x74": "0|0|0",
            "x75": "Google Inc.",
            "x76": "true",
            "x77": "1|1|1|1|1|1|1|1|1|1",
            "x78": {
                "x": 0, "y": 3231, "left": 0, "right": 401.3125,
                "bottom": 3249, "height": 18, "top": 3231, "width": 401.3125,
                "font": 'system-ui, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji", -apple-system, "Segoe UI", Roboto, Ubuntu, Cantarell, "Noto Sans", sans-serif, BlinkMacSystemFont, "Helvetica Neue", Arial, "PingFang SC", "PingFang TC", "PingFang HK", "Microsoft Yahei", "Microsoft JhengHei"'
            },
            "x31": "124.04347527516074",
            "x81": "328|9e56892d480f88505e4f7632f28ccc62",
            "x79": "144|292299357388",
            "x53": "1b5fffbc65fbb103e7e5ceca47640415",
            "x54": "11311144241322244122",
            "x80": "1|[object FileSystemDirectoryHandle]"
        }
        # 将 profileData 转为 JSON 后进行 Base64 编码，再使用 DES 加密
        profile_json = json.dumps(profileData)
        pro_base64 = base64.b64encode(profile_json.encode("utf-8")).decode("utf-8")
        profileData_encrypted = self.des_encrypt(pro_base64, "zbp30y86").hex()

        webprofile_data = {
            'platform': "Windows",
            'profileData': profileData_encrypted,
            'sdkVersion': "4.1.0",
            'svn': "2"
        }


        yield self.xhs_request('https://as.xiaohongshu.com/api/sec/v1/shield/webprofile','POST',
                               webprofile_data,
                               self.parse_webprofile,
                               meta={'final_callback': response.meta['final_callback']},
                               cookie=self.cookie
        )


    def parse_webprofile(self, response):
        return response.meta['final_callback'](response)


    def run(self, crawler, final_callback):
        """
        示例流程：
            1. 初始化 Cookies
            2. 调用激活接口
            3. 构造 profileData 并调用 webprofile 接口
        """
        explore_url = 'https://www.xiaohongshu.com/explore'
        yield scrapy.Request(
            url=explore_url,
            meta={'final_callback':final_callback},
            callback=self.parse_explore
        )






