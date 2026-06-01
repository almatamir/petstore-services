import pytest
import requests

PET_STORE_1_URL = "http://localhost:5001"
PET_STORE_2_URL = "http://localhost:5002"
PET_ORDER_URL   = "http://localhost:5003"
NGINX_URL       = "http://localhost:80"

PET_TYPE1 = {"type": "Golden Retriever"}
PET_TYPE2 = {"type": "Australian Shepherd"}
PET_TYPE3 = {"type": "Abyssinian"}
PET_TYPE4 = {"type": "bulldog"}

PET1_TYPE1 = {"name": "Lander", "birthdate": "14-05-2020"}
PET2_TYPE1 = {"name": "Lanky"}
PET3_TYPE1 = {"name": "Shelly", "birthdate": "07-07-2019"}
PET4_TYPE2 = {"name": "Felicity", "birthdate": "27-11-2011"}
PET5_TYPE3 = {"name": "Muscles"}
PET6_TYPE3 = {"name": "Junior"}
PET7_TYPE4 = {"name": "Lazy",  "birthdate": "07-08-2018"}
PET8_TYPE4 = {"name": "Lemon", "birthdate": "27-03-2020"}

pet_type_ids = {}


def test_00_health_checks():
    """All services and nginx must respond before any other test runs."""
    assert requests.get(f"{PET_STORE_1_URL}/health").status_code == 200
    assert requests.get(f"{PET_STORE_2_URL}/health").status_code == 200
    assert requests.get(f"{PET_ORDER_URL}/health").status_code == 200
    assert requests.get(f"{NGINX_URL}/store1/health").status_code == 200


def test_01_post_pet_types_to_store1():
    """POST 3 pet-types to pet-store #1 — assert 201 and unique IDs."""
    global pet_type_ids

    r1 = requests.post(f"{PET_STORE_1_URL}/pet-types", json=PET_TYPE1)
    assert r1.status_code == 201, f"Expected 201, got {r1.status_code}"
    assert "id" in r1.json()
    pet_type_ids['id_1'] = r1.json()["id"]

    r2 = requests.post(f"{PET_STORE_1_URL}/pet-types", json=PET_TYPE2)
    assert r2.status_code == 201, f"Expected 201, got {r2.status_code}"
    assert "id" in r2.json()
    pet_type_ids['id_2'] = r2.json()["id"]

    r3 = requests.post(f"{PET_STORE_1_URL}/pet-types", json=PET_TYPE3)
    assert r3.status_code == 201, f"Expected 201, got {r3.status_code}"
    assert "id" in r3.json()
    pet_type_ids['id_3'] = r3.json()["id"]

    assert len({pet_type_ids['id_1'], pet_type_ids['id_2'], pet_type_ids['id_3']}) == 3, \
        "IDs must be unique"


def test_02_post_pet_types_to_store2():
    """POST 3 pet-types to pet-store #2 — assert 201 and unique IDs."""
    global pet_type_ids

    r4 = requests.post(f"{PET_STORE_2_URL}/pet-types", json=PET_TYPE1)
    assert r4.status_code == 201, f"Expected 201, got {r4.status_code}"
    pet_type_ids['id_4'] = r4.json()["id"]

    r5 = requests.post(f"{PET_STORE_2_URL}/pet-types", json=PET_TYPE2)
    assert r5.status_code == 201, f"Expected 201, got {r5.status_code}"
    pet_type_ids['id_5'] = r5.json()["id"]

    r6 = requests.post(f"{PET_STORE_2_URL}/pet-types", json=PET_TYPE4)
    assert r6.status_code == 201, f"Expected 201, got {r6.status_code}"
    pet_type_ids['id_6'] = r6.json()["id"]

    assert len({pet_type_ids['id_4'], pet_type_ids['id_5'], pet_type_ids['id_6']}) == 3, \
        "IDs must be unique"


def test_03_post_pets_to_store1_type1():
    """POST 2 pets to store1/type1 — assert 201."""
    id_1 = pet_type_ids['id_1']
    assert requests.post(f"{PET_STORE_1_URL}/pet-types/{id_1}/pets", json=PET1_TYPE1).status_code == 201
    assert requests.post(f"{PET_STORE_1_URL}/pet-types/{id_1}/pets", json=PET2_TYPE1).status_code == 201


def test_04_post_pets_to_store1_type3():
    """POST 2 pets to store1/type3 — assert 201."""
    id_3 = pet_type_ids['id_3']
    assert requests.post(f"{PET_STORE_1_URL}/pet-types/{id_3}/pets", json=PET5_TYPE3).status_code == 201
    assert requests.post(f"{PET_STORE_1_URL}/pet-types/{id_3}/pets", json=PET6_TYPE3).status_code == 201


def test_05_post_pet_to_store2_type1():
    """POST 1 pet to store2/type1 — assert 201."""
    id_4 = pet_type_ids['id_4']
    assert requests.post(f"{PET_STORE_2_URL}/pet-types/{id_4}/pets", json=PET3_TYPE1).status_code == 201


def test_06_post_pet_to_store2_type2():
    """POST 1 pet to store2/type2 — assert 201."""
    id_5 = pet_type_ids['id_5']
    assert requests.post(f"{PET_STORE_2_URL}/pet-types/{id_5}/pets", json=PET4_TYPE2).status_code == 201


def test_07_post_pets_to_store2_type4():
    """POST 2 pets to store2/type4 — assert 201."""
    id_6 = pet_type_ids['id_6']
    assert requests.post(f"{PET_STORE_2_URL}/pet-types/{id_6}/pets", json=PET7_TYPE4).status_code == 201
    assert requests.post(f"{PET_STORE_2_URL}/pet-types/{id_6}/pets", json=PET8_TYPE4).status_code == 201


def test_08_purchase_removes_pet_from_store():
    """POST /purchases — pet must be removed from store after purchase."""
    id_1 = pet_type_ids['id_1']

    before = requests.get(f"{PET_STORE_1_URL}/pet-types/{id_1}/pets").json()
    before_count = len(before)

    r = requests.post(f"{PET_ORDER_URL}/purchases",
                      json={"purchaser": "TestBuyer", "pet-type": "Golden Retriever", "store": 1})
    assert r.status_code == 201, f"Expected 201, got {r.status_code}"
    assert "purchase-id" in r.json()

    after = requests.get(f"{PET_STORE_1_URL}/pet-types/{id_1}/pets").json()
    assert len(after) == before_count - 1, "Pet count must decrease by 1 after purchase"
