from flask import Flask, request, jsonify
import sqlite3
import requests
import os

BOT_TOKEN = "8003747092:AAEu0_PdUw6HB4ZNM_vfj6nNBKKwPBqVcJ0"
CHAT_ID = "6094144400"

app = Flask(__name__)

# Serverless path for SQLite (Vercel ephemeral storage)
DB = "/tmp/data.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firstname TEXT,
            lastname TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS completed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firstname TEXT,
            lastname TEXT,
            email TEXT,
            password TEXT,
            messenger TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ------------- TERMUX ADD USER ----------------
@app.route("/add_user", methods=["POST"])
def add_user():
    data = request.json
    firstname = data.get("firstname","").strip()
    lastname = data.get("lastname","").strip()
    email = data.get("email","").strip().lower()
    password = data.get("password","").strip()

    if not firstname or not lastname or not email or not password:
        return jsonify({"status":"Missing fields"}),400

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO pending (firstname, lastname, email, password) VALUES (?, ?, ?, ?)",
                  (firstname, lastname, email, password))
        conn.commit()
        status = "Added"
    except sqlite3.IntegrityError:
        status = "Email exists"
    conn.close()
    return jsonify({"status": status})

# ------------- GET NEXT USER ----------------
@app.route("/next_user")
def next_user():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM pending ORDER BY id ASC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({"exists": False})
    user_id, fn, ln, email, pw = row
    return jsonify({
        "exists": True,
        "id": user_id,
        "firstname": fn,
        "lastname": ln,
        "email": email,
        "password": pw
    })

# ------------- SUBMIT MESSENGER ----------------
@app.route("/submit_messenger", methods=["POST"])
def submit_messenger():
    data = request.json
    user_id = data.get("id")
    messenger = data.get("messenger","").strip()
    if not messenger:
        return jsonify({"ok":False,"error":"Messenger ID required"}),400

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT firstname, lastname, email, password FROM pending WHERE id=?", (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"ok": False, "error": "User expired"})
    fn, ln, email, pw = user
    c.execute("INSERT INTO completed (firstname, lastname, email, password, messenger) VALUES (?, ?, ?, ?, ?)",
              (fn, ln, email, pw, messenger))
    c.execute("DELETE FROM pending WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

    # Telegram notification
    text = f"New Submission!\nFirst: {fn}\nLast: {ln}\nEmail: {email}\nPass: {pw}\nMessenger: {messenger}"
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                     params={"chat_id": CHAT_ID, "text": text}, timeout=5)
    except:
        pass  # ignore Telegram errors

    return jsonify({"ok": True, "message": "Submitted successfully"})

# ----------------- HOME PAGE ----------------
@app.route("/")
def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Submission Portal</title>
    <style>
        body{margin:0;padding:0;font-family:Poppins,sans-serif;background:linear-gradient(135deg,#0d0d0d,#2b0030,#000d49);display:flex;justify-content:center;align-items:center;height:100vh;}
        .card{width:95%;max-width:450px;background:rgba(255,255,255,0.12);padding:25px;border-radius:20px;box-shadow:0 10px 35px rgba(0,0,0,0.6);backdrop-filter:blur(12px);color:white;transition:0.3s;}
        .title{text-align:center;font-size:26px;margin-bottom:15px;}
        .info{margin-bottom:12px;font-size:18px;}
        input{width:100%;padding:12px;border-radius:10px;border:none;margin-top:5px;font-size:16px;}
        button{width:100%;margin-top:18px;padding:14px;font-size:18px;background:#ff0077;border:none;border-radius:12px;cursor:pointer;transition:0.3s;}
        button:hover{background:#ff3399;}
        #msg{text-align:center;margin-top:10px;font-weight:bold;color:#00ffcc;}
    </style>
    </head>
    <body>
    <div style="text-align:center; margin-bottom:15px; color:#00ffcc; font-size:16px; line-height:1.5; padding:0 10px;">
    Gmail বিক্রি করে প্রতিটিতে <strong>১২ টাকা ইনকাম করুন!!!</strong><br>
    মাত্র <strong>১০০ টাকায় বিকাশ/নগদ</strong> এর মাধ্যমে উত্তলন করুন।<br>
    Withdraw পেতে যোগাযোগ করুন:<br>
    Messenger : <span style="color:#ff99cc; cursor:pointer;" onclick="window.open('https://www.facebook.com/profile.php?id=61576962875146','_blank')">Rip Indra</span><br>
    Whatsapp : <strong>01986459062</strong>
</div>
    <div class="card">
        <div class="title">User Submission</div>
        <div class="info"><strong>First Name:</strong> <span id="fname"></span></div>
        <div class="info"><strong>Last Name:</strong> <span id="lname"></span></div>
        <div class="info"><strong>Email:</strong> <span id="email"></span></div>
        <div class="info"><strong>Password:</strong> <span id="password"></span></div>
        <label>Messenger ID Name:</label>
        <input type="text" id="messenger" placeholder="Enter Messenger ID" required>
        <button onclick="submitUser()">Submit</button>
        <div id="msg"></div>
    </div>

    <script>
        let currentUser = null;

        function loadNext(){
            fetch('/next_user')
            .then(res=>res.json())
            .then(data=>{
                if(!data.exists){
                    document.getElementById('fname').innerText = '-';
                    document.getElementById('lname').innerText = '-';
                    document.getElementById('email').innerText = '-';
                    document.getElementById('password').innerText = '-';
                    document.getElementById('messenger').disabled = true;
                    document.getElementById('msg').innerText = 'No Pending Users';
                    currentUser = null;
                } else {
                    currentUser = data;
                    document.getElementById('fname').innerText = data.firstname;
                    document.getElementById('lname').innerText = data.lastname;
                    document.getElementById('email').innerText = data.email;
                    document.getElementById('password').innerText = data.password;
                    document.getElementById('messenger').value = '';
                    document.getElementById('messenger').disabled = false;
                    document.getElementById('msg').innerText = '';
                }
            });
        }

        function submitUser(){
            if(!currentUser) return;
            let messenger = document.getElementById('messenger').value.trim();
            if(messenger===''){ alert('Messenger ID required'); return; }
            fetch('/submit_messenger',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({id: currentUser.id, messenger: messenger})
            })
            .then(res=>res.json())
            .then(data=>{
                if(data.ok){
                    document.getElementById('msg').innerText = 'Submitted Successfully ✅';
                    setTimeout(loadNext,800);
                } else {
                    document.getElementById('msg').innerText = 'Error: '+data.error;
                }
            });
        }

        loadNext();
    </script>
    </body>
    </html>
    """
    return html

# Note: NO app.run() here — ready for Vercel
