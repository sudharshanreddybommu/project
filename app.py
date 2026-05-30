from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import sqlite3
import os
import random
import string
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import json
import base64
import io
from PIL import Image

app = Flask(__name__)
CORS(app, origins="*")

app.config["JWT_SECRET_KEY"] = "opmd-secret-key-2024-secure"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)
jwt = JWTManager(app)


# Use /data for persistent storage on Render, local path for development
DATA_DIR = '/data' if os.path.exists('/data') else os.path.dirname(__file__)
DB_PATH = os.path.join(DATA_DIR, "opmd.db")
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Email config - update with real SMTP credentials
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USER = "your_email@gmail.com"
EMAIL_PASS = "your_app_password"

# In-memory OTP store: {email: {otp, expires}}
otp_store = {}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT,
        name TEXT,
        phone TEXT,
        address TEXT,
        age INTEGER,
        is_verified INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT,
        name TEXT,
        phone TEXT,
        hospital TEXT,
        address TEXT,
        specialization TEXT,
        is_verified INTEGER DEFAULT 0,
        verification_status TEXT DEFAULT 'pending',
        hospital_id_doc TEXT,
        medical_cert_doc TEXT,
        degree_cert_doc TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        left_image TEXT,
        front_image TEXT,
        right_image TEXT,
        prediction TEXT,
        risk_level TEXT,
        suggestions TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        scan_id INTEGER,
        status TEXT DEFAULT 'pending',
        scheduled_date TEXT,
        notes TEXT,
        patient_notified INTEGER DEFAULT 0,
        doctor_notified INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES patients(id),
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        user_type TEXT NOT NULL,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    conn.commit()
    conn.close()
    print("Database initialized.")


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


def send_otp_email(to_email, otp):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = "OPMD Portal - Your OTP Verification Code"
        body = f"""
        <html><body>
        <h2 style='color:#1a73e8'>OPMD AI Detection Portal</h2>
        <p>Your OTP verification code is:</p>
        <h1 style='color:#e53935;letter-spacing:8px'>{otp}</h1>
        <p>This code expires in 10 minutes. Do not share it with anyone.</p>
        </body></html>
        """
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def ai_predict(left_img_b64, front_img_b64, right_img_b64):
    """
    Simulated AI prediction. In production, replace with actual ML model.
    Returns risk_level: 'low', 'moderate', or 'high'
    """
    import random
    risk_scores = []
    for img_b64 in [left_img_b64, front_img_b64, right_img_b64]:
        if img_b64:
            try:
                img_data = base64.b64decode(img_b64.split(',')[-1])
                img = Image.open(io.BytesIO(img_data)).convert('RGB')
                img = img.resize((224, 224))
                pixels = list(img.getdata())
                avg_r = sum(p[0] for p in pixels) / len(pixels)
                avg_g = sum(p[1] for p in pixels) / len(pixels)
                avg_b = sum(p[2] for p in pixels) / len(pixels)
                # Heuristic: reddish/whitish patches indicate higher risk
                redness = avg_r - avg_g
                brightness = (avg_r + avg_g + avg_b) / 3
                score = min(100, max(0, redness * 0.5 + (255 - brightness) * 0.1 + random.uniform(-10, 10)))
                risk_scores.append(score)
            except:
                risk_scores.append(random.uniform(10, 40))
        else:
            risk_scores.append(0)

    avg_score = sum(risk_scores) / max(len(risk_scores), 1) if risk_scores else 0

    if avg_score < 35:
        risk_level = "low"
        prediction = "No significant oral lesions detected"
        suggestions = [
            "Maintain good oral hygiene by brushing twice daily",
            "Floss daily and use antiseptic mouthwash",
            "Avoid tobacco and alcohol consumption",
            "Eat a balanced diet rich in vitamins C and E",
            "Schedule regular dental check-ups every 6 months",
            "Stay hydrated and limit sugar intake"
        ]
    elif avg_score < 65:
        risk_level = "moderate"
        prediction = "Possible early-stage oral changes detected"
        suggestions = [
            "Consult a dentist within the next 2 weeks",
            "Avoid tobacco, betel nut, and alcohol immediately",
            "Rinse mouth with warm saline water twice daily",
            "Monitor the affected area for any changes in size or color",
            "Maintain strict oral hygiene practices",
            "Take Vitamin B12 and folate supplements as advised",
            "Avoid spicy and acidic foods that may irritate the area"
        ]
    else:
        risk_level = "high"
        prediction = "High-risk oral lesions detected - Immediate consultation required"
        suggestions = [
            "URGENT: Consult an oral oncologist or ENT specialist immediately",
            "Do not delay medical evaluation",
            "Avoid all tobacco products and alcohol completely",
            "Document and photograph the affected area daily",
            "Request a biopsy or histopathological examination",
            "Seek a second medical opinion if needed",
            "Inform your family and support network"
        ]

    return {
        "risk_level": risk_level,
        "prediction": prediction,
        "suggestions": suggestions,
        "confidence": round(min(99, max(60, avg_score + random.uniform(20, 35))), 1),
        "analyzed_at": datetime.now().isoformat()
    }


