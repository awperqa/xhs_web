# xhs_encryptor.py
import ctypes
import random
import time
from typing import List, Tuple
from wasmtime import Store, Module, Instance, Memory


class XhsEncryptor:
    """小红书Web端加密算法封装"""

    # 固定错误信息模板
    ERROR_TEMPLATES = (
        '    at _0x2dad65 (https://fe-static.xhscdn.com/as/v1/3e44/public/11b080d07a42355a374e830a4a0dc392.js:1:45658)',
        '    at https://fe-static.xhscdn.com/formula-static/xhs-pc-web/public/resource/js/vendor-dynamic.afb39cde.js:1:172348'
    )

    def __init__(self, wasm_path: str = '000238fa'):
        """
        初始化加密器
        :param wasm_path: WASM模块文件路径
        """
        self.wasm_path = wasm_path
        self._init_wasm_engine()

    def _init_wasm_engine(self):
        """初始化WASM运行时环境"""
        self.store = Store()
        self.module = Module.from_file(self.store.engine, self.wasm_path)
        self.instance = Instance(self.store, self.module, [])

        exports = self.instance.exports(self.store)
        self.malloc = exports['malloc']
        self.free = exports['free']
        self.xy_func = exports['xy_6f5d11bd973b7aae1c1be925d5d699c1']
        self.encrypt = exports['xy_daa92688ff9309e1a29d25224fd0164a']
        self.memory = exports['memory']

    def _allocate_buffer(self, data: bytes) -> int:
        """分配并写入内存"""
        ptr = self.malloc(self.store, len(data))
        self.memory.write(self.store, data, ptr)
        return ptr

    def _read_memory(self, address: int, length: int) -> bytes:
        """从内存读取数据"""
        return self.memory.read(self.store, address, address + length)

    @staticmethod
    def _clamp_32bit(value: int) -> int:
        """限制为32位有符号整数"""
        MAX_32BIT = 2147483647
        if not -MAX_32BIT - 1 <= value <= MAX_32BIT:
            value = (value + (MAX_32BIT + 1)) % (2 * (MAX_32BIT + 1)) - MAX_32BIT - 1
        return value

    @staticmethod
    def _unsigned_right_shift(n: int, shift: int) -> int:
        """无符号右移实现"""
        if n < 0:
            n = ctypes.c_uint32(n).value
        return XhsEncryptor._clamp_32bit(n >> shift) if shift >= 0 else -XhsEncryptor._clamp_32bit(n << abs(shift))

    @staticmethod
    def _calculate_checksum(data: List[int], mask: int) -> int:
        """计算校验和"""
        return sum((b & mask) for b in data) % 256

    def _process_with_lfsr(self, data: List[int], seed: int) -> List[int]:
        """LFSR算法处理数据"""
        BIT_POSITIONS = [15, 13, 12, 10]
        processed = []
        lfsr_state = seed

        for byte in data:
            processed.append(byte ^ (lfsr_state & 0xFF))

            feedback_bit = 0
            for pos in BIT_POSITIONS:
                feedback_bit ^= (lfsr_state >> pos) & 1

            lfsr_state = (lfsr_state >> 1) | (feedback_bit << 31)

        return processed

    def _generate_timestamp_block(self, seed: int) -> List[int]:
        """生成时间戳数据块"""
        timestamp = int(time.time() * 1000)
        time_low = timestamp & 0xFFFFFFFF
        time_high = (timestamp >> 32) & 0xFF

        return [
            125, 126, 131, 111, 1, 0, 1, 0, 1, 0xFF, 0xFF, 0xFF,
            seed & 0xFF, (seed >> 8) & 0xFF,
            (seed >> 16) & 0xFF, (seed >> 24) & 0xFF,
            time_low & 0xFF, (time_low >> 8) & 0xFF,
            (time_low >> 16) & 0xFF, (time_low >> 24) & 0xFF,
            time_high, 1, 0, 0
        ]

    def get_signature(self,
                      input_str: str,
                      md5_hash: str,
                      a1_str: str = '19576c1fc567jj18aqok5leyekr50sw1rcwzkehdh50000296779',
                      platform: str = 'xhs-pc-web') -> str:
        """
        获取加密签名
        :param input_str: 待加密的请求参数
        :param md5_hash: MD5哈希字符串
        :param a1_str: 固定a1参数
        :param platform: 平台标识
        :return: 加密后的签名字符串
        """
        # 生成加密组件
        random_seed = random.randint(0, 0xFFFFFFFF)
        xor_base = 97 + random_seed % 26
        # 处理MD5哈希
        initial_md5 = [b ^ (random_seed & 0xFF) for b in bytes.fromhex(md5_hash)]

        # WASM处理输入字符串
        input_data = input_str.encode()
        input_ptr = self._allocate_buffer(input_data)
        wasm_result = self.xy_func(self.store, input_ptr, len(input_data))
        processed_data = list(self._read_memory(wasm_result, 16))

        # 清理内存
        self.free(self.store, wasm_result)
        self.free(self.store, input_ptr)

        # 构建元数据块
        metadata_block = [
                             17,
                             self._calculate_checksum(processed_data, random_seed & 0xFF)
                         ] + processed_data + initial_md5

        # 添加平台信息
        platform_block = [
            len(a1_str),
            *a1_str.encode(),
            len(platform),
            *platform.encode()
        ]
        metadata_block += [
            len(platform_block),
            *platform_block,
            122, 0, 0, 0, 0, 0, 16, 17
        ]

        # 构建错误信息块
        error_block = [
            len(self.ERROR_TEMPLATES[0]),
            *self.ERROR_TEMPLATES[0].encode(),
            len(self.ERROR_TEMPLATES[1]),
            *self.ERROR_TEMPLATES[1].encode()
        ]

        error_block = [
            1,
            *error_block,
            len(error_block) % 100,
            1, 35, 1, 0, 1
        ]

        error_block = [*metadata_block, len(error_block), 1, *error_block]

        # 加密处理
        encrypted_block = self._process_with_lfsr(error_block, random_seed)
        final_payload = [
            *self._generate_timestamp_block(random_seed),
            216, 2,
            self._calculate_checksum(encrypted_block, 233),
            *encrypted_block
        ]

        # 异或处理
        xor_payload = [b ^ xor_base for b in final_payload]

        # WASM加密
        payload_ptr = self._allocate_buffer(bytes(xor_payload))
        result_addr = self.encrypt(self.store, payload_ptr, len(xor_payload))
        # 读取结果
        result_data = self.memory.read(self.store)

        signature = 'aw'+ chr(xor_base) + self._extract_string(result_addr, result_data)
        # 清理资源
        self.free(self.store, payload_ptr)
        return signature

    @staticmethod
    def _extract_string(start_index: int, buffer_data: bytes) -> str:
        result = []
        # 从起始位置开始遍历字节数据
        for idx in range(start_index, len(buffer_data)):
            byte = buffer_data[idx]
            if byte == 0:  # 遇到零字节时停止
                break
            result.append(chr(byte))  # 将字节转换为字符
        return ''.join(result)  # 拼接最终字符串


def get_encrypted_signature(
        input_str: str,
        md5_hash: str,
        a1_str: str = '19576c1fc567jj18aqok5leyekr50sw1rcwzkehdh50000296779',
        platform: str = 'xhs-pc-web',
        wasm_path: str = 'D:\\code\\crawler\\scrapy\\xiaohongshu\\xiaohongshu\\util\\000238fa'
) -> str:
    """
    快速获取加密签名（单例方式）
    """
    encryptor = XhsEncryptor(wasm_path)
    return encryptor.get_signature(input_str, md5_hash, a1_str, platform)

                     #/api/sns/web/v1/feed
# input_str = 'mns_' + url + body   md5_hash = md5(url +body) 32
A = get_encrypted_signature(
    'mns_/api/sns/web/v1/feed{"source_note_id":"67dc2e1a000000001b026be1","image_formats":["jpg","webp","avif"],"extra":{"need_body_topic":"1"},"xsec_source":"pc_feed","xsec_token":"AB5lq7QZ5eYYTz_gdnv8TDpphHczIpamSNM9Gvf3C7Z2s="}',
    'e537a8c1b47cb40334ba5a1135ae9a47'
)
print(A)
print(len(A))