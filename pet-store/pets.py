# pets.py - Pet Store Service with MongoDB Persistence
import os
import uuid
import requests
import re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import logging

from db import PetStoreDB

load_dotenv()

app = Flask(__name__)

# Configuration from environment variables
PORT = int(os.getenv("PORT", 8000))
STORE_ID = os.getenv("STORE_ID", "1")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
DB_NAME = os.getenv("DB_NAME", "petstore")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", f"pet_store_{STORE_ID}")

NINJA_API_URL = 'https://api.api-ninjas.com/v1/animals?name='
NINJA_API_KEY = os.getenv("NINJA_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


db = PetStoreDB(MONGO_URI, DB_NAME, COLLECTION_NAME)
db.create_indexes()


# --- Helper Functions ---

def parse_lifespan(text):
    numbers = re.findall(r'\d+', text)
    if numbers:
        return min(int(n) for n in numbers)
    return None

def parse_attributes(ninja_characteristics):
    text_to_parse = ""
    if 'temperament' in ninja_characteristics:
        text_to_parse = ninja_characteristics['temperament']
    elif 'group_behavior' in ninja_characteristics:
        text_to_parse = ninja_characteristics['group_behavior']
    if text_to_parse:
        return re.sub(r'[^\w\s]', '', text_to_parse).split()
    return []

def validate_date_format(date_string):
    if date_string == "NA":
        return True
    try:
        datetime.strptime(date_string, '%d-%m-%Y')
        return True
    except ValueError:
        return False

def generate_unique_filename(name, pet_type_name, ext):
    safe_name = name.lower().strip().replace(" ", "_")
    safe_type = pet_type_name.lower().strip().replace(" ", "_")
    return f"{safe_name}-{safe_type}-{STORE_ID}.{ext}"

def safe_date_compare(date_str, compare_date, operator):
    if date_str == "NA":
        return False
    try:
        date_obj = datetime.strptime(date_str, '%d-%m-%Y')
        if operator == ">":
            return date_obj > compare_date
        elif operator == "<":
            return date_obj < compare_date
        return False
    except Exception:
        return False

def case_insensitive_compare(str1, str2):
    return (str1 or "").strip().lower() == (str2 or "").strip().lower()

def find_exact_match(results, name):
    for item in results:
        if item.get('name', '').lower() == name.lower():
            return item
    return None

def resolve_pet_name_key(pet_type_dict, candidate_name):
    for existing_name in pet_type_dict.get('pets_details', {}).keys():
        if case_insensitive_compare(existing_name, candidate_name.strip()):
            return existing_name
    return None

def ensure_meta_store(pet_type_dict):
    if 'pets_meta' not in pet_type_dict:
        pet_type_dict['pets_meta'] = {}
    return pet_type_dict['pets_meta']

def serialize_pet_type_for_api(pet_type_dict):
    return {
        "id": pet_type_dict.get("id"),
        "type": pet_type_dict.get("type"),
        "family": pet_type_dict.get("family"),
        "genus": pet_type_dict.get("genus"),
        "attributes": pet_type_dict.get("attributes", []),
        "lifespan": pet_type_dict.get("lifespan"),
        "pets": pet_type_dict.get("pets", []),
    }



# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Malformed data"}), 400

@app.errorhandler(415)
def unsupported_media_type(error):
    return jsonify({"error": "Expected application/json media type"}), 415

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def server_error(error):
    if hasattr(error, 'code') and error.code == 500 and hasattr(error, 'description'):
        return jsonify({"server error": error.description}), 500
    return jsonify({"server error": "An internal error occurred"}), 500


# --- Health & Kill Endpoints ---
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "store": STORE_ID}), 200

@app.route('/kill', methods=['GET'])
def kill_container():
    os._exit(1)


# --- Endpoints ---
@app.route('/pet-types', methods=['POST'])
def create_pet_type():
    if not request.is_json:
        return unsupported_media_type(None)

    data = request.get_json()
    if 'type' not in data:
        return bad_request(None)

    pet_type_name = data['type']

    all_pet_types = db.find_all()
    for pt in all_pet_types:
        if case_insensitive_compare(pt.get('type'), pet_type_name):
            return bad_request(None)

    headers = {'X-Api-Key': NINJA_API_KEY}
    try:
        response = requests.get(NINJA_API_URL + pet_type_name, headers=headers)
    except Exception as e:
        logger.error(f"Failed to call Ninja API: {e}")
        return server_error(type('MyError', (object,), {'code': 500, 'description': 'API connection failed'})())

    if not response.ok:
        error_msg = f"API response code {response.status_code}"
        return server_error(type('MyError', (object,), {'code': 500, 'description': error_msg})())

    api_results = response.json()
    if not api_results:
        return bad_request(None)

    exact_match = find_exact_match(api_results, pet_type_name)
    if not exact_match:
        return bad_request(None)

    taxonomy = exact_match.get('taxonomy', {})
    characteristics = exact_match.get('characteristics', {})

    new_id = str(uuid.uuid4())

    new_pet_type = {
        "id": new_id,
        "type": exact_match.get('name'),
        "family": taxonomy.get('family'),
        "genus": taxonomy.get('genus'),
        "attributes": parse_attributes(characteristics),
        "lifespan": parse_lifespan(characteristics.get('lifespan', '')),
        "pets": [],
        "pets_details": {},
        "pets_meta": {}
    }

    db.save(new_pet_type)
    return jsonify(serialize_pet_type_for_api(new_pet_type)), 201


