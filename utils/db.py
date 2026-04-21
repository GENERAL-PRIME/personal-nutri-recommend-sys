from os import environ
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = environ.get("MONGO_URI")
MONGO_DB = environ.get("MONGO_DB_NAME")

client = None
db = None
users_col = None
plans_col = None

if MONGO_URI:
    client = MongoClient(MONGO_URI)
    if MONGO_DB:
        db = client[MONGO_DB]
    else:
        # get_default_database() works when DB is specified in the uri
        try:
            db = client.get_default_database()
        except Exception:
            db = None

# compare with None explicitly (Database objects do not implement truth testing)
if db is not None:
    users_col = db['users']
    plans_col = db['plans']
