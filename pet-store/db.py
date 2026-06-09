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

    def atomic_remove_pet(self, pet_type_id, pet_name):
        # Single atomic operation: only matches if pet_name is still in the pets array.
        # If two concurrent requests race for the same pet, exactly one will get
        # modified_count=1; the other gets 0 (pet already gone) and should return 404.
        result = self._col.update_one(
            {"id": pet_type_id, "pets": pet_name},
            {
                "$pull": {"pets": pet_name},
                "$unset": {
                    f"pets_details.{pet_name}": "",
                    f"pets_meta.{pet_name}": ""
                }
            }
        )
        return result.modified_count > 0
