import scrapy
from xiaohongshu.items import PostItem, CommentItem, UserItem, ImageItem, TagItem
from xhs import XiaohongshuClient


class XhsSpiderSpider(scrapy.Spider):
    name = 'xhs_spider'
    allowed_domains = ['xiaohongshu.com']

    def start_requests(self):
        self.client = XiaohongshuClient(self.crawler)
        # 初始搜索请求
        def start_search(response):
            keyword = 'btc'
            self.logger.info('开始搜索')
            for i in range(1,6):
                yield self.client.search_notes(keyword, i, 20, self.parse_search, meta={'isApi':True})

        yield from self.client.run(self.crawler, final_callback=start_search)  # 初始化必要参数

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        # 创建 Spider 实例
        spider = super().from_crawler(crawler, *args, **kwargs)
        # 将 crawler 传递给自定义类
        spider.client = XiaohongshuClient.from_crawler(crawler)
        return spider


    def parse_search(self, response):
        data = response.json()
        print(data)
        items = data['data']['items']
        self.logger.info('开始获取帖子和评论数据......')
        for item in items:
            if item.get('model_type') == 'note':
                xsec_token = item['xsec_token']
                note_id = item['id']
                yield self.client.get_note(note_id, xsec_token, self.parse_note)
                yield self.client.get_comment(note_id=note_id,xsec_token= xsec_token, callback=self.parse_comments,meta={'note_id':note_id,'xsec_token':xsec_token})

    def parse_note(self, response):
        data = response.json()
        for item in data.get("data", {}).get("items", []):
            note_card = item.get("note_card", {})
            post_item = PostItem(
                note_id=note_card.get("note_id", ""),
                type=note_card.get("type", ""),
                tag_list=note_card.get("tag_list", []),
                ip_location=note_card.get("ip_location", ""),
                last_update_time=note_card.get("last_update_time", 0),
                title=note_card.get("title", ""),
                desc=note_card.get("desc", ""),
                user=note_card.get("user", {}).get('nickname', {}),
                interact_info=note_card.get("interact_info", {}),
                image_list=note_card.get("image_list", []),
                at_user_list=note_card.get("at_user_list", []),
                time=note_card.get("time", 0),
                id=item.get("id", ""),
                model_type=item.get("model_type", "")
            )
            yield post_item

    def parse_comments(self, response):
        result = response.json()
        if result['data']['has_more']:
            self.logger.info("继续获取未获取完的评论")
            new_cursor = result['data']['cursor']
            yield self.client.get_comment(response.meta['note_id'], response.meta['xsec_token'],new_cursor, callback=self.parse_comments, meta=response.meta)

        comments = result.get("data", {}).get("comments", [])
        for comment in comments:
            item = CommentItem(
                comment_id=comment.get("id", ""),
                note_id=comment.get("note_id", ""),
                content=comment.get("content", ""),
                create_time=comment.get("create_time", 0),
                like_count=comment.get("like_count", "0"),
                ip_location=comment.get("ip_location", ""),
                user_info=comment.get("user_info", {}),
                sub_comments=comment.get("sub_comments", []),
                sub_comment_count=comment.get("sub_comment_count", "0"),
                sub_comment_cursor=comment.get("sub_comment_cursor", ""),
                at_users=comment.get("at_users", []),
                show_tags=comment.get("show_tags", [])
            )
            yield item


    def parse_user_notes(self, response):
        result = response.json()
        if result['data']['has_more']:
            self.logger.info(f"继续获取用户:{response.meta['user_id']}的笔记")
            new_cursor = result['data']['cursor']
            yield self.client.get_user_notes(response.meta['user_id'], response.meta['xsec_token'],new_cursor, callback=self.parse_user_notes, meta=response.meta)

        notes = result.get("data", {}).get("notes", [])
        for note in notes:
            xsec_token = note['xsec_token']
            note_id = note['note_id']
            yield self.client.get_note(note_id, xsec_token, self.parse_note)
            yield self.client.get_comment(note_id=note_id,xsec_token= xsec_token, callback=self.parse_comments,meta={'note_id':note_id,'xsec_token':xsec_token})
