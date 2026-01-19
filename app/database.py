# database.py
import sqlite3
import os
import json
from datetime import datetime
from typing import List
from PIL import Image
import io

DB_PATH = "invoices.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL
        )
    ''')

    # Create invoices table
    c.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            upload_time TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            fields TEXT NOT NULL,
            file_data BLOB,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Ensure file_data column exists if table already existed

    try:
        c.execute("ALTER TABLE invoices ADD COLUMN file_data BLOB")
    except sqlite3.OperationalError:
        pass # Column already exists

    conn.commit()
    conn.close()

def get_or_create_user(username: str) -> int:
    """Get user ID or create new user"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = c.fetchone()

    if row:
        user_id = row[0]
    else:
        c.execute("INSERT INTO users (username) VALUES (?)", (username,))
        user_id = c.lastrowid

    conn.commit()
    conn.close()
    return user_id


def save_invoice(user_id: int, filename: str, file_content: bytes, result: dict):
    # Prepare fields to store (flatten validation into fields)
    stored_fields = result["fields"].copy()
    stored_fields.update({
        "page_count": result.get("page_count", 1),
        "raw_text": result.get("raw_text", "")[:500],  # store snippet only
        "validation": result.get("validation", {}),
        "duplicates": [dup["id"] for dup in result.get("duplicates", [])]
    })

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    raw_text_to_save = result.get("raw_text", "")[:1000]  # truncate if needed
    c.execute('''
        INSERT INTO invoices (user_id, filename, upload_time, raw_text, fields, file_data)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        filename,
        datetime.now().isoformat(),
        raw_text_to_save,  # ← must be string, not None
        json.dumps(stored_fields),
        file_content
    ))
    conn.commit()
    conn.close()


def get_user_invoices(user_id: int) -> list:
    """Get list of invoices for user (for table)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    c = conn.cursor()

    c.execute('''
        SELECT id, filename, upload_time, fields
        FROM invoices
        WHERE user_id = ?
        ORDER BY upload_time DESC
    ''', (user_id,))

    rows = c.fetchall()
    invoices = []
    for row in rows:
        fields = json.loads(row['fields'])
        invoices.append({
            'id': row['id'],
            'filename': row['filename'],
            'upload_time': row['upload_time'],
            'vendor': fields.get('vendor', '—'),
            'total_amount': fields.get('total_amount', '—'),
            'date': fields.get('date', '—')
        })

    conn.close()
    return invoices


def get_invoice_by_id(invoice_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
    row = c.fetchone()
    conn.close()  # ← always close!

    if not row:
        return None

    # ✅ Use 'file_data', not 'image'
    file_bytes = row['file_data']  # ← correct column name

    return {
        'id': row['id'],
        'filename': row['filename'],
        'upload_time': row['upload_time'],
        'raw_text': row['raw_text'],
        'fields': json.loads(row['fields']),
        'file_data': file_bytes  # raw bytes (PDF or image)
    }

def delete_invoices_by_ids(user_id: int, invoice_ids: List[int]):
    """Delete selected invoices for user"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ','.join('?' * len(invoice_ids))
    c.execute(f'''
        DELETE FROM invoices
        WHERE id IN ({placeholders}) AND user_id = ?
    ''', (*invoice_ids, user_id))
    conn.commit()
    conn.close()



