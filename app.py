from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response, session
import sqlite3

app = Flask(__name__, template_folder="templates")
DB_NAME = "funvote.db"
app.secret_key = "una_clave_super_secreta"  # 🔑 Para firmar cookies y sesiones

# -------------------------------------------
# 🔹 Funciones de base de datos
# -------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS eventos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    descripcion TEXT NOT NULL
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS participantes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    evento_id INTEGER,
                    nombre TEXT,
                    votos INTEGER DEFAULT 0,
                    FOREIGN KEY (evento_id) REFERENCES eventos(id)
                )''')
    conn.commit()
    conn.close()

def eliminar_evento_por_id(evento_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM participantes WHERE evento_id=?", (evento_id,))
    c.execute("DELETE FROM eventos WHERE id=?", (evento_id,))
    conn.commit()
    conn.close()

# -------------------------------------------
# 🏠 Página principal
# -------------------------------------------
@app.route('/')
def index():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM eventos")
    eventos = c.fetchall()
    conn.close()
    return render_template('index.html', eventos=eventos)

# -------------------------------------------
# 🎉 Crear evento
# -------------------------------------------
@app.route('/create', methods=['GET', 'POST'])
def crear_evento():
    if request.method == 'POST':
        nombre = request.form['nombre_evento'].strip()
        descripcion = request.form['descripcion_evento'].strip()
        participantes = [p.strip() for p in request.form['participantes'].split(',') if p.strip()]

        if not nombre or not participantes:
            return "Debés poner un nombre y al menos 1 participante 😅", 400
        if len(set(participantes)) != len(participantes):
            return "No se permiten nombres duplicados 😅", 400

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO eventos (nombre, descripcion) VALUES (?, ?)", (nombre, descripcion))
        evento_id = c.lastrowid
        c.executemany(
            "INSERT INTO participantes (evento_id, nombre) VALUES (?, ?)",
            [(evento_id, p) for p in participantes]
        )
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('create_event.html')

# -------------------------------------------
# 🗳️ Editar evento
# -------------------------------------------
@app.route('/evento/<int:evento_id>/editar', methods=['GET', 'POST'])
def editar_evento(evento_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM eventos WHERE id=?", (evento_id,))
    evento = c.fetchone()
    if not evento:
        conn.close()
        return "Evento no encontrado 😅", 404

    c.execute("SELECT id, nombre FROM participantes WHERE evento_id=?", (evento_id,))
    participantes = c.fetchall()

    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        descripcion = request.form['descripcion'].strip()
        nuevos_participantes = [p.strip() for p in request.form.getlist('participantes[]') if p.strip()]

        if not nombre or not nuevos_participantes:
            return "Debés poner un nombre y al menos 1 participante 😅", 400
        if len(set(nuevos_participantes)) != len(nuevos_participantes):
            return "No se permiten nombres duplicados 😅", 400

        c.execute("UPDATE eventos SET nombre=?, descripcion=? WHERE id=?", (nombre, descripcion, evento_id))
        c.execute("DELETE FROM participantes WHERE evento_id=?", (evento_id,))
        c.executemany(
            "INSERT INTO participantes (evento_id, nombre) VALUES (?, ?)",
            [(evento_id, p) for p in nuevos_participantes]
        )
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('editar_evento.html', evento=evento, participantes=participantes)

# -------------------------------------------
# 🗑️ Borrar evento
# -------------------------------------------
@app.route('/evento/<int:evento_id>/eliminar', methods=['POST'])
def eliminar_evento(evento_id):
    eliminar_evento_por_id(evento_id)
    return redirect(url_for('index'))

# -------------------------------------------
# 🗳️ Votar
# -------------------------------------------
@app.route('/votar/<int:evento_id>', methods=['GET', 'POST'])
def votar(evento_id):
    conn = get_db_connection()
    c = conn.cursor()

    vote_cookie = request.cookies.get(f"voted_event_{evento_id}")
    ya_votaste = False
    if vote_cookie and session.get(f"voted_event_{evento_id}") == "true":
        ya_votaste = True

    if ya_votaste and request.method == 'POST':
        conn.close()
        return jsonify({"status": "ya_votaste"})

    if request.method == 'POST':
        votos = request.json.get('votos', {})
        votos_limpios = {}
        for participante, puntos in votos.items():
            if not isinstance(puntos, int) or puntos < 1:
                continue
            c.execute("SELECT 1 FROM participantes WHERE evento_id=? AND nombre=?", (evento_id, participante))
            if c.fetchone():
                votos_limpios[participante] = puntos

        if not votos_limpios:
            conn.close()
            return jsonify({"status": "no_votos_validos"})

        for participante, puntos in votos_limpios.items():
            c.execute(
                "UPDATE participantes SET votos = votos + ? WHERE evento_id=? AND nombre=?",
                (puntos, evento_id, participante)
            )
        conn.commit()
        conn.close()

        session[f"voted_event_{evento_id}"] = "true"
        resp = make_response(jsonify({"status": "ok"}))
        resp.set_cookie(f"voted_event_{evento_id}", "true", max_age=60*60*24*365, secure=False, httponly=True, samesite='Lax')
        return resp

    c.execute("SELECT * FROM eventos WHERE id=?", (evento_id,))
    evento = c.fetchone()
    if not evento:
        conn.close()
        return "Evento no encontrado 😅", 404

    c.execute("SELECT nombre, votos FROM participantes WHERE evento_id=?", (evento_id,))
    participantes = [{"nombre": row["nombre"], "votos": row["votos"]} for row in c.fetchall()]
    conn.close()

    criterios = [
        "Puntualidad", "Actitud hacia el trabajo", "Actitud personal",
        "Trabajo en equipo", "Crecimiento técnico", "Iniciativa",
        "Liderazgo", "Honestidad", "Respeto a los demás",
        "Buena comunicación", "Desarrollo profesional", "Creatividad"
    ]

    return render_template(
        'vote.html',
        evento=evento,
        participantes=participantes,
        criterios=criterios,
        ya_votaste=ya_votaste
    )

# -------------------------------------------
# 🏆 Resultados
# -------------------------------------------
@app.route('/resultados/<int:evento_id>')
def resultados(evento_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM eventos WHERE id=?", (evento_id,))
    evento = c.fetchone()
    if not evento:
        conn.close()
        return "Evento no encontrado 😅", 404

    c.execute("SELECT nombre, votos FROM participantes WHERE evento_id=?", (evento_id,))
    participantes_db = c.fetchall()
    conn.close()

    votos_dict = {p["nombre"]: int(p["votos"]) for p in participantes_db}
    sorted_part = sorted(votos_dict.items(), key=lambda x: x[1], reverse=True)

    podio_visual = []
    ganador = None
    if sorted_part:
        max_votos = sorted_part[0][1]
        empates = [p for p, v in sorted_part if v == max_votos]
        if len(empates) > 1:
            podio_visual = sorted_part
        else:
            ganador = sorted_part[0][0]
            podio_visual = sorted_part

    return render_template('results.html', evento={
        'nombre': evento["nombre"],
        'descripcion': evento["descripcion"],
        'votos': votos_dict,
        'podio': podio_visual,
        'ganador': ganador
    }, sorted_part=podio_visual)

# -------------------------------------------
# 🚀 Iniciar app
# -------------------------------------------
if __name__ == '__main__':
    init_db()
    import os
    port = int(os.environ.get("PORT", 5000))  # toma el puerto que Render asigne
    app.run(host="0.0.0.0", port=port, debug=True)

