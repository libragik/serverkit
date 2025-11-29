import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid
import time
import os
import sys
import shutil
import subprocess
from typing import Optional
from worker import SkoolClassroomScraper, Config as ScraperConfig

# --- AUTO-INSTALL BROWSERS (CRUCIAL FOR RENDER) ---
def install_browsers():
    print("🔧 Checking/Installing Playwright Browsers...")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✅ Browsers installed.")
    except Exception as e:
        print(f"⚠️ Warning: Could not install browsers: {e}")

# Run install on startup
install_browsers()

app = FastAPI()

# Enable CORS for the React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage (Use Redis/DB in production)
jobs = {}

class ScrapeRequest(BaseModel):
    classroomUrl: str
    email: str
    password: str
    downloadFiles: bool = True
    headless: bool = False

@app.post("/api/start_job")
async def start_job(request: ScrapeRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        "status": "queued",
        "logs": [],
        "result": None,
        "progress": 0
    }
    
    # Start the worker in background
    background_tasks.add_task(run_scraper_task, job_id, request)
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/download_result/{job_id}")
async def download_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed" or not job["result"]:
         raise HTTPException(status_code=400, detail="Job not completed or no result found")
    
    output_dir = job["result"]
    zip_filename = f"skool_export_{job_id}"
    
    # Create zip archive of the output directory
    # make_archive saves to current directory, we return that path
    try:
        zip_path = shutil.make_archive(zip_filename, 'zip', output_dir)
        return FileResponse(zip_path, media_type='application/zip', filename=f"{zip_filename}.zip")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create zip: {str(e)}")

# Root endpoint for health check
@app.get("/")
def read_root():
    return {"status": "ok", "message": "Skool Scraper API is running"}

def run_scraper_task(job_id, request: ScrapeRequest):
    job = jobs[job_id]
    job["status"] = "running"
    
    def log_callback(message, type="info"):
        print(f"[{job_id}] {message}")
        job["logs"].append({
            "timestamp": time.strftime("%H:%M:%S"),
            "message": message,
            "type": type
        })
    
    try:
        # Map Request to Scraper Config
        config = ScraperConfig()
        config.CLASSROOM_URL = request.classroomUrl
        config.SKOOL_EMAIL = request.email
        config.SKOOL_PASSWORD = request.password
        config.DOWNLOAD_FILES = request.downloadFiles
        config.HEADLESS = request.headless
        # Use unique output dir for this job to avoid collisions
        config.OUTPUT_DIR = f"skool_export_{job_id}"
        
        log_callback("Initializing Scraper Engine...", "info")
        
        # Initialize Scraper with Callback
        scraper = SkoolClassroomScraper(config, callback=log_callback)
        result_path = scraper.run()
        
        job["result"] = result_path
        job["status"] = "completed"
        job["progress"] = 100
        log_callback("Job finished successfully!", "success")
        
    except Exception as e:
        job["status"] = "failed"
        log_callback(f"Critical Error: {str(e)}", "error")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting Skool Scraper API on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
