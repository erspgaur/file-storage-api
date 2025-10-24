from flask import Flask, request, jsonify, send_file
import requests
import jwt
import os
import logging
import sys
from io import BytesIO
from models import StorageDB

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
logger = logging.getLogger('storage_service')

# Configuration
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://auth:5001')
db = None

def get_user_id_from_token(token):
    """Extract user ID from token"""
    try:
        # First try to decode the token
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload.get('user_id')
    except jwt.InvalidTokenError:
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
            return jsonify({'error': 'Username and password required'}), 400
        
        response = requests.post(
            f"{AUTH_SERVICE_URL}/authenticate",
            json=data,
            timeout=5
        )
        
        # Forward the response from auth service
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
        return jsonify({'error': 'Bearer token required'}), 401
    
    if not path:
        return jsonify({'error': 'Path parameter required'}), 400
    
    user_id = get_user_id_from_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    if not check_auth(token, path, 'read'):
        return jsonify({'error': 'Access denied'}), 403
    
    files = db.list_files(path, user_id)
    logger.info(f"User {user_id} listed files in {path}")
    return jsonify({'path': path, 'files': files})

@app.route('/get', methods=['GET'])
def get_file():
    """Get file content"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    path = request.args.get('path', '')
    filename = request.args.get('filename', '')
    
    if not token:
        return jsonify({'error': 'Bearer token required'}), 401
    
    if not path or not filename:
        return jsonify({'error': 'Path and filename parameters required'}), 400
    
    user_id = get_user_id_from_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    if not check_auth(token, path, 'read'):
        return jsonify({'error': 'Access denied'}), 403
    
    content = db.get_file(path, filename, user_id)
    if content is None:
        return jsonify({'error': 'File not found'}), 404
    
    logger.info(f"User {user_id} retrieved file {path}/{filename}")
    return send_file(
        BytesIO(content),
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
        return jsonify({'error': 'Bearer token required'}), 401
    
    if not path or not filename:
        return jsonify({'error': 'Path and filename parameters required'}), 400
    
    user_id = get_user_id_from_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    if not check_auth(token, path, 'write'):
        return jsonify({'error': 'Access denied'}), 403
    
    content = request.get_data()
    
    if db.put_file(path, filename, content, user_id):
        logger.info(f"User {user_id} stored file {path}/{filename}")
        return jsonify({'message': 'File stored successfully'}), 200
    else:
        return jsonify({'error': 'Failed to store file'}), 500

if __name__ == '__main__':
    dsn = os.environ.get('DATABASE_DSN', 'postgresql://postgres:password@db:5432/file_storage')
    db = StorageDB(dsn)
    
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    
    logger.info(f"Starting storage service on {host}:{port}")
    app.run(host=host, port=port, debug=False)