@app.route('/pet-types', methods=['GET'])
def get_pet_types():
    query_params = request.args
    allowed_params = {'id', 'type', 'family', 'genus', 'lifespan', 'hasAttribute'}

    for key in query_params.keys():
        if key not in allowed_params:
            return jsonify([]), 200

    # Push filters to MongoDB — uses the index on 'type' instead of scanning everything
    mongo_query = {}
    if 'id' in query_params:
        mongo_query['id'] = query_params['id']
    if 'type' in query_params:
        mongo_query['type'] = {'$regex': f"^{query_params['type']}$", '$options': 'i'}
    if 'family' in query_params:
        mongo_query['family'] = {'$regex': f"^{query_params['family']}$", '$options': 'i'}
    if 'genus' in query_params:
        mongo_query['genus'] = {'$regex': f"^{query_params['genus']}$", '$options': 'i'}
    if 'lifespan' in query_params:
        try:
            mongo_query['lifespan'] = int(query_params['lifespan'])
        except ValueError:
            return bad_request(None)

    filtered_results = db.find_by_filter(mongo_query) if mongo_query else db.find_all()

    # hasAttribute requires array element matching — kept in Python for simplicity
    if 'hasAttribute' in query_params:
        attr = query_params['hasAttribute'].strip().lower()
        filtered_results = [
            pt for pt in filtered_results
            if any(a.lower() == attr for a in pt.get('attributes', []))
        ]

    serialized = [serialize_pet_type_for_api(pt) for pt in filtered_results]
    return jsonify(serialized), 200


@app.route('/pet-types/<string:id>', methods=['GET'])
def get_pet_type_by_id(id):
    pet_type = db.find_by_id(id)
    if not pet_type:
        return not_found(None)
    return jsonify(serialize_pet_type_for_api(pet_type)), 200


@app.route('/pet-types/<string:id>', methods=['DELETE'])
def delete_pet_type(id):
    pet_type = db.find_by_id(id)
    if not pet_type:
        return not_found(None)
    if pet_type.get('pets'):
        return bad_request(None)
    db.delete(id)
    return "", 204


@app.route('/pet-types/<string:id>/pets', methods=['POST'])
def add_pet_to_type(id):
    pet_type = db.find_by_id(id)
    if not pet_type:
        return not_found(None)

    if not request.is_json:
        return unsupported_media_type(None)

    data = request.get_json()
    if 'name' not in data:
        return bad_request(None)

    birthdate_val = data.get('birthdate', "NA")
    if not validate_date_format(birthdate_val):
        return bad_request(None)

    if any(case_insensitive_compare(existing, data['name']) for existing in pet_type.get('pets', [])):
        return bad_request(None)

    picture_filename = "NA"
    meta_store = ensure_meta_store(pet_type)

    if 'picture-url' in data and data['picture-url']:
        picture_url = data['picture-url']
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            pic_response = requests.get(picture_url, headers=headers, timeout=10)
            content_type = pic_response.headers.get('Content-Type', '')
            if pic_response.ok and content_type in ['image/jpeg', 'image/png']:
                if content_type == 'image/jpeg':
                    ext = 'jpg'
                else:
                    ext = 'png'
                filename = generate_unique_filename(data['name'], pet_type['type'], ext)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                with open(filepath, 'wb') as f:
                    f.write(pic_response.content)
                picture_filename = filename
                meta_store[data['name']] = {"picture_url": picture_url}
            else:
                return bad_request(None)
        except Exception:
            return bad_request(None)
    else:
        meta_store[data['name']] = {"picture_url": None}

    new_pet = {
        "name": data['name'],
        "birthdate": birthdate_val,
        "picture": picture_filename
    }

    pet_type['pets'].append(data['name'])
    if 'pets_details' not in pet_type:
        pet_type['pets_details'] = {}
    pet_type['pets_details'][data['name']] = new_pet
    pet_type['pets_meta'] = meta_store

    db.save(pet_type)
    return jsonify(new_pet), 201


