import psycopg2
from psycopg2.extras import RealDictCursor
import logging

class StorageDB:
    def __init__(self, dsn):
        self.dsn = dsn
        self.logger = logging.getLogger('storage_service')
    
    def get_connection(self):
        return psycopg2.connect(self.dsn)
    
    def list_files(self, path, user_id):
        """List files in a path for a user"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT filename 
                        FROM files 
                        WHERE path = %s AND user_id = %s
                        ORDER BY filename
                    """, (path, user_id))
                    files = cur.fetchall()
                    return [file['filename'] for file in files]
        except Exception as e:
            self.logger.error(f"List files error: {str(e)}")
            return []
    
    def get_file(self, path, filename, user_id):
        """Get file content"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT content 
                        FROM files 
                        WHERE path = %s AND filename = %s AND user_id = %s
                    """, (path, filename, user_id))
                    result = cur.fetchone()
                    return result['content'] if result else None
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
                        DO UPDATE SET content = %s, updated_at = CURRENT_TIMESTAMP
                    """, (path, filename, content, user_id, content))
                    conn.commit()
                    return True
        except Exception as e:
            self.logger.error(f"Put file error: {str(e)}")
            return False
    
    def delete_file(self, path, filename, user_id):
        """Delete file"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM files 
                        WHERE path = %s AND filename = %s AND user_id = %s
                    """, (path, filename, user_id))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self.logger.error(f"Delete file error: {str(e)}")
            return False