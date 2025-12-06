from flask import Flask, jsonify, request
from pymongo import MongoClient

app = Flask(__name__)

# 连接到 MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["insurance_client"]


# 创建一个API端点来获取指定集合的数据
@app.route("/data", methods=["GET"])
def get_data():
    collection_name = request.args.get("collection")
    if not collection_name:
        return jsonify({"error": "No collection specified"}), 400

    collection = db[collection_name]
    data = list(collection.find({}, {"_id": 0}))  # 忽略 MongoDB 默认的 _id 字段
    return jsonify({collection_name: data})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
