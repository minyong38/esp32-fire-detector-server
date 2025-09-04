"""
DB의 sensor_data 테이블의 모든 데이터를 삭제하는 유틸리티 스크립트
"""
from db_utils import get_db_connection

if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM sensor_data")
            conn.commit()
            cur.execute("ALTER TABLE sensor_data AUTO_INCREMENT = 1")
            conn.commit()
            print("sensor_data 테이블의 모든 데이터가 삭제되고, AUTO_INCREMENT가 1로 초기화되었습니다.")
        except Exception as e:
            print("삭제 중 오류:", e)
        finally:
            cur.close()
            conn.close()
    else:
        print("DB 연결 실패")
