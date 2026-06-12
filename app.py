from flask import Flask, jsonify, request, send_file, render_template_string
import requests
import json
import time
import threading
import os
import io
from datetime import datetime

app = Flask(__name__)

# ========== CONFIG ==========
START_ID = 4885000
END_ID = 5000000
BATCH_SIZE = 50
MAX_RETRIES = 3

# ========== GLOBAL ==========
all_workers = []
failed_ids = []
scanned_count = 0
current_id = START_ID
is_running = True
last_update = datetime.now()

DATA_FILE = 'workers_data.json'

def save_data():
    global last_update
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump({
                'workers': all_workers,
                'failed': failed_ids,
                'scanned': scanned_count,
                'current_id': current_id,
                'last_update': datetime.now().isoformat()
            }, f, indent=2)
        last_update = datetime.now()
    except Exception as e:
        print(f"Save error: {e}")

def load_data():
    global all_workers, failed_ids, scanned_count, current_id
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                all_workers = data.get('workers', [])
                failed_ids = data.get('failed', [])
                scanned_count = data.get('scanned', 0)
                current_id = data.get('current_id', START_ID)
            print(f"Loaded {len(all_workers)} workers")
    except Exception as e:
        print(f"Load error: {e}")

def fetch_worker(uid):
    url = f"https://bocwboard.bihar.gov.in/api/workers/generalInfoUserView/{uid}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }
    for i in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=headers, timeout=20)
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
            time.sleep(2)
        except:
            time.sleep(2)
    return None

def scanner():
    global current_id, all_workers, scanned_count, is_running
    print(f"Scanner started: {START_ID} to {END_ID}")
    while is_running and current_id <= END_ID:
        batch_end = min(current_id + BATCH_SIZE - 1, END_ID)
        for uid in range(current_id, batch_end + 1):
            if not is_running:
                break
            w = fetch_worker(uid)
            scanned_count += 1
            if w:
                all_workers.append(w)
                print(f"Found: {w['name']} ({len(all_workers)})")
            current_id = uid + 1
            if len(all_workers) % 5 == 0:
                save_data()
        time.sleep(1)
    save_data()
    print(f"Scan complete! Total: {len(all_workers)}")

