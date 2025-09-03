# 센서 데이터 서버 (MySQL 연동)

인텔 노트북에서 전송되는 센서 데이터를 MySQL 데이터베이스에 저장하는 Flask 서버입니다.

## 기능

- 센서 데이터 수신 및 MySQL 저장
- 데이터 조회 (페이지네이션 지원)
- 최신 데이터 조회
- 데이터 통계 조회
- 모든 데이터 삭제

## 설치 및 설정

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. MySQL 서버 설치 및 설정
MySQL 서버가 설치되어 있어야 합니다.

### 3. 환경 변수 설정
`.env` 파일에서 MySQL 연결 정보를 수정하세요:
```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=sensor_db
```

### 4. 데이터베이스 초기화
```bash
python init_db.py
```

### 5. 서버 실행
```bash
python server.py
```

## API 엔드포인트

### POST /data
센서 데이터를 전송합니다.

**요청 예시:**
```bash
curl -X POST http://192.168.219.63:8080/data \
  -H 'Content-Type: application/json' \
  -d '{"temperature": 25.5, "humidity": 60.2, "pressure": 1013.25}'
```

### GET /data
모든 센서 데이터를 조회합니다. (페이지네이션 지원)

**요청 예시:**
```bash
curl "http://192.168.219.63:8080/data?page=1&limit=50"
```

### GET /latest
최신 센서 데이터를 조회합니다.

### GET /stats
센서 데이터 통계를 조회합니다.

### POST /clear
모든 저장된 데이터를 삭제합니다.

## 데이터베이스 스키마

```sql
CREATE TABLE sensor_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temperature DECIMAL(5,2),
    humidity DECIMAL(5,2),
    pressure DECIMAL(7,2),
    timestamp DATETIME,
    raw_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 접속 주소

- 로컬: http://localhost:8080
- 네트워크: http://192.168.219.63:8080
