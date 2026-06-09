# DataNotebook

A web application for interactive data analysis and visualization with AI-powered chat capabilities, code execution, and drawing features.

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Docker Deployment](#docker-deployment)
- [Technologies](#technologies)
- [Contributing](#contributing)

## Features

- **Interactive Chat**: AI-powered chat interface for data analysis queries
- **Code Execution**: Execute Python code in a sandboxed environment
- **Data Visualization**: Create and manage drawings/visualizations
- **Notebook Support**: Work with notebooks for data analysis
- **File Upload**: Upload datasets and files for analysis
- **Session Management**: Persistent session handling
- **S3 Integration**: Cloud storage support for uploaded files
- **Health Monitoring**: Built-in health check endpoints

## Project Structure

```
datanotebook/
├── backend/
│   ├── main.py                 # FastAPI application entry point
│   ├── requirements.txt        # Python dependencies
│   ├── cookies.txt            # Session cookies
│   ├── app/
│   │   ├── __init__.py
│   │   ├── api/               # API route handlers
│   │   │   ├── routes/
│   │   │   │   ├── chat.py           # Chat endpoints
│   │   │   │   ├── draw.py           # Drawing endpoints
│   │   │   │   ├── execute.py        # Code execution endpoints
│   │   │   │   ├── health.py         # Health check endpoints
│   │   │   │   ├── notebook.py       # Notebook endpoints
│   │   │   │   └── upload.py         # File upload endpoints
│   │   ├── core/              # Core configurations
│   │   │   ├── config.py      # App configuration
│   │   │   └── session.py     # Session management
│   │   ├── models/            # Database/data models
│   │   │   └── session.py
│   │   ├── schemas/           # Pydantic schemas (validation)
│   │   │   ├── chat.py
│   │   │   ├── draw.py
│   │   │   ├── execute.py
│   │   │   └── notebook.py
│   │   ├── services/          # Business logic
│   │   │   ├── dataset_service.py    # Dataset management
│   │   │   ├── executor_service.py   # Code execution
│   │   │   ├── openai_service.py     # OpenAI integration
│   │   │   └── s3_service.py         # S3 file storage
│   │   └── utils/
│   │       └── prompt_builder.py     # AI prompt templates
│   └── uploads/               # Uploaded files directory
│
├── frontend/
│   ├── index.html            # Main application page
│   └── projects.html         # Projects/notebook listing page
│
├── Dockerfile                 # Docker container configuration
├── docker-compose.yml        # Docker compose for orchestration
├── .gitignore               # Git ignore rules
└── README.md                # This file
```

## Prerequisites

- **Python 3.11+**
- **Node.js 16+** (for frontend development, optional)
- **Docker & Docker Compose** (for containerized deployment)
- **Git**

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd datanotebook
```

### 2. Create Python Virtual Environment

```bash
# Using venv
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
cd ..
```

## Configuration

### Environment Variables

Create a `.env` file in the backend directory with the following variables:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_S3_BUCKET=your_bucket_name
AWS_REGION=us-east-1

# Database Configuration (if using)
DATABASE_URL=postgresql://user:password@localhost/datanotebook

# Application Configuration
DEBUG=True
LOG_LEVEL=INFO
```

### Configuration File

Edit `backend/app/core/config.py` to customize application settings.

## Running the Application

### Development Mode (Local)

```bash
cd backend

# Run the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
API documentation: `http://localhost:8000/docs` (Swagger UI)

### Frontend Development

Open `frontend/index.html` in a web browser or serve via a local web server:

```bash
# Using Python's built-in server
python -m http.server 8080 --directory frontend
```

Access frontend at `http://localhost:8080`

## API Endpoints

### Health Check
- `GET /api/health` - Application health status

### Chat
- `POST /api/chat` - Send chat message
- `GET /api/chat/history` - Get chat history
- `DELETE /api/chat/clear` - Clear chat history

### Code Execution
- `POST /api/execute` - Execute Python code
- `GET /api/execute/history` - Get execution history

### Notebook
- `GET /api/notebook/list` - List notebooks
- `POST /api/notebook/create` - Create new notebook
- `PUT /api/notebook/{id}` - Update notebook
- `DELETE /api/notebook/{id}` - Delete notebook

### Drawing
- `POST /api/draw` - Save drawing
- `GET /api/draw/{id}` - Get drawing
- `DELETE /api/draw/{id}` - Delete drawing

### File Upload
- `POST /api/upload` - Upload file
- `GET /api/upload/list` - List uploaded files
- `DELETE /api/upload/{id}` - Delete uploaded file

## Docker Deployment

### Build and Run with Docker Compose

```bash
# Build and start services
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down

# Remove volumes and clean up
docker-compose down -v
```

The application will be available at `http://localhost:8000`

### Build Individual Docker Image

```bash
# Build image
docker build -t datanotebook:latest .

# Run container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e AWS_ACCESS_KEY_ID=your_key \
  -v ./backend/uploads:/app/uploads \
  datanotebook:latest
```

## Technologies

**Backend:**
- FastAPI - Modern Python web framework
- Pydantic - Data validation
- Uvicorn - ASGI server
- SQLAlchemy - (optional) ORM for database
- OpenAI Python SDK - AI integration
- Boto3 - AWS S3 integration

**Frontend:**
- HTML5
- CSS3
- JavaScript (Vanilla/Vue.js/React - as implemented)

**Infrastructure:**
- Docker & Docker Compose
- Python 3.11

## Development Guidelines

### Code Style
- Follow PEP 8 conventions
- Use type hints for functions
- Document complex functions with docstrings

### Testing
```bash
# Run tests (when test suite is created)
pytest tests/
```

### Linting
```bash
# Install linting tools
pip install flake8 black isort

# Format code
black backend/
isort backend/

# Check code style
flake8 backend/
```

## Troubleshooting

### Port 8000 Already in Use
```bash
# Kill process on port 8000 (Linux/macOS)
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Or use a different port
uvicorn app.main:app --port 8001
```

### Import Errors
```bash
# Ensure virtual environment is activated
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

### CORS Issues
Update CORS settings in `backend/app/main.py` to allow frontend origin.

## Contributing

1. Create a feature branch: `git checkout -b feature/feature-name`
2. Commit changes: `git commit -am 'Add feature'`
3. Push to branch: `git push origin feature/feature-name`
4. Submit a pull request

## License

MIT License - Feel free to use this project for your own purposes.

## Support

For issues, questions, or suggestions, please create an issue on the repository.

---

**Last Updated:** June 2026
**Status:** In Development
