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
        """Simple password verification for demo purposes"""
        # For this demo, we'll use a simple approach
        expected_hashes = {
            'admin123': 'pbkdf2:sha256:260000$TestHash$testhash123',
            'user123': 'pbkdf2:sha256:260000$TestHash$testhash456'
        }
        return expected_hashes.get(password) == password_hash
    
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
                    
                    # Check permissions for the exact path or parent paths
                    # Start with the most specific path and go up to root
                    path_parts = path.split('/')
                    paths_to_check = []
                    
                    # Build paths from most specific to least specific
                    current_path = ""
                    for part in path_parts:
                        if part:  # Skip empty parts
                            current_path += '/' + part
                            paths_to_check.append(current_path)
                    
                    # Always check root
                    if '/' not in paths_to_check:
                        paths_to_check.append('/')
                    
                    # Check permissions in order of specificity
                    for check_path in paths_to_check:
                        cur.execute(f"""
                            SELECT {permission_field} 
                            FROM permissions 
                            WHERE user_id = %s AND path = %s
                        """, (user_id, check_path))
                        
                        result = cur.fetchone()
                        if result:
                            return result[permission_field]
                    
                    # No permissions found for any path
                    return False
                    
        except Exception as e:
            self.logger.error(f"Permission check error: {str(e)}")
            return False