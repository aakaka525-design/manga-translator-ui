"""
Web routes module.

This module contains Web UI related endpoints for the manga translator server.
"""

import os
import shutil
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

router = APIRouter(tags=["web"])

# Static directory path
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
dist_dir = os.path.join(static_dir, "dist")


def _serve_spa() -> HTMLResponse:
    index_path = os.path.join(dist_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as handle:
            return HTMLResponse(handle.read())
    return HTMLResponse(
        "<h1>Vue frontend not built</h1><p>Please build frontend and place files under manga_translator/server/static/dist/</p>",
        status_code=503,
    )


# ============================================================================
# Web UI Page Endpoints
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve SPA root page."""
    return _serve_spa()


@router.get("/admin", response_class=HTMLResponse)
async def read_admin():
    return _serve_spa()


@router.get("/signin", response_class=HTMLResponse)
async def read_signin():
    return _serve_spa()


@router.get("/scraper", response_class=HTMLResponse)
async def read_scraper():
    return _serve_spa()


@router.get("/manga/{manga_id}", response_class=HTMLResponse)
async def read_manga(manga_id: str):
    _ = manga_id
    return _serve_spa()


@router.get("/read/{manga_id}/{chapter_id}", response_class=HTMLResponse)
async def read_reader(manga_id: str, chapter_id: str):
    _ = (manga_id, chapter_id)
    return _serve_spa()


@router.get("/static/login.html", include_in_schema=False)
async def legacy_login_redirect():
    return RedirectResponse("/signin", status_code=307)





@router.get("/api")
async def api_info():
    """API server information"""
    return {
        "message": "Manga Translator API Server",
        "version": "2.0",
        "endpoints": {
            "translate": "/translate/image",
            "translate_stream": "/translate/with-form/image/stream",
            "batch": "/translate/batch/json",
            "docs": "/docs"
        }
    }


# ============================================================================
# Result File Management Endpoints
# ============================================================================

@router.api_route("/result/{folder_name}/final.png", methods=["GET", "HEAD"])
async def get_result_by_folder(folder_name: str):
    """Get translation result image by folder name"""
    result_dir = "../result"
    if not os.path.exists(result_dir):
        raise HTTPException(404, detail="Result directory not found")

    folder_path = os.path.join(result_dir, folder_name)
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        raise HTTPException(404, detail=f"Folder {folder_name} not found")

    final_png_path = os.path.join(folder_path, "final.png")
    if not os.path.exists(final_png_path):
        raise HTTPException(404, detail="final.png not found in folder")

    async def file_iterator():
        with open(final_png_path, "rb") as f:
            yield f.read()

    return StreamingResponse(
        file_iterator(),
        media_type="image/png",
        headers={"Content-Disposition": "inline; filename=final.png"}
    )


@router.get("/results/list")
async def list_results():
    """List all result directories"""
    result_dir = "../result"
    if not os.path.exists(result_dir):
        return {"directories": []}
    
    try:
        directories = []
        for item in os.listdir(result_dir):
            item_path = os.path.join(result_dir, item)
            if os.path.isdir(item_path):
                # Check if final.png exists in this directory
                final_png_path = os.path.join(item_path, "final.png")
                if os.path.exists(final_png_path):
                    directories.append(item)
        return {"directories": directories}
    except Exception as e:
        raise HTTPException(500, detail=f"Error listing results: {str(e)}")


@router.delete("/results/clear")
async def clear_results():
    """Delete all result directories"""
    result_dir = "../result"
    if not os.path.exists(result_dir):
        return {"message": "No results directory found"}
    
    try:
        deleted_count = 0
        for item in os.listdir(result_dir):
            item_path = os.path.join(result_dir, item)
            if os.path.isdir(item_path):
                # Check if final.png exists in this directory
                final_png_path = os.path.join(item_path, "final.png")
                if os.path.exists(final_png_path):
                    shutil.rmtree(item_path)
                    deleted_count += 1
        
        return {"message": f"Deleted {deleted_count} result directories"}
    except Exception as e:
        raise HTTPException(500, detail=f"Error clearing results: {str(e)}")


@router.delete("/results/{folder_name}")
async def delete_result(folder_name: str):
    """Delete a specific result directory"""
    result_dir = "../result"
    folder_path = os.path.join(result_dir, folder_name)
    
    if not os.path.exists(folder_path):
        raise HTTPException(404, detail="Result directory not found")
    
    try:
        # Check if final.png exists in this directory
        final_png_path = os.path.join(folder_path, "final.png")
        if not os.path.exists(final_png_path):
            raise HTTPException(404, detail="Result file not found")
        
        shutil.rmtree(folder_path)
        return {"message": f"Deleted result directory: {folder_name}"}
    except Exception as e:
        raise HTTPException(500, detail=f"Error deleting result: {str(e)}")


# ============================================================================
# Cleanup Endpoint
# ============================================================================

@router.post("/cleanup/temp")
async def cleanup_temp_files(max_age_hours: int = 24):
    """
    Clean up temporary files
    
    Args:
        max_age_hours: Clean up temporary files older than this many hours (default 24 hours)
    
    Returns:
        Cleanup result statistics
    """
    import time
    
    result_dir = "result"
    if not os.path.exists(result_dir):
        return {"deleted": 0, "message": "No temp directory found"}
    
    deleted_count = 0
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    try:
        for filename in os.listdir(result_dir):
            if filename.startswith("temp_"):
                filepath = os.path.join(result_dir, filename)
                try:
                    # Check file age
                    file_age = current_time - os.path.getmtime(filepath)
                    if file_age > max_age_seconds:
                        if os.path.isfile(filepath):
                            os.unlink(filepath)
                            deleted_count += 1
                        elif os.path.isdir(filepath):
                            shutil.rmtree(filepath)
                            deleted_count += 1
                except Exception as _e:
                    # Ignore individual file deletion errors (may be in use)
                    continue
        
        return {
            "deleted": deleted_count,
            "message": f"Successfully cleaned up {deleted_count} temporary files older than {max_age_hours} hours"
        }
    except Exception as e:
        raise HTTPException(500, detail=f"Error during cleanup: {str(e)}")


# ============================================================================
# User Login Endpoint
# ============================================================================

@router.post("/user/login")
async def user_login(password: str = Form(...)):
    """User login"""
    from manga_translator.server.core.config_manager import admin_settings

    user_access = admin_settings.get('user_access', {})
    
    # If no password required, allow access directly
    if not user_access.get('require_password', False):
        return {"success": True, "message": "No password required"}
    
    # Verify password
    if password == user_access.get('user_password', ''):
        return {"success": True, "message": "Login successful"}
    
    return {"success": False, "message": "Invalid password"}
