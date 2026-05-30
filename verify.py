import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'opmd.db')
conn = sqlite3.connect(db_path)
conn.execute("UPDATE doctors SET is_verified=1, verification_status='approved'")
conn.commit()
print(f"Successfully verified {conn.total_changes} doctor(s) in the database.")
conn.close()