@app.route('/pet-types/<string:id>/pets', methods=['GET'])
def get_pets_of_type(id):
    pet_type = db.find_by_id(id)
    if not pet_type:
        return not_found(None)

    all_pets = list(pet_type.get('pets_details', {}).values())
    query_params = request.args
    filtered_pets = all_pets[:]

    try:
        if 'birthdateGT' in query_params:
            gt_date = datetime.strptime(query_params['birthdateGT'], '%d-%m-%Y')
            filtered_pets = [p for p in filtered_pets if safe_date_compare(p['birthdate'], gt_date, ">")]
        if 'birthdateLT' in query_params:
            lt_date = datetime.strptime(query_params['birthdateLT'], '%d-%m-%Y')
            filtered_pets = [p for p in filtered_pets if safe_date_compare(p['birthdate'], lt_date, "<")]
    except ValueError:
        return bad_request(None)

    return jsonify(filtered_pets), 200


@app.route('/pet-types/<string:id>/pets/<string:name>', methods=['GET'])
def get_specific_pet(id, name):
    pet_type = db.find_by_id(id)
    if not pet_type:
        return not_found(None)
    resolved_name = resolve_pet_name_key(pet_type, name)
    if resolved_name is None:
        return not_found(None)
    pet = pet_type['pets_details'][resolved_name]
    return jsonify(pet), 200


@app.route('/pet-types/<string:id>/pets/<string:name>', methods=['DELETE'])
def delete_specific_pet(id, name):
    pet_type = db.find_by_id(id)
    if not pet_type:
        return not_found(None)
    resolved_name = resolve_pet_name_key(pet_type, name)
    if resolved_name is None:
        return not_found(None)

    # Read picture path before the atomic delete so we can clean up the file.
    pet = pet_type['pets_details'].get(resolved_name, {})
    picture = pet.get('picture', 'NA')

    # Atomic: filter includes "pets": resolved_name so only one concurrent
    # request wins. The loser gets modified_count=0 → 404 → pet_order rolls back.
    if not db.atomic_remove_pet(id, resolved_name):
        return not_found(None)

    if picture != "NA":
        filepath = os.path.join(UPLOAD_FOLDER, picture)
        if os.path.exists(filepath):
            os.remove(filepath)

    return "", 204


@app.route('/pet-types/<string:id>/pets/<string:name>', methods=['PUT'])
def update_specific_pet(id, name):
    pet_type = db.find_by_id(id)
    if not pet_type:
        return not_found(None)
    resolved_name = resolve_pet_name_key(pet_type, name)
    if resolved_name is None:
        return not_found(None)

    if not request.is_json:
        return unsupported_media_type(None)

    data = request.get_json()
    if 'name' not in data:
        return bad_request(None)

    pet = pet_type['pets_details'][resolved_name]

    if 'birthdate' in data:
        if not validate_date_format(data['birthdate']):
            return bad_request(None)
        pet['birthdate'] = data['birthdate']

    meta_store = ensure_meta_store(pet_type)

    if 'picture-url' in data:
        picture_url = data['picture-url']
        if picture_url:
            previous_url = (meta_store.get(resolved_name) or {}).get('picture_url')
            if previous_url and previous_url == picture_url:
                pass
            else:
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    pic_response = requests.get(picture_url, headers=headers, timeout=10)
                    content_type = pic_response.headers.get('Content-Type', '')
                    if pic_response.ok and content_type in ['image/jpeg', 'image/png']:
                        if content_type == 'image/jpeg':
                            ext = 'jpg'
                        else:
                            ext = 'png'
                        if pet['picture'] != "NA":
                            old_filepath = os.path.join(UPLOAD_FOLDER, pet['picture'])
                            if os.path.exists(old_filepath):
                                os.remove(old_filepath)
                        filename = generate_unique_filename(pet['name'], pet_type['type'], ext)
                        filepath = os.path.join(UPLOAD_FOLDER, filename)
                        with open(filepath, 'wb') as f:
                            f.write(pic_response.content)
                        pet['picture'] = filename
                        meta_store[resolved_name] = {"picture_url": picture_url}
                    else:
                        return bad_request(None)
                except Exception:
                    return bad_request(None)
        else:
            if pet['picture'] != "NA":
                old_filepath = os.path.join(UPLOAD_FOLDER, pet['picture'])
                if os.path.exists(old_filepath):
                    os.remove(old_filepath)
            pet['picture'] = "NA"
            meta_store[resolved_name] = {"picture_url": None}

    pet_type['pets_details'][resolved_name] = pet
    pet_type['pets_meta'] = meta_store
    db.save(pet_type)
    return jsonify(pet), 200


@app.route('/pictures/<string:filename>', methods=['GET'])
def get_picture(filename):
    try:
        return send_from_directory(UPLOAD_FOLDER, filename)
    except FileNotFoundError:
        return not_found(None)


if __name__ == '__main__':
    logger.info(f"Starting Pet Store {STORE_ID} on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
