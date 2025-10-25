from flask import Flask, request, jsonify, send_file
import requests
import jwt
import os
import logging
from io import BytesIO
from models import StorageDB

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Get logger
logger = logging.getLogger('storage_service')

# Configuration
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://auth:5001')
db = None

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
        logger.info(f"Checking authorization for path: {path}, operation: {operation}")
        response = requests.post(
            f"{AUTH_SERVICE_URL}/authorize",
            json={
                'token': token,
                'path': path,
                'operation': operation
            },
            timeout=5
        )
        logger.info(f"Auth service response: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            return result.get('authorized', False)
        return False
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
        
        logger.info(f"Login attempt for user: {data.get('username')}")
        response = requests.post(
            f"{AUTH_SERVICE_URL}/authenticate",
            json=data,
            timeout=5
        )
        
        logger.info(f"Login response status: {response.status_code}")
        return jsonify(response.json()), response.status_code
        
    except requests.RequestException as e:
        logger.error(f"Auth service connection error: {str(e)}")
        return jsonify({'error': 'Authentication service unavailable'}), 503

@app.route('/list', methods=['GET'])
def list_files():
    """List files in a path"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    path = request.args.get('path', '')
    
    logger.info(f"List files request - Path: {path}, Token present: {bool(token)}")
    
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
    
    logger.info(f"Get file request - Path: {path}, File: {filename}, Token present: {bool(token)}")
    
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
    
    logger.info(f"Put file request - Path: {path}, File: {filename}, Token present: {bool(token)}")
    
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

if __name__ == '__main__':
    dsn = os.environ.get('DATABASE_DSN', 'postgresql://postgres:password@db:5432/file_storage')
    db = StorageDB(dsn)
    
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    
    logger.info(f"Starting storage service on {host}:{port}")
    app.run(host=host, port=port, debug=False)