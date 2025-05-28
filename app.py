import os
import psutil
import subprocess
from flask import Flask, render_template, request, jsonify
from pathlib import Path
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_PATH = os.getenv('DEFAULT_PATH', '/Users/vinod/POCs')
HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', 5000))

def get_size(path):
    """Calculate total size of a directory or file"""
    total_size = 0
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except (PermissionError, FileNotFoundError):
        return 0
    return total_size

def format_size(size):
    """Convert size to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def get_directory_contents(path):
    """Get contents of a directory with sizes"""
    try:
        items = []
        files_size = 0
        
        # Get all items in the directory
        for item in os.listdir(path):
            full_path = os.path.join(path, item)
            try:
                if os.path.isdir(full_path):
                    size = get_size(full_path)
                    items.append({
                        'name': item,
                        'type': 'directory',
                        'size': size,  # Store raw size for sorting
                        'formatted_size': format_size(size),  # Store formatted size for display
                        'path': full_path
                    })
                else:
                    files_size += os.path.getsize(full_path)
            except (PermissionError, FileNotFoundError):
                continue
        
        # Add files category if there are any files
        if files_size > 0:
            items.append({
                'name': 'Files',
                'type': 'files',
                'size': files_size,  # Store raw size for sorting
                'formatted_size': format_size(files_size),  # Store formatted size for display
                'path': path
            })
        
        # Sort by size in descending order by default
        return sorted(items, key=lambda x: (-x['size'], x['type'] != 'directory', x['name'].lower()))
    except (PermissionError, FileNotFoundError):
        return []

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/get_directory_contents')
def get_contents():
    """API endpoint to get directory contents"""
    path = request.args.get('path', DEFAULT_PATH)
    if not os.path.exists(path):
        return jsonify({'error': 'Path does not exist'}), 404
    
    contents = get_directory_contents(path)
    parent_path = str(Path(path).parent)
    
    return jsonify({
        'contents': contents,
        'current_path': path,
        'parent_path': parent_path
    })

@app.route('/execute_command', methods=['POST'])
def execute_command():
    try:
        command = request.json.get('command')
        logger.debug(f"Received command: {command}")
        
        if not command:
            logger.error("No command provided in request")
            return jsonify({'error': 'No command provided'}), 400

        # Execute the command and capture output
        logger.debug("Executing command...")
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ.copy()
            )
            
            # Get both stdout and stderr
            stdout, stderr = process.communicate()
            logger.debug(f"Command output: {stdout}")
            if stderr:
                logger.debug(f"Command error: {stderr}")
            
            response = {
                'output': stdout,
                'error': stderr,
                'exit_code': process.returncode
            }
            logger.debug(f"Response: {response}")
            return jsonify(response)
            
        except subprocess.SubprocessError as e:
            logger.error(f"Subprocess error: {str(e)}", exc_info=True)
            return jsonify({'error': f'Command execution failed: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/get_config')
def get_config():
    """API endpoint to get application configuration"""
    return jsonify({
        'default_path': DEFAULT_PATH
    })

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=True) 