from flask import Flask, render_template, jsonify, request
from flask import Response
from datetime import datetime
from functools import wraps
from flask import request
import sqlite3
import os


app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

def check_auth(username, password):
    return (
        username == os.environ.get("ADMIN_USER") and
        password == os.environ.get("ADMIN_PASS")
    )

def authenticate():
    return Response(
        "Authentication required", 401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route("/admin/feedback")

@requires_auth
def view_feedback():
    conn = sqlite3.connect("/data/events.db")
    cursor = conn.cursor()
    cursor.execute("SELECT email, message, timestamp FROM feedback ORDER BY timestamp DESC")
    entries = cursor.fetchall()
    conn.close()
    return render_template("feedback_list.html", feedback=entries)
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    email = request.form.get("email", "")
    message = request.form.get("message")

    conn = sqlite3.connect("events.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feedback (email, message, timestamp)
        VALUES (?, ?, ?)
    """, (email, message, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return render_template("about.html", submitted=True)
@app.route("/events")
def get_events():
    source_filter = request.args.get("source")
    conn = sqlite3.connect("events.db")
    cursor = conn.cursor()

    # Use COALESCE to support both date/link and start/url columns
    if source_filter:
        cursor.execute("""
            SELECT title,
                   COALESCE(date, start) as start,
                   COALESCE(link, url) as url,
                   end,
                   allDay,
                   color,
                   source
            FROM events
            WHERE source = ?
        """, (source_filter,))
    else:
        cursor.execute("""
            SELECT title,
                   COALESCE(date, start) as start,
                   COALESCE(link, url) as url,
                   end,
                   allDay,
                   color,
                   source
            FROM events
        """)

    events = []
    for row in cursor.fetchall():
        events.append({
            "title": row[0],
            "start": row[1],
            "url": row[2],
            "end": row[3] if row[3] else None,
            "allDay": bool(row[4]),
            "color": row[5],
            "source": row[6]
        })
    conn.close()
    return jsonify(events)


if __name__ == "__main__":
    #app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    app.run(debug=True)
