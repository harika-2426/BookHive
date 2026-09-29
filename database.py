import sqlite3
from collections import deque

DATABASE = "library.db"

# Transaction Stack
transaction_stack = []

# Book Waitlist Queues
waitlist_queues = {}


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


# =========================
# INITIALIZE DATABASE
# =========================

def init_db():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            available INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS borrowed_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT,
            member_id TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waitlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT,
            member_id TEXT,
            position INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT,
            book_id TEXT,
            member_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


# =========================
# BOOKS
# =========================

def add_book(book_id, title, author):

    connection = get_connection()

    try:

        connection.execute("""
            INSERT INTO books
            (book_id, title, author, available)
            VALUES (?, ?, ?, 1)
        """, (
            book_id,
            title,
            author
        ))

        connection.commit()

        return True, "Book added successfully."

    except sqlite3.IntegrityError:

        return False, "Book ID already exists."

    finally:

        connection.close()


def get_books(search=""):

    connection = get_connection()

    if search:

        rows = connection.execute("""
            SELECT *
            FROM books
            WHERE book_id LIKE ?
               OR title LIKE ?
               OR author LIKE ?
            ORDER BY id DESC
        """, (
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%"
        )).fetchall()

    else:

        rows = connection.execute("""
            SELECT *
            FROM books
            ORDER BY id DESC
        """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


# =========================
# MEMBERS
# =========================

def add_member(member_id, name):

    connection = get_connection()

    try:

        connection.execute("""
            INSERT INTO members
            (member_id, name)
            VALUES (?, ?)
        """, (
            member_id,
            name
        ))

        connection.commit()

        return True, "Member registered successfully."

    except sqlite3.IntegrityError:

        return False, "Member ID already exists."

    finally:

        connection.close()


def get_members():

    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM members
        ORDER BY id DESC
    """).fetchall()

    result = []

    for row in rows:

        member = dict(row)

        borrowed = connection.execute("""
            SELECT book_id
            FROM borrowed_books
            WHERE member_id = ?
        """, (
            member["member_id"],
        )).fetchall()

        member["borrowed_books"] = [
            item["book_id"]
            for item in borrowed
        ]

        result.append(member)

    connection.close()

    return result


# =========================
# ISSUE BOOK
# =========================

def issue_book(book_id, member_id):

    connection = get_connection()

    book = connection.execute("""
        SELECT *
        FROM books
        WHERE book_id = ?
    """, (
        book_id,
    )).fetchone()

    member = connection.execute("""
        SELECT *
        FROM members
        WHERE member_id = ?
    """, (
        member_id,
    )).fetchone()

    if not book:

        connection.close()

        return False, "Book not found."

    if not member:

        connection.close()

        return False, "Member not found."

    # Book unavailable
    if book["available"] == 0:

        existing = connection.execute("""
            SELECT *
            FROM waitlists
            WHERE book_id = ?
              AND member_id = ?
        """, (
            book_id,
            member_id
        )).fetchone()

        if existing:

            connection.close()

            return False, "Member is already in the waitlist."

        count = connection.execute("""
            SELECT COUNT(*) AS count
            FROM waitlists
            WHERE book_id = ?
        """, (
            book_id,
        )).fetchone()["count"]

        position = count + 1

        connection.execute("""
            INSERT INTO waitlists
            (book_id, member_id, position)
            VALUES (?, ?, ?)
        """, (
            book_id,
            member_id,
            position
        ))

        connection.commit()
        connection.close()

        return True, "Book unavailable. Member added to waitlist."

    # Check if member already borrowed
    existing = connection.execute("""
        SELECT *
        FROM borrowed_books
        WHERE book_id = ?
          AND member_id = ?
    """, (
        book_id,
        member_id
    )).fetchone()

    if existing:

        connection.close()

        return False, "Member already has this book."

    # Issue book
    connection.execute("""
        UPDATE books
        SET available = 0
        WHERE book_id = ?
    """, (
        book_id,
    ))

    connection.execute("""
        INSERT INTO borrowed_books
        (book_id, member_id)
        VALUES (?, ?)
    """, (
        book_id,
        member_id
    ))

    connection.execute("""
        INSERT INTO transactions
        (transaction_type, book_id, member_id)
        VALUES (?, ?, ?)
    """, (
        "ISSUED",
        book_id,
        member_id
    ))

    connection.commit()

    connection.close()

    transaction_stack.append({
        "type": "ISSUED",
        "book_id": book_id,
        "member_id": member_id
    })

    return True, "Book issued successfully."


# =========================
# RETURN BOOK
# =========================

def return_book(book_id, member_id):

    connection = get_connection()

    borrowed = connection.execute("""
        SELECT *
        FROM borrowed_books
        WHERE book_id = ?
          AND member_id = ?
    """, (
        book_id,
        member_id
    )).fetchone()

    if not borrowed:

        connection.close()

        return False, "This member has not borrowed this book."

    connection.execute("""
        DELETE FROM borrowed_books
        WHERE book_id = ?
          AND member_id = ?
    """, (
        book_id,
        member_id
    ))

    connection.execute("""
        INSERT INTO transactions
        (transaction_type, book_id, member_id)
        VALUES (?, ?, ?)
    """, (
        "RETURNED",
        book_id,
        member_id
    ))

    # Check queue
    next_member = connection.execute("""
        SELECT *
        FROM waitlists
        WHERE book_id = ?
        ORDER BY position ASC
        LIMIT 1
    """, (
        book_id,
    )).fetchone()

    if next_member:

        next_member_id = next_member["member_id"]

        connection.execute("""
            DELETE FROM waitlists
            WHERE id = ?
        """, (
            next_member["id"],
        ))

        connection.execute("""
            UPDATE waitlists
            SET position = position - 1
            WHERE book_id = ?
        """, (
            book_id,
        ))

        connection.execute("""
            INSERT INTO borrowed_books
            (book_id, member_id)
            VALUES (?, ?)
        """, (
            book_id,
            next_member_id
        ))

        connection.execute("""
            INSERT INTO transactions
            (transaction_type, book_id, member_id)
            VALUES (?, ?, ?)
        """, (
            "AUTO-ISSUED",
            book_id,
            next_member_id
        ))

        message = (
            "Book returned and automatically "
            "issued to the first member in the waitlist."
        )

    else:

        connection.execute("""
            UPDATE books
            SET available = 1
            WHERE book_id = ?
        """, (
            book_id,
        ))

        message = "Book returned successfully."

    connection.commit()

    connection.close()

    transaction_stack.append({
        "type": "RETURNED",
        "book_id": book_id,
        "member_id": member_id
    })

    return True, message


# =========================
# WAITLIST
# =========================

def get_waitlists():

    connection = get_connection()

    rows = connection.execute("""
        SELECT
            w.book_id,
            b.title,
            w.member_id,
            m.name,
            w.position
        FROM waitlists w
        JOIN books b
            ON w.book_id = b.book_id
        JOIN members m
            ON w.member_id = m.member_id
        ORDER BY w.book_id, w.position
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


# =========================
# TRANSACTIONS
# =========================

def get_transactions():

    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM transactions
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


# =========================
# DASHBOARD
# =========================

def get_stats():

    connection = get_connection()

    total_books = connection.execute("""
        SELECT COUNT(*) AS count
        FROM books
    """).fetchone()["count"]

    available_books = connection.execute("""
        SELECT COUNT(*) AS count
        FROM books
        WHERE available = 1
    """).fetchone()["count"]

    issued_books = connection.execute("""
        SELECT COUNT(*) AS count
        FROM books
        WHERE available = 0
    """).fetchone()["count"]

    total_members = connection.execute("""
        SELECT COUNT(*) AS count
        FROM members
    """).fetchone()["count"]

    waitlist_count = connection.execute("""
        SELECT COUNT(*) AS count
        FROM waitlists
    """).fetchone()["count"]

    connection.close()

    return {
        "total_books": total_books,
        "available_books": available_books,
        "issued_books": issued_books,
        "total_members": total_members,
        "waitlist_count": waitlist_count
    }