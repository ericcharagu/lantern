Lantern - Foot Traffic & Security Analytics Platform

The application is a robust, real-time video analytics platform designed to monitor and analyze foot traffic and security events from multiple camera feeds. It leverages machine learning for object detection, a database for persistent logging, and provides insights through a web dashboard and automated WhatsApp reports.

Key Features

Real-time Multi-Camera Monitoring: Stream and process feeds from multiple RTSP cameras simultaneously.

AI-Powered Object Detection: Utilizes a YOLO model to detect, count, and log objects like people, cars, etc.

Persistent Detection Logging: Every detection is logged in a structured PostgreSQL database with precise timestamps and details.

Automated Nightly Security Reports: A background service automatically counts human detections between 10 PM and 5 AM and sends a summary report via WhatsApp.

Interactive Web Dashboard: A secure, role-based dashboard for viewing live camera feeds and analytics (built with FastAPI, Jinja2, and Bootstrap).

User Authentication & Authorization: A complete authentication system with password hashing and role-based access control (Staff, Manager, Admin).

Conversational AI Chatbot: A public-facing WhatsApp chatbot, powered by a local LLM (Ollama), to answer general inquiries.

Asynchronous Architecture: Built on FastAPI and asyncio for high performance and concurrent task handling.

Containerized & Scalable: Fully containerized with Docker and Docker Compose for easy setup, deployment, and scalability.

Architecture Overview

The platform is built on a microservices-oriented architecture, orchestrated by Docker Compose.

Generated code
+-----------------------------+ HTTP Request +-------------------------+
| User / Browser |--------------------->| Lantern FastAPI App |
+-----------------------------+ (Container: llm_service) |
+-------------+-----------+
|
+------------------------------------------------------------------+------------------------------------------------------------------+
| | |
| (Async Task) | (User Request) |
v v v
+------------------------+ Frame for Detection +------------------------+ Prompt for Analysis +------------------------+
| Camera Capture |<--------------------------->| YOLO Service |<--------------------------->| Ollama LLM Service |
| (routers/cameras.py) | | (Container: yolo_server) | | (Container: ollama_server)|
+------------------------+ +------------------------+ +------------------------+
|
| Detection Data (Async Queue)
v
+------------------------+
| Detection Processor |
| (routers/cameras.py) |
+------------------------+
|
| Bulk Insert
v
+------------------------+ Read/Write Data +------------------------+
| PostgreSQL Database |<--------------------------->| Valkey Cache |
| (Container: db_server)| | (Container: cache_server)|
+------------------------+ +------------------------+

Technology Stack

Backend: FastAPI, Python 3.10+

Machine Learning: Ultralytics YOLO, Supervision

Large Language Model: Ollama (with qwen3:0.6b model)

Database: PostgreSQL (interfaced with SQLAlchemy and asyncpg)

Caching: Valkey

Real-time Communication: WebSockets for video streaming

Frontend: Jinja2 Templates, Bootstrap 5, CSS

Authentication: Passlib (for hashing), python-jose (for JWT)

Containerization: Docker, Docker Compose

Prerequisites

Before you begin, ensure you have the following installed:

Docker

Docker Compose

Setup and Installation

Clone the repository:

Generated bash
git clone "github.com/ericcharagu/lantern"
cd ericcharagu-lantern

Create the secrets directory and files:
This project uses Docker Secrets to manage sensitive information.

Generated bash
mkdir secrets
touch secrets/postgres_secrets.txt
touch secrets/whatsapp_secrets.txt
touch secrets/request_secrets.txt
touch secrets/camera_login_secrets.txt

Populate the secret files with the appropriate credentials:

postgres_secrets.txt: Your desired database password.

whatsapp_secrets.txt: Your WhatsApp App Secret.

request_secrets.txt: A long, random string for signing JWTs.

camera_login_secrets.txt: The password for your NVR/camera RTSP streams.

Create the environment file (.env):
Copy the example file and customize it for your environment.

Your .env file should look like this. Fill in the values accordingly.

Generated env

# .env

# -- PostgreSQL Database Configuration --

# These must match the values in docker-compose.yml and your postgres_secrets.txt

