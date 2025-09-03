from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
import json
from mysql.connector import Error

# 우리가 만든 모듈들 import
from fire_detector import check_fire_risk, format_fire_alert, FIRE_THRESHOLDS
from db_utils import get_db_connection, get_data_count, get_latest_sensor_data, insert_sensor_data

app = Flask(__name__)
CORS(app)


@app.route('/dashboard', methods=['GET'])
def dashboard():
    """웹 대시보드 페이지"""
    return render_template("dashboard.html")

@app.route('/', methods=['GET'])
def home():
    """홈페이지 - 현재 저장된 데이터 개수 표시"""
    data_count = get_data_count()
    return f"""
    <h1>🔥 ESP32 화재 감지 시스템 (MySQL 연동)</h1>
    <p>현재 저장된 데이터: {data_count}개</p>
    <p>지원하는 센서 데이터:</p>
    <ul>
        <li>온도 (temperature)</li>
        <li>습도 (humidity)</li>
        <li>eCO2 (eco2)</li>
        <li>TVOC (tvoc)</li>
        <li>기기 ID (device_id)</li>
    </ul>
    <p>API 엔드포인트:</p>
    <ul>
        <li>POST /data - 센서 데이터 전송</li>
        <li>GET /data - 모든 데이터 조회</li>
        <li>GET /latest - 최신 데이터 조회</li>
        <li>GET /stats - 데이터 통계</li>
        <li><strong>GET /fire-check - 화재 위험도 체크</strong></li>
        <li>POST /clear - 모든 데이터 삭제</li>
    </ul>
    <p>🔥 화재 감지 임계값:</p>
    <ul>
        <li>온도: {FIRE_THRESHOLDS['temperature']}°C 이상</li>
        <li>TVOC: {FIRE_THRESHOLDS['tvoc']}ppb 이상</li>
        <li>eCO2: {FIRE_THRESHOLDS['eco2']}ppm 이상</li>
        <li>습도: 30% 미만 (건조 상태)</li>
    </ul>
    """

