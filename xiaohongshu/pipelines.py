# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
import pymongo
# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import json
import os

from scrapy.utils import spider
from scrapy.utils.project import get_project_settings

from xiaohongshu.items import CommentItem, PostItem


class XiaohongshuPipeline:
    def __init__(self):
        settings = get_project_settings()
        self.mongo_uri = settings.get("MONGO_URI")
        self.mongo_db = settings.get("MONGO_DATABASE")

        # 批量插入配置
        self.batch_size = 100  # 每批插入 100 条
        self.comment_buffer = []  # CommentItem 缓存
        self.post_buffer = []  # PostItem 缓存

        self.client = None
        self.db = None

        self.total_comments = 0  # 总评论数
        self.total_posts = 0  # 总帖子数

    def open_spider(self, spider):
        """连接 MongoDB 并创建索引"""
        try:
            self.client = pymongo.MongoClient(self.mongo_uri)
            self.db = self.client[self.mongo_db]

            spider.logger.info("MongoDB 连接成功")
        except Exception as e:
            spider.logger.error(f"MongoDB 连接失败: {e}")

    def close_spider(self, spider):
        """处理剩余数据并关闭连接"""
        try:
            if self.comment_buffer:
                self._insert_comments()
            if self.post_buffer:
                self._insert_posts()
        finally:
            if self.client:
                self.client.close()
                spider.logger.info("MongoDB 连接已关闭")

    def process_item(self, item, spider):
        """分类缓存数据"""
        item_dict = ItemAdapter(item).asdict()

        if isinstance(item, CommentItem):
            self.comment_buffer.append(item_dict)
            if len(self.comment_buffer) >= self.batch_size:
                self._insert_comments()

        elif isinstance(item, PostItem):
            self.post_buffer.append(item_dict)
            if len(self.post_buffer) >= self.batch_size:
                self._insert_posts()

        return item

    def _insert_comments(self):
        """批量插入评论数据"""
        try:
            if self.comment_buffer:
                result = self.db.comments.insert_many(self.comment_buffer)
                spider.logger.info(f"批量插入 {len(result.inserted_ids)} 条评论")
                self.comment_buffer = []
                self.total_comments += len(result.inserted_ids)
                spider.logger.info(f"累计已插入评论: {self.total_comments}")
        except pymongo.errors.BulkWriteError as e:
            spider.logger.error(f"评论批量插入失败: {e.details}")
        except Exception as e:
            spider.logger.error(f"评论插入异常: {e}")

    def _insert_posts(self):
        """批量插入帖子数据"""
        try:
            if self.post_buffer:
                result = self.db.posts.insert_many(self.post_buffer)
                spider.logger.info(f"批量插入 {len(result.inserted_ids)} 条帖子")
                self.post_buffer = []
                self.total_posts += len(result.inserted_ids)
                spider.logger.info(f"累计已插入帖子: {self.total_posts}")
        except pymongo.errors.BulkWriteError as e:
            spider.logger.error(f"帖子批量插入失败: {e.details}")
        except Exception as e:
            spider.logger.error(f"帖子插入异常: {e}")



