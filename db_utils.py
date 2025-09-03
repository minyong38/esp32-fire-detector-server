"""
MySQL 데이터베이스 유틸리티 모듈
"""

import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()

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

def get_latest_sensor_data(device_id=None):
    """최신 센서 데이터 조회"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        if device_id:
            cursor.execute("""
                SELECT temperature, humidity, eco2, tvoc, device_id, timestamp, created_at
                FROM sensor_data 
                WHERE device_id = %s
                ORDER BY created_at DESC 
                LIMIT 1
            """, (device_id,))
        else:
            cursor.execute("""
                SELECT temperature, humidity, eco2, tvoc, device_id, timestamp, created_at
                FROM sensor_data 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
        
        return cursor.fetchone()
        
    except Error as e:
        print(f"최신 데이터 조회 오류: {e}")
        return None
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def insert_sensor_data(temperature, humidity, eco2, tvoc, device_id, timestamp, raw_data):
    """센서 데이터를 데이터베이스에 저장"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        
        insert_query = """
        INSERT INTO sensor_data (temperature, humidity, eco2, tvoc, device_id, timestamp, raw_data)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            temperature, humidity, eco2, tvoc, device_id, timestamp, raw_data
        ))
        
        return cursor.lastrowid
        
    except Error as e:
        print(f"데이터 저장 오류: {e}")
        return None
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
