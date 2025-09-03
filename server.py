from flask import Flask, request, jsonify
from datetime import datetime
import json
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

app = Flask(__name__)

# MySQL 연결 설정
def get_db_connection():
    """MySQL 데이터베이스 연결"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME', 'sensor_db'),
            autocommit=True
        )
        return connection
    except Error as e:
        print(f"MySQL 연결 오류: {e}")
        return None

def get_data_count():
    """데이터베이스에 저장된 데이터 개수 조회"""
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM sensor_data")
            count = cursor.fetchone()[0]
            return count
        except Error as e:
            print(f"데이터 개수 조회 오류: {e}")
            return 0
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    return 0

@app.route('/', methods=['GET'])
def home():
    """홈페이지 - 현재 저장된 데이터 개수 표시"""
    data_count = get_data_count()
    return f"""
    <h1>센서 데이터 서버 (MySQL 연동)</h1>
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
        <li>POST /clear - 모든 데이터 삭제</li>
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
        
        # MySQL에 데이터 저장
        connection = get_db_connection()
        if not connection:
            return jsonify({
                "status": "error",
                "message": "데이터베이스 연결 실패"
            }), 500
        
        try:
            cursor = connection.cursor()
            
            # 센서 데이터 추출 (실제 센서 데이터에 맞춤)
            temperature = data.get('temp') or data.get('temperature')
            humidity = data.get('hum') or data.get('humidity')
            eco2 = data.get('eco2')
            tvoc = data.get('tvoc')
            device_id = data.get('device_id') or 'esp32_fire_detector_01'  # 기본값 설정
            
            # 데이터 삽입
            insert_query = """
            INSERT INTO sensor_data (temperature, humidity, eco2, tvoc, device_id, timestamp, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                temperature,
                humidity,
                eco2,
                tvoc,
                device_id,
                timestamp,
                json.dumps(data, ensure_ascii=False)
            ))
            
            # 삽입된 데이터의 ID 가져오기
            data_id = cursor.lastrowid
            
            # 콘솔에 출력 (확인용)
            print("=" * 50)
            print(f"새로운 센서 데이터 수신 (ID: {data_id}): {data['timestamp']}")
            print(f"기기 ID: {device_id}")
            print(f"온도: {temperature}°C, 습도: {humidity}%")
            print(f"eCO2: {eco2}ppm, TVOC: {tvoc}ppb")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("=" * 50)
            
            return jsonify({
                "status": "success", 
                "message": "데이터가 성공적으로 저장되었습니다",
                "data_id": data_id,
                "received_data": data
            }), 200
            
        except Error as e:
            print(f"데이터 저장 오류: {e}")
            return jsonify({
                "status": "error",
                "message": f"데이터 저장 실패: {str(e)}"
            }), 500
        
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
        
    except Exception as e:
        print(f"오류 발생: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 400

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
    connection = get_db_connection()
    if not connection:
        return jsonify({
            "status": "error",
            "message": "데이터베이스 연결 실패"
        }), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # 기기 ID별 최신 데이터 조회
        device_id = request.args.get('device_id')
        
        if device_id:
            cursor.execute("""
                SELECT id, temperature, humidity, eco2, tvoc, device_id, timestamp, created_at
                FROM sensor_data 
                WHERE device_id = %s
                ORDER BY created_at DESC 
                LIMIT 1
            """, (device_id,))
        else:
            cursor.execute("""
                SELECT id, temperature, humidity, eco2, tvoc, device_id, timestamp, created_at
                FROM sensor_data 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
        
        latest_data = cursor.fetchone()
        
        if latest_data:
            return jsonify({
                "latest_data": latest_data
            })
        else:
            return jsonify({
                "message": "저장된 데이터가 없습니다"
            })
            
    except Error as e:
        print(f"최신 데이터 조회 오류: {e}")
        return jsonify({
            "status": "error",
            "message": f"데이터 조회 실패: {str(e)}"
        }), 500
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

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
    print("센서 데이터 서버 시작... (MySQL 연동)")
    print("지원하는 센서 데이터: temp, hum, eco2, tvoc, device_id")
    print("다음 주소에서 접속 가능:")
    print("- 로컬: http://localhost:8080")
    print("- 네트워크: http://192.168.219.53:8080")
    print("\n데이터 전송 예시:")
    print("curl -X POST http://192.168.219.53:8080/data \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"temp\": 25.5, \"hum\": 60.2, \"eco2\": 400, \"tvoc\": 10, \"device_id\": \"intel_laptop_01\"}'")
    print("\n주요 엔드포인트:")
    print("- GET /data?device_id=intel_laptop_01 : 특정 기기 데이터 조회")
    print("- GET /devices : 등록된 기기 목록")
    print("- GET /stats?device_id=intel_laptop_01 : 기기별 통계")
    
    # 모든 네트워크 인터페이스에서 접속 가능하도록 설정
    app.run(host='0.0.0.0', port=8080, debug=True)