@app.route('/data', methods=['POST'])
def receive_data():
    """센서 데이터 받기 - MySQL에 저장"""
    try:
        # JSON 데이터 받기
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "JSON 데이터가 필요합니다"
            }), 400
        
        # 타임스탬프 추가
        timestamp = datetime.now()
        data['timestamp'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # 센서 데이터 추출
        temperature = data.get('temp') or data.get('temperature')
        humidity = data.get('hum') or data.get('humidity')
        eco2 = data.get('eco2')
        tvoc = data.get('tvoc')
        device_id = data.get('device_id') or 'esp32_fire_detector_01'
        
        # 데이터베이스에 저장
        data_id = insert_sensor_data(
            temperature, humidity, eco2, tvoc, device_id, 
            timestamp, json.dumps(data, ensure_ascii=False)
        )
        
        if not data_id:
            return jsonify({
                "status": "error",
                "message": "데이터베이스 저장 실패"
            }), 500
        
        # 화재 위험도 체크
        fire_risk = check_fire_risk(temperature, humidity, eco2, tvoc)
        alert_message = format_fire_alert(fire_risk, device_id)
        
        # 콘솔에 출력
        print("=" * 50)
        print(f"새로운 센서 데이터 수신 (ID: {data_id}): {data['timestamp']}")
        print(f"기기 ID: {device_id}")
        print(f"온도: {temperature}°C, 습도: {humidity}%")
        print(f"eCO2: {eco2}ppm, TVOC: {tvoc}ppb")
        print(alert_message)
        print("=" * 50)
        
        return jsonify({
            "status": "success", 
            "message": "데이터가 성공적으로 저장되었습니다",
            "data_id": data_id,
            "received_data": data,
            "fire_risk_analysis": fire_risk
        }), 200
        
    except Exception as e:
        print(f"오류 발생: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 400

@app.route('/fire-check', methods=['GET'])
def fire_check():
    """최신 센서 데이터로 화재 위험도 체크"""
    device_id = request.args.get('device_id')
    latest_data = get_latest_sensor_data(device_id)
    
    if not latest_data:
        return jsonify({
            "message": "저장된 데이터가 없습니다"
        })
    
    # 화재 위험도 분석
    fire_risk = check_fire_risk(
        latest_data['temperature'],
        latest_data['humidity'], 
        latest_data['eco2'],
        latest_data['tvoc']
    )
    
    return jsonify({
        "sensor_data": latest_data,
        "fire_risk_analysis": fire_risk
    })

@app.route('/data', methods=['GET'])
def get_all_data():
    """모든 센서 데이터 조회"""
    connection = get_db_connection()
    if not connection:
        return jsonify({
            "status": "error",
            "message": "데이터베이스 연결 실패"
        }), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # 페이지네이션 지원
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 100, type=int)
        offset = (page - 1) * limit
        
        # 기기 ID 필터링
        device_id = request.args.get('device_id')
        
        # 전체 데이터 수 조회
        count_query = "SELECT COUNT(*) as total FROM sensor_data"
        if device_id:
            count_query += " WHERE device_id = %s"
            cursor.execute(count_query, (device_id,))
        else:
            cursor.execute(count_query)
        total = cursor.fetchone()['total']
        
        # 데이터 조회 (최신 데이터부터)
        query = """
        SELECT id, temperature, humidity, eco2, tvoc, device_id, timestamp, created_at
        FROM sensor_data 
        """
        if device_id:
            query += "WHERE device_id = %s "
            query += "ORDER BY created_at DESC LIMIT %s OFFSET %s"
            cursor.execute(query, (device_id, limit, offset))
        else:
            query += "ORDER BY created_at DESC LIMIT %s OFFSET %s"
            cursor.execute(query, (limit, offset))
        
        data = cursor.fetchall()
        
        return jsonify({
            "total_count": total,
            "page": page,
            "limit": limit,
            "device_filter": device_id,
            "data": data
        })
        
    except Error as e:
        print(f"데이터 조회 오류: {e}")
        return jsonify({
            "status": "error",
            "message": f"데이터 조회 실패: {str(e)}"
        }), 500
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/latest', methods=['GET'])
def get_latest():
    """최신 센서 데이터 조회"""
    device_id = request.args.get('device_id')
    latest_data = get_latest_sensor_data(device_id)
    
    if latest_data:
        return jsonify({
            "latest_data": latest_data
        })
    else:
        return jsonify({
            "message": "저장된 데이터가 없습니다"
        })

@app.route('/devices', methods=['GET'])
def get_devices():
    """등록된 기기 목록 조회"""
    connection = get_db_connection()
    if not connection:
        return jsonify({
            "status": "error",
            "message": "데이터베이스 연결 실패"
        }), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                device_id,
                COUNT(*) as data_count,
                MIN(created_at) as first_data,
                MAX(created_at) as last_data
            FROM sensor_data 
            GROUP BY device_id
            ORDER BY last_data DESC
        """)
        
        devices = cursor.fetchall()
        
        return jsonify({
            "devices": devices
        })
        
    except Error as e:
        print(f"기기 목록 조회 오류: {e}")
        return jsonify({
            "status": "error",
            "message": f"기기 목록 조회 실패: {str(e)}"
        }), 500
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/clear', methods=['POST'])
def clear_data():
    """저장된 모든 데이터 삭제"""
    connection = get_db_connection()
    if not connection:
        return jsonify({
            "status": "error",
            "message": "데이터베이스 연결 실패"
        }), 500
    
    try:
        cursor = connection.cursor()
        
        # 삭제 전 데이터 수 확인
        cursor.execute("SELECT COUNT(*) FROM sensor_data")
        count = cursor.fetchone()[0]
        
        # 모든 데이터 삭제
        cursor.execute("DELETE FROM sensor_data")
        
        # AUTO_INCREMENT 값 초기화
        cursor.execute("ALTER TABLE sensor_data AUTO_INCREMENT = 1")
        
        return jsonify({
            "status": "success",
            "message": f"{count}개의 데이터가 삭제되었습니다"
        })
        
    except Error as e:
        print(f"데이터 삭제 오류: {e}")
        return jsonify({
            "status": "error",
            "message": f"데이터 삭제 실패: {str(e)}"
        }), 500
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/stats', methods=['GET'])
def get_stats():
    """센서 데이터 통계 조회"""
    connection = get_db_connection()
    if not connection:
        return jsonify({
            "status": "error",
            "message": "데이터베이스 연결 실패"
        }), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # 기기 ID별 통계
        device_id = request.args.get('device_id')
        
        base_query = """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT device_id) as device_count,
                AVG(temperature) as avg_temperature,
                MIN(temperature) as min_temperature,
                MAX(temperature) as max_temperature,
                AVG(humidity) as avg_humidity,
                MIN(humidity) as min_humidity,
                MAX(humidity) as max_humidity,
                AVG(eco2) as avg_eco2,
                MIN(eco2) as min_eco2,
                MAX(eco2) as max_eco2,
                AVG(tvoc) as avg_tvoc,
                MIN(tvoc) as min_tvoc,
                MAX(tvoc) as max_tvoc,
                MIN(timestamp) as earliest_data,
                MAX(timestamp) as latest_data
            FROM sensor_data
        """
        
        if device_id:
            cursor.execute(base_query + " WHERE device_id = %s", (device_id,))
        else:
            cursor.execute(base_query)
        
        stats = cursor.fetchone()
        
        return jsonify({
            "device_filter": device_id,
            "statistics": stats
        })
        
    except Error as e:
        print(f"통계 조회 오류: {e}")
        return jsonify({
            "status": "error",
            "message": f"통계 조회 실패: {str(e)}"
        }), 500
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == '__main__':
    print("🔥 ESP32 화재 감지 시스템 서버 시작... (MySQL 연동)")
    print("지원하는 센서 데이터: temp, hum, eco2, tvoc, device_id")
    print("화재 감지 임계값:")
    print(f"- 온도: {FIRE_THRESHOLDS['temperature']}°C 이상")
    print(f"- TVOC: {FIRE_THRESHOLDS['tvoc']}ppb 이상")
    print(f"- eCO2: {FIRE_THRESHOLDS['eco2']}ppm 이상")
    print("다음 주소에서 접속 가능:")
    print("- 로컬: http://localhost:8080")
    print("- 네트워크: http://192.168.219.51:8080")
    print("\n주요 엔드포인트:")
    print("- POST /data : 센서 데이터 전송")
    print("- GET /fire-check : 화재 위험도 체크")
    print("- GET /latest : 최신 데이터 조회")
    print("- GET /devices : 등록된 기기 목록")
    
    # 모든 네트워크 인터페이스에서 접속 가능하도록 설정
    app.run(host='0.0.0.0', port=8080, debug=True)