DB_HOST=db_server
DB_PORT=5432
DB_USER=postgres
DB_NAME=postgres
DB_PASSWORD=your_db_password_from_secrets_file

# -- JWT Authentication Configuration --

# The SECRET_KEY should match the content of secrets/request_secrets.txt

SECRET_KEY=your_super_secret_jwt_key_from_secrets_file
ALGORITHM=HS256
TOKEN_VALIDITY_DAYS=30

# -- Camera NVR Configuration --

CAMERA_RTSP_USERNAME=admin
NVR_IP_ADDRESS=192.168.2.200

# -- WhatsApp Integration --

# The verification token for the initial webhook setup with Meta

WHATSAPP_VERIFY_TOKEN=your_whatsapp_verify_token

# Your WhatsApp Business phone number ID

PHONE_NUMBER_ID=your_phone_number_id

# The number to receive the automated nightly report

NIGHTLY_REPORT_RECIPIENT_NUMBER=+2547XXXXXXXX

Running the Application
Development Mode

This mode uses local volume mounts, which enables hot-reloading for the FastAPI application when you change the code.

Generated bash
docker-compose up --build

The application will be available at http://localhost:8000.

Production Mode

This mode uses the docker-compose.prod.yml file, which does not mount the local code. It builds a self-contained image for more stable deployments.

Generated bash
docker-compose -f docker-compose.prod.yml up -d --build

The application will be available at http://127.0.0.1:8000.

Project Structure
Generated code
└── ericcharagu-lantern/
├── config.py # Pydantic-based settings management (loads .env)
├── dependencies.py # FastAPI dependency injection functions (clients, auth)
├── main.py # FastAPI application entrypoint and lifespan manager
├── prompts.py # Centralized store for all LLM system prompts
├── middleware/
│ └── auth_middleware.py # Checks for JWT token and handles redirects
├── routers/ # API endpoint definitions
│ ├── analysis.py # Data analysis endpoints
│ ├── auth.py # User login, registration, and session management
│ ├── cameras.py # Camera streaming and detection processing logic
│ └── webhooks.py # Handles incoming webhooks from WhatsApp
├── services/ # Business logic and background tasks
│ ├── analysis_service.py # Core logic for data analysis reports
│ ├── nightly_report_service.py # Scheduled task for daily WhatsApp reports
│ └── whatsapp_service.py # Logic for handling WhatsApp chatbot interactions
├── static/ # CSS, JS, and other static assets
├── templates/ # Jinja2 HTML templates for the web dashboard
├── tests/ # Application tests
├── utils/ # Reusable utility functions and modules
│ ├── db/ # Database models, connection, and query logic
│ └── whatsapp/ # Tools for interacting with the WhatsApp API
└── yolo_service/ # Standalone service for YOLO model inference
├── yolo_app.py # FastAPI app for the YOLO service
└── models/ # Directory for trained model files (.pt)

GET /: Welcome message.

GET /dashboard/: Main analytics web dashboard (requires login).

GET /cameras/home: Web page with all live camera feeds (requires login).

GET /cameras/video/{cam_id}: The multipart/x-mixed-replace stream for a single camera.

POST /auth/login: Handles form submission for user login.

POST /auth/token: API endpoint to get a JWT bearer token.

POST /webhooks: Public endpoint to receive notifications from the WhatsApp Business API.

POST /internal/summarize: Secured endpoint for internal staff AI assistance.

Background Services

The application runs two critical background services managed by asyncio:

Detection Processor (routers/cameras.py):

An asyncio.Queue (detection_queue) receives individual detection records from all camera capture tasks.

A dedicated background task (detection_processor) consumes items from this queue.

It batches these records and performs efficient BULK INSERT operations into the detection_logs table in the PostgreSQL database.

Nightly Report Service (services/nightly_report_service.py):

This task (nightly_report_task) runs in a continuous loop.

It calculates the time until the next 5:00 AM (Nairobi Time) and sleeps.

At 5:00 AM, it wakes up, queries the detection_logs table for all 'person' detections within the 10 PM - 4:50 AM window, and sends a formatted summary via WhatsApp.
