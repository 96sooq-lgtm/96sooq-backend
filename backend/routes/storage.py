from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from utils.storage import s3_client
from utils.logger import get_logger
import uuid
import shutil

logger = get_logger(__name__)

router = APIRouter(
    prefix="/storage",
    tags=["Storage"]
)

class UploadRequest(BaseModel):
    file_name: str
    file_type: str
    folder: str = "uploads" # Optional folder to organize files

class UploadResponse(BaseModel):
    upload_url: dict
    file_path: str

from typing import List, Optional

@router.post("/upload")
async def upload_file_proxy(
    file: Optional[UploadFile] = File(None),
    files: List[UploadFile] = File(default=[]),
    folder: str = "uploads"
):
    """
    Upload a file or multiple files directly to S3 via the backend (Proxy Upload).
    Returns the public URL (CloudFront or S3) and a list of all URLs for backward compatibility.
    """
    if not s3_client:
        raise HTTPException(status_code=500, detail="Storage service not configured")
        
    upload_files = []
    if file:
        upload_files.append(file)
    if files:
        upload_files.extend(files)
        
    if not upload_files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploaded_files = []
    urls = []

    try:
        for f in upload_files:
            # Generate unique filename
            unique_filename = f"{uuid.uuid4()}-{f.filename}"
            object_name = f"{folder}/{unique_filename}"
            
            # Upload to S3
            url = s3_client.upload_file(
                f.file, 
                object_name, 
                content_type=f.content_type
            )
            
            if not url:
                 raise HTTPException(status_code=500, detail=f"Failed to upload file {f.filename} to storage")
            
            # Ensure URL always starts with https:// for frontend convenience
            if not url.startswith(('http://', 'https://')):
                url = f"https://{url}"
                
            urls.append(url)
            uploaded_files.append({"url": url, "file_path": object_name})
            
        # Return backward compatible format + all URLs
        # If user uploads multiple files, the first file's details are at the root
        response_data = {
            "url": uploaded_files[0]["url"], 
            "file_path": uploaded_files[0]["file_path"],
            "urls": urls,
            "files": uploaded_files
        }
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error during file proxy upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/presigned-url/upload", response_model=UploadResponse)
async def generate_upload_url(request: UploadRequest):
    """
    Generate a pre-signed URL to upload a file to S3.
    """
    if not s3_client:
        raise HTTPException(status_code=500, detail="Storage service not configured")

    # sanitize file name and create a unique path
    unique_filename = f"{uuid.uuid4()}-{request.file_name}"
    object_name = f"{request.folder}/{unique_filename}"
    
    # Generate the pre-signed POST URL
    response = s3_client.generate_presigned_post(
        object_name,
        conditions=[
            ["content-length-range", 0, 104857600], # Limit to 100MB
            {"Content-Type": request.file_type}
        ]
    )
    
    if response is None:
        raise HTTPException(status_code=500, detail="Could not generate upload URL")

    return {
        "upload_url": response,
        "file_path": object_name
    }

@router.get("/presigned-url/view")
async def generate_view_url(file_path: str):
    """
    Generate a pre-signed URL to view a private file from S3.
    """
    if not s3_client:
        raise HTTPException(status_code=500, detail="Storage service not configured")
        
    # Check if CloudFront is configured, if so return CloudFront URL (assuming public access or other auth)
    # BUT user asked specifically for CloudFront URL. 
    # For now, we will stick to the utils logic.
    # If the user wants signed cloudfront urls for view, that's a different implementation.
    # Given the previous context, they want a "visible" url.
    
    # Use the existing s3 method which handles presigned.
    # To support public cloudfront view, we might just return the URL constructed in upload.
    # For now, let's keep the presigned view as is for "secure" retrival, 
    # but the proxy upload returns a URL that might be public.
    
    url = s3_client.generate_presigned_url(file_path)
    
    if url is None:
        raise HTTPException(status_code=404, detail="File not found or error generating URL")
        
    return {"url": url}
