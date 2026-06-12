from flask import Flask, jsonify, request, send_file
import requests
import json
import time
import threading
import os
import io
from datetime import datetime

app = Flask(__name__)

START_ID = 4885000
END_ID = 5000000
BATCH_SIZE = 50
MAX_RETRIES = 3

all_workers = []
failed_ids = []
scanned_count = 0
current_id = START_ID
is_running = True

DATA_FILE = 'workers_data.json'

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({'workers': all_workers, 'failed': failed_ids, 'scanned': scanned_count, 'current_id': current_id}, f)

def load_data():
    global all_workers, failed_ids, scanned_count, current_id
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            all_workers = data.get('workers', [])
            failed_ids = data.get('failed', [])
            scanned_count = data.get('scanned', 0)
            current_id = data.get('current_id', START_ID)

def fetch_worker(uid):
    url = f"https://bocwboard.bihar.gov.in/api/workers/generalInfoUserView/{uid}"
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    for i in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                data = r.json()
                if data and data.get('applicantName'):
                    return {'id': uid, 'name': data['applicantName'], 'father': data.get('fatherHusband','N/A'), 'aadhaar': data.get('aadhaarCardNumber','N/A'), 'mobile': data.get('mobileNo','N/A'), 'regNo': data.get('registrationNo','N/A'), 'district': data.get('districtEnglish','N/A')}
            time.sleep(2)
        except: time.sleep(2)
    return None

def scanner():
    global current_id, all_workers, scanned_count, is_running
    while is_running and current_id <= END_ID:
        batch_end = min(current_id + BATCH_SIZE - 1, END_ID)
        for uid in range(current_id, batch_end + 1):
            if not is_running: break
            w = fetch_worker(uid)
            scanned_count += 1
            if w:
                all_workers.append(w)
                print(f"Found: {w['name']} ({len(all_workers)})")
            current_id = uid + 1
            if len(all_workers) % 10 == 0:
                save_data()
        time.sleep(1)
    save_data()
    print(f"Scan complete! Total: {len(all_workers)}")

@app.route('/')
def home():
    with open('index.html', 'r') as f:
        return f.read()

@app.route('/api/status')
def status():
    return jsonify({
        'current_id': current_id,
        'total_found': len(all_workers),
        'scanned_count': scanned_count,
        'is_running': is_running,
        'start_id': START_ID,
        'end_id': END_ID,
        'progress': round((current_id - START_ID) / (END_ID - START_ID) * 100, 2) if END_ID > START_ID else 0
    })

@app.route('/api/data')
def data():
    return jsonify(all_workers)

@app.route('/api/start', methods=['POST'])
def start():
    global is_running
    if not is_running:
        is_running = True
        threading.Thread(target=scanner).start()
    return jsonify({'ok': True})

@app.route('/api/stop', methods=['POST'])
def stop():
    global is_running
    is_running = False
    save_data()
    return jsonify({'ok': True})

@app.route('/api/update_range', methods=['POST'])
def update_range():
    global START_ID, END_ID, current_id, is_running
    data = request.json
    new_start = data.get('start_id')
    new_end = data.get('end_id')
    if new_start and new_end and new_start < new_end:
        is_running = False
        time.sleep(1)
        START_ID = new_start
        END_ID = new_end
        current_id = START_ID
        save_data()
        is_running = True
        threading.Thread(target=scanner).start()
        return jsonify({'ok': True})
    return jsonify({'error': 'invalid range'}), 400

@app.route('/api/download/csv')
def download_csv():
    if not all_workers:
        return "No data", 404
    output = io.StringIO()
    output.write('ID,Name,Father,Aadhaar,Mobile,RegNo,District\n')
    for w in all_workers:
        output.write(f"{w['id']},{w['name']},{w['father']},{w['aadhaar']},{w['mobile']},{w['regNo']},{w['district']}\n")
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name=f'bocw_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

if __name__ == '__main__':
    load_data()
    if is_running:
        threading.Thread(target=scanner).start()
    app.run(host='0.0.0.0', port=10000)
