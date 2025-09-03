import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def create_database_and_table():
    """데이터베이스와 테이블 생성"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD')
        )
        
        cursor = connection.cursor()
        
        # 데이터베이스 생성
        db_name = os.getenv('DB_NAME', 'sensor_db')
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"데이터베이스 '{db_name}' 생성 완료")
        
        # 데이터베이스 선택
        cursor.execute(f"USE {db_name}")
        
        # 센서 데이터 테이블 생성 (실제 센서 데이터에 맞춤)
        create_table_query = """
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            temperature DECIMAL(5,2),
            humidity DECIMAL(5,2),
            eco2 INT,
            tvoc INT,
            device_id VARCHAR(50),
            timestamp DATETIME,
            raw_data JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        cursor.execute(create_table_query)
        print("센서 데이터 테이블 생성 완료")
        
        connection.commit()
        print("데이터베이스 설정이 완료되었습니다!")
        
    except Error as e:
        print(f"MySQL 오류: {e}")
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    print("데이터베이스 초기화 시작...")
    create_database_and_table()
