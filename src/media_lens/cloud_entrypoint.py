import os
import logging
import time
import uuid
from flask import Flask, request, jsonify
import asyncio
from threading import Thread

from src.media_lens.common import create_logger, LOGGER_NAME, RunState, SITES
from src.media_lens.runner import run, Steps, process_weekly_content, summarize_all
from src.media_lens.storage_adapter import StorageAdapter

# Initialize Flask app
app = Flask(__name__)

# Setup logging
create_logger(LOGGER_NAME)
logger = logging.getLogger(LOGGER_NAME)

# Use shared storage adapter
storage: StorageAdapter = StorageAdapter.get_instance()

# Dictionary to track running tasks
active_runs = {}

@app.route('/')
def index():
    """Root endpoint that returns the application status"""
    return jsonify({
        "status": "online",
        "app": "Media Lens",
        "endpoints": [
            {"path": "/run", "method": "POST", "description": "Run the daily media lens pipeline"},
            {"path": "/weekly", "method": "POST", "description": "Process weekly content analysis"},
            {"path": "/summarize", "method": "POST", "description": "Generate daily summaries"},
            {"path": "/stop/{run_id}", "method": "POST", "description": "Stop a running pipeline by ID"},
            {"path": "/status", "method": "GET", "description": "Get status of active runs"},
            {"path": "/health", "method": "GET", "description": "Health check endpoint"}
        ]
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

def run_task_async(steps, run_id, data=None):
    """Run a task in a separate thread and track its status"""
    try:
        # Run the pipeline
        result = asyncio.run(run(
            steps=steps, 
            run_id=run_id
        ))
        
        # Update status when done
        active_runs[run_id]["status"] = result["status"]
        active_runs[run_id]["completed_steps"] = result["completed_steps"]
        if result["error"]:
            active_runs[run_id]["error"] = result["error"]
    except Exception as e:
        logger.error(f"Error in async task {run_id}: {str(e)}", exc_info=True)
        active_runs[run_id]["status"] = "error"
        active_runs[run_id]["error"] = str(e)
    finally:
        # Mark the run as no longer running
        active_runs[run_id]["running"] = False

@app.route('/run', methods=['POST'])
def run_pipeline():
    """Endpoint to run the daily pipeline asynchronously"""
    try:
        # Parse request parameters
        data = request.get_json(silent=True) or {}
        requested_steps = data.get('steps', ['harvest', 'extract', 'interpret', 'deploy'])
        
        # Convert string steps to enum
        steps = [Steps(step) for step in requested_steps]
        
        # Update sites if provided
        if data.get('sites'):
            import src.media_lens.common
            src.media_lens.common.SITES = data.get('sites')

        # Generate a unique run ID
        run_id = data.get('run_id', str(uuid.uuid4())[:8])
        
        # Check if this run ID is already in use
        if run_id in active_runs and active_runs[run_id]["running"]:
            return jsonify({
                "status": "error",
                "message": f"Run with ID {run_id} is already in progress"
            }), 409
        
        # Create a new task entry
        active_runs[run_id] = {
            "run_id": run_id,
            "status": "running",
            "running": True,
            "steps": [s.value for s in steps],
            "completed_steps": [],
            "error": None,
            "start_time": time.time()
        }
        
        # Start the task in a separate thread
        logger.info(f"Starting run {run_id} with steps: {', '.join(s.value for s in steps)}")
        thread = Thread(target=run_task_async, args=(steps, run_id, data))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "accepted", 
            "message": f"Pipeline run started with ID: {run_id}",
            "run_id": run_id
        })
    
    except Exception as e:
        logger.error(f"Error setting up pipeline run: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error", 
            "message": f"Failed to start pipeline: {str(e)}"
        }), 500

@app.route('/stop/<run_id>', methods=['POST'])
def stop_run(run_id):
    """Stop a running pipeline by ID"""
    if run_id not in active_runs:
        return jsonify({
            "status": "error",
            "message": f"No run found with ID: {run_id}"
        }), 404
        
    if not active_runs[run_id]["running"]:
        return jsonify({
            "status": "error",
            "message": f"Run {run_id} is not currently running"
        }), 400
    
    # Request the run to stop
    RunState.request_stop()
    logger.info(f"Stop requested for run {run_id}")
    
    return jsonify({
        "status": "accepted",
        "message": f"Stop requested for run {run_id}"
    })

