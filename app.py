from flask import Flask, jsonify, render_template_string, request, session
import requests
import json
import time
import threading
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'bocw_secret_key_8809219140'

# ========== CONFIGURATION ==========
START_ID = 100000
END_ID = 10000000
BATCH_SIZE = 100
MAX_RETRIES = 2
ADMIN_PASSWORD = "8809219140"

# ========== GLOBAL VARIABLES ==========
all_workers = []
failed_ids = []
retry_success_ids = []
scanned_count = 0
current_id = START_ID
is_running = True
scan_thread = None
last_save_time = 0

# ========== DATA PERSISTENCE ==========
DATA_FILE = 'workers_data.json'
STATUS_FILE = 'scan_status.json'

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
        print(f"Loaded {len(all_workers)} workers, {len(failed_ids)} failed")
    except Exception as e:
        print(f"Error loading data: {e}")

def save_data():
    global last_save_time
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump({
                'workers': all_workers,
                'failed': failed_ids,
                'retry_success': retry_success_ids,
                'scanned': scanned_count,
                'current_id': current_id
            }, f, indent=2)
        with open(STATUS_FILE, 'w') as f:
            json.dump({
                'current_id': current_id,
                'total_found': len(all_workers),
                'failed_count': len(failed_ids),
                'retry_success': len(retry_success_ids),
                'scanned_count': scanned_count,
                'is_running': is_running,
                'progress': round((current_id - START_ID) / (END_ID - START_ID) * 100, 2)
            }, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

def fetch_worker(worker_id, attempt=1):
    """Fetch worker data with retry logic"""
    url = f"https://bocwboard.bihar.gov.in/api/workers/generalInfoUserView/{worker_id}"
    try:
        response = requests.get(url, timeout=15)
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
        if attempt < MAX_RETRIES:
            print(f"Retry {attempt}/{MAX_RETRIES} for ID {worker_id}")
            time.sleep(2)
            return fetch_worker(worker_id, attempt + 1)
    except Exception as e:
        if attempt < MAX_RETRIES:
            print(f"Error ID {worker_id}, retry {attempt}/{MAX_RETRIES}")
            time.sleep(2)
            return fetch_worker(worker_id, attempt + 1)
    return None

def background_scanner():
    global current_id, all_workers, failed_ids, retry_success_ids, scanned_count, is_running
    
    print(f"🚀 Scanner started! Range: {START_ID} to {END_ID}")
    print(f"⚡ Batch Size: {BATCH_SIZE}, Max Retries: {MAX_RETRIES}")
    
    while is_running and current_id <= END_ID:
        batch_end = min(current_id + BATCH_SIZE - 1, END_ID)
        print(f"📊 Processing batch: {current_id} to {batch_end}")
        
        for uid in range(current_id, batch_end + 1):
            if not is_running:
                break
            
            print(f"🔍 Scanning ID: {uid}")
            worker = fetch_worker(uid)
            scanned_count += 1
            
            if worker:
                all_workers.append(worker)
                print(f"✅ Found: {worker['name']} (Total: {len(all_workers)})")
            else:
                failed_ids.append(uid)
                print(f"❌ Failed: {uid}")
            
            current_id = uid + 1
            
            # Save every 50 records
            if len(all_workers) % 50 == 0 or scanned_count % 100 == 0:
                save_data()
        
        # Batch delay
        time.sleep(1)
    
    # Retry failed IDs
    if is_running and failed_ids:
        print(f"🔄 Retrying {len(failed_ids)} failed IDs...")
        still_failed = []
        for uid in failed_ids:
            if not is_running:
                break
            print(f"🔄 Retrying ID {uid}")
            worker = fetch_worker(uid)
            if worker:
                all_workers.append(worker)
                retry_success_ids.append(uid)
                print(f"✅ Recovered: {uid}")
            else:
                still_failed.append(uid)
            time.sleep(1)
        failed_ids = still_failed
        save_data()
    
    print(f"✅ Scan complete! Total: {len(all_workers)} workers")
    is_running = False
    save_data()

# ========== ADMIN AUTH DECORATOR ==========
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            if request.is_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return render_template_string(ADMIN_LOGIN_HTML)
        return f(*args, **kwargs)
    return decorated_function

# ========== ADMIN LOGIN HTML ==========
ADMIN_LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login - BOCW Scanner</title>
    <style>
        body { font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; }
        .login-box { background: white; padding: 30px; border-radius: 20px; width: 350px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
        h2 { color: #333; margin-bottom: 20px; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; }
        button { width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; font-weight: bold; }
        .error { color: red; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🔐 Admin Login</h2>
        <form method="post">
            <input type="password" name="password" placeholder="Enter Admin Password" required>
            <button type="submit">Login</button>
        </form>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
    </div>
</body>
</html>
'''

ADMIN_PANEL_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Panel - BOCW Scanner</title>
    <style>
        body { font-family: Arial; background: #f0f0f0; padding: 20px; }
        .container { max-width: 600px; margin: auto; background: white; border-radius: 20px; padding: 25px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
        h1 { color: #333; text-align: center; }
        .btn { width: 100%; padding: 15px; margin: 10px 0; border: none; border-radius: 10px; font-size: 16px; font-weight: bold; cursor: pointer; }
        .btn-start { background: #28a745; color: white; }
        .btn-stop { background: #dc3545; color: white; }
        .btn-download-csv { background: #17a2b8; color: white; }
        .btn-download-json { background: #ffc107; color: #333; }
        .btn-clear { background: #6c757d; color: white; }
        .btn-logout { background: #667eea; color: white; }
        .status { background: #f8f9fa; padding: 15px; border-radius: 10px; margin: 15px 0; text-align: center; }
        .range-input { display: flex; gap: 10px; margin: 10px 0; }
        .range-input input { flex: 1; padding: 10px; border: 2px solid #ddd; border-radius: 8px; }
        hr { margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 Admin Control Panel</h1>
        <div class="status">
            <strong>Scanner Status:</strong> <span id="scanStatus">Loading...</span>
        </div>
        
        <button class="btn btn-start" id="startBtn">▶️ START SCAN</button>
        <button class="btn btn-stop" id="stopBtn">⏹️ STOP SCAN</button>
        
        <hr>
        <h3>📥 Download Data</h3>
        <button class="btn btn-download-csv" id="downloadCSVBtn">📥 Download CSV</button>
        <button class="btn btn-download-json" id="downloadJSONBtn">📥 Download JSON</button>
        <button class="btn btn-clear" id="clearConsoleBtn">🗑️ Clear Console Logs</button>
        
        <hr>
        <h3>⚙️ Scan Range Settings</h3>
        <div class="range-input">
            <input type="number" id="startId" placeholder="Start ID">
            <input type="number" id="endId" placeholder="End ID">
        </div>
        <button class="btn" id="updateRangeBtn" style="background:#28a745;">Update Range & Restart</button>
        
        <hr>
        <button class="btn btn-logout" id="logoutBtn">🚪 Logout</button>
    </div>
    
    <script>
        async function apiCall(endpoint, method='GET', body=null) {
            const res = await fetch(endpoint, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: body ? JSON.stringify(body) : null
            });
            return res.json();
        }
        
        async function updateStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('scanStatus').innerHTML = data.is_running ? '🟢 RUNNING' : '🔴 STOPPED';
                document.getElementById('scanStatus').style.color = data.is_running ? 'green' : 'red';
            } catch(e) {}
        }
        
        document.getElementById('startBtn').onclick = () => {
            fetch('/api/start', { method: 'POST' }).then(() => updateStatus());
        };
        document.getElementById('stopBtn').onclick = () => {
            fetch('/api/stop', { method: 'POST' }).then(() => updateStatus());
        };
        document.getElementById('downloadCSVBtn').onclick = () => {
            window.open('/api/download/csv', '_blank');
        };
        document.getElementById('downloadJSONBtn').onclick = () => {
            window.open('/api/download/json', '_blank');
        };
        document.getElementById('clearConsoleBtn').onclick = () => {
            fetch('/api/clear_console', { method: 'POST' });
        };
        document.getElementById('updateRangeBtn').onclick = async () => {
            const startId = parseInt(document.getElementById('startId').value);
            const endId = parseInt(document.getElementById('endId').value);
            if(startId && endId && startId < endId) {
                await apiCall('/api/update_range', 'POST', { start_id: startId, end_id: endId });
                alert('Range updated! Scanner will restart.');
                updateStatus();
            } else {
                alert('Enter valid range (Start < End)');
            }
        };
        document.getElementById('logoutBtn').onclick = () => {
            window.location.href = '/admin/logout';
        };
        
        setInterval(updateStatus, 2000);
        updateStatus();
    </script>
</body>
</html>
'''

# ========== API ROUTES ==========
@app.route('/')
def home():
    return render_template_string(open('index.html').read() if os.path.exists('index.html') else '<h1>Loading...</h1>')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return render_template_string(ADMIN_PANEL_HTML)
        return render_template_string(ADMIN_LOGIN_HTML, error='Wrong password!')
    if session.get('admin_logged_in'):
        return render_template_string(ADMIN_PANEL_HTML)
    return render_template_string(ADMIN_LOGIN_HTML)

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return '<script>window.close();</script>'

@app.route('/api/status')
def api_status():
    return jsonify({
        'current_id': current_id,
        'total_found': len(all_workers),
        'failed_count': len(failed_ids),
        'retry_success': len(retry_success_ids),
        'scanned_count': scanned_count,
        'is_running': is_running,
        'progress': round((current_id - START_ID) / (END_ID - START_ID) * 100, 2),
        'start_id': START_ID,
        'end_id': END_ID
    })

@app.route('/api/data')
def api_data():
    return jsonify(all_workers)

@app.route('/api/start', methods=['POST'])
def api_start():
    global is_running, scan_thread, current_id
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
    global START_ID, END_ID, current_id, is_running, all_workers, failed_ids, retry_success_ids, scanned_count
    data = request.json
    new_start = data.get('start_id')
    new_end = data.get('end_id')
    if new_start and new_end and new_start < new_end:
        is_running = False
        time.sleep(1)
        START_ID = new_start
        END_ID = new_end
        current_id = START_ID
        all_workers = []
        failed_ids = []
        retry_success_ids = []
        scanned_count = 0
        save_data()
        is_running = True
        threading.Thread(target=background_scanner).start()
        return jsonify({'status': 'updated'})
    return jsonify({'error': 'invalid range'}), 400

@app.route('/api/download/csv')
def download_csv():
    if not all_workers:
        return "No data available", 404
    headers = ['S.No', 'User ID', 'Name', 'Father/Husband', 'Aadhaar', 'Mobile', 'Registration No', 'Address', 'District', 'Status']
    rows = [[i+1, w['id'], w['name'], w['father'], w['aadhaar'], w['mobile'], w['regNo'], w.get('address', 'N/A'), w['district'], w.get('status', 'Active')] for i, w in enumerate(all_workers)]
    csv_lines = [','.join(map(str, row)) for row in [headers] + rows]
    csv_data = '\n'.join(csv_lines)
    return csv_data, 200, {'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=bocw_data.csv'}

@app.route('/api/download/json')
def download_json():
    return jsonify(all_workers)

@app.route('/api/clear_console', methods=['POST'])
def clear_console():
    return jsonify({'status': 'cleared'})

# ========== START SERVER ==========
if __name__ == '__main__':
    load_data()
    if is_running:
        scan_thread = threading.Thread(target=background_scanner)
        scan_thread.daemon = True
        scan_thread.start()
    app.run(host='0.0.0.0', port=10000)
