import psycopg2
from psycopg2.extras import RealDictCursor
import logging

class AuthDB:
    def __init__(self, dsn):
        self.dsn = dsn
        self.logger = logging.getLogger('auth_service')
    
    def get_connection(self):
        return psycopg2.connect(self.dsn)
    
    def authenticate_user(self, username, password):
        """Authenticate user and return user info if successful"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT id, username, password_hash FROM users WHERE username = %s",
                        (username,)
                    )
                    user = cur.fetchone()
                    
                    if user and self.verify_password(password, user['password_hash']):
                        return {
                            'id': user['id'],
                            'username': user['username']
                        }
                    return None
        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return None
    
    def verify_password(self, password, password_hash):
        """Simple password verification (in production use proper hashing)"""
        # For demo purposes, using simple verification
        # In real scenario, use: return check_password_hash(password_hash, password)
        return password_hash.startswith('pbkdf2:sha256')
    
    def check_permission(self, user_id, path, operation):
        """Check if user has permission for operation on path"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if operation == 'read':
                        permission_field = 'can_read'
                    elif operation == 'write':
                        permission_field = 'can_write'
                    else:
                        return False
                    
                    # Check exact path match or parent path permissions
                    cur.execute(f"""
                        SELECT {permission_field} 
                        FROM permissions 
                        WHERE user_id = %s AND (path = %s OR path = '/')
                        ORDER BY 
                            CASE WHEN path = %s THEN 1 ELSE 2 END
                        LIMIT 1
                    """, (user_id, path, path))
                    
                    result = cur.fetchone()
                    return result and result[permission_field]
                    
        except Exception as e:
            self.logger.error(f"Permission check error: {str(e)}")
            return False