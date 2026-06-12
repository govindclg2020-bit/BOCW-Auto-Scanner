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
END_ID = 4885100  # Small range for testing
all_workers = []
scanned_count = 0
current_id = START_ID
is_running = True

def fetch_worker(uid):
    url = f"https://bocwboard.bihar.gov.in/api/workers/generalInfoUserView/{uid}"
    
    # Try multiple approaches
    headers_list = [
        {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept': 'application/json'},
        {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', 'Accept': 'application/json'},
        {'User-Agent': 'curl/7.68.0', 'Accept': 'application/json'}
    ]
    
    for headers in headers_list:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data and data.get('applicantName'):
                    return {
                        'id': uid,
                        'name': data.get('applicantName', 'N/A'),
                        'father': data.get('fatherHusband', 'N/A'),
                        'aadhaar': data.get('aadhaarCardNumber', 'N/A'),
                        'mobile': data.get('mobileNo', 'N/A'),
                        'regNo': data.get('registrationNo', 'N/A'),
                        'district': data.get('districtEnglish', 'N/A')
                    }
            time.sleep(1)
        except Exception as e:
            print(f"Error {uid}: {e}")
            continue
    return None

def scanner():
    global current_id, all_workers, scanned_count, is_running
    print(f"Scanner Started: {START_ID} to {END_ID}")
    
    while is_running and current_id <= END_ID:
        worker = fetch_worker(current_id)
        scanned_count += 1
        
        if worker:
            all_workers.append(worker)
            print(f"✅ Found: {worker['name']} (Total: {len(all_workers)})")
            # Save immediately
            with open('workers_data.json', 'w') as f:
                json.dump(all_workers, f)
        else:
            print(f"❌ No data for ID: {current_id}")
        
        current_id += 1
        time.sleep(1.5)
    
    print(f"Scan Complete! Total Workers: {len(all_workers)}")

# HTML (सिंपल - सिर्फ काम करने के लिए)
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>BOCW Scanner</title>
    <style>
        body{font-family:monospace;padding:20px;background:#fff;}
        .container{max-width:1200px;margin:auto;border:1px solid #000;padding:20px;}
        h1{font-size:20px;}
        .stats{display:flex;gap:20px;margin:20px 0;flex-wrap:wrap;}
        .stat{border:1px solid #ccc;padding:10px;min-width:120px;}
        .stat-value{font-size:28px;font-weight:bold;}
        input,select,button{padding:10px;margin:5px;border:1px solid #000;background:#fff;}
        button{cursor:pointer;}
        table{width:100%;border-collapse:collapse;margin-top:15px;}
        th,td{border:1px solid #ccc;padding:8px;text-align:left;}
        th{background:#f5f5f5;}
        .admin-btn{position:fixed;bottom:10px;right:10px;border:1px solid #000;padding:8px 12px;cursor:pointer;}
        .modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);}
        .modal-content{background:#fff;width:400px;margin:100px auto;padding:20px;border:2px solid #000;}
    </style>
</head>
<body>
<div class="container">
    <h1>BOCW WORKER DATA SCANNER</h1>
    
    <div class="stats">
        <div class="stat"><div class="stat-value" id="workerCount">0</div><div>Workers Found</div></div>
        <div class="stat"><div class="stat-value" id="currentId">-</div><div>Current ID</div></div>
        <div class="stat"><div class="stat-value" id="progress">0%</div><div>Progress</div></div>
    </div>
    
    <div>
        <select id="searchType">
            <option value="id">ID</option>
            <option value="aadhaar">Aadhaar</option>
            <option value="regNo">Reg No</option>
        </select>
        <input type="text" id="searchValue" placeholder="Search...">
        <button onclick="searchData()">Search</button>
        <button onclick="resetSearch()">Reset</button>
    </div>
    
    <div style="overflow-x:auto">
        <table id="dataTable">
            <thead><tr><th>ID</th><th>Name</th><th>Father</th><th>Aadhaar</th><th>Mobile</th><th>Reg No</th></tr></thead>
            <tbody id="tableBody"><tr><td colspan="6">Loading... Scanner is running</td></tr></tbody>
        </table>
    </div>
</div>

<div class="admin-btn" onclick="openAdmin()">[ADMIN]</div>

<div id="adminModal" class="modal">
    <div class="modal-content">
        <h3>ADMIN LOGIN</h3>
        <input type="password" id="adminPass" placeholder="Password">
        <button onclick="adminLogin()">Login</button>
        <div id="adminPanel" style="display:none; margin-top:15px;">
            <button onclick="startScan()">START SCAN</button>
            <button onclick="stopScan()">STOP SCAN</button>
            <button onclick="downloadCSV()">DOWNLOAD CSV</button>
            <hr>
            <label>Start ID: <input type="number" id="setStart" style="width:100%"></label>
            <label>End ID: <input type="number" id="setEnd" style="width:100%"></label>
            <button onclick="updateRange()">UPDATE RANGE</button>
            <hr>
            <p>Status: <span id="adminStatus">-</span></p>
            <button onclick="closeAdmin()">Close</button>
        </div>
    </div>
</div>

<script>
let allData = [];
const PASSWORD = "8809219140";

async function loadData(){
    try{
        let res = await fetch('/api/data?t='+Date.now());
        if(res.ok){
            allData = await res.json();
            document.getElementById('workerCount').innerHTML = allData.length;
            displayTable();
        }
    }catch(e){}
}

async function loadStatus(){
    try{
        let res = await fetch('/api/status?t='+Date.now());
        if(res.ok){
            let d = await res.json();
            document.getElementById('currentId').innerHTML = d.current_id;
            document.getElementById('progress').innerHTML = d.progress+'%';
            if(document.getElementById('adminStatus')){
                document.getElementById('adminStatus').innerHTML = d.is_running ? 'RUNNING' : 'STOPPED';
                document.getElementById('setStart').value = d.start_id;
                document.getElementById('setEnd').value = d.end_id;
            }
        }
    }catch(e){}
}

function displayTable(){
    let tbody = document.getElementById('tableBody');
    if(allData.length === 0){
        tbody.innerHTML = '<tr><td colspan="6">No data yet. Scanner is running...</td></tr>';
        return;
    }
    let html = '';
    for(let w of allData.slice(0,100)){
        html += `<tr><td>${w.id}</td><td>${w.name}</td><td>${w.father}</td><td>${w.aadhaar}</td><td>${w.mobile}</td><td>${w.regNo}</td></tr>`;
    }
    tbody.innerHTML = html;
}

function searchData(){
    let type = document.getElementById('searchType').value;
    let val = document.getElementById('searchValue').value.trim();
    if(!val){ displayTable(); return; }
    let filtered = allData.filter(w => {
        if(type=='id') return w.id == val;
        if(type=='aadhaar') return w.aadhaar && w.aadhaar.includes(val);
        if(type=='regNo') return w.regNo && w.regNo.includes(val);
        return false;
    });
    let tbody = document.getElementById('tableBody');
    if(filtered.length===0){
        tbody.innerHTML = '<tr><td colspan="6">No results</td></tr>';
    } else {
        let html = '';
        for(let w of filtered){
            html += `<tr><td>${w.id}</td><td>${w.name}</td><td>${w.father}</td><td>${w.aadhaar}</td><td>${w.mobile}</td><td>${w.regNo}</td></tr>`;
        }
        tbody.innerHTML = html;
    }
}

function resetSearch(){
    document.getElementById('searchValue').value = '';
    displayTable();
}

function openAdmin(){
    document.getElementById('adminModal').style.display = 'block';
}

function closeAdmin(){
    document.getElementById('adminModal').style.display = 'none';
}

function adminLogin(){
    let pwd = document.getElementById('adminPass').value;
    if(pwd === PASSWORD){
        document.getElementById('adminPanel').style.display = 'block';
        loadStatus();
    } else {
        alert('Wrong password');
    }
}

async function startScan(){
    await fetch('/api/start', {method:'POST'});
    loadStatus();
}

async function stopScan(){
    await fetch('/api/stop', {method:'POST'});
    loadStatus();
}

async function updateRange(){
    let s = parseInt(document.getElementById('setStart').value);
    let e = parseInt(document.getElementById('setEnd').value);
    if(s && e && s<e){
        await fetch('/api/update_range', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({start_id:s, end_id:e})
        });
        alert('Range updated');
    }
}

function downloadCSV(){
    window.open('/api/download/csv', '_blank');
}

loadData();
loadStatus();
setInterval(loadData, 5000);
setInterval(loadStatus, 2000);
</script>
</body>
</html>
'''

@app.route('/')
def home():
    return HTML

@app.route('/api/status')
def status():
    progress = round((current_id - START_ID) / (END_ID - START_ID) * 100, 2)
    return jsonify({
        'current_id': current_id,
        'total_found': len(all_workers),
        'is_running': is_running,
        'start_id': START_ID,
        'end_id': END_ID,
        'progress': progress
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
        is_running = True
        threading.Thread(target=scanner).start()
        return jsonify({'ok': True})
    return jsonify({'error': 'invalid'}), 400

@app.route('/api/download/csv')
def download_csv():
    if not all_workers:
        return "No data", 404
    output = io.StringIO()
    output.write('ID,Name,Father,Aadhaar,Mobile,RegNo,District\n')
    for w in all_workers:
        output.write(f"{w['id']},{w['name']},{w['father']},{w['aadhaar']},{w['mobile']},{w['regNo']},{w['district']}\n")
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name='bocw_data.csv')

if __name__ == '__main__':
    if os.path.exists('workers_data.json'):
        with open('workers_data.json', 'r') as f:
            all_workers = json.load(f)
        print(f"Loaded {len(all_workers)} existing workers")
    if is_running:
        threading.Thread(target=scanner).start()
    app.run(host='0.0.0.0', port=10000)
