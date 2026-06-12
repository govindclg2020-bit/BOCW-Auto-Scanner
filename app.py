from flask import Flask, jsonify, render_template_string, request, session, send_file
import requests
import json
import time
import threading
import os
import io
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'bocw_secret_key_8809219140'

# ========== CONFIGURATION ==========
START_ID = 4885000  # Working ID range (confirmed working)
END_ID = 4886000    # Test range - will work
BATCH_SIZE = 50
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

# ========== DATA FILES ==========
DATA_FILE = 'workers_data.json'
STATUS_FILE = 'scan_status.json'

def save_data():
    """Permanently save data"""
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
    """Load previously saved data"""
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
    """Fetch worker data - FIXED with proper headers and session"""
    
    # Using requests.Session for better connection handling
    session = requests.Session()
    
    # Complete headers to mimic browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': 'bocwboard.bihar.gov.in',
        'Origin': 'https://bocwboard.bihar.gov.in',
        'Referer': 'https://bocwboard.bihar.gov.in/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }
    
    url = f"https://bocwboard.bihar.gov.in/api/workers/generalInfoUserView/{worker_id}"
    
    try:
        print(f"🌐 Fetching ID: {worker_id} (Attempt {attempt})")
        
        response = session.get(url, headers=headers, timeout=30, verify=True)
        
        print(f"📡 Status: {response.status_code} for ID {worker_id}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                # Check if we got valid data
                if data and isinstance(data, dict):
                    # Try different possible field names
                    name = data.get('applicantName') or data.get('applicant_name') or data.get('name') or data.get('workerName')
                    
                    if name and name != 'N/A' and name != '':
                        worker_info = {
                            'id': worker_id,
                            'name': str(name)[:100],
                            'father': str(data.get('fatherHusband') or data.get('father_name') or data.get('fatherName') or 'N/A')[:100],
                            'aadhaar': str(data.get('aadhaarCardNumber') or data.get('aadhaar_number') or data.get('aadhaarNo') or 'N/A'),
                            'mobile': str(data.get('mobileNo') or data.get('mobile_number') or data.get('mobile') or 'N/A'),
                            'regNo': str(data.get('registrationNo') or data.get('registration_number') or data.get('regNo') or 'N/A'),
                            'district': str(data.get('districtEnglish') or data.get('district') or data.get('district_name') or 'N/A'),
                            'address': str(data.get('permanentAddress') or data.get('address') or 'N/A').replace('\n', ' ')[:200],
                            'status': str(data.get('formNumber') or data.get('status') or 'Active'),
                            'fetch_time': datetime.now().isoformat()
                        }
                        print(f"✅ FOUND: ID {worker_id} - {worker_info['name']}")
                        return worker_info
                    else:
                        print(f"⚠️ No valid name in response for ID {worker_id}")
                        print(f"   Response keys: {list(data.keys())[:5] if data else 'None'}")
                else:
                    print(f"⚠️ Invalid response format for ID {worker_id}")
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON Error for ID {worker_id}: {e}")
                print(f"   Response text: {response.text[:100]}...")
        else:
            print(f"❌ HTTP {response.status_code} for ID {worker_id}")
            
    except requests.exceptions.Timeout:
        print(f"⏰ Timeout for ID {worker_id}")
    except requests.exceptions.ConnectionError as e:
        print(f"🔌 Connection error for ID {worker_id}: {e}")
    except Exception as e:
        print(f"❌ Error for ID {worker_id}: {type(e).__name__}: {e}")
    finally:
        session.close()
    
    # Retry logic
    if attempt < MAX_RETRIES:
        wait_time = attempt * 2
        print(f"🔄 Retry {attempt}/{MAX_RETRIES} for ID {worker_id} in {wait_time}s...")
        time.sleep(wait_time)
        return fetch_worker(worker_id, attempt + 1)
    
    print(f"❌ FAILED: ID {worker_id} after {MAX_RETRIES} attempts")
    return None

def background_scanner():
    """Main scanner function"""
    global current_id, all_workers, failed_ids, retry_success_ids, scanned_count, is_running
    
    print(f"\n{'='*60}")
    print(f"🚀 SCANNER STARTED")
    print(f"{'='*60}")
    print(f"📊 Range: {START_ID:,} to {END_ID:,}")
    print(f"⚡ Batch Size: {BATCH_SIZE}, Max Retries: {MAX_RETRIES}")
    print(f"💾 Existing data: {len(all_workers)} workers")
    print(f"{'='*60}\n")
    
    batch_count = 0
    
    while is_running and current_id <= END_ID:
        batch_count += 1
        batch_end = min(current_id + BATCH_SIZE - 1, END_ID)
        print(f"\n📦 BATCH #{batch_count}: IDs {current_id:,} to {batch_end:,}")
        
        for uid in range(current_id, batch_end + 1):
            if not is_running:
                break
            
            worker = fetch_worker(uid)
            scanned_count += 1
            
            if worker:
                all_workers.append(worker)
                print(f"✅ TOTAL: {len(all_workers)} workers collected")
            else:
                failed_ids.append(uid)
                print(f"❌ Failed ID {uid} added to retry list")
            
            current_id = uid + 1
            
            # Save after every 5 records
            if len(all_workers) % 5 == 0 or scanned_count % 20 == 0:
                save_data()
                print(f"💾 Auto-saved at {len(all_workers)} workers")
        
        # Delay between batches
        if is_running and current_id <= END_ID:
            time.sleep(3)
    
    # Retry failed IDs
    if is_running and failed_ids:
        print(f"\n{'='*60}")
        print(f"🔄 RETRYING {len(failed_ids)} FAILED IDs")
        print(f"{'='*60}")
        
        still_failed = []
        for idx, uid in enumerate(failed_ids):
            if not is_running:
                break
            print(f"\n🔄 Retry {idx+1}/{len(failed_ids)}: ID {uid}")
            worker = fetch_worker(uid)
            if worker:
                all_workers.append(worker)
                retry_success_ids.append(uid)
                print(f"✅ RECOVERED: {uid}")
                save_data()
            else:
                still_failed.append(uid)
            time.sleep(2)
        
        failed_ids = still_failed
        save_data()
        print(f"\n📊 Retry complete! Recovered: {len(retry_success_ids)}, Failed: {len(failed_ids)}")
    
    print(f"\n{'='*60}")
    print(f"✅ SCAN COMPLETE")
    print(f"{'='*60}")
    print(f"📊 Total workers found: {len(all_workers):,}")
    print(f"📊 Total scanned: {scanned_count:,}")
    print(f"{'='*60}\n")
    
    is_running = False
    save_data()

# ========== ADMIN PANEL HTML ==========
ADMIN_LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login</title>
    <style>
        body { font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; }
        .login-box { background: white; padding: 40px; border-radius: 20px; width: 350px; text-align: center; }
        h2 { color: #333; margin-bottom: 20px; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; }
        button { width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; }
        .error { color: red; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🔐 Admin Login</h2>
        <form method="post">
            <input type="password" name="password" placeholder="Admin Password" required>
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
    <title>Admin Panel</title>
    <style>
        body { font-family: Arial; background: #f0f0f0; padding: 20px; }
        .container { max-width: 600px; margin: auto; background: white; border-radius: 20px; padding: 25px; }
        h1 { color: #333; text-align: center; }
        h3 { color: #555; margin-top: 20px; }
        .btn { width: 100%; padding: 15px; margin: 10px 0; border: none; border-radius: 10px; font-size: 16px; font-weight: bold; cursor: pointer; }
        .btn-start { background: #28a745; color: white; }
        .btn-stop { background: #dc3545; color: white; }
        .btn-download { background: #17a2b8; color: white; }
        .btn-logout { background: #667eea; color: white; }
        .status { background: #f8f9fa; padding: 15px; border-radius: 10px; margin: 15px 0; text-align: center; }
        .status-running { color: green; font-weight: bold; }
        .status-stopped { color: red; font-weight: bold; }
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 15px 0; }
        .stat-item { background: #e9ecef; padding: 10px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 20px; font-weight: bold; color: #667eea; }
        .stat-label { font-size: 11px; color: #666; }
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
        
        <div class="stats-grid">
            <div class="stat-item"><div class="stat-value" id="statCurrentId">-</div><div class="stat-label">Current ID</div></div>
            <div class="stat-item"><div class="stat-value" id="statTotalFound">0</div><div class="stat-label">Workers Found</div></div>
            <div class="stat-item"><div class="stat-value" id="statScanned">0</div><div class="stat-label">Scanned</div></div>
            <div class="stat-item"><div class="stat-value" id="statProgress">0%</div><div class="stat-label">Progress</div></div>
        </div>
        
        <button class="btn btn-start" id="startBtn">▶️ START SCAN</button>
        <button class="btn btn-stop" id="stopBtn">⏹️ STOP SCAN</button>
        
        <hr>
        <h3>📥 Download Data</h3>
        <button class="btn btn-download" id="downloadCSVBtn">📥 Download CSV</button>
        <button class="btn btn-download" id="downloadJSONBtn">📥 Download JSON</button>
        
        <hr>
        <h3>⚙️ Range Settings</h3>
        <div class="range-input">
            <input type="number" id="startId" placeholder="Start ID">
            <input type="number" id="endId" placeholder="End ID">
        </div>
        <button class="btn" id="updateRangeBtn" style="background:#28a745;">Update Range</button>
        
        <hr>
        <button class="btn btn-logout" id="logoutBtn">🚪 Logout</button>
    </div>
    
    <script>
        async function updateStatus() {
            try {
                const res = await fetch('/api/status?t=' + Date.now());
                const data = await res.json();
                const span = document.getElementById('scanStatus');
                if(data.is_running) {
                    span.innerHTML = '🟢 RUNNING';
                    span.className = 'status-running';
                } else {
                    span.innerHTML = '🔴 STOPPED';
                    span.className = 'status-stopped';
                }
                document.getElementById('statCurrentId').innerHTML = data.current_id?.toLocaleString() || '-';
                document.getElementById('statTotalFound').innerHTML = data.total_found?.toLocaleString() || '0';
                document.getElementById('statScanned').innerHTML = data.scanned_count?.toLocaleString() || '0';
                document.getElementById('statProgress').innerHTML = (data.progress || 0) + '%';
            } catch(e) {}
        }
        
        document.getElementById('startBtn').onclick = () => fetch('/api/start', { method: 'POST' }).then(() => updateStatus());
        document.getElementById('stopBtn').onclick = () => fetch('/api/stop', { method: 'POST' }).then(() => updateStatus());
        document.getElementById('downloadCSVBtn').onclick = () => window.open('/api/download/csv', '_blank');
        document.getElementById('downloadJSONBtn').onclick = () => window.open('/api/download/json', '_blank');
        document.getElementById('updateRangeBtn').onclick = async () => {
            const startId = parseInt(document.getElementById('startId').value);
            const endId = parseInt(document.getElementById('endId').value);
            if(startId && endId && startId < endId) {
                await fetch('/api/update_range', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ start_id: startId, end_id: endId }) });
                alert('Range updated!');
                setTimeout(() => location.reload(), 2000);
            } else { alert('Invalid range'); }
        };
        document.getElementById('logoutBtn').onclick = () => window.location.href = '/admin/logout';
        
        setInterval(updateStatus, 2000);
        updateStatus();
    </script>
</body>
</html>
'''

# ========== API ROUTES ==========
@app.route('/')
def home():
    try:
        with open('index.html', 'r') as f:
            return f.read()
    except:
        return "<h1>BOCW Scanner</h1><p><a href='/admin'>Admin Panel</a></p>"

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
    progress = round((current_id - START_ID) / (END_ID - START_ID) * 100, 2) if END_ID > START_ID else 0
    return jsonify({
        'current_id': current_id,
        'total_found': len(all_workers),
        'failed_count': len(failed_ids),
        'retry_success': len(retry_success_ids),
        'scanned_count': scanned_count,
        'is_running': is_running,
        'progress': progress
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
        time.sleep(1)
        START_ID = new_start
        END_ID = new_end
        current_id = START_ID
        save_data()
        is_running = True
        threading.Thread(target=background_scanner).start()
        return jsonify({'status': 'updated'})
    return jsonify({'error': 'invalid range'}), 400

@app.route('/api/download/csv')
def download_csv():
    if not all_workers:
        return "No data available", 404
    
    output = io.StringIO()
    headers = ['S.No', 'ID', 'Name', 'Father', 'Aadhaar', 'Mobile', 'Registration No', 'District']
    output.write(','.join(headers) + '\n')
    
    for i, w in enumerate(all_workers):
        row = [str(i+1), str(w.get('id', '')), f"\"{w.get('name', 'N/A')}\"", f"\"{w.get('father', 'N/A')}\"", f"\"{w.get('aadhaar', 'N/A')}\"", f"\"{w.get('mobile', 'N/A')}\"", f"\"{w.get('regNo', 'N/A')}\"", f"\"{w.get('district', 'N/A')}\""]
        output.write(','.join(row) + '\n')
    
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name=f'bocw_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

@app.route('/api/download/json')
def download_json():
    return send_file(io.BytesIO(json.dumps(all_workers, indent=2).encode('utf-8')), mimetype='application/json', as_attachment=True, download_name=f'bocw_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

# ========== START SERVER ==========
if __name__ == '__main__':
    load_data()
    
    if is_running:
        scan_thread = threading.Thread(target=background_scanner)
        scan_thread.daemon = True
        scan_thread.start()
        print("🚀 Scanner auto-started")
    
    app.run(host='0.0.0.0', port=10000)
