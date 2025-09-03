#!/usr/bin/env python3
"""
데이터베이스 정리 스크립트
오래된 센서 데이터를 삭제하여 데이터베이스 용량을 관리합니다.
"""

import mysql.connector
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

def cleanup_old_data(days_to_keep=7):
    """
    지정된 일수보다 오래된 데이터를 삭제합니다.
    
    Args:
        days_to_keep (int): 보관할 일수 (기본값: 7일)
    """
    load_dotenv()
    
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor()
        
        # 삭제할 날짜 계산
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # 현재 데이터 개수 확인
        cursor.execute('SELECT COUNT(*) FROM sensor_data')
        total_count = cursor.fetchone()[0]
        
        # 삭제할 데이터 개수 확인
        cursor.execute('SELECT COUNT(*) FROM sensor_data WHERE timestamp < %s', (cutoff_date,))
        delete_count = cursor.fetchone()[0]
        
        print(f"📊 현재 총 데이터: {total_count}개")
        print(f"🗑️ 삭제 대상 ({days_to_keep}일 이전): {delete_count}개")
        
        if delete_count > 0:
            # 오래된 데이터 삭제
            cursor.execute('DELETE FROM sensor_data WHERE timestamp < %s', (cutoff_date,))
            conn.commit()
            print(f"✅ {delete_count}개의 오래된 데이터가 삭제되었습니다!")
        else:
            print("✅ 삭제할 오래된 데이터가 없습니다.")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

def delete_all_data():
    """모든 데이터를 삭제합니다."""
    load_dotenv()
    
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM sensor_data')
        count = cursor.fetchone()[0]
        
        print(f"현재 저장된 데이터: {count}개")
        choice = input("모든 데이터를 삭제하시겠습니까? (y/N): ")
        
        if choice.lower() == 'y':
            cursor.execute('DELETE FROM sensor_data')
            deleted_count = cursor.rowcount
            conn.commit()
            print(f"✅ {deleted_count}개의 데이터가 삭제되었습니다!")
        else:
            print("❌ 삭제를 취소했습니다.")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    print("🔧 ESP32 화재 감지 시스템 - 데이터 정리 도구")
    print("1. 오래된 데이터 삭제 (7일 이전)")
    print("2. 오래된 데이터 삭제 (1일 이전)")
    print("3. 모든 데이터 삭제")
    print("4. 종료")
    
    choice = input("선택해주세요 (1-4): ")
    
    if choice == "1":
        cleanup_old_data(7)
    elif choice == "2":
        cleanup_old_data(1)
    elif choice == "3":
        delete_all_data()
    elif choice == "4":
        print("종료합니다.")
    else:
        print("잘못된 선택입니다.")
