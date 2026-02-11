#!/usr/bin/env python3
from flask import Flask, request, jsonify
import time

app = Flask(__name__)

@app.route("/ai/process", methods=["POST"])
def process_ai():
    data = request.get_json()
    
    start_time = time.time()
    
    # AI 처리 시뮬레이션 (정확히 1초)
    time.sleep(1.0)
    
    end_time = time.time()
    actual_processing_time = end_time - start_time
    
    response = {
        'message_id': data['message_id'],
        'robot_id': data['robot_id'],
        'ai_analysis': {
            'battery_status': 'good' if data['battery'] > 50 else 'low',
            'recommendation': '정상 작동 중' if data['status'] == 'running' else '점검 필요',
            'processing_time': f'{actual_processing_time:.3f}초'
        },
        'timestamp': data['timestamp']
    }
    
    print(f"[AI:5000] 처리 완료: {data['message_id'][:8]}... ({actual_processing_time:.3f}초)")
    
    return jsonify(response)

@app.route("/", methods=["GET"])
def read_root():
    return jsonify({"status": "malle_ai_service running", "port": 5000})

if __name__ == '__main__':
    print("="*60)
    print("AI 서비스 시작: http://0.0.0.0:5000")
    print("처리 시간: 1.00초")
    print("="*60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)