# ========== HTML (Embedded - Single File) ==========
HTML_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BOCW Worker Scanner</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box;}
        body{font-family:'Courier New',monospace;background:#fff;padding:15px;}
        .container{max-width:1400px;margin:0 auto;border:1px solid #000;}
        .header{border-bottom:2px solid #000;padding:15px;text-align:center;}
        .header h1{font-size:22px;font-weight:normal;}
        .stats{display:grid;grid-template-columns:repeat(5,1fr);border-bottom:1px solid #ccc;}
        .stat-card{padding:12px;border-right:1px solid #ccc;text-align:center;}
        .stat-card:last-child{border-right:none;}
        .stat-value{font-size:24px;font-weight:bold;}
        .stat-label{font-size:10px;margin-top:5px;color:#555;}
        .search-section{padding:15px;border-bottom:1px solid #ccc;}
        .search-box{display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;}
        .search-box select,.search-box input,.search-box button{padding:10px;border:1px solid #000;background:#fff;font-family:monospace;font-size:13px;}
        .search-box select{flex:1;}
        .search-box input{flex:3;}
        .search-box button{background:#000;color:#fff;cursor:pointer;}
        .results-section{padding:15px;}
        .results-table{overflow-x:auto;border:1px solid #ccc;}
        table{width:100%;border-collapse:collapse;font-size:12px;}
        th,td{padding:10px;text-align:left;border-bottom:1px solid #eee;}
        th{background:#f5f5f5;border-bottom:2px solid #ccc;}
        .pagination{display:flex;justify-content:center;gap:5px;margin-top:15px;flex-wrap:wrap;}
        .pagination button{padding:5px 12px;border:1px solid #ccc;background:#fff;cursor:pointer;}
        .pagination button:hover{background:#f0f0f0;}
        .footer{padding:12px;text-align:center;border-top:1px solid #ccc;font-size:10px;color:#666;}
        .admin-btn{position:fixed;bottom:10px;right:10px;width:35px;height:35px;border:1px solid #000;background:#fff;text-align:center;line-height:33px;cursor:pointer;font-size:16px;z-index:999;}
        .admin-btn:hover{background:#f0f0f0;}
        .modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:1000;}
        .modal-content{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:450px;max-width:95%;background:#fff;border:2px solid #000;padding:20px;}
        .modal-header{border-bottom:1px solid #ccc;padding-bottom:10px;margin-bottom:15px;}
        .modal-header h3{font-size:16px;font-weight:normal;}
        .close-modal{float:right;cursor:pointer;font-size:22px;}
        .modal input{width:100%;padding:10px;margin:8px 0;border:1px solid #ccc;font-family:monospace;}
        .modal button{width:100%;padding:10px;margin:5px 0;border:1px solid #000;background:#fff;cursor:pointer;}
        .modal button:hover{background:#f0f0f0;}
        .admin-panel{display:none;}
        .info-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee;}
        hr{margin:12px 0;border:none;border-top:1px solid #ccc;}
        .btn-start{background:#000!important;color:#fff!important;}
        @media(max-width:700px){
            .stats{grid-template-columns:repeat(2,1fr);}
            .stat-card{border-right:none;border-bottom:1px solid #ccc;}
            .search-box{flex-direction:column;}
        }
    </style>
</head>
<body>

<div class="admin-btn" id="adminBtn">[A]</div>

<div id="adminModal" class="modal">
    <div class="modal-content">
        <div class="modal-header">
            <span class="close-modal" id="closeModal">&times;</span>
            <h3>ADMIN PANEL</h3>
        </div>
        <div id="loginDiv">
            <input type="password" id="adminPass" placeholder="Enter Password">
            <button id="loginBtn">LOGIN</button>
        </div>
        <div id="adminDiv" class="admin-panel">
            <div class="info-row"><strong>STATUS:</strong> <span id="statStatus">-</span></div>
            <div class="info-row"><strong>CURRENT ID:</strong> <span id="statCurrentId">-</span></div>
            <div class="info-row"><strong>WORKERS:</strong> <span id="statWorkers">0</span></div>
            <div class="info-row"><strong>SCANNED:</strong> <span id="statScanned">0</span></div>
            <div class="info-row"><strong>PROGRESS:</strong> <span id="statProgress">0%</span></div>
            <hr>
            <button id="startBtn" class="btn-start">[ START SCAN ]</button>
            <button id="stopBtn">[ STOP SCAN ]</button>
            <hr>
            <button id="downloadBtn">[ DOWNLOAD CSV ]</button>
            <hr>
            <label>START ID:</label>
            <input type="number" id="rangeStart" placeholder="Start ID">
            <label>END ID:</label>
            <input type="number" id="rangeEnd" placeholder="End ID">
            <button id="updateRangeBtn">[ UPDATE RANGE ]</button>
            <hr>
            <button id="logoutBtn">[ LOGOUT ]</button>
        </div>
    </div>
</div>

<div class="container">
    <div class="header">
        <h1>BOCW WORKER DATA SCANNER</h1>
        <p>Search by ID | Aadhaar | Registration No | Name | Mobile</p>
    </div>
    
    <div class="stats">
        <div class="stat-card"><div class="stat-value" id="pubWorkers">0</div><div class="stat-label">WORKERS FOUND</div></div>
        <div class="stat-card"><div class="stat-value" id="pubCurrent">-</div><div class="stat-label">CURRENT ID</div></div>
        <div class="stat-card"><div class="stat-value" id="pubProgress">0%</div><div class="stat-label">PROGRESS</div></div>
        <div class="stat-card"><div class="stat-value" id="pubRange">-</div><div class="stat-label">SCAN RANGE</div></div>
        <div class="stat-card"><div class="stat-value" id="pubUpdate">-</div><div class="stat-label">LAST UPDATE</div></div>
    </div>
    
    <div class="search-section">
        <h3>SEARCH WORKER</h3>
        <div class="search-box">
            <select id="searchType">
                <option value="id">USER ID</option>
                <option value="aadhaar">AADHAAR</option>
                <option value="regNo">REGISTRATION NO</option>
                <option value="name">NAME</option>
                <option value="mobile">MOBILE</option>
            </select>
            <input type="text" id="searchValue" placeholder="Enter value...">
            <button id="searchBtn">SEARCH</button>
            <button id="resetBtn" style="background:#f0f0f0;color:#000;">RESET</button>
        </div>
    </div>
    
    <div class="results-section">
        <div class="results-table">
            <table id="dataTable">
                <thead><tr><th>ID</th><th>NAME</th><th>FATHER</th><th>AADHAAR</th><th>MOBILE</th><th>REG NO</th><th>DISTRICT</th></tr></thead>
                <tbody id="tableBody"><tr><td colspan="7">[ LOADING... ]</td></tr></tbody>
            </table>
            <div class="pagination" id="pagination"></div>
        </div>
    </div>
    
    <div class="footer">BOCW BIHAR | REAL-TIME DATA</div>
</div>

<script>
const PASSWORD = "8809219140";
let allData = [];
let currentPage = 1;
const perPage = 50;

// DOM
const adminBtn = document.getElementById('adminBtn');
const modal = document.getElementById('adminModal');
const closeModal = document.getElementById('closeModal');
const loginDiv = document.getElementById('loginDiv');
const adminDiv = document.getElementById('adminDiv');
const adminPass = document.getElementById('adminPass');
const loginBtn = document.getElementById('loginBtn');

// Functions
async function loadData(){
    try{
        let res = await fetch('/api/data?t='+Date.now());
        if(res.ok){
            allData = await res.json();
            document.getElementById('pubWorkers').innerText = allData.length;
            showTable();
        }
    }catch(e){}
}

async function loadStatus(){
    try{
        let res = await fetch('/api/status?t='+Date.now());
        if(res.ok){
            let d = await res.json();
            document.getElementById('pubCurrent').innerText = d.current_id?.toLocaleString() || '-';
            document.getElementById('pubProgress').innerText = (d.progress || 0)+'%';
            document.getElementById('pubRange').innerText = (d.start_id||'?')+' - '+(d.end_id||'?');
            document.getElementById('pubUpdate').innerText = new Date().toLocaleTimeString();
            if(document.getElementById('statStatus')){
                document.getElementById('statStatus').innerText = d.is_running ? 'RUNNING' : 'STOPPED';
                document.getElementById('statCurrentId').innerText = d.current_id?.toLocaleString() || '-';
                document.getElementById('statWorkers').innerText = d.total_found || 0;
                document.getElementById('statScanned').innerText = d.scanned_count || 0;
                document.getElementById('statProgress').innerText = (d.progress||0)+'%';
                document.getElementById('rangeStart').value = d.start_id || '';
                document.getElementById('rangeEnd').value = d.end_id || '';
            }
        }
    }catch(e){}
}

function showTable(filtered=null){
    let data = filtered || allData;
    if(data.length===0){
        document.getElementById('tableBody').innerHTML = '<tr><td colspan="7">[ NO DATA YET. SCANNER IS RUNNING... ]</td></tr>';
        document.getElementById('pagination').innerHTML = '';
        return;
    }
    let start = (currentPage-1)*perPage;
    let pageData = data.slice(start, start+perPage);
    let html = '';
    for(let w of pageData){
        html += `<tr>
            <td>${w.id || '-'}</td>
            <td>${(w.name||'-').substring(0,50)}</td>
            <td>${(w.father||'-').substring(0,40)}</td>
            <td>${w.aadhaar||'-'}</td>
            <td>${w.mobile||'-'}</td>
            <td>${w.regNo||'-'}</td>
            <td>${w.district||'-'}</td>
        </tr>`;
    }
    document.getElementById('tableBody').innerHTML = html;
    let totalPages = Math.ceil(data.length/perPage);
    let pgHtml = '';
    for(let i=1;i<=Math.min(totalPages,10);i++){
        pgHtml += `<button onclick="goToPage(${i})" ${i===currentPage?'style="background:#000;color:#fff;"':''}>${i}</button>`;
    }
    document.getElementById('pagination').innerHTML = pgHtml;
}

function search(){
    let type = document.getElementById('searchType').value;
    let val = document.getElementById('searchValue').value.trim().toLowerCase();
    if(!val){ showTable(); return; }
    let filtered = allData.filter(w => {
        if(type==='id') return w.id == val;
        if(type==='aadhaar') return w.aadhaar && w.aadhaar.includes(val);
        if(type==='regNo') return w.regNo && w.regNo.toLowerCase().includes(val);
        if(type==='name') return w.name && w.name.toLowerCase().includes(val);
        if(type==='mobile') return w.mobile && w.mobile.includes(val);
        return false;
    });
    currentPage = 1;
    showTable(filtered);
}

function resetSearch(){
    document.getElementById('searchValue').value = '';
    showTable();
}

function goToPage(p){ currentPage = p; showTable(); }

// Admin
adminBtn.onclick = () => modal.style.display = 'block';
closeModal.onclick = () => modal.style.display = 'none';
window.onclick = (e) => { if(e.target==modal) modal.style.display = 'none'; };

loginBtn.onclick = () => {
    if(adminPass.value === PASSWORD){
        loginDiv.style.display = 'none';
        adminDiv.style.display = 'block';
        loadStatus();
        setInterval(loadStatus, 2000);
    } else { alert('WRONG PASSWORD'); }
};

document.getElementById('startBtn')?.addEventListener('click', async () => {
    await fetch('/api/start', {method:'POST'});
    loadStatus();
});
document.getElementById('stopBtn')?.addEventListener('click', async () => {
    await fetch('/api/stop', {method:'POST'});
    loadStatus();
});
document.getElementById('downloadBtn')?.addEventListener('click', () => {
    window.open('/api/download/csv', '_blank');
});
document.getElementById('updateRangeBtn')?.addEventListener('click', async () => {
    let s = parseInt(document.getElementById('rangeStart').value);
    let e = parseInt(document.getElementById('rangeEnd').value);
    if(s && e && s<e){
        await fetch('/api/update_range', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({start_id:s, end_id:e})
        });
        alert('RANGE UPDATED');
    } else { alert('INVALID RANGE'); }
});
document.getElementById('logoutBtn')?.addEventListener('click', () => {
    loginDiv.style.display = 'block';
    adminDiv.style.display = 'none';
    adminPass.value = '';
    modal.style.display = 'none';
});

document.getElementById('searchBtn').onclick = search;
document.getElementById('resetBtn').onclick = resetSearch;
document.getElementById('searchValue').addEventListener('keypress', (e) => { if(e.key==='Enter') search(); });

window.goToPage = goToPage;

loadData();
loadStatus();
setInterval(loadData, 8000);
setInterval(loadStatus, 3000);
</script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_PAGE)

@app.route('/api/status')
def status():
    progress = round((current_id - START_ID) / (END_ID - START_ID) * 100, 2) if END_ID > START_ID else 0
    return jsonify({
        'current_id': current_id,
        'total_found': len(all_workers),
        'scanned_count': scanned_count,
        'is_running': is_running,
        'start_id': START_ID,
        'end_id': END_ID,
        'progress': progress,
        'last_update': last_update.isoformat()
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
