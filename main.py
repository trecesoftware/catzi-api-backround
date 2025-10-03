from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Header
from fastapi.responses import StreamingResponse
from rembg import remove
from PIL import Image, ImageFilter
from typing import Optional
import io
import os

app = FastAPI(title="Background Removal API")

# Configuration
SECRET_KEY = os.getenv("API_SECRET_KEY", "Lp8Z2ry4yqeHNIlU99TQwbfbuo9iH1")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB in bytes

def verify_secret_key(x_api_key: str = Header(...)):
    """Verify the API key from request header"""
    if x_api_key != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key

@app.post("/remove-background")
async def remove_background(
    file: UploadFile = File(...),
    background_color: Optional[str] = Form(None),
    add_shadow: bool = Form(False),
    x_api_key: str = Header(..., description="API Secret Key")
):
    """
    Remove background from an uploaded image and return PNG format.

    Args:
        file: Image file to process
        background_color: Optional background color ('white', 'black', or None for transparent)
        add_shadow: Add a soft shadow effect to the image
        x_api_key: API Secret Key for authentication
    """
    # Verify API key
    verify_secret_key(x_api_key)

    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Validate file size
    file.file.seek(0, 2)  # Seek to end of file
    file_size = file.file.tell()  # Get current position (file size)
    file.file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is 50 MB"
        )

    # Validate background color
    if background_color and background_color.lower() not in ['white', 'black']:
        raise HTTPException(status_code=400, detail="background_color must be 'white' or 'black'")

    try:
        # Read uploaded image
        image_bytes = await file.read()

        # Remove background
        output_bytes = remove(image_bytes)

        # Convert to image
        output_image = Image.open(io.BytesIO(output_bytes)).convert("RGBA")

        # Apply shadow if requested
        if add_shadow:
            # Create shadow layer
            shadow = Image.new("RGBA", output_image.size, (0, 0, 0, 0))
            shadow_mask = output_image.split()[3]  # Get alpha channel

            # Create shadow effect
            shadow.paste((0, 0, 0, 180), (0, 0), shadow_mask)
            shadow = shadow.filter(ImageFilter.GaussianBlur(15))

            # Offset shadow
            shadow_offset = Image.new("RGBA",
                (output_image.width + 30, output_image.height + 30),
                (0, 0, 0, 0)
            )
            shadow_offset.paste(shadow, (15, 15))

            # Composite image with shadow
            final_image = Image.new("RGBA", shadow_offset.size, (0, 0, 0, 0))
            final_image.paste(shadow_offset, (0, 0))
            final_image.paste(output_image, (0, 0), output_image)
            output_image = final_image

        # Apply background color if specified
        if background_color:
            # Create a new image with the specified background color
            bg_color = (255, 255, 255, 255) if background_color.lower() == 'white' else (0, 0, 0, 255)
            background = Image.new("RGBA", output_image.size, bg_color)
            background.paste(output_image, (0, 0), output_image)
            output_image = background.convert("RGB")

        # Prepare response
        img_io = io.BytesIO()
        output_image.save(img_io, format='PNG')
        img_io.seek(0)

        return StreamingResponse(
            img_io,
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename=no_bg_{file.filename.rsplit('.', 1)[0]}.png"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Background Removal API - Use POST /remove-background to remove image backgrounds"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
