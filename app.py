from flask import Flask, render_template, jsonify, request
import sqlite3
import os


app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    email = request.form.get("email", "")
    message = request.form.get("message")

    # Save to text file
    with open("feedback.txt", "a") as f:
        f.write(f"Email: {email}\nMessage: {message}\n---\n")

    return render_template("about.html", submitted=True)
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    #app.run(debug=True)
