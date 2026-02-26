from fastapi import FastAPI, Request, UploadFile, File, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
import shutil
import os
import json
import pandas as pd
import uvicorn
from app.detection.scoring import FraudDetector

app = FastAPI(title="Money Muling Forensics Engine")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Global storage for latest results (for demo simplicity)
# In production, use a database or session-based storage
LATEST_RESULTS = {}
LATEST_RESULTS_FILE = "results.json"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/results", response_class=HTMLResponse)
async def read_results(request: Request):
    return templates.TemplateResponse("results.html", {"request": request})

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    print(f"Received file upload: {file.filename}")
    # Save file temporarily
    file_location = f"temp_{file.filename}"
    try:
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        
        print(f"File saved to {file_location}. Starting analysis...")
        
        # Run analysis
        detector = FraudDetector()
        results = detector.run_analysis(file_location)
        print("Analysis complete.")
        
        # Store results
        global LATEST_RESULTS
        LATEST_RESULTS = results
        
        # Save to file for download
        with open(LATEST_RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Clean up temp file
        if os.path.exists(file_location):
            os.remove(file_location)
        
        if "error" in results:
            print(f"Analysis error: {results['error']}")
            return JSONResponse(content=results, status_code=400)
            
        print("Returning success response.")
        return JSONResponse(content={"status": "success", "summary": results['summary']})
    except Exception as e:
        print(f"Critical error during processing: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/results")
async def get_results():
    global LATEST_RESULTS
    if not LATEST_RESULTS:
        # Return empty structure or error
        return JSONResponse(content={"error": "No analysis results found. Please upload a CSV."}, status_code=404)
    return JSONResponse(content=LATEST_RESULTS)

@app.get("/api/download")
async def download_results():
    if not os.path.exists(LATEST_RESULTS_FILE):
         return JSONResponse(content={"error": "No results available to download"}, status_code=404)
    return FileResponse(LATEST_RESULTS_FILE, media_type="application/json", filename="results.json")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