# ─── AUTH ROUTES ──────────────────────────────────────────────────────────────

@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    user_type = data.get('user_type', 'patient')
    if not email:
        return jsonify({"error": "Email is required"}), 400

    otp = generate_otp()
    otp_store[email] = {
        "otp": otp,
        "expires": (datetime.now() + timedelta(minutes=10)).isoformat()
    }

    sent = send_otp_email(email, otp)
    if not sent:
        # Dev fallback: return OTP in response
        print(f"[DEV] OTP for {email}: {otp}")
        return jsonify({"message": "OTP sent (dev mode)", "dev_otp": otp}), 200

    return jsonify({"message": "OTP sent to your email"}), 200


@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()

    if email not in otp_store:
        return jsonify({"error": "No OTP found for this email"}), 400

    record = otp_store[email]
    if datetime.now() > datetime.fromisoformat(record['expires']):
        del otp_store[email]
        return jsonify({"error": "OTP has expired. Please request a new one."}), 400

    if record['otp'] != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    del otp_store[email]
    return jsonify({"message": "OTP verified successfully", "verified": True}), 200


# ─── PATIENT ROUTES ───────────────────────────────────────────────────────────

@app.route('/api/patient/register', methods=['POST'])
def patient_register():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO patients (email, password, is_verified) VALUES (?, ?, 1)",
            (email, hash_password(password))
        )
        conn.commit()
        patient = conn.execute("SELECT * FROM patients WHERE email=?", (email,)).fetchone()
        token = create_access_token(identity=json.dumps({"id": patient['id'], "type": "patient"}))
        return jsonify({"message": "Registration successful", "token": token, "patient": dict(patient)}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already registered"}), 409
    finally:
        conn.close()


@app.route('/api/patient/login', methods=['POST'])
def patient_login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    conn = get_db()
    patient = conn.execute("SELECT * FROM patients WHERE email=?", (email,)).fetchone()
    conn.close()

    if not patient:
        return jsonify({"error": "No account found with this email"}), 404

    if not patient['password']:
        return jsonify({"error": "Please complete registration first"}), 400

    if patient['password'] != hash_password(password):
        return jsonify({"error": "Invalid password"}), 401

    token = create_access_token(identity=json.dumps({"id": patient['id'], "type": "patient"}))
    return jsonify({"message": "Login successful", "token": token, "patient": dict(patient)}), 200


@app.route('/api/patient/profile', methods=['PUT'])
@jwt_required()
def update_patient_profile():
    identity = json.loads(get_jwt_identity())
    if identity['type'] != 'patient':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    conn = get_db()
    conn.execute(
        "UPDATE patients SET name=?, phone=?, address=?, age=? WHERE id=?",
        (data.get('name'), data.get('phone'), data.get('address'), data.get('age'), identity['id'])
    )
    conn.commit()
    patient = conn.execute("SELECT * FROM patients WHERE id=?", (identity['id'],)).fetchone()
    conn.close()
    return jsonify({"message": "Profile updated", "patient": dict(patient)}), 200


@app.route('/api/patient/me', methods=['GET'])
@jwt_required()
def get_patient_me():
    identity = json.loads(get_jwt_identity())
    conn = get_db()
    patient = conn.execute("SELECT * FROM patients WHERE id=?", (identity['id'],)).fetchone()
    conn.close()
    if not patient:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(patient)), 200


