from datetime import datetime, timedelta
import scrapy

class UserItem(scrapy.Item):
    user_id = scrapy.Field()
    nickname = scrapy.Field()
    avatar = scrapy.Field()
    xsec_token = scrapy.Field()


class ProxyItem:
    def __init__(self, ip, port, cookie):
        self.ip = ip
        self.port = port
        self.cookie = cookie  # 绑定的 Cookie
        self.expire_time = datetime.now() + timedelta(minutes=9)  # 有效期 10 分钟（提前 1 分钟过期）
        self.is_valid = True  # 是否有效


class TagItem(scrapy.Item):
    tag_id = scrapy.Field()
    name = scrapy.Field()
    type = scrapy.Field()

class ImageItem(scrapy.Item):
    url_pre = scrapy.Field()
    url_default = scrapy.Field()
    width = scrapy.Field()
    height = scrapy.Field()

class CommentItem(scrapy.Item):
    # 评论的唯一标识，对应 JSON 中的 "id"
    comment_id = scrapy.Field()
    # 帖子标识，评论所属的帖子 note_id
    note_id = scrapy.Field()
    # 评论内容
    content = scrapy.Field()
    # 评论创建时间（毫秒级时间戳）
    create_time = scrapy.Field()
    # 点赞数量（注意：数据类型可能为字符串）
    like_count = scrapy.Field()
    # IP 定位信息
    ip_location = scrapy.Field()
    # 评论作者的详细信息，包括 user_id、nickname、image、xsec_token 等
    user_info = scrapy.Field()
    # 子评论列表（若存在子评论，则为一个列表）
    sub_comments = scrapy.Field()
    # 子评论总数（通常为字符串，可根据需要转换成数字）
    sub_comment_count = scrapy.Field()
    # 用于分页获取子评论时的游标
    sub_comment_cursor = scrapy.Field()
    # 评论中提及的用户列表
    at_users = scrapy.Field()
    # 显示标签列表
    show_tags = scrapy.Field()



class PostItem(scrapy.Item):
    # 帖子唯一标识（note_card 内部的 note_id）
    note_id = scrapy.Field()
    # 帖子的类型，如 "normal"
    type = scrapy.Field()
    # 帖子标签列表，每个标签包含 id、name、type 等信息
    tag_list = scrapy.Field()
    # IP 定位信息（例如湖南）
    ip_location = scrapy.Field()
    # 帖子最后更新时间（毫秒级时间戳）
    last_update_time = scrapy.Field()
    # 帖子的标题
    title = scrapy.Field()
    # 帖子的描述内容
    desc = scrapy.Field()
    # 用户信息（包含 user_id、nickname、avatar、xsec_token 等）
    user = scrapy.Field()
    # 互动信息（如点赞、评论、收藏数等）
    interact_info = scrapy.Field()
    # 图片列表，每个图片包含相关属性（宽度、高度、info_list 等）
    image_list = scrapy.Field()
    # 提及用户列表
    at_user_list = scrapy.Field()
    # 帖子创建时间（毫秒级时间戳）
    time = scrapy.Field()
    # 外层 id（通常与 note_card 内的 note_id 相同）
    id = scrapy.Field()
    # 模型类型，如 "note"
    model_type = scrapy.Field()