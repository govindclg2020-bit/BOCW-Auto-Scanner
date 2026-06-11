import requests
import json
import time
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ========== CONFIGURATION ==========
START_ID = 4885000
END_ID = 4935000
PORT = 8000

# ========== SCANNER (Background Work) ==========
all_workers = []
is_running = True

def fetch_worker(worker_id):
    url = f"https://bocwboard.bihar.gov.in/api/workers/generalInfoUserView/{worker_id}"
    for retry in range(5):
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
                        'fetch_time': datetime.now().isoformat()
                    }
            time.sleep(2)
        except:
            time.sleep(2)
    return None

def background_scanner():
    global all_workers, is_running
    print(f"🟢 Scanner started from ID {START_ID}")
    
    # Load existing data
    if os.path.exists('workers_data.json'):
        with open('workers_data.json', 'r') as f:
            all_workers = json.load(f)
    
    current_id = START_ID
    if all_workers:
        existing_ids = [w['id'] for w in all_workers]
        current_id = max(existing_ids) + 1 if existing_ids else START_ID
    
    while current_id <= END_ID and is_running:
        print(f"Scanning ID: {current_id}")
        worker = fetch_worker(current_id)
        
        if worker:
            all_workers.append(worker)
            print(f"✅ Found: {worker['name']} (Total: {len(all_workers)})")
        else:
            print(f"❌ No data for ID {current_id}")
        
        # Save every 10 records
        if len(all_workers) % 10 == 0:
            with open('workers_data.json', 'w') as f:
                json.dump(all_workers, f, indent=2)
        
        # Update status
        status = {
            'current_id': current_id,
            'total_found': len(all_workers),
            'progress': round((current_id - START_ID) / (END_ID - START_ID) * 100, 2),
            'last_update': datetime.now().isoformat(),
            'is_running': True
        }
        with open('scan_status.json', 'w') as f:
            json.dump(status, f)
        
        current_id += 1
        time.sleep(2)
    
    # Final save
    with open('workers_data.json', 'w') as f:
        json.dump(all_workers, f, indent=2)
    print("✅ Scan complete!")

# ========== WEB SERVER (To show data) ==========
class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(get_index_html().encode())
        elif self.path == '/scan_status.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            if os.path.exists('scan_status.json'):
                with open('scan_status.json', 'r') as f:
                    self.wfile.write(f.read().encode())
            else:
                self.wfile.write(b'{}')
        elif self.path == '/workers_data.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            if os.path.exists('workers_data.json'):
                with open('workers_data.json', 'r') as f:
                    self.wfile.write(f.read().encode())
            else:
                self.wfile.write(b'[]')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Keep logs clean

def get_index_html():
    return """<!DOCTYPE html>
<html>
<head>
    <title>BOCW Scanner Live</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial; padding: 20px; background: #f0f0f0; }
        .container { max-width: 900px; margin: auto; background: white; padding: 20px; border-radius: 10px; }
        pre { background: #1e1e1e; color: #0f0; padding: 15px; border-radius: 8px; overflow-x: auto; }
        .status { color: #28a745; font-weight: bold; }
        button { padding: 10px 15px; margin: 5px; cursor: pointer; }
        input { padding: 8px; margin: 5px; width: 200px; }
    </style>
</head>
<body>
<div class="container">
    <h1>🤖 BOCW Auto Scanner</h1>
    <p>Status: <span class="status" id="statusText">🟢 Running</span></p>
    
    <h3>📊 Live Scan Status</h3>
    <pre id="status">Loading...</pre>
    
    <h3>🔍 Search Worker</h3>
    <select id="searchType">
        <option value="id">User ID</option>
        <option value="aadhaar">Aadhaar</option>
        <option value="regNo">Registration No</option>
    </select>
    <input type="text" id="searchValue" placeholder="Enter value">
    <button onclick="search()">Search</button>
    <button onclick="showAll()">Show All (first 50)</button>
    
    <h3>📋 Results</h3>
    <pre id="results">Click "Show All" to load data</pre>
    
    <p>📥 <a href="/workers_data.json" target="_blank">Download All Data (JSON)</a></p>
    <p>Last update: <span id="lastUpdate">-</span></p>
</div>

<script>
    let allData = [];
    
    async function updateStatus() {
        try {
            const res = await fetch('/scan_status.json?t=' + Date.now());
            const data = await res.json();
            document.getElementById('status').innerHTML = JSON.stringify(data, null, 2);
            document.getElementById('lastUpdate').innerText = new Date().toLocaleString();
        } catch(e) {}
    }
    
    async function loadAllData() {
        const res = await fetch('/workers_data.json');
        allData = await res.json();
        document.getElementById('results').innerHTML = `Loaded ${allData.length} records. Click "Show All" to view.`;
    }
    
    async function search() {
        const type = document.getElementById('searchType').value;
        const value = document.getElementById('searchValue').value;
        
        if(!value) { alert('Enter search value'); return; }
        
        let filtered = allData.filter(w => {
            if(type === 'id') return w.id == value;
            if(type === 'aadhaar') return w.aadhaar && w.aadhaar.includes(value);
            if(type === 'regNo') return w.regNo && w.regNo.toLowerCase().includes(value.toLowerCase());
            return false;
        });
        
        document.getElementById('results').innerHTML = filtered.length ? 
            JSON.stringify(filtered.slice(0, 20), null, 2) : 'No results found';
    }
    
    function showAll() {
        document.getElementById('results').innerHTML = JSON.stringify(allData.slice(0, 50), null, 2);
    }
    
    updateStatus();
    loadAllData();
    setInterval(updateStatus, 5000);
</script>
</body>
</html>"""

def start_server():
    server = HTTPServer(('0.0.0.0', PORT), MyHandler)
    print(f"🌐 Web server running on port {PORT}")
    server.serve_forever()

# ========== RUN BOTH ==========
if __name__ == '__main__':
    # Start scanner in background thread
    scanner_thread = threading.Thread(target=background_scanner)
    scanner_thread.daemon = True
    scanner_thread.start()
    
    # Start web server (this runs forever)
    start_server()
