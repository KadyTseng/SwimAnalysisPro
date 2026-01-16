
import requests
import time
import os
import sys

# 設定 API 基礎 URL
BASE_URL = "http://127.0.0.1:9000"

# 設定要上傳的測試影片路徑
# 請確保此路徑指向一個存在的影片檔案
VIDEO_PATH = r"d:\Kady\Pool_UI_processed\SwimAnalysisPro\data\videos\Excellent_20230414_backstroke_M_3 (6).mp4"

def test_upload_flow():
    print(f"Checking if video exists at: {VIDEO_PATH}")
    if not os.path.exists(VIDEO_PATH):
        print("Error: Video file not found!")
        return

    print(f"Targeting API at: {BASE_URL}")

    # 1. Test Root Endpoint
    try:
        resp = requests.get(f"{BASE_URL}/")
        print(f"Root endpoint status: {resp.status_code}")
        if resp.status_code != 200:
            print("Server might not be healthy.")
            return
        print("Server is reachable.")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Is it running on port 8000?")
        return

    # 2. Upload Video
    print("\n[Step 1] Uploading video...")
    url = f"{BASE_URL}/analysis/upload"
    files = {'file': open(VIDEO_PATH, 'rb')}
    
    try:
        response = requests.post(url, files=files)
        if response.status_code == 202:
            data = response.json()
            video_id = data['video_id']
            print(f"Upload successful! Video ID: {video_id}")
            print(f"Message: {data['message']}")
        else:
            print(f"Upload failed: {response.status_code}")
            print(response.text)
            return
    except Exception as e:
        print(f"Upload request failed: {e}")
        return

    # 3. Poll Status
    print("\n[Step 2] Polling status...")
    status_url = f"{BASE_URL}/analysis/{video_id}/status"
    
    while True:
        try:
            status_resp = requests.get(status_url)
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                status = status_data['status']
                progress = status_data['progress']
                print(f"Status: {status}, Progress: {progress}%")
                
                if status == 'completed':
                    print("\n[Step 3] Analysis completed!")
                    break
                elif status == 'failed':
                    print(f"\nAnalysis failed: {status_data.get('error_message')}")
                    break
            else:
                print(f"Error checking status: {status_resp.status_code}")
                break
            
            time.sleep(2)
        except KeyboardInterrupt:
            print("Stopped by user.")
            break

    # 4. Get Result
    if status == 'completed':
        print("\n[Step 4] Fetching results...")
        result_url = f"{BASE_URL}/analysis/{video_id}/result"
        result_resp = requests.get(result_url)
        if result_resp.status_code == 200:
            result = result_resp.json()
            print("Result received!")
            print(f"Stroke Style: {result.get('stroke_style')}")
            print(f"Total Strokes: {result.get('stroke_result', {}).get('total_count')}")
        else:
            print(f"Failed to get result: {result_resp.status_code}")

if __name__ == "__main__":
    test_upload_flow()
