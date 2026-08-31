# ImageMorph Studio

A modern PySide6 desktop application for creating smooth image morph animations.

ImageMorph Studio transforms two images into an animated transition using **G'MIC** for morph generation and **FFmpeg** for video encoding.

---

## Features

- Modern PySide6 desktop interface
- Select two source images
- Image preview cards
- Image validation
- G'MIC tool detection
- FFmpeg tool detection
- Configurable number of intermediate frames
- Configurable frames per second
- MP4 output
- GIF output
- Automatic output extension handling
- Processing progress bar
- Live processing status
- Detailed processing log
- Cancellation support
- Safe worker thread handling
- Protection against starting multiple morph operations
- Open completed output directly
- Open output folder directly
- Automatic temporary workspace cleanup
- Safe application shutdown while processing

---

## How It Works

```text
Image 1
   +
Image 2
   │
   ▼
G'MIC Morph Engine
   │
   ▼
Generated Morph Frames
   │
   ▼
FFmpeg Encoder
   │
   ├── MP4
   │
   └── GIF
```

---

## Requirements

ImageMorph Studio requires:

- Python 3
- PySide6
- Pillow
- G'MIC
- FFmpeg

---

## Python Dependencies

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Installing G'MIC

On Debian, Ubuntu, MX Linux, or compatible distributions:

```bash
sudo apt install gmic
```

Check the installation:

```bash
gmic --version
```

---

## Installing FFmpeg

On Debian, Ubuntu, MX Linux, or compatible distributions:

```bash
sudo apt install ffmpeg
```

Check the installation:

```bash
ffmpeg -version
```

---

## Running the Application

Activate your virtual environment if you use one:

```bash
source .venv/bin/activate
```

Then run:

```bash
python3 image_morph_studio.py
```

---

## Usage

### 1. Select Image 1

Choose the starting image.

### 2. Select Image 2

Choose the ending image.

Supported image formats include:

- PNG
- JPG
- JPEG
- BMP
- WEBP
- TIFF

### 3. Configure Morph Settings

Set:

- Number of intermediate frames
- Frames per second
- Output format

### 4. Choose Output Location

Select where the generated animation should be saved.

If no output location is selected, ImageMorph Studio automatically creates a default output file near the first image.

### 5. Start Morph

Click:

```text
▶ Start Morph
```

The application will:

1. Validate the selected images
2. Check G'MIC
3. Check FFmpeg
4. Create a temporary workspace
5. Generate morph frames using G'MIC
6. Detect the actual generated frame files
7. Build an FFmpeg frame list
8. Encode the final animation
9. Clean up temporary files

---

## Output Formats

### MP4

MP4 output uses:

- H.264 encoding
- libx264
- yuv420p pixel format
- High-quality CRF encoding

This provides broad compatibility with most media players.

### GIF

GIF output uses:

- Generated morph frames
- FFmpeg palette generation
- Optimized palette conversion

---

## Safety Features

ImageMorph Studio includes several protections for stable processing.

### Worker Protection

The application prevents multiple morph operations from running simultaneously.

### Cancellation

The active morph operation can be cancelled while processing.

### Safe Shutdown

If processing is active and the user attempts to close the application, ImageMorph Studio asks whether the operation should be cancelled before exiting.

This prevents the application from destroying an active worker thread.

### Temporary File Cleanup

Temporary morph frames and processing files are automatically removed after processing.

---

## Processing Architecture

```text
PySide6 Interface
        │
        ▼
MorphWorker
        │
        ├── Validate G'MIC
        │
        ├── Validate FFmpeg
        │
        ├── Create Temporary Workspace
        │
        ├── Run G'MIC
        │
        ├── Detect Generated PNG Frames
        │
        ├── Build FFmpeg Frame List
        │
        └── Encode Output
                 │
                 ├── MP4
                 └── GIF
```

---

## Supported Image Types

The application supports:

```text
.png
.jpg
.jpeg
.bmp
.webp
.tif
.tiff
```

---

## Example

```text
Image 1: love_image.png
Image 2: IMG_0783.jpg

Intermediate Frames: 15
FPS: 15
Output Format: MP4

Output:
image_morph.mp4
```

The result is an animated morph transition between the two images.

---

## Troubleshooting

### G'MIC Not Found

Install G'MIC:

```bash
sudo apt install gmic
```

Then verify:

```bash
gmic --version
```

---

### FFmpeg Not Found

Install FFmpeg:

```bash
sudo apt install ffmpeg
```

Then verify:

```bash
ffmpeg -version
```

---

### Invalid Image

Make sure the selected image:

- Exists
- Is not corrupted
- Uses a supported format
- Can be opened by Pillow

---

### Output File Not Created

Check:

- G'MIC completed successfully
- FFmpeg is installed
- The output directory is writable
- The processing log for error messages

---

## Project Structure

```text
ImageMorph-Studio/
├── image_morph_studio.py
├── README.md
├── requirements.txt
└── .gitignore
```

---

## Technologies

ImageMorph Studio is built with:

- Python
- PySide6
- Pillow
- G'MIC
- FFmpeg

---

## License

This project is open source. Add a license appropriate for your preferred usage and distribution.

---

## Future Ideas

Possible future enhancements include:

- Persistent generated-frame preview
- Frame export
- Adjustable morph smoothness
- Output resolution control
- Automatic image size normalization
- Batch morph processing
- Reverse animation generation
- Loop mode
- Custom video quality settings
- Drag-and-drop image loading
- Dark mode
- Recent project history
- Project save and load support

---

## Author

Developed as a Python and PySide6 desktop application project.

---

## ImageMorph Studio

Create smooth animated transitions between images with:

**Python + PySide6 + G'MIC + FFmpeg**
