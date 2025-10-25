import psycopg2
from psycopg2.extras import RealDictCursor
import logging

class StorageDB:
    def __init__(self, dsn):
        self.dsn = dsn
        self.logger = logging.getLogger('storage_service')
    
    def get_connection(self):
        return psycopg2.connect(self.dsn)
    
    def list_files(self, path):
        """List files in a path (regardless of user)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT filename, user_id 
                        FROM files 
                        WHERE path = %s
                        ORDER BY filename
                    """, (path,))
                    files = cur.fetchall()
                    return [{'filename': file['filename'], 'user_id': file['user_id']} for file in files]
        except Exception as e:
            self.logger.error(f"List files error: {str(e)}")
            return []
    
    def get_file(self, path, filename):
        """Get file content (regardless of user - permissions are handled at API level)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT content, user_id 
                        FROM files 
                        WHERE path = %s AND filename = %s
                    """, (path, filename))
                    result = cur.fetchone()
                    return result if result else None
        except Exception as e:
            self.logger.error(f"Get file error: {str(e)}")
            return None
    
    def put_file(self, path, filename, content, user_id):
        """Store or update file"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO files (path, filename, content, user_id, updated_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (path, filename) 
                        DO UPDATE SET content = %s, user_id = %s, updated_at = CURRENT_TIMESTAMP
                    """, (path, filename, content, user_id, content, user_id))
                    conn.commit()
                    return True
        except Exception as e:
            self.logger.error(f"Put file error: {str(e)}")
            return False
    
    def delete_file(self, path, filename):
        """Delete file"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM files 
                        WHERE path = %s AND filename = %s
                    """, (path, filename))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self.logger.error(f"Delete file error: {str(e)}")
            return False