# app.py
from flask import Flask, render_template, request, redirect, session, url_for
from flask_socketio import SocketIO, emit
from datetime import datetime
import sqlite3
import os
import requests

# Heure fixe de lancement du cours (à adapter selon ton besoin)
heure_debut_cours = datetime(
    2025, 5, 28, 16, 35, 0
)  # Format : AAAA, MM, JJ, HH, MM, SS

app = Flask(__name__)
app.secret_key = "secret_key"
DB_PATH = "data/database.db"

# SocketIO, async_mode eventlet dans run.py
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Création de la BDD si elle n'existe pas
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT,
    prenom TEXT,
    arrivee TEXT,
    depart TEXT
)
"""
)

# Table pour suivre les visites de /video
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS video_visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_id INTEGER,
        timestamp TEXT
    )
    """
)

conn.commit()
conn.close()


def call_elevenlabs_agent(question):
    try:
        response = requests.post(
            "http://127.0.0.1:6000/ask", json={"question": question}, timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data.get("answer_text", "Désolé, je n'ai pas pu obtenir de réponse.")
    except Exception as e:
        print("Erreur API ElevenLabs:", e)
        return "Désolé, une erreur est survenue."


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        nom = request.form["nom"]
        prenom = request.form["prenom"]
        session["nom"] = nom
        session["prenom"] = prenom
        session["arrivee"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Enregistrement arrivée
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (nom, prenom, arrivee) VALUES (?, ?, ?)",
            (nom, prenom, session["arrivee"]),
        )
        session["log_id"] = cursor.lastrowid
        conn.commit()
        conn.close()

        return redirect("/video")
    return render_template("index.html")


@app.route("/video")
def video():
    if "nom" not in session:
        return redirect("/")

    now = datetime.now()
    offset = max(0, int((now - heure_debut_cours).total_seconds()))
    temps_restant = max(0, int((heure_debut_cours - now).total_seconds()))

    return render_template(
        "video.html",
        nom=session["nom"],
        prenom=session["prenom"],
        offset=offset,
        temps_restant=temps_restant,
    )


@app.route("/logout")
def logout():
    if "log_id" in session:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        depart = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE logs SET depart=? WHERE id=?", (depart, session["log_id"])
        )
        conn.commit()
        conn.close()
    session.clear()
    return redirect("/")


@app.route("/deconnexion-auto", methods=["POST"])
def deconnexion_auto():
    if "log_id" in session:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE logs SET depart=? WHERE id=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session["log_id"]),
            )
            conn.commit()
    return "", 204


@app.route("/admin", methods=["GET", "POST"])
def admin():
    prenom_recherche = request.args.get("prenom", "")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if prenom_recherche:
        cursor.execute(
            "SELECT * FROM logs WHERE prenom LIKE ?", ("%" + prenom_recherche + "%",)
        )
    else:
        cursor.execute("SELECT * FROM logs")

    logs = cursor.fetchall()
    conn.close()

    total_seconds = 0
    logs_with_duration = []

    for log in logs:
        id_, nom, prenom, arrivee, depart = log
        if depart:
            dt_arrivee = datetime.strptime(arrivee, "%Y-%m-%d %H:%M:%S")
            dt_depart = datetime.strptime(depart, "%Y-%m-%d %H:%M:%S")
            duration = dt_depart - dt_arrivee
            seconds = duration.total_seconds()
            total_seconds += seconds

            minutes = int(seconds // 60)
            secondes = int(seconds % 60)
            duree = f"{minutes} min {secondes} sec"
        else:
            duree = "En cours..."
        logs_with_duration.append((id_, nom, prenom, arrivee, depart, duree))

    # Calcul du temps total cumulé en h/min/sec
    total_minutes = int(total_seconds // 60)
    total_heures = total_minutes // 60
    total_minutes_restant = total_minutes % 60
    total_secondes = int(total_seconds % 60)
    temps_total_format = (
        f"{total_heures} h {total_minutes_restant} min {total_secondes} sec"
    )

    return render_template(
        "admin.html",
        logs=logs_with_duration,
        prenom_recherche=prenom_recherche,
        temps_total=temps_total_format,
    )


# --------- SOCKET.IO EVENTS -----------


@socketio.on("connect")
def handle_connect():
    print(f"Client connecté: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    print(f"Client déconnecté: {request.sid}")


@socketio.on("send_question")
def handle_send_question(data):
    username = data.get("username", "Anonyme")
    question = data.get("question", "").strip()

    if not question:
        return  # Ne rien faire si question vide

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Diffuser la question de l'utilisateur à tous les clients
    emit(
        "receive_question",
        {"username": username, "question": question, "timestamp": timestamp},
        broadcast=True,
    )

    # Appel au microservice ElevenLabs via HTTP
    try:
        response = requests.post(
            "http://127.0.0.1:6000/ask", json={"question": question}, timeout=40
        )
        response.raise_for_status()
        data = response.json()

        response_text = data.get(
            "answer_text", "Désolé, je n'ai pas pu obtenir de réponse."
        )
        audio_b64 = data.get("audio_b64")

        # Diffuser la réponse textuelle de l'agent
        emit(
            "receive_question",
            {
                "username": "Agent Eleven Labs",
                "question": response_text,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            },
            broadcast=True,
        )

        # Diffuser le flux audio base64 si présent
        if audio_b64:
            emit("receive_audio", {"audio_b64": audio_b64}, broadcast=True)

    except Exception as e:
        print("Erreur lors de l'appel au microservice ElevenLabs:", e)
        emit(
            "receive_question",
            {
                "username": "Agent Eleven Labs",
                "question": "Désolé, une erreur est survenue.",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            },
            broadcast=True,
        )


if __name__ == "__main__":
    # Pour le lancement direct sans eventlet, mais pour WebSocket eventlet est recommandé
    app.run(debug=True)
