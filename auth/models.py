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
                    
                    # First, check if user has explicit permission for the exact path
                    cur.execute(f"""
                        SELECT {permission_field} 
                        FROM permissions 
                        WHERE user_id = %s AND path = %s
                    """, (user_id, path))
                    
                    exact_match = cur.fetchone()
                    if exact_match:
                        self.logger.info(f"Exact permission match for user {user_id} on path {path}: {exact_match[permission_field]}")
                        return exact_match[permission_field]
                    
                    # If no exact match, check if user has permission for parent paths
                    # Build parent paths (e.g., for "/docs/file" check "/docs" and "/")
                    path_parts = path.rstrip('/').split('/')
                    parent_paths = []
                    
                    # Start from the most specific parent to the root
                    current_path = ""
                    for part in path_parts:
                        if part:  # Skip empty parts for root
                            current_path += '/' + part
                            parent_paths.append(current_path)
                    
                    # Check each parent path from most specific to least specific
                    for parent_path in reversed(parent_paths):
                        cur.execute(f"""
                            SELECT {permission_field} 
                            FROM permissions 
                            WHERE user_id = %s AND path = %s
                        """, (user_id, parent_path))
                        
                        parent_match = cur.fetchone()
                        if parent_match:
                            self.logger.info(f"Parent permission match for user {user_id} on parent path {parent_path}: {parent_match[permission_field]}")
                            return parent_match[permission_field]
                    
                    # Check root permission as last resort
                    cur.execute(f"""
                        SELECT {permission_field} 
                        FROM permissions 
                        WHERE user_id = %s AND path = '/'
                    """, (user_id,))
                    
                    root_match = cur.fetchone()
                    if root_match:
                        self.logger.info(f"Root permission match for user {user_id}: {root_match[permission_field]}")
                        return root_match[permission_field]
                    
                    # No permissions found
                    self.logger.info(f"No permissions found for user {user_id} on path {path}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Permission check error: {str(e)}")
            return False