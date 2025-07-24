import sqlite3
import uuid
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class User:
    id: str
    email: str
    name: str
    created_at: str
    last_login: str

class UserStorage:
    def __init__(self, db_path: str = "events.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the database and create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_login TEXT NOT NULL
                )
            """)
            conn.commit()
    
    def create_or_update_user(self, email: str, name: str, ) -> User:
        """Create a new user or update existing user's login time"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Check if user exists
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            existing_user = cursor.fetchone()
            current_time = datetime.now().isoformat()
            if existing_user:
                # Update last login time and other info
                user_id = existing_user[0]
                cursor.execute("""
                    UPDATE users 
                    SET name = ?, last_login = ?
                    WHERE email = ?
                """, (name, current_time, email))
                
                return User(
                    id=user_id,
                    email=email,
                    name=name,
                    created_at=existing_user[3],
                    last_login=current_time
                )
            else:
                # Create new user
                user_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO users (id, email, name, created_at, last_login)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, email, name, current_time, current_time))
                
                return User(
                    id=user_id,
                    email=email,
                    name=name,
                    created_at=current_time,
                    last_login=current_time
                )
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            
            if row:
                return User(
                    id=row[0],
                    email=row[1],
                    name=row[2],
                    created_at=row[3],
                    last_login=row[4]
                )
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                return User(
                    id=row[0],
                    email=row[1],
                    name=row[2],
                    created_at=row[3],
                    last_login=row[4]
                )
            return None