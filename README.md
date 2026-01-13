Photo Stock Manager
A Python-based tool for managing, tagging, and preparing photos for stock photography websites.

Features
Current (Phase 1)
📸 Extract EXIF metadata (dimensions, format, file size, modification date)
🌍 GPS location extraction and reverse geocoding
🏷️ AI-powered photo tagging using OpenAI Vision API
💾 Tag caching to avoid duplicate API calls
🔄 Batch processing support
Planned
Phase 2: SQLite database, configuration management, enhanced batch processing
Phase 3: Web interface with photo browsing, manual tag editing, GPS map view
Phase 4: Duplicate detection, stock website upload integration
Installation
Prerequisites
Python 3.9 or higher
OpenAI API key (for tagging features)
Setup
Clone the repository:
bash
git clone https://github.com/YOUR_USERNAME/photo-stock-manager.git
cd photo-stock-manager
Create a virtual environment:
bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
Install dependencies:
bash
pip install -r requirements.txt
Set up OpenAI API key (for tagging):
bash
# Windows (Command Prompt)
set OPENAI_API_KEY=your_api_key_here

# Windows (PowerShell)
$env:OPENAI_API_KEY="your_api_key_here"

# macOS/Linux
export OPENAI_API_KEY=your_api_key_here
Usage
Inspect Photos
List all photos in a folder with metadata:

bash
python photo_inspector.py "/path/to/photos"

# Recursive mode (search subfolders)
python photo_inspector.py "/path/to/photos" --recursive
Tag Photos with AI
Generate keywords for a single photo:

bash
python photo_tagger.py "/path/to/photo.jpg"
Use in Python code:

python
from photo_tagger import tag_photo

tags = tag_photo("photo.jpg")
print(tags)
# ['sunset', 'beach', 'ocean', 'golden hour', 'scenic', ...]
Project Structure
photo-stock-manager/
├── photo_inspector.py    # Metadata extraction
├── photo_tagger.py       # AI tagging with caching
├── requirements.txt      # Python dependencies
├── .gitignore           # Git ignore rules
└── README.md            # This file
Development Roadmap
✅ Phase 1: Foundation (Current)
 Metadata extraction
 GPS/location support
 AI tagging with caching
 GitHub setup
🚧 Phase 2: Backend (Next)
 SQLite database for metadata
 Configuration file support
 Enhanced batch processing
 Progress tracking
📋 Phase 3: Web Interface
 Flask/FastAPI backend
 Photo browsing UI
 Manual tag editing
 GPS map visualization
 Filter and search
🚀 Phase 4: Advanced Features
 Duplicate photo detection
 Bulk operations
 Export for stock sites
 Stock website API integration (Shutterstock, Adobe Stock)
Contributing
This is a personal project, but suggestions and bug reports are welcome via GitHub issues.

License
MIT License - feel free to use and modify for your own projects.

Known Issues
HEIC support requires optional pillow-heif package
Reverse geocoding database downloads on first use (~30MB)
OpenAI Vision API calls cost money (use caching to minimize costs)
Tips
Use caching to avoid re-tagging photos (saves API costs)
Start with gpt-4o-mini model for cost efficiency
Use detail="low" for faster/cheaper processing of simple images
Keep photos organized in folders by date or event for easier management
