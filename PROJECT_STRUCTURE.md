# 📁 Project Structure Documentation

## 🏗️ Overview

This document outlines the complete project structure for the LangGraph-based Content Monitoring System, explaining the purpose and organization of each component.

## 📂 Directory Structure

```
monitoring-system/
├── 📁 agents/                     # Legacy agents (coordinator & scheduler only)
│   ├── __init__.py
│   ├── coordinator_agent.py       # Orchestrates LangGraph workflows
│   └── scheduler_agent.py         # Manages target scheduling
│
├── 📁 nodes/                      # LangGraph workflow nodes
│   ├── __init__.py
│   ├── analyzer_node.py           # AI-powered change detection
│   ├── notifier_node.py           # Multi-channel notifications
│   ├── scraper_node.py            # Content scraping with error handling
│   └── storage_node.py            # Data persistence and audit trail
│
├── 📁 workflows/                  # LangGraph workflow definitions
│   ├── __init__.py
│   └── monitoring_workflow.py     # Main monitoring workflow orchestrator
│
├── 📁 static/                     # Web interface assets
│   ├── index.html                 # Main dashboard
│   ├── style.css                  # Styling
│   └── script.js                  # Frontend JavaScript
│
├── 📁 .kiro/                      # Kiro IDE configuration
│   └── settings/
│
├── 📄 Core Application Files
├── api.py                         # FastAPI web server and endpoints
├── auth.py                        # JWT authentication system
├── celery_app.py                  # Celery task definitions and configuration
├── config.py                      # Environment configuration management
├── database.py                    # MongoDB connection and utilities
├── main.py                        # Application entry point
├── models.py                      # Pydantic models and TypedDict definitions
│
├── 📄 Documentation
├── README.md                      # Main project documentation
├── LANGGRAPH_ARCHITECTURE.md     # Detailed technical architecture
├── PROJECT_STRUCTURE.md          # This file
│
├── 📄 Configuration & Setup
├── requirements.txt               # Python dependencies
├── .env                          # Environment variables (not in repo)
├── .gitignore                    # Git ignore rules
│
└── 📄 Configuration Files
    ├── .env.example              # Environment variables template
    └── docker-compose.yml        # Docker setup (if added)
```

## 🔧 Core Components

### 📁 `agents/` - Legacy Agent System

#### `coordinator_agent.py`
**Purpose**: Orchestrates monitoring cycles using LangGraph workflows
**Key Functions**:
- `monitor_target()`: Executes LangGraph workflow for single target
- `run_monitoring_cycle()`: Processes all due targets in batch
- `_get_previous_content()`: Retrieves stored content for comparison
- `_store_current_content()`: Updates target content snapshots

#### `scheduler_agent.py`
**Purpose**: Manages target scheduling and timing logic
**Key Functions**:
- `get_targets_to_monitor()`: Finds targets due for monitoring
- `update_last_checked()`: Updates target timestamps

### 📁 `nodes/` - LangGraph Processing Nodes

#### `scraper_node.py`
**Purpose**: Content extraction with robust error handling
**Features**:
- Multi-platform support (LinkedIn profiles/companies, websites)
- HTTP error categorization and retry logic
- Content validation and sanitization
- Respectful scraping with proper headers

**Key Functions**:
```python
def scraper_node(state: MonitoringWorkflowState) -> MonitoringWorkflowState
def _extract_linkedin_profile(html: str) -> str
def _extract_linkedin_company(html: str) -> str
def _extract_website_content(html: str) -> str
```

#### `analyzer_node.py`
**Purpose**: AI-powered change detection and analysis
**Features**:
- Google Gemini integration for intelligent analysis
- Meaningful vs. minor change classification
- Fallback to simple text comparison
- Context-aware change summaries

**Key Functions**:
```python
def analyzer_node(state: MonitoringWorkflowState) -> MonitoringWorkflowState
def _detect_meaningful_changes(before: str, after: str, target_type: str) -> str
def _simple_change_detection(before: str, after: str) -> str
```

#### `notifier_node.py`
**Purpose**: Multi-channel notification delivery
**Features**:
- Console notifications with rich formatting
- Email notifications (if SMTP configured)
- User preference respect
- Multi-user target support

**Key Functions**:
```python
def notifier_node(state: MonitoringWorkflowState) -> MonitoringWorkflowState
def _send_console_notification(change: Dict, user_email: str) -> Dict
def _send_email_notification(change: Dict, user_email: str) -> Dict
```

