from flask import Flask, request, jsonify
import jwt
import datetime
import os
import logging
import sys
from models import AuthDB

class CombinedLogFormatter(logging.Formatter):
    """Custom formatter for combined log format"""
    def format(self, record):
        # Get client IP (approximation in containerized environment)
        client_ip = getattr(record, 'client_ip', '-')
        
        # Get timestamp
        timestamp = self.formatTime(record, self.datefmt)
        
        # Get request line if available
        request_line = getattr(record, 'request_line', '-')
        
        # Get status code if available
        status_code = getattr(record, 'status_code', '-')
        
        # Get response size if available
        response_size = getattr(record, 'response_size', '-')
        
        # Standard combined log format
        if hasattr(record, 'request_line'):
            return f'{client_ip} - - [{timestamp}] "{request_line}" {status_code} {response_size}'
        else:
            # For non-request logs, use standard format
            return f'{timestamp} - {record.name} - {record.levelname} - {record.getMessage()}'

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

def setup_logging():
    # Create logger
    logger = logging.getLogger('auth_service')
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create combined log formatter
    formatter = CombinedLogFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%d/%b/%Y:%H:%M:%S %z'
    )
    
    # Stdout handler for all logs (combined format)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(stdout_handler)
    
    # Also configure Flask's logger
    flask_logger = logging.getLogger('werkzeug')
    flask_logger.setLevel(logging.INFO)
    flask_logger.handlers.clear()
    flask_logger.addHandler(stdout_handler)
    
    return logger

# Initialize logger
logger = setup_logging()

# Initialize database
db = None
tokens = {}  # In-memory token storage

# Request logging middleware
@app.before_request
def log_request():
    """Log incoming requests"""
    request.environ['START_TIME'] = os.times().elapsed
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', '-'))
    request.environ['CLIENT_IP'] = client_ip

@app.after_request
def log_response(response):
    """Log responses in combined log format"""
    # Get request information
    client_ip = getattr(request, 'environ', {}).get('CLIENT_IP', '-')
    method = request.method
    path = request.path
    http_version = request.environ.get('SERVER_PROTOCOL', 'HTTP/1.1')
    status_code = response.status_code
    response_size = response.content_length if response.content_length else 0
    
    # Build request line
    request_line = f"{method} {path} {http_version}"
    
    # Log in combined format
    logger.info(
        "",
        extra={
            'client_ip': client_ip,
            'request_line': request_line,
            'status_code': status_code,
            'response_size': response_size
        }
    )
    
    return response

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
        if db.check_permission(user_id, path, operation):
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

# Custom error handlers that log errors
@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404 Not Found: {request.url}")
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 Internal Server Error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    dsn = os.environ.get('DATABASE_DSN', 'postgresql://postgres:password@db:5432/file_storage')
    db = AuthDB(dsn)
    
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5001))
    
    logger.info(f"Starting auth service on {host}:{port}")
    app.run(host=host, port=port, debug=False)