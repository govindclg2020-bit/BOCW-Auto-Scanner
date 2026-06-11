import requests
import json
import time
import os
from datetime import datetime

# Configuration
START_ID = 4885000
END_ID = 4935000  # Change this to your range
BATCH_SIZE = 50

def fetch_worker(worker_id):
    """Fetch worker data from API"""
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
            print(f"Retry {retry+1}/5 for ID {worker_id}")
            time.sleep(3)
        except Exception as e:
            print(f"Error ID {worker_id}: {e}")
            time.sleep(3)
    
    return None

def main():
    print(f"🚀 Scanner Started at {datetime.now()}")
    print(f"📊 Range: {START_ID} to {END_ID}")
    print(f"⚡ Batch Size: {BATCH_SIZE}")
    
    # Load existing data if any
    all_workers = []
    if os.path.exists('workers_data.json'):
        with open('workers_data.json', 'r') as f:
            all_workers = json.load(f)
        print(f"📀 Loaded {len(all_workers)} existing records")
    
    current_id = START_ID
    if all_workers:
        existing_ids = [w['id'] for w in all_workers]
        current_id = max(existing_ids) + 1 if existing_ids else START_ID
    
    while current_id <= END_ID:
        print(f"\n🔍 Scanning ID: {current_id}")
        
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
            print(f"💾 Saved {len(all_workers)} records")
        
        # Create status file for monitoring
        status = {
            'current_id': current_id,
            'total_found': len(all_workers),
            'progress': round((current_id - START_ID) / (END_ID - START_ID) * 100, 2),
            'last_update': datetime.now().isoformat(),
            'is_running': current_id <= END_ID
        }
        with open('scan_status.json', 'w') as f:
            json.dump(status, f)
        
        current_id += 1
        time.sleep(2)  # Delay to avoid rate limiting
    
    print(f"\n✅ SCAN COMPLETE!")
    print(f"📊 Total Workers Found: {len(all_workers)}")
    
    # Final save
    with open('workers_data.json', 'w') as f:
        json.dump(all_workers, f, indent=2)
    
    # Keep the process alive for Render
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()