#### `storage_node.py`
**Purpose**: Data persistence and audit trail creation
**Features**:
- Change record storage in MongoDB
- Target state updates
- Workflow execution audit trail
- Performance metrics collection

**Key Functions**:
```python
def storage_node(state: MonitoringWorkflowState) -> MonitoringWorkflowState
```

### 📁 `workflows/` - LangGraph Orchestration

#### `monitoring_workflow.py`
**Purpose**: Main LangGraph workflow definition and execution
**Features**:
- Conditional routing based on success/failure and content changes
- Comprehensive error handling with retry logic
- State persistence with MemorySaver
- Async and sync execution modes

**Key Classes & Functions**:
```python
class MonitoringWorkflow:
    def __init__(self)
    def _build_workflow(self) -> StateGraph
    def create_initial_state(self, target_data: Dict) -> MonitoringWorkflowState
    async def run_monitoring(self, target_data: Dict) -> Dict
    def run_monitoring_sync(self, target_data: Dict) -> Dict
    
    # Routing functions
    def _route_after_scrape(self, state) -> str
    def _route_after_analyze(self, state) -> str
    def _route_after_notify(self, state) -> str
    
    # Control nodes
    def _error_handler_node(self, state) -> MonitoringWorkflowState
    def _retry_handler_node(self, state) -> MonitoringWorkflowState
```

### 📄 Core Application Files

#### `api.py`
**Purpose**: FastAPI web server with REST endpoints
**Endpoints**:
- **Authentication**: `/auth/register`, `/auth/login`, `/auth/me`
- **Target Management**: `/targets` (GET, POST, PUT, DELETE)
- **Change Tracking**: `/changes`
- **User Preferences**: `/user/notification-preferences`
- **System**: `/health`

**Key Features**:
- JWT authentication with user sessions
- CORS middleware for web interface
- Pydantic request/response validation
- Error handling and logging

#### `auth.py`
**Purpose**: JWT authentication and user management
**Functions**:
- `create_access_token()`: Generate JWT tokens
- `authenticate_user()`: Validate user credentials
- `get_current_active_user()`: Extract user from JWT token
- Password hashing and verification

#### `celery_app.py`
**Purpose**: Celery task definitions and Redis configuration
**Tasks**:
- `monitor_target_task()`: Execute LangGraph workflow for single target
- `check_due_targets_task()`: Find and queue targets due for monitoring
- `queue_initial_targets()`: Bootstrap monitoring on startup

**Configuration**:
- Redis connection with SSL fallback
- Windows-compatible worker pool settings
- Automatic retry with exponential backoff
- Beat schedule for periodic target checking

#### `config.py`
**Purpose**: Environment configuration management
**Settings**:
- Database connections (MongoDB, Redis)
- API keys (Gemini, JWT)
- SMTP configuration for email notifications
- Collection names and timeouts

#### `database.py`
**Purpose**: MongoDB connection and utilities
**Features**:
- Connection pooling and retry logic
- Collection access with automatic reconnection
- Graceful connection handling

#### `main.py`
**Purpose**: Application entry point and process management
**Modes**:
- `start`: Complete system (API + Celery worker + beat scheduler)
- `api`: Web API server only
- `worker`: Celery worker only
- `beat`: Celery beat scheduler only
- `monitor`: Single monitoring cycle
- `test`: System validation

#### `models.py`
**Purpose**: Data models and type definitions
**Models**:
- **LangGraph State**: `MonitoringWorkflowState` (TypedDict)
- **Database Models**: `MonitoringTarget`, `ChangeDetection`, `User`
- **API Models**: Request/response schemas
- **Authentication**: Token and user models

## 📁 Static Assets (`static/`)

### Web Interface Files
- **`index.html`**: Single-page dashboard application
- **`style.css`**: Responsive CSS styling
- **`script.js`**: Frontend JavaScript for API interaction

**Features**:
- User authentication (login/register)
- Target management (add/edit/delete)
- Real-time change monitoring
- Notification preferences
- Responsive design for mobile/desktop

## 📄 Documentation Files

### `README.md`
**Purpose**: Main project documentation
**Sections**:
- Quick start guide
- Feature overview
- Installation instructions
- Usage examples
- API reference
- Configuration guide

### `LANGGRAPH_ARCHITECTURE.md`
**Purpose**: Detailed technical architecture documentation
**Sections**:
- LangGraph workflow design
- State management system
- Node implementation details
- Routing logic and error handling
- Performance optimization
- Future enhancements

### `PROJECT_STRUCTURE.md`
**Purpose**: This file - complete project organization guide

## 🔧 Configuration Files

### `requirements.txt`
**Purpose**: Python dependency specification
**Key Dependencies**:
- `langgraph==0.2.14`: Core workflow orchestration
- `langchain-google-genai`: Gemini AI integration
- `fastapi`: Web API framework
- `celery`: Background task processing
- `pymongo`: MongoDB driver
- `redis`: Celery broker
- `beautifulsoup4`: HTML parsing
- `pydantic`: Data validation

### `.env` (Environment Variables)
**Purpose**: Configuration secrets and settings
**Required Variables**:
```env
GEMINI_API_KEY=your_gemini_api_key
MONGODB_URI=mongodb://localhost:27017/monitoring_system
```

**Optional Variables**:
```env
REDIS_URL=redis://localhost:6379/0
SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
JWT_SECRET_KEY=your-secret-key
```

## 🗄️ Database Collections

### MongoDB Collections Structure

#### `targets`
**Purpose**: Monitoring target configuration
```javascript
{
  _id: ObjectId,
  url: "https://example.com",
  target_type: "website|linkedin_profile|linkedin_company",
  frequency_minutes: 60,
  name: "Example Site",
  active: true,
  created_at: ISODate,
  last_checked: ISODate,
  last_content: "cached content for comparison"
}
```

#### `changes`
**Purpose**: Detected content changes
```javascript
{
  _id: ObjectId,
  target_id: "target_url",
  target_url: "https://example.com",
  change_type: "website",
  summary: "AI-generated change summary",
  before_content: "previous content",
  after_content: "current content",
  detected_at: ISODate
}
```

#### `users`
**Purpose**: User accounts and preferences
```javascript
{
  _id: ObjectId,
  email: "user@example.com",
  hashed_password: "bcrypt_hash",
  full_name: "User Name",
  is_active: true,
  notification_preferences: {
    email_notifications: true,
    console_notifications: true
  },
  monitored_targets: ["https://example.com", "..."],
  created_at: ISODate
}
```

#### `workflow_executions`
**Purpose**: LangGraph workflow audit trail
```javascript
{
  _id: ObjectId,
  workflow_id: "uuid",
  target_url: "https://example.com",
  target_type: "website",
  started_at: ISODate,
  completed_at: ISODate,
  success: true,
  error: null,
  changes_count: 1,
  retry_count: 0,
  final_step: "storage_completed",
  execution_time_ms: 1500,
  content_length: 2048
}
```

## 🔄 Data Flow Architecture

### Request Flow
```
User Request → FastAPI → Authentication → Business Logic → Database
                ↓
            LangGraph Workflow → Celery Task → Background Processing
```

### Monitoring Flow
```
Celery Beat → Check Due Targets → Queue Tasks → Execute LangGraph Workflow
                                                        ↓
                                              Scrape → Analyze → Notify → Store
```

### Error Flow
```
Node Error → Error Handler → Retry Logic → Success/Failure → Audit Trail
```

## 🚀 Deployment Structure

### Development
```
Local Machine:
├── Python 3.10+ environment
├── MongoDB (local or cloud)
├── Redis (optional, local)
└── Environment variables in .env
```

### Production
```
Production Environment:
├── Application Server (Docker container)
├── MongoDB Cluster (Atlas or self-hosted)
├── Redis Cluster (for Celery)
├── Load Balancer (nginx/Apache)
├── SSL Certificates
└── Environment variables (secure storage)
```

## 📊 Monitoring & Observability

### Log Files
- **Application Logs**: Structured JSON logs with workflow context
- **Celery Logs**: Task execution and scheduling logs
- **Database Logs**: MongoDB operation logs
- **Web Server Logs**: FastAPI request/response logs

### Metrics Collection
- **Workflow Metrics**: Success rates, execution times, retry counts
- **System Metrics**: CPU, memory, disk usage
- **Business Metrics**: Targets monitored, changes detected, users active

### Health Checks
- **API Health**: `/health` endpoint
- **Database Health**: Connection and query tests
- **Celery Health**: Worker and beat status
- **LangGraph Health**: Workflow compilation and execution tests

This project structure provides a solid foundation for a scalable, maintainable content monitoring system built on LangGraph principles.