@app.route('/api/patient/check-email', methods=['POST'])
def check_patient_email():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    conn = get_db()
    patient = conn.execute("SELECT id, password FROM patients WHERE email=?", (email,)).fetchone()
    conn.close()
    if not patient:
        return jsonify({"exists": False}), 200
    return jsonify({"exists": True, "has_password": bool(patient['password'])}), 200


# ─── SCAN / AI ROUTES ─────────────────────────────────────────────────────────

@app.route('/api/scan/analyze', methods=['POST'])
@jwt_required()
def analyze_scan():
    identity = json.loads(get_jwt_identity())
    if identity['type'] != 'patient':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    left_img = data.get('left_image', '')
    front_img = data.get('front_image', '')
    right_img = data.get('right_image', '')

    if not any([left_img, front_img, right_img]):
        return jsonify({"error": "At least one image is required"}), 400

    result = ai_predict(left_img, front_img, right_img)

    conn = get_db()
    cur = conn.execute(
        """INSERT INTO scans (patient_id, left_image, front_image, right_image, prediction, risk_level, suggestions)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (identity['id'], left_img[:200] if left_img else None,
         front_img[:200] if front_img else None,
         right_img[:200] if right_img else None,
         result['prediction'], result['risk_level'],
         json.dumps(result['suggestions']))
    )
    conn.commit()
    scan_id = cur.lastrowid
    conn.close()

    return jsonify({"scan_id": scan_id, **result}), 200


@app.route('/api/scan/history', methods=['GET'])
@jwt_required()
def scan_history():
    identity = json.loads(get_jwt_identity())
    conn = get_db()
    scans = conn.execute(
        "SELECT id, prediction, risk_level, created_at FROM scans WHERE patient_id=? ORDER BY created_at DESC",
        (identity['id'],)
    ).fetchall()
    conn.close()
    return jsonify([dict(s) for s in scans]), 200


# ─── DOCTOR ROUTES ────────────────────────────────────────────────────────────

@app.route('/api/doctor/register', methods=['POST'])
def doctor_register():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    hospital_id_doc = data.get('hospital_id_doc', '')
    medical_cert_doc = data.get('medical_cert_doc', '')
    degree_cert_doc = data.get('degree_cert_doc', '')

    if not email:
        return jsonify({"error": "Email is required"}), 400
    if not any([hospital_id_doc, medical_cert_doc, degree_cert_doc]):
        return jsonify({"error": "At least one verification document is required"}), 400

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO doctors (email, hospital_id_doc, medical_cert_doc, degree_cert_doc, verification_status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (email, hospital_id_doc[:100] if hospital_id_doc else None,
             medical_cert_doc[:100] if medical_cert_doc else None,
             degree_cert_doc[:100] if degree_cert_doc else None)
        )
        conn.commit()
        return jsonify({"message": "Documents submitted. Awaiting admin verification."}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already registered"}), 409
    finally:
        conn.close()


@app.route('/api/doctor/check-email', methods=['POST'])
def check_doctor_email():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    conn = get_db()
    doctor = conn.execute("SELECT id, password, verification_status, is_verified FROM doctors WHERE email=?", (email,)).fetchone()
    conn.close()
    if not doctor:
        return jsonify({"exists": False}), 200
    return jsonify({
        "exists": True,
        "has_password": bool(doctor['password']),
        "verification_status": doctor['verification_status'],
        "is_verified": bool(doctor['is_verified'])
    }), 200


@app.route('/api/doctor/set-password', methods=['POST'])
def doctor_set_password():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    conn = get_db()
    doctor = conn.execute("SELECT * FROM doctors WHERE email=?", (email,)).fetchone()
    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404
    if not doctor['is_verified']:
        return jsonify({"error": "Your account is pending verification by admin"}), 403

    conn.execute("UPDATE doctors SET password=? WHERE email=?", (hash_password(password), email))
    conn.commit()
    doctor = conn.execute("SELECT * FROM doctors WHERE email=?", (email,)).fetchone()
    token = create_access_token(identity=json.dumps({"id": doctor['id'], "type": "doctor"}))
    conn.close()
    return jsonify({"message": "Password set successfully", "token": token, "doctor": dict(doctor)}), 200


@app.route('/api/doctor/login', methods=['POST'])
def doctor_login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    conn = get_db()
    doctor = conn.execute("SELECT * FROM doctors WHERE email=?", (email,)).fetchone()
    conn.close()

    if not doctor:
        return jsonify({"error": "No account found with this email"}), 404
    if not doctor['is_verified']:
        return jsonify({"error": "Your account is pending verification"}), 403
    if not doctor['password']:
        return jsonify({"error": "Please complete registration first"}), 400
    if doctor['password'] != hash_password(password):
        return jsonify({"error": "Invalid password"}), 401

    token = create_access_token(identity=json.dumps({"id": doctor['id'], "type": "doctor"}))
    return jsonify({"message": "Login successful", "token": token, "doctor": dict(doctor)}), 200


@app.route('/api/doctor/profile', methods=['PUT'])
@jwt_required()
def update_doctor_profile():
    identity = json.loads(get_jwt_identity())
    if identity['type'] != 'doctor':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    conn = get_db()
    conn.execute(
        "UPDATE doctors SET name=?, phone=?, hospital=?, address=?, specialization=?, profile_image=?, payment_qr=?, consultation_fee=? WHERE id=?",
        (data.get('name'), data.get('phone'), data.get('hospital'),
         data.get('address'), data.get('specialization'), data.get('profile_image'), 
         data.get('payment_qr'), data.get('consultation_fee'), identity['id'])
    )
    conn.commit()
    doctor = conn.execute("SELECT * FROM doctors WHERE id=?", (identity['id'],)).fetchone()
    conn.close()
    return jsonify({"message": "Profile updated", "doctor": dict(doctor)}), 200


@app.route('/api/doctor/me', methods=['GET'])
@jwt_required()
def get_doctor_me():
    identity = json.loads(get_jwt_identity())
    conn = get_db()
    doctor = conn.execute("SELECT * FROM doctors WHERE id=?", (identity['id'],)).fetchone()
    conn.close()
    if not doctor:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(doctor)), 200


@app.route('/api/doctors', methods=['GET'])
def list_doctors():
    conn = get_db()
    doctors = conn.execute(
        "SELECT id, name, hospital, address, specialization, phone FROM doctors WHERE is_verified=1 AND name IS NOT NULL"
    ).fetchall()
    conn.close()
    return jsonify([dict(d) for d in doctors]), 200


# ─── APPOINTMENTS ─────────────────────────────────────────────────────────────

@app.route('/api/appointment/request', methods=['POST'])
@jwt_required()
def request_appointment():
    identity = json.loads(get_jwt_identity())
    if identity['type'] != 'patient':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    doctor_id = data.get('doctor_id')
    scan_id = data.get('scan_id')

    if not doctor_id:
        return jsonify({"error": "Doctor ID required"}), 400

    conn = get_db()
    patient = conn.execute("SELECT name FROM patients WHERE id=?", (identity['id'],)).fetchone()
    doctor = conn.execute("SELECT name FROM doctors WHERE id=?", (doctor_id,)).fetchone()

    cur = conn.execute(
        "INSERT INTO appointments (patient_id, doctor_id, scan_id, status) VALUES (?, ?, ?, 'pending')",
        (identity['id'], doctor_id, scan_id)
    )
    appt_id = cur.lastrowid

    # Notify doctor
    conn.execute(
        "INSERT INTO notifications (user_id, user_type, message) VALUES (?, 'doctor', ?)",
        (doctor_id, f"New appointment request from patient {patient['name'] or 'Unknown'}")
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Appointment requested successfully", "appointment_id": appt_id}), 201


@app.route('/api/doctor/appointments', methods=['GET'])
@jwt_required()
def doctor_appointments():
    identity = json.loads(get_jwt_identity())
    if identity['type'] != 'doctor':
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    now_str = datetime.now().strftime('%Y-%m-%dT%H:%M')
    conn.execute("UPDATE appointments SET status='rejected' WHERE status IN ('scheduled', 'confirmed') AND scheduled_date IS NOT NULL AND scheduled_date < ?", (now_str,))
    conn.commit()

    appts = conn.execute("""
        SELECT a.*, p.name as patient_name, p.phone as patient_phone, p.age as patient_age,
               s.prediction, s.risk_level, s.suggestions, s.created_at as scan_date
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        LEFT JOIN scans s ON a.scan_id = s.id
        WHERE a.doctor_id = ?
        ORDER BY a.created_at DESC
    """, (identity['id'],)).fetchall()
    conn.close()

    result = []
    for a in appts:
        d = dict(a)
        d['suggestions'] = json.loads(d['suggestions']) if d['suggestions'] else []
        result.append(d)
    return jsonify(result), 200

@app.route('/api/doctor/appointment/<int:appt_id>/complete', methods=['PUT'])
@jwt_required()
def complete_appointment(appt_id):
    identity = json.loads(get_jwt_identity())
    if identity['type'] != 'doctor':
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    appt = conn.execute("SELECT * FROM appointments WHERE id=? AND doctor_id=?", (appt_id, identity['id'])).fetchone()
    if not appt:
        conn.close()
        return jsonify({"error": "Appointment not found"}), 404

    conn.execute("UPDATE appointments SET status='completed' WHERE id=?", (appt_id,))
    
    doctor = conn.execute("SELECT name FROM doctors WHERE id=?", (identity['id'],)).fetchone()
    conn.execute(
        "INSERT INTO notifications (user_id, user_type, message) VALUES (?, 'patient', ?)",
        (appt['patient_id'], f"Your appointment with Dr. {doctor['name'] or 'Unknown'} has been marked as completed. Thank you for visiting!")
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Appointment completed"}), 200

@app.route('/api/doctor/appointment/<int:appt_id>/schedule', methods=['PUT'])
@jwt_required()
def schedule_appointment(appt_id):
    identity = json.loads(get_jwt_identity())
    if identity['type'] != 'doctor':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    scheduled_date = data.get('scheduled_date')
    notes = data.get('notes', '')

    conn = get_db()
    appt = conn.execute("SELECT * FROM appointments WHERE id=? AND doctor_id=?", (appt_id, identity['id'])).fetchone()
    if not appt:
        conn.close()
        return jsonify({"error": "Appointment not found"}), 404

    conn.execute(
        "UPDATE appointments SET status='scheduled', scheduled_date=?, notes=? WHERE id=?",
        (scheduled_date, notes, appt_id)
    )

    # Notify patient
    doctor = conn.execute("SELECT name FROM doctors WHERE id=?", (identity['id'],)).fetchone()
    conn.execute(
        "INSERT INTO notifications (user_id, user_type, message) VALUES (?, 'patient', ?)",
        (appt['patient_id'], f"Your appointment has been scheduled by Dr. {doctor['name'] or 'Unknown'} for {scheduled_date}")
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Appointment scheduled successfully"}), 200


@app.route('/api/patient/appointments', methods=['GET'])
@jwt_required()
def patient_appointments():
    identity = json.loads(get_jwt_identity())
    conn = get_db()
    appts = conn.execute("""
        SELECT a.*, d.name as doctor_name, d.hospital as doctor_hospital, d.specialization
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.patient_id = ?
        ORDER BY a.created_at DESC
    """, (identity['id'],)).fetchall()
    conn.close()
    return jsonify([dict(a) for a in appts]), 200


# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────

@app.route('/api/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    identity = json.loads(get_jwt_identity())
    conn = get_db()
    notifs = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND user_type=? ORDER BY created_at DESC LIMIT 20",
        (identity['id'], identity['type'])
    ).fetchall()
    conn.close()
    return jsonify([dict(n) for n in notifs]), 200


@app.route('/api/notifications/read', methods=['PUT'])
@jwt_required()
def mark_notifications_read():
    identity = json.loads(get_jwt_identity())
    conn = get_db()
    conn.execute(
        "UPDATE notifications SET is_read=1 WHERE user_id=? AND user_type=?",
        (identity['id'], identity['type'])
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Marked as read"}), 200


# ─── ADMIN ────────────────────────────────────────────────────────────────────

@app.route('/api/admin/verify-doctor/<int:doctor_id>', methods=['PUT'])
def admin_verify_doctor(doctor_id):
    conn = get_db()
    conn.execute("UPDATE doctors SET is_verified=1, verification_status='approved' WHERE id=?", (doctor_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Doctor verified"}), 200


@app.route('/api/admin/doctors', methods=['GET'])
def admin_list_doctors():
    conn = get_db()
    doctors = conn.execute("SELECT id, email, name, verification_status, is_verified, created_at FROM doctors").fetchall()
    conn.close()
    return jsonify([dict(d) for d in doctors]), 200


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=True, port=5000)
