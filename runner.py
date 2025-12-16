"""
Refactored Flask API with proper error handling and logging.
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from celery.result import AsyncResult
import base64

from worker import celery_app, long_running_task, analyse_sample
from config import get_settings
from logging_config import setup_logging, get_logger

# Initialize settings and logging
settings = get_settings()
setup_logging(
    log_level=settings.log_level,
    log_file=settings.log_file
)
logger = get_logger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Active tasks tracking
active_tasks = {}

logger.info("Flask API initialized")


@app.route("/start-analysis", methods=["POST"])
def start_analysis():
    """
    Start VirusTotal analysis for uploaded file.
    
    Expected JSON:
        {
            "file_name": "example.exe",
            "byte_data": "base64_encoded_file_content"
        }
    
    Returns:
        JSON with task_id
    """
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("No JSON data received")
            return jsonify({"error": "No data provided"}), 400
        
        file_name = data.get("file_name")
        encoded_data = data.get("byte_data")
        
        if not file_name or not encoded_data:
            logger.warning("Missing file_name or byte_data")
            return jsonify({"error": "Missing file_name or byte_data"}), 400
        
        # Decode base64 data
        try:
            byte_data = base64.b64decode(encoded_data)
            logger.info(f"Received file: {file_name}, size: {len(byte_data)} bytes")
        except Exception as e:
            logger.error(f"Failed to decode base64 data: {e}", exc_info=True)
            return jsonify({"error": "Invalid base64 data"}), 400
        
        # Start analysis task
        args = [file_name, byte_data]
        task = analyse_sample.apply_async(args=args)
        active_tasks[task.id] = "PENDING"
        
        logger.info(f"Started analysis task: {task.id}")
        return jsonify({"task_id": task.id}), 202
    
    except Exception as e:
        logger.error(f"Error starting analysis: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/start-task", methods=["POST"])
def start_task():
    """
    Start crawling task.
    
    Expected JSON:
        {
            "web": "https://example.com",
            "filter": "search_keyword",
            "driver": "chrome",
            "device": "desktop"
        }
    
    Returns:
        JSON with task_id
    """
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("No JSON data received")
            return jsonify({"error": "No data provided"}), 400
        
        url = data.get("web")
        what_to_crawl = data.get("filter")
        driver = data.get("driver", "chrome")
        device = data.get("device", "desktop")
        
        if not url or not what_to_crawl:
            logger.warning("Missing required parameters")
            return jsonify({"error": "Missing web or filter parameter"}), 400
        
        logger.info(f"Starting crawl task: {url}, filter: {what_to_crawl}")
        
        # Start crawling task
        args = [url, what_to_crawl, driver, device]
        task = long_running_task.apply_async(args=args)
        active_tasks[task.id] = "PENDING"
        
        logger.info(f"Started crawl task: {task.id}")
        return jsonify({"task_id": task.id}), 202
    
    except Exception as e:
        logger.error(f"Error starting task: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/tasks-status", methods=["GET"])
def get_all_tasks_status():
    """
    Get status of all active tasks.
    
    Returns:
        JSON array with task statuses
    """
    try:
        task_status_list = []
        
        for task_id in list(active_tasks.keys()):
            try:
                task_result = AsyncResult(task_id, app=celery_app)
                logger.debug(f"Task {task_id} status: {task_result.status}")
                
                # Remove completed tasks (except analysis completed)
                if task_result.status in ["SUCCESS", "FAILURE", "REVOKED"]:
                    if not (isinstance(task_result.info, dict) and 
                           task_result.info.get("status") == "Analysis completed"):
                        active_tasks.pop(task_id, None)
                        logger.debug(f"Removed completed task: {task_id}")
                
                task_status_list.append({
                    "task_id": task_id,
                    "status": task_result.status,
                    "progress": task_result.info if task_result.info else {}
                })
            
            except Exception as e:
                logger.error(f"Error getting status for task {task_id}: {e}", exc_info=True)
                active_tasks.pop(task_id, None)
        
        return jsonify(task_status_list)
    
    except Exception as e:
        logger.error(f"Error getting tasks status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/get-analysis", methods=["GET"])
def get_latest_analysis():
    """
    Get latest completed analysis results.
    
    Returns:
        JSON with analysis data or waiting message
    """
    try:
        for task_id in list(active_tasks.keys()):
            try:
                task_result = AsyncResult(task_id, app=celery_app)
                
                if task_result.state == "SUCCESS":
                    result_data = task_result.result
                    
                    if isinstance(result_data, dict) and \
                       result_data.get("status") == "Analysis completed":
                        active_tasks.pop(task_id, None)
                        logger.info(f"Analysis completed for task: {task_id}")
                        
                        return jsonify({
                            "message": "Analysis completed",
                            "data": result_data.get("data")
                        }), 200
            
            except Exception as e:
                logger.error(f"Error processing analysis for task {task_id}: {e}", exc_info=True)
                active_tasks.pop(task_id, None)
        
        return jsonify({
            "message": "No completed analysis yet",
        }), 202
    
    except Exception as e:
        logger.error(f"Error getting analysis: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "active_tasks": len(active_tasks)
    }), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    logger.info(f"Starting Flask server on {settings.flask_host}:{settings.flask_port}")
    app.run(
        host=settings.flask_host,
        port=settings.flask_port,
        debug=settings.flask_debug
    )