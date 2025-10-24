from flask import Flask, request, jsonify
import jwt
import datetime
import os
import logging
from logging.handlers import RotatingFileHandler
import sys
from models import AuthDB

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Combined log to stdout
        logging.StreamHandler(sys.stderr)   # Error log to stderr
    ]
)
logger = logging.getLogger('auth_service')

# Initialize database
db = None
tokens = {}  # In-memory token storage (in production use Redis)

@app.route('/authenticate', methods=['POST'])
def authenticate():
    """Authenticate user and return token"""
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Username and password required'}), 400
        
        username = data['username']
        password = data['password']
        
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
            return jsonify({'error': 'Token, path and operation required'}), 400
        
        token = data['token']
        path = data['path']
        operation = data['operation']
        
        if operation not in ['read', 'write']:
            return jsonify({'error': 'Operation must be read or write'}), 400
        
        # Verify token
        if token not in tokens:
            try:
                payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                user_id = payload['user_id']
                # Refresh token in storage
                tokens[token] = user_id
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Invalid token'}), 401
        else:
            user_id = tokens[token]
        
        # Check permission
        if db.check_permission(user_id, path, operation):
            logger.info(f"Authorization granted for user {user_id} on {path} for {operation}")
            return jsonify({'authorized': True}), 200
        else:
            logger.warning(f"Authorization denied for user {user_id} on {path} for {operation}")
            return jsonify({'authorized': False}), 403
            
    except Exception as e:
        logger.error(f"Authorization error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    dsn = os.environ.get('DATABASE_DSN', 'postgresql://postgres:password@localhost:5432/file_storage')
    db = AuthDB(dsn)
    
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5001))
    
    logger.info(f"Starting auth service on {host}:{port}")
    app.run(host=host, port=port, debug=False)