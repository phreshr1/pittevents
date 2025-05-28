from flask import Flask, render_template, jsonify, request
import sqlite3

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/events")
def get_events():
    source_filter = request.args.get("source")
    conn = sqlite3.connect("events.db")
    cursor = conn.cursor()

    if source_filter:
        cursor.execute("SELECT title, date, link, end, allDay, color, source FROM events WHERE source = ?", (source_filter,))
    else:
        cursor.execute("SELECT title, date, link, end, allDay, color, source FROM events")

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

import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
