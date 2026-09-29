from flask import Flask, request, jsonify, send_file
from database import (
    init_db,
    add_book,
    get_books,
    add_member,
    get_members,
    issue_book,
    return_book,
    get_waitlists,
    get_transactions,
    get_stats
)

app = Flask(__name__)

init_db()


@app.route("/")
def home():
    return send_file("index.html")


# =========================
# DASHBOARD
# =========================

@app.route("/api/stats")
def stats():
    return jsonify(get_stats())


# =========================
# BOOKS
# =========================

@app.route("/api/books", methods=["GET"])
def books():
    search = request.args.get("search", "")
    return jsonify(get_books(search))


@app.route("/api/books", methods=["POST"])
def create_book():

    data = request.json

    book_id = data.get("book_id")
    title = data.get("title")
    author = data.get("author")

    if not book_id or not title or not author:
        return jsonify({
            "success": False,
            "message": "All book fields are required."
        }), 400

    success, message = add_book(
        book_id,
        title,
        author
    )

    return jsonify({
        "success": success,
        "message": message
    })


# =========================
# MEMBERS
# =========================

@app.route("/api/members", methods=["GET"])
def members():
    return jsonify(get_members())


@app.route("/api/members", methods=["POST"])
def create_member():

    data = request.json

    member_id = data.get("member_id")
    name = data.get("name")

    if not member_id or not name:
        return jsonify({
            "success": False,
            "message": "All member fields are required."
        }), 400

    success, message = add_member(
        member_id,
        name
    )

    return jsonify({
        "success": success,
        "message": message
    })


# =========================
# ISSUE BOOK
# =========================

@app.route("/api/issue", methods=["POST"])
def issue():

    data = request.json

    book_id = data.get("book_id")
    member_id = data.get("member_id")

    if not book_id or not member_id:
        return jsonify({
            "success": False,
            "message": "Book ID and Member ID are required."
        }), 400

    success, message = issue_book(
        book_id,
        member_id
    )

    return jsonify({
        "success": success,
        "message": message
    })


# =========================
# RETURN BOOK
# =========================

@app.route("/api/return", methods=["POST"])
def return_book_route():

    data = request.json

    book_id = data.get("book_id")
    member_id = data.get("member_id")

    if not book_id or not member_id:
        return jsonify({
            "success": False,
            "message": "Book ID and Member ID are required."
        }), 400

    success, message = return_book(
        book_id,
        member_id
    )

    return jsonify({
        "success": success,
        "message": message
    })


# =========================
# WAITLIST
# =========================

@app.route("/api/waitlists")
def waitlists():
    return jsonify(get_waitlists())


# =========================
# TRANSACTIONS
# =========================

@app.route("/api/transactions")
def transactions():
    return jsonify(get_transactions())


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )