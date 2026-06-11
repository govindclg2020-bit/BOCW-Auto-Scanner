from flask import Flask, jsonify, render_template_string, request
import requests
import json
import time
import threading
import os

app = Flask(__name__)

# Configuration
START_ID = 4885000
END_ID = 4935000
all_workers = []
failed_ids = []
current_id = START_ID
is_running = False
scan_thread = None

# HTML Template (same as index.html but as string)
HTML_TEMPLATE = open('index.html').read() if os.path.exists('index.html') else "<h1>Loading...</h1>"

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
                        'address': data.get('permanentAddress', 'N/A'),
                        'status': data.get('formNumber', 'Active')
                    }
            time.sleep(2)
        except:
            time.sleep(2)
    return None

def background_scan():
    global current_id, all_workers, failed_ids, is_running
    while is_running and current_id <= END_ID:
        print(f"Scanning ID: {current_id}")
        worker = fetch_worker(current_id)
        if worker:
            all_workers.append(worker)
            print(f"Found: {worker['name']}")
        else:
            failed_ids.append(current_id)
            print(f"Failed: {current_id}")
        
        current_id += 1
        
        # Save every 10 records
        if len(all_workers) % 10 == 0:
            with open('workers_data.json', 'w') as f:
                json.dump(all_workers, f, indent=2)
            with open('scan_status.json', 'w') as f:
                json.dump({
                    'current_id': current_id,
                    'total_found': len(all_workers),
                    'failed_count': len(failed_ids),
                    'is_running': is_running
                }, f)
        
        time.sleep(1.5)
    
    is_running = False
    print("Scan complete!")

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/start', methods=['POST'])
def start_scan():
    global is_running, scan_thread, current_id, all_workers, failed_ids
    if not is_running:
        is_running = True
        scan_thread = threading.Thread(target=background_scan)
        scan_thread.daemon = True
        scan_thread.start()
        return jsonify({'status': 'started'})
    return jsonify({'status': 'already_running'})

@app.route('/api/stop', methods=['POST'])
def stop_scan():
    global is_running
    is_running = False
    return jsonify({'status': 'stopped'})

@app.route('/api/status')
def status():
    return jsonify({
        'current_id': current_id,
        'total_found': len(all_workers),
        'failed_count': len(failed_ids),
        'is_running': is_running,
        'progress': round((current_id - START_ID) / (END_ID - START_ID) * 100, 2)
    })

@app.route('/api/data')
def data():
    return jsonify(all_workers)

@app.route('/workers_data.json')
def workers_data():
    return jsonify(all_workers)

@app.route('/scan_status.json')
def scan_status():
    return jsonify({
        'current_id': current_id,
        'total_found': len(all_workers),
        'failed_count': len(failed_ids),
        'is_running': is_running
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
