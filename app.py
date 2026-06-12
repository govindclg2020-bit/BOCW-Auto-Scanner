from flask import Flask, jsonify, render_template_string, request, session, send_file
import requests
import json
import time
import threading
import os
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'bocw_secret_key_8809219140'

# ========== CONFIGURATION ==========
START_ID = 4885000
END_ID = 5000000
BATCH_SIZE = 100
MAX_RETRIES = 3
ADMIN_PASSWORD = "8809219140"

# ========== GLOBAL VARIABLES ==========
all_workers = []
failed_ids = []
retry_success_ids = []
scanned_count = 0
current_id = START_ID
is_running = True
scan_thread = None

DATA_FILE = 'workers_data.json'
STATUS_FILE = 'scan_status.json'

def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump({
                'workers': all_workers,
                'failed': failed_ids,
                'retry_success': retry_success_ids,
                'scanned': scanned_count,
                'current_id': current_id,
                'last_updated': datetime.now().isoformat()
            }, f, indent=2)
        
        with open(STATUS_FILE, 'w') as f:
            json.dump({
                'current_id': current_id,
                'total_found': len(all_workers),
                'failed_count': len(failed_ids),
                'retry_success': len(retry_success_ids),
                'scanned_count': scanned_count,
                'is_running': is_running,
                'start_id': START_ID,
                'end_id': END_ID,
                'progress': round((current_id - START_ID) / (END_ID - START_ID) * 100, 2) if END_ID > START_ID else 0
            }, f, indent=2)
        print(f"💾 Saved: {len(all_workers)} workers")
    except Exception as e:
        print(f"Save error: {e}")

def load_data():
    global all_workers, failed_ids, retry_success_ids, scanned_count, current_id
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                all_workers = data.get('workers', [])
                failed_ids = data.get('failed', [])
                retry_success_ids = data.get('retry_success', [])
                scanned_count = data.get('scanned', 0)
                current_id = data.get('current_id', START_ID)
            print(f"✅ Loaded {len(all_workers)} workers")
    except Exception as e:
        print(f"Load error: {e}")

def fetch_worker(worker_id, attempt=1):
    url = f"https://bocwboard.bihar.gov.in/api/workers/generalInfoUserView/{worker_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Connection': 'keep-alive',
        'Referer': 'https://bocwboard.bihar.gov.in/'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data and data.get('applicantName'):
                return {
                    'id': worker_id,
                    'name': data.get('applicantName', 'N/A'),
                    'father': data.get('fatherHusband', 'N/A'),
                    'aadhaar': data.get('aadhaarCardNumber', 'N/A'),
                    'mobile': data.get('mobileNo', 'N/A'),
                    'regNo': data.get('registrationNo', 'N/A'),
                    'district': data.get('districtEnglish', 'N/A'),
                    'address': (data.get('permanentAddress', 'N/A')).replace('\n', ' '),
                    'status': data.get('formNumber', 'Active')
                }
    except Exception as e:
        print(f"Error ID {worker_id}: {e}")
    
    if attempt < MAX_RETRIES:
        time.sleep(2)
        return fetch_worker(worker_id, attempt + 1)
    return None

def background_scanner():
    global current_id, all_workers, failed_ids, scanned_count, is_running
    
    print(f"🚀 Scanner started: {START_ID} to {END_ID}")
    
    while is_running and current_id <= END_ID:
        batch_end = min(current_id + BATCH_SIZE - 1, END_ID)
        
        for uid in range(current_id, batch_end + 1):
            if not is_running:
                break
            
            worker = fetch_worker(uid)
            scanned_count += 1
            
            if worker:
                all_workers.append(worker)
                print(f"✅ Found: {worker['name']} (Total: {len(all_workers)})")
            else:
                failed_ids.append(uid)
                print(f"❌ Failed: {uid}")
            
            current_id = uid + 1
            
            if len(all_workers) % 10 == 0:
                save_data()
        
        time.sleep(1)
    
    save_data()
    print(f"✅ Scan complete! Total workers: {len(all_workers)}")

@app.route('/')
def home():
    try:
        with open('index.html', 'r') as f:
            return f.read()
    except:
        return "<h1>BOCW Scanner</h1>"

@app.route('/api/status')
def api_status():
    return jsonify({
        'current_id': current_id,
        'total_found': len(all_workers),
        'failed_count': len(failed_ids),
        'scanned_count': scanned_count,
        'is_running': is_running,
        'progress': round((current_id - START_ID) / (END_ID - START_ID) * 100, 2) if END_ID > START_ID else 0,
        'start_id': START_ID,
        'end_id': END_ID
    })

@app.route('/api/data')
def api_data():
    return jsonify(all_workers)

@app.route('/api/start', methods=['POST'])
def api_start():
    global is_running, scan_thread
    if not is_running:
        is_running = True
        scan_thread = threading.Thread(target=background_scanner)
        scan_thread.daemon = True
        scan_thread.start()
        return jsonify({'status': 'started'})
    return jsonify({'status': 'already_running'})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    global is_running
    is_running = False
    save_data()
    return jsonify({'status': 'stopped'})

@app.route('/api/update_range', methods=['POST'])
def api_update_range():
    global START_ID, END_ID, current_id, is_running
    data = request.json
    new_start = data.get('start_id')
    new_end = data.get('end_id')
    
    if new_start and new_end and new_start < new_end:
        is_running = False
        time.sleep(2)
        START_ID = new_start
        END_ID = new_end
        current_id = START_ID
        save_data()
        is_running = True
        threading.Thread(target=background_scanner).start()
        return jsonify({'status': 'updated'})
    return jsonify({'error': 'invalid range'}), 400

@app.route('/api/reset_data', methods=['POST'])
def reset_data():
    global all_workers, failed_ids, retry_success_ids, scanned_count, current_id
    all_workers = []
    failed_ids = []
    retry_success_ids = []
    scanned_count = 0
    current_id = START_ID
    save_data()
    return jsonify({'status': 'reset'})

@app.route('/api/download/csv')
def download_csv():
    if not all_workers:
        return "No data available", 404
    
    output = io.StringIO()
    headers = ['S.No', 'User ID', 'Name', 'Father/Husband', 'Aadhaar', 'Mobile', 'Registration No', 'District']
    output.write(','.join(headers) + '\n')
    
    for i, w in enumerate(all_workers):
        row = [str(i+1), str(w.get('id', '')), f"\"{w.get('name', 'N/A')}\"", f"\"{w.get('father', 'N/A')}\"", f"\"{w.get('aadhaar', 'N/A')}\"", f"\"{w.get('mobile', 'N/A')}\"", f"\"{w.get('regNo', 'N/A')}\"", f"\"{w.get('district', 'N/A')}\""]
        output.write(','.join(row) + '\n')
    
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name=f'bocw_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

@app.route('/api/download/json')
def download_json():
    return send_file(io.BytesIO(json.dumps(all_workers, indent=2).encode('utf-8')), mimetype='application/json', as_attachment=True, download_name=f'bocw_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

if __name__ == '__main__':
    load_data()
    if is_running:
        scan_thread = threading.Thread(target=background_scanner)
        scan_thread.daemon = True
        scan_thread.start()
    app.run(host='0.0.0.0', port=10000)
