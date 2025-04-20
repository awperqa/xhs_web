import ctypes
import random
import time

from wasmtime import Store, Module, Instance, Memory

def xyd1b4df64eb152aa1d24e82f9bd0bfe7b(start_index: int, buffer_data: bytes) -> str:
    result = []
    # 从起始位置开始遍历字节数据
    for idx in range(start_index, len(buffer_data)):
        byte = buffer_data[idx]
        if byte == 0:  # 遇到零字节时停止
            break
        result.append(chr(byte))  # 将字节转换为字符
    return ''.join(result)  # 拼接最终字符串


def int_overflow(val):
    maxint = 2147483647
    if not -maxint-1 <= val <= maxint:
        val = (val + (maxint + 1)) % (2 * (maxint + 1)) - maxint - 1
    return val

def unsigned_right_shitf(n, i):
    if n<0:
        n = ctypes.c_uint32(n).value
    if i<0:
        return -int_overflow(n << abs(i))
    return int_overflow(n >> i)

def deal_list(l, masked_val):
    deal_result = 0
    for i in l:
        deal_result = (deal_result + (i & masked_val)) % 256
    return deal_result

def deal_343_list(l, masked_val):
    c = []
    e = masked_val
    oo = [15, 13, 12, 10]

    for i in l:
        c.append(i ^ (e & 255))
        before_index = 0
        for w in oo:
            rs = (e >> w) & 1
            rs = before_index ^ rs
            before_index = rs
        a1 = unsigned_right_shitf(e, 1)
        e = a1 | (before_index << 31)

    return c



# 初始化WASM运行时
store = Store()
# 加载WASM模块
module = Module.from_file(store.engine, '000238fa')
instance = Instance(store, module, [])

# 获取导出的函数和内存
malloc = instance.exports(store)['malloc']
xy_func = instance.exports(store)['xy_6f5d11bd973b7aae1c1be925d5d699c1']
encrypt = instance.exports(store)['xy_daa92688ff9309e1a29d25224fd0164a']
memory = instance.exports(store)['memory']
free = instance.exports(store)['free']

#随机值
aa = 4218443955 # int(random.random() * 4294967295)
print(aa)
xor_value = 97 + aa % 26
print(f"异或值: {xor_value}")
# 原始字符串
md5 = 'e537a8c1b47cb40334ba5a1135ae9a47'
input_str = r'mns_/api/sns/web/v1/feed{"source_note_id":"67dc2e1a000000001b026be1","image_formats":["jpg","webp","avif"],"extra":{"need_body_topic":"1"},"xsec_source":"pc_feed","xsec_token":"AB5lq7QZ5eYYTz_gdnv8TDpphHczIpamSNM9Gvf3C7Z2s="}'
a1 = '19576c1fc567jj18aqok5leyekr50sw1rcwzkehdh50000296779'
platform = 'xhs-pc-web'
err1 = '    at _0x2dad65 (https://fe-static.xhscdn.com/as/v1/3e44/public/11b080d07a42355a374e830a4a0dc392.js:1:45658)'
err2 = '    at https://fe-static.xhscdn.com/formula-static/xhs-pc-web/public/resource/js/vendor-dynamic.afb39cde.js:1:172348'

# 处理初始md5
init_16 = list(bytes.fromhex(md5))
for i in range(len(init_16)):
    init_16[i] = init_16[i] ^ (aa & 255)
print(f"初始16数组:{init_16}")

# 编码为UTF-8字节数据
data = input_str.encode('utf-8')
ptr = malloc(store, len(input_str))
memory.write(store, data, ptr)

# 调用目标函数并获取返回值
result = xy_func(store, ptr, len(input_str))
bytes_data = memory.read(store, result, result+16)  # 读取16字节
new_16 = list(bytes_data)
print(f"新16数组:{new_16}")

# free内存
free(store, result)
free(store, ptr)

# 得到34数组
new_18 = [17, deal_list(new_16, aa & 255)] + new_16
new_34 = new_18 + init_16
print(f"34数组:{new_34}")

# a1  'xhs-pc-web'
a1_list = list(a1.encode('utf-8'))
print(f"a1:{a1_list}")
a1_list = [len(a1_list)] + a1_list

platform_list = list(platform.encode('utf-8'))
print(f"platform:{platform_list}")
platform_list = [len(platform_list)] + platform_list

new_64 = a1_list+platform_list
new_65 = [len(new_64)] + a1_list+platform_list
new_107 = new_34 + new_65 + [122, 0, 0, 0] + [0, 0, 16, 17]
print(f"a1 platform:{new_107}")

# err1 err2
err1_list = list(err1.encode('utf-8'))
print(f"err1:{err1_list}")
err1_list = [len(err1_list)] + err1_list

err2_list = list(err2.encode('utf-8'))
print(f"err2:{err2_list}")
err2_list = [len(err2_list)] + err2_list

err_list = err1_list+err2_list
err_list = [1] + err_list + [len(err_list) % 100] + [1, 35] + [1, 0, 1]
err_list = new_107 + [len(err_list), 1] + err_list

print(f"err_list:{err_list}")
err_list = deal_343_list(err_list, aa)
print(f"err_list处理后结果:{err_list}")
err_list = [216, 2, deal_list(err_list, 233)] + err_list

timestamp = 1744699085754 # int(time.time()*1000)
print(timestamp)
bb = timestamp % 4294967296  # timestamp % 4294967296
list_24 = [125, 126, 131, 111, 1, 0, 1, 0, 1, 255, 255, 255, aa&255, unsigned_right_shitf(aa,8) & 255, unsigned_right_shitf(aa,16) & 255, unsigned_right_shitf(aa,24) & 255, bb&255, unsigned_right_shitf(bb,8) & 255,  unsigned_right_shitf(bb,16) & 255, unsigned_right_shitf(bb,24) & 255, int(timestamp / 4294967296) & 255, 1,0,0]
result = list_24 + err_list
print(f"结果:{result}")
result = [i ^ xor_value for i in result]
print(f"加密明文:{result}")

# 调用malloc分配内存（长度225字节）
ptr = malloc(store, len(result))
memory.write(store, bytes(result), ptr)

# 调用目标函数并获取返回值
result = encrypt(store, ptr, len(result))
bytes_data = memory.read(store)
print(chr(bytes_data[result]))
result = 'aw'+ chr(xor_value) +xyd1b4df64eb152aa1d24e82f9bd0bfe7b(result, bytes_data)
print(result)
print(len(result))


