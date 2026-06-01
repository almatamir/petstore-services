from pymongo import MongoClient


class PetStoreDB:
    """
    Encapsulates all MongoDB access for one store.
    Generic: instantiate with any collection name — adding a third store
    means one new instance, zero code changes.
    """

    def __init__(self, mongo_uri, db_name, collection_name):
        client = MongoClient(mongo_uri)
        db = client[db_name]
        self._col = db[collection_name]

    def create_indexes(self):
        self._col.create_index("type")

    def find_all(self):
        return list(self._col.find({}))

    def find_by_filter(self, query):
        return list(self._col.find(query))

    def find_by_id(self, id):
        return self._col.find_one({"id": id})

    def save(self, doc):
        self._col.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)

    def delete(self, id):
        self._col.delete_one({"id": id})
