from flask import Flask, request, jsonify
import jwt
import datetime
import os
import logging
from models import AuthDB

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Get logger
logger = logging.getLogger('auth_service')

# Initialize database
db = None
tokens = {}  # In-memory token storage

@app.route('/authenticate', methods=['POST'])
def authenticate():
    """Authenticate user and return token"""
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            logger.warning("Authentication attempt missing credentials")
            return jsonify({'error': 'Username and password required'}), 400
        
        username = data['username']
        password = data['password']
        
        logger.info(f"Authentication attempt for user: {username}")
        user = db.authenticate_user(username, password)
        if user:
            # Generate token
            token_payload = {
                'user_id': user['id'],
                'username': user['username'],
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }
            token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm='HS256')
            
            # Store token in memory
            tokens[token] = user['id']
            
            logger.info(f"User {username} authenticated successfully")
            return jsonify({'token': token})
        else:
            logger.warning(f"Failed authentication attempt for user: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/authorize', methods=['POST'])
def authorize():
    """Authorize user for file operation"""
    try:
        data = request.get_json()
        if not data or 'token' not in data or 'path' not in data or 'operation' not in data:
            logger.warning("Authorization attempt missing required fields")
            return jsonify({'error': 'Token, path and operation required'}), 400
        
        token = data['token']
        path = data['path']
        operation = data['operation']
        
        logger.info(f"Authorization check - Path: {path}, Operation: {operation}")
        
        if operation not in ['read', 'write']:
            logger.warning(f"Invalid operation attempted: {operation}")
            return jsonify({'error': 'Operation must be read or write'}), 400
        
        # Verify token
        if token not in tokens:
            try:
                payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                user_id = payload['user_id']
                # Refresh token in storage
                tokens[token] = user_id
                logger.info(f"Token validated for user {user_id}")
            except jwt.ExpiredSignatureError:
                logger.warning("Expired token used for authorization")
                return jsonify({'error': 'Token expired'}), 401
            except jwt.InvalidTokenError:
                logger.warning("Invalid token used for authorization")
                return jsonify({'error': 'Invalid token'}), 401
        else:
            user_id = tokens[token]
        
        # Check permission
        authorized = db.check_permission(user_id, path, operation)
        logger.info(f"Permission check result for user {user_id}: {authorized}")
        
        if authorized:
            logger.info(f"Authorization granted for user {user_id} on {path} for {operation}")
            return jsonify({'authorized': True}), 200
        else:
            logger.warning(f"Authorization denied for user {user_id} on {path} for {operation}")
            return jsonify({'authorized': False}), 403
            
    except Exception as e:
        logger.error(f"Authorization error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for testing"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    dsn = os.environ.get('DATABASE_DSN', 'postgresql://postgres:password@db:5432/file_storage')
    db = AuthDB(dsn)
    
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5001))
    
    logger.info(f"Starting auth service on {host}:{port}")
    app.run(host=host, port=port, debug=False)