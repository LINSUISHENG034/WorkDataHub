# /database_operations/mongo_ops.py
import pandas as pd
from datetime import datetime
from bson.objectid import ObjectId
from pymongo import MongoClient
from logger.logger import logger
from pymongo.errors import PyMongoError


class MongoDBManager:
    def __init__(self, uri='mongodb://localhost:27017/', database_name='enterprise_data'):
        self.uri = uri
        self.database_name = database_name
        self.client = None
        self.db = None
        self.connect()

    def connect(self):
        try:
            self.client = MongoClient(self.uri)
            self.db = self.client[self.database_name]
        except PyMongoError as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise

    def _handle_failed_insert(self, data, collection_name):
        temp_collection_name = f"temp_{collection_name}"
        temp_collection = self.db[temp_collection_name]
        try:
            temp_collection.insert_one(data)
            logger.info(f"Failed data inserted into temp collection {temp_collection_name}")
        except PyMongoError as e:
            logger.error(f"Error inserting data into temp collection {temp_collection_name}: {e}")

    def __enter__(self):
        if not self.client:
            self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.client:
            self.client.close()

    def get_collection_fields(self, collection_name: str):
        """
        Retrieves the full list of fields (keys) present in the specified collection.
        :param collection_name: The name of the MongoDB collection.
        :return: A set of unique field names in the collection.
        """
        collection = self.db[collection_name]
        try:
            # 从集合中取出一条样本记录，用于获取字段列表
            sample_record = collection.find_one()
            if sample_record:
                fields = set(sample_record.keys())
                logger.info(f"Retrieved fields for collection {collection_name}: {fields}")
                return fields
            else:
                logger.warning(f"No records found in collection {collection_name}")
                return set()
        except PyMongoError as e:
            logger.error(f"Error retrieving fields from {collection_name}: {e}")
            raise

    def get_latest_unique_data(self, collection_name, unique_fields, time_field=None, start_time=None):
        collection = self.db[collection_name]
        if time_field is None:
            time_field = '_id'  # 默认使用 ObjectId
        try:
            pipeline = []

            # 如果提供了 start_time，添加过滤条件
            if start_time is not None:
                if not isinstance(start_time, datetime):
                    raise ValueError("start_time must be a datetime instance")

                # 如果 time_field 是 '_id'，将 datetime 转换为 ObjectId
                if time_field == '_id':
                    start_object_id = ObjectId.from_datetime(start_time)
                    pipeline.append({
                        "$match": {time_field: {"$gte": start_object_id}}
                    })
                else:
                    # 其他时间字段，直接使用 datetime 比较
                    pipeline.append({
                        "$match": {time_field: {"$gte": start_time}}
                    })

            pipeline.extend([
                {"$sort": {time_field: -1}},  # 按时间字段降序排序
                {"$group": {
                    "_id": {field: f"${field}" for field in unique_fields},
                    "latest_record": {"$first": "$$ROOT"}
                }},
                {"$replaceRoot": {"newRoot": "$latest_record"}}
            ])
            unique_data = list(collection.aggregate(pipeline))
            df = pd.DataFrame(unique_data)
            logger.info(f"Retrieved {len(unique_data)} unique documents from {collection_name}")
            return df
        except PyMongoError as e:
            logger.error(f"Error retrieving unique data from {collection_name}: {e}")
            raise

    def insert_data(self, collection_name, data, suppress_log=False):
        collection = self.db[collection_name]
        try:
            collection.insert_one(data)
            if not suppress_log:
                logger.info(f"Data inserted into {collection_name} collection")
        except PyMongoError as e:
            logger.error(f"Error inserting data into {collection_name}: {e}")
            self._handle_failed_insert(data, collection_name)

    def insert_many_data(self, collection_name, data_list):
        collection = self.db[collection_name]
        try:
            collection.insert_many(data_list)
            logger.info(f"All data inserted into {collection_name} collection")
        except PyMongoError as e:
            logger.error(f"Error inserting data into {collection_name}: {e}")
            for data in data_list:
                self._handle_failed_insert(data, collection_name)

    def merge_fields_to_dataframe(self, collection_name, fields, expand_array=False, time_field=None, start_time=None):
        collection = self.db[collection_name]
        try:
            query = {}
            if start_time is not None and time_field is not None:
                if not isinstance(start_time, datetime):
                    raise ValueError("start_time must be a datetime instance")

                if time_field == '_id':
                    # 将 datetime 转换为对应的 ObjectId
                    start_object_id = ObjectId.from_datetime(start_time)
                    query[time_field] = {'$gte': start_object_id}
                else:
                    query[time_field] = {'$gte': start_time}

            # 构建投影字段
            projection = {field: 1 for field in fields}
            # 如果 time_field 不在 fields 中，确保在投影中包含它
            if time_field and time_field not in fields:
                projection[time_field] = 1

            documents = list(collection.find(query, projection))

            if not documents:
                logger.info(f"No documents found in {collection_name} after {start_time}")
                return pd.DataFrame()  # 返回空的 DataFrame

            if not expand_array:
                # 水平展开：将数组元素用逗号连接
                for doc in documents:
                    for field in fields:
                        if isinstance(doc.get(field), list):
                            doc[field] = ", ".join(map(str, doc[field]))
            else:
                # 垂直展开：将数组元素展开为多个记录
                expanded_docs = []
                for doc in documents:
                    array_lengths = [len(doc.get(field)) if isinstance(doc.get(field), list) else 1 for field in fields]
                    max_len = max(array_lengths)
                    for i in range(max_len):
                        expanded_doc = {}
                        for field in fields:
                            if isinstance(doc.get(field), list):
                                expanded_doc[field] = doc[field][i] if i < len(doc[field]) else None
                            else:
                                expanded_doc[field] = doc[field]
                        expanded_docs.append(expanded_doc)
                documents = expanded_docs

            df = pd.DataFrame(documents)
            logger.info(f"Converted documents from {collection_name} to DataFrame with shape {df.shape}")
            return df
        except PyMongoError as e:
            logger.error(f"Error merging fields from {collection_name} to DataFrame: {e}")
            raise


if __name__ == '__main__':
    pass
