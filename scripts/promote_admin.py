"""
Promote a user to admin by email.

HOW TO RUN:
    docker cp scripts/promote_admin.py empowered-academy-backend-api-1:/app/promote_admin.py
    docker exec -it empowered-academy-backend-api-1 python3 /app/promote_admin.py your@email.com
"""

import sys
sys.path.insert(0, "/app")

from app.core.database import SessionLocal
from app.models.user import User

if len(sys.argv) < 2:
    print("Usage: python3 promote_admin.py <email>")
    sys.exit(1)

email = sys.argv[1].strip()
db = SessionLocal()

user = db.query(User).filter(User.email == email).first()
if not user:
    print(f"ERROR: No user found with email '{email}'")
    sys.exit(1)

user.role = "admin"
db.commit()
print(f"Done. '{email}' is now admin.")
db.close()
