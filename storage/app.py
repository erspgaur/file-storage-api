from flask import Flask, request, jsonify, send_file
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import WSGIRequestHandler
import requests
import jwt
import os
import logging
import sys
from io import BytesIO
from models import StorageDB

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

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Custom logger class to capture request information
class RequestLogger:
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger('storage_service')
        
    def __call__(self, environ, start_response):
        def custom_start_response(status, headers, exc_info=None):
            # Capture status code
            status_code = status.split(' ')[0]
            environ['STATUS_CODE'] = status_code
            
            # Capture response size
            content_length = next((h[1] for h in headers if h[0].lower() == 'content-length'), '0')
            environ['RESPONSE_SIZE'] = content_length
            
            return start_response(status, headers, exc_info)
        
        return self.app(environ, custom_start_response)

# Setup comprehensive logging
def setup_logging():
    # Create logger
    logger = logging.getLogger('storage_service')
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

# Configuration
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://auth:5001')
db = None

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
    query_string = request.query_string.decode()
    if query_string:
        path = f"{path}?{query_string}"
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

def get_user_id_from_token(token):
    """Extract user ID from token"""
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload.get('user_id')
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        return None

def check_auth(token, path, operation):
    """Check authorization with auth service"""
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/authorize",
            json={
                'token': token,
                'path': path,
                'operation': operation
            },
            timeout=5
        )
        logger.info(f"Auth check for path {path}, operation {operation}: {response.status_code}")
        return response.status_code == 200 and response.json().get('authorized', False)
    except requests.RequestException as e:
        logger.error(f"Auth service error: {str(e)}")
        return False

@app.route('/login', methods=['POST'])
def login():
    """Login endpoint that forwards to auth service"""
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            logger.warning("Login attempt missing username or password")
            return jsonify({'error': 'Username and password required'}), 400
        
        response = requests.post(
            f"{AUTH_SERVICE_URL}/authenticate",
            json=data,
            timeout=5
        )
        
        username = data.get('username')
        logger.info(f"Login attempt for user {username}: {response.status_code}")
        return jsonify(response.json()), response.status_code
        
    except requests.RequestException as e:
        logger.error(f"Auth service connection error: {str(e)}")
        return jsonify({'error': 'Authentication service unavailable'}), 503

@app.route('/list', methods=['GET'])
def list_files():
    """List files in a path"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    path = request.args.get('path', '')
    
    if not token:
        logger.warning("List files attempt without token")
        return jsonify({'error': 'Bearer token required'}), 401
    
    if not path:
        logger.warning("List files attempt without path")
        return jsonify({'error': 'Path parameter required'}), 400
    
    user_id = get_user_id_from_token(token)
    if not user_id:
        logger.warning(f"List files attempt with invalid token for path {path}")
        return jsonify({'error': 'Invalid token'}), 401
    
    if not check_auth(token, path, 'read'):
        logger.warning(f"User {user_id} denied read access to path {path}")
        return jsonify({'error': 'Access denied'}), 403
    
    files_data = db.list_files(path)
    files = [file_data['filename'] for file_data in files_data]
    
    logger.info(f"User {user_id} listed {len(files)} files in {path}")
    return jsonify({'path': path, 'files': files})

@app.route('/get', methods=['GET'])
def get_file():
    """Get file content"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    path = request.args.get('path', '')
    filename = request.args.get('filename', '')
    
    if not token:
        logger.warning("Get file attempt without token")
        return jsonify({'error': 'Bearer token required'}), 401
    
    if not path or not filename:
        logger.warning("Get file attempt missing path or filename")
        return jsonify({'error': 'Path and filename parameters required'}), 400
    
    user_id = get_user_id_from_token(token)
    if not user_id:
        logger.warning(f"Get file attempt with invalid token for {path}/{filename}")
        return jsonify({'error': 'Invalid token'}), 401
    
    if not check_auth(token, path, 'read'):
        logger.warning(f"User {user_id} denied read access to {path}/{filename}")
        return jsonify({'error': 'Access denied'}), 403
    
    file_data = db.get_file(path, filename)
    if file_data is None:
        logger.info(f"File not found: {path}/{filename}")
        return jsonify({'error': 'File not found'}), 404
    
    logger.info(f"User {user_id} retrieved file {path}/{filename}")
    return send_file(
        BytesIO(file_data['content']),
        as_attachment=True,
        download_name=filename
    )

@app.route('/put', methods=['PUT'])
def put_file():
    """Store or update file"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    path = request.args.get('path', '')
    filename = request.args.get('filename', '')
    
    if not token:
        logger.warning("Put file attempt without token")
        return jsonify({'error': 'Bearer token required'}), 401
    
    if not path or not filename:
        logger.warning("Put file attempt missing path or filename")
        return jsonify({'error': 'Path and filename parameters required'}), 400
    
    user_id = get_user_id_from_token(token)
    if not user_id:
        logger.warning(f"Put file attempt with invalid token for {path}/{filename}")
        return jsonify({'error': 'Invalid token'}), 401
    
    if not check_auth(token, path, 'write'):
        logger.warning(f"User {user_id} denied write access to {path}/{filename}")
        return jsonify({'error': 'Access denied'}), 403
    
    content = request.get_data()
    
    if db.put_file(path, filename, content, user_id):
        logger.info(f"User {user_id} stored file {path}/{filename} ({len(content)} bytes)")
        return jsonify({'message': 'File stored successfully'}), 200
    else:
        logger.error(f"User {user_id} failed to store file {path}/{filename}")
        return jsonify({'error': 'Failed to store file'}), 500

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
    db = StorageDB(dsn)
    
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    
    # Wrap app with request logger
    app.wsgi_app = RequestLogger(app.wsgi_app)
    
    logger.info(f"Starting storage service on {host}:{port}")
    
    # Configure WSGI request handler for better logging
    WSGIRequestHandler.log_request = lambda self, *args: None  # Disable default logging
    
    app.run(host=host, port=port, debug=False)