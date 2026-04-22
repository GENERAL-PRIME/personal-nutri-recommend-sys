"""
delete_all_users.py - Clean up script to delete all user data from MongoDB
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PARENT, '.env'))

from utils.db import users_col, plans_col

def delete_all_users():
    """Delete all users and diet plans from MongoDB"""
    try:
        if users_col is None or plans_col is None:
            print("❌ MongoDB connection failed. Check MONGO_URI and MONGO_DB_NAME in .env")
            return
        
        # Get counts before deletion
        user_count = users_col.count_documents({})
        plan_count = plans_col.count_documents({})
        
        print(f"📊 Current Data:")
        print(f"   Users: {user_count}")
        print(f"   Diet Plans: {plan_count}")
        print()
        
        if user_count == 0 and plan_count == 0:
            print("✅ Database is already clean. No data to delete.")
            return
        
        # Confirm deletion
        confirm = input("⚠️  This will DELETE ALL user data. Type 'yes' to confirm: ").strip().lower()
        if confirm != 'yes':
            print("❌ Deletion cancelled.")
            return
        
        # Delete all users
        users_result = users_col.delete_many({})
        print(f"🗑️  Deleted {users_result.deleted_count} user(s)")
        
        # Delete all plans
        plans_result = plans_col.delete_many({})
        print(f"🗑️  Deleted {plans_result.deleted_count} diet plan(s)")
        
        print()
        print("✅ All user data has been deleted successfully!")
        
    except Exception as e:
        print(f"❌ Error deleting users: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    delete_all_users()
