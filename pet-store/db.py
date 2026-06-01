from pymongo import MongoClient


class PetStoreDB:
    """
    Encapsulates all MongoDB access for one store.
    Generic: instantiate with any collection name — adding a third store
    means one new instance, zero code changes.
    """

    def __init__(self, mongo_uri, db_name, collection_name, store_id):
        client = MongoClient(mongo_uri)
        db = client[db_name]
        self._col = db[collection_name]
        self._counters = db[f"counters_{store_id}"]

    def find_all(self):
        return list(self._col.find({}))

    def find_by_id(self, id):
        return self._col.find_one({"id": id})

    def save(self, doc):
        self._col.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)

    def delete(self, id):
        self._col.delete_one({"id": id})

    def next_id(self):
        result = self._counters.find_one_and_update(
            {"_id": "pet_type_id"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True,
        )
        return str(result["seq"])