@app.route('/status', methods=['GET'])
def get_status():
    """Get status of all active runs"""
    # Optionally filter by run_id
    run_id = request.args.get('run_id')
    
    if run_id and run_id in active_runs:
        return jsonify({
            "status": "success",
            "run": active_runs[run_id]
        })
    elif run_id:
        return jsonify({
            "status": "error",
            "message": f"No run found with ID: {run_id}"
        }), 404
    
    # Return all runs
    return jsonify({
        "status": "success",
        "active_runs": len([r for r in active_runs.values() if r["running"]]),
        "total_runs": len(active_runs),
        "runs": active_runs
    })

@app.route('/weekly', methods=['POST'])
def run_weekly():
    """Endpoint to run weekly content processing"""
    try:
        # Parse request parameters
        data = request.get_json(silent=True) or {}
        current_week_only = data.get('current_week_only', True)
        overwrite = data.get('overwrite', False)
        specific_weeks = data.get('specific_weeks', None)
        
        # Generate a unique run ID
        run_id = data.get('run_id', f"weekly-{str(uuid.uuid4())[:8]}")
        
        # Create a new task entry
        active_runs[run_id] = {
            "run_id": run_id,
            "status": "running",
            "running": True,
            "type": "weekly",
            "parameters": {
                "current_week_only": current_week_only,
                "overwrite": overwrite,
                "specific_weeks": specific_weeks
            },
            "error": None,
            "start_time": time.time()
        }
        
        # Reset run state
        RunState.reset(run_id=run_id)
        
        # Define the async task
        def run_weekly_async():
            try:
                # Run weekly processing
                asyncio.run(process_weekly_content(
                    current_week_only=current_week_only,
                    overwrite=overwrite,
                    specific_weeks=specific_weeks
                ))
                active_runs[run_id]["status"] = "success"
            except Exception as e:
                logger.error(f"Error in weekly task {run_id}: {str(e)}", exc_info=True)
                active_runs[run_id]["status"] = "error"
                active_runs[run_id]["error"] = str(e)
            finally:
                active_runs[run_id]["running"] = False
        
        # Start the task in a separate thread
        logger.info(f"Starting weekly processing {run_id} with current_week_only={current_week_only}")
        thread = Thread(target=run_weekly_async)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "accepted",
            "message": f"Weekly processing started with ID: {run_id}",
            "run_id": run_id
        })
    
    except Exception as e:
        logger.error(f"Error setting up weekly processing: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error", 
            "message": f"Failed to start weekly processing: {str(e)}"
        }), 500

@app.route('/summarize', methods=['POST'])
def run_summarize():
    """Endpoint to run daily summarization"""
    try:
        # Parse request parameters
        data = request.get_json(silent=True) or {}
        force = data.get('force', False)
        
        # Generate a unique run ID
        run_id = data.get('run_id', f"summary-{str(uuid.uuid4())[:8]}")
        
        # Create a new task entry
        active_runs[run_id] = {
            "run_id": run_id,
            "status": "running",
            "running": True,
            "type": "summarize",
            "parameters": {
                "force": force
            },
            "error": None,
            "start_time": time.time()
        }
        
        # Reset run state
        RunState.reset(run_id=run_id)
        
        # Define the async task
        def run_summarize_async():
            try:
                # Run summarization
                asyncio.run(summarize_all(force=force))
                active_runs[run_id]["status"] = "success"
            except Exception as e:
                logger.error(f"Error in summarize task {run_id}: {str(e)}", exc_info=True)
                active_runs[run_id]["status"] = "error"
                active_runs[run_id]["error"] = str(e)
            finally:
                active_runs[run_id]["running"] = False
        
        # Start the task in a separate thread
        logger.info(f"Starting daily summarization {run_id} with force={force}")
        thread = Thread(target=run_summarize_async)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "accepted",
            "message": f"Summarization started with ID: {run_id}",
            "run_id": run_id
        })
    
    except Exception as e:
        logger.error(f"Error setting up summarization: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error", 
            "message": f"Failed to start summarization: {str(e)}"
        }), 500

if __name__ == '__main__':
    # For local testing
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')