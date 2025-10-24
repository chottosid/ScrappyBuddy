# 🔍 Intelligent Content Monitoring System

An advanced monitoring agent system built with **LangGraph** that tracks and analyzes content changes across LinkedIn profiles, company pages, and websites. Uses AI-powered change detection to identify meaningful updates and notify users in real-time.

## ✨ Key Features

- **🎯 Multi-Source Monitoring**: LinkedIn profiles, company pages, and websites
- **🤖 AI-Powered Analysis**: Uses Google Gemini to detect meaningful changes (not just formatting)
- **🔄 LangGraph Orchestration**: Proper state management, conditional routing, and error recovery
- **📧 Smart Notifications**: Console and email alerts with user preferences
- **🌐 Web Dashboard**: Easy-to-use interface for managing targets
- **⚡ Real-Time Processing**: Celery + Redis for scalable background processing
- **🔒 User Authentication**: Secure multi-user support with JWT tokens
- **📊 Audit Trail**: Complete workflow execution history and observability

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- MongoDB database
- Redis (optional, for Celery)
- Google Gemini API key

### Installation

1. **Clone and install dependencies:**
   ```bash
   git clone <repository-url>
   cd monitoring-system
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   Create a `.env` file:
   ```env
   # Required
   GEMINI_API_KEY=your_gemini_api_key_here
   MONGODB_URI=mongodb://localhost:27017/monitoring_system
   
   # Optional (for Celery)
   REDIS_URL=redis://localhost:6379/0
   
   # Optional (for email notifications)
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   
   # Security
   JWT_SECRET_KEY=your-secret-key-change-in-production
   ```

3. **Run the migration:**
   ```bash
   python migrate_to_langgraph.py
   ```

4. **Start the system:**
   ```bash
   python main.py start
   ```

5. **Access the dashboard:**
   Open http://localhost:8000 in your browser

## 🏗️ LangGraph Architecture

This system uses **LangGraph** for proper agent orchestration with:

### Core Workflow Nodes
- **🕷️ Scraper Node**: Fetches content with retry logic and error handling
- **🧠 Analyzer Node**: AI-powered change detection using Gemini
- **📢 Notifier Node**: Multi-channel notifications (console, email)
- **💾 Storage Node**: Data persistence and audit trail creation
- **🔄 Error Handler**: Comprehensive error recovery strategies
- **⏰ Retry Handler**: Exponential backoff retry mechanism

### State Management
```python
class MonitoringWorkflowState(TypedDict):
    # Target information
    target_url: str
    target_type: str
    frequency_minutes: int
    
    # Content tracking
    current_content: Optional[str]
    previous_content: Optional[str]
    
    # Change detection
    changes_detected: List[Dict[str, Any]]
    
    # Workflow control
    messages: Annotated[List[BaseMessage], add_messages]
    step: str
    error: Optional[str]
    retry_count: int
    
    # Metadata
    workflow_id: str
    started_at: str
    last_updated: str
```

### Conditional Routing
```
START → scrape → analyze → notify → store → END
         ↓         ↓        ↓       ↓
      error → retry_handler ← error_handler
```

## 📖 Usage Guide

### Adding Monitoring Targets

1. **Via Web Interface:**
   - Navigate to http://localhost:8000
   - Register/login with your account
   - Use the "Add Target" form
   - Set monitoring frequency and preferences

2. **Via API:**
   ```bash
   curl -X POST "http://localhost:8000/targets" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://example.com",
       "target_type": "website",
       "frequency_minutes": 60,
       "name": "Example Site"
     }'
   ```

### Monitoring Changes

- **Real-time Console**: Watch live notifications in the terminal
- **Web Dashboard**: Check the "Recent Changes" section
- **Email Alerts**: Configure SMTP for email notifications
- **API Access**: Use `/changes` endpoint for integrations

## 🛠️ Running Modes

```bash
# Complete system (recommended)
python main.py start

# Individual components
python main.py api      # Web API only
python main.py worker   # Celery worker only
python main.py beat     # Celery scheduler only
python main.py monitor  # Single monitoring cycle

# Testing
python test_langgraph.py        # Test LangGraph workflow
python test_complete_system.py  # End-to-end system test
```

## 🔌 API Reference

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and get JWT token
- `GET /auth/me` - Get current user info

### Target Management
- `POST /targets` - Add monitoring target
- `GET /targets` - List user's targets
- `PUT /targets/{url}` - Update target settings
- `DELETE /targets/{url}` - Remove target

### Change Tracking
- `GET /changes` - Get recent changes
- `GET /changes?target_url={url}` - Changes for specific target

### System
- `GET /health` - System health check
- `GET /user/notification-preferences` - Get notification settings
- `PUT /user/notification-preferences` - Update notification settings

## 💾 Data Storage

### MongoDB Collections
- **`targets`**: Monitoring configuration and content snapshots
- **`changes`**: Detected changes with before/after content
- **`users`**: User accounts and preferences
- **`workflow_executions`**: LangGraph workflow audit trail

### Indexes
Optimized indexes for:
- Target URL lookups
- User target associations
- Change detection queries
- Workflow execution tracking

## 🔧 Configuration

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key for AI analysis |
| `MONGODB_URI` | Yes | MongoDB connection string |
| `REDIS_URL` | No | Redis URL for Celery (falls back to local) |
| `SMTP_HOST` | No | SMTP server for email notifications |
| `SMTP_USER` | No | SMTP username |
| `SMTP_PASSWORD` | No | SMTP password |
| `JWT_SECRET_KEY` | No | JWT signing key (change in production) |

### Target Types
- **`linkedin_profile`**: LinkedIn personal profiles
- **`linkedin_company`**: LinkedIn company pages  
- **`website`**: General websites

### Monitoring Frequencies
- Minimum: 1 minute
- Maximum: 24 hours (1440 minutes)
- Default: 60 minutes

## 🧪 Testing

### Run All Tests
```bash
# Test LangGraph workflow
python test_langgraph.py

# Test complete system
python test_complete_system.py

# Test individual components
python -m pytest tests/  # If you add pytest tests
```

### Manual Testing
```bash
# Single monitoring cycle
python main.py monitor

# Test specific target
python -c "
from workflows.monitoring_workflow import monitoring_workflow
result = monitoring_workflow.run_monitoring_sync({
    'url': 'https://example.com',
    'target_type': 'website',
    'frequency_minutes': 60,
    'name': 'Test'
})
print(result)
"
```

## 📊 Monitoring & Observability

### LangGraph Features
- **Workflow State Tracking**: Complete state history for each execution
- **Message History**: Conversation logs for debugging
- **Conditional Routing**: Smart path selection based on conditions
- **Error Recovery**: Automatic retry with exponential backoff
- **Audit Trail**: Full execution records in `workflow_executions` collection

### Logging
- **Structured Logging**: JSON-formatted logs with context
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Component Tagging**: Easy filtering by component (scraper, analyzer, etc.)

### Metrics
- Workflow execution success/failure rates
- Average processing times per target type
- Change detection accuracy
- Retry attempt statistics

## 🚨 Troubleshooting

### Common Issues

1. **"Cannot connect to MongoDB"**
   ```bash
   # Check MongoDB is running
   mongosh --eval "db.adminCommand('ping')"
   
   # Verify connection string in .env
   echo $MONGODB_URI
   ```

2. **"Gemini API key invalid"**
   ```bash
   # Test API key
   curl -H "Authorization: Bearer $GEMINI_API_KEY" \
     https://generativelanguage.googleapis.com/v1/models
   ```

3. **"Redis connection failed"**
   ```bash
   # Redis is optional, system will work without it
   # Check Redis status
   redis-cli ping
   ```

4. **"Target not being monitored"**
   - Check target is active: `db.targets.find({active: true})`
   - Verify user association: Check `monitored_targets` array
   - Check last_checked timestamp

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py start
```

## 🔒 Security Considerations

- **JWT Tokens**: Secure authentication with configurable expiration
- **Password Hashing**: bcrypt with salt for user passwords
- **Input Validation**: Pydantic models for API request validation
- **Rate Limiting**: Respectful scraping with delays and retries
- **Environment Variables**: Sensitive data in .env files (not committed)

## 🚀 Production Deployment

### Docker Setup (Recommended)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py", "start"]
```

### Environment Setup
- Use production MongoDB cluster
- Configure Redis for Celery
- Set up proper SMTP service
- Use strong JWT secret keys
- Enable HTTPS with reverse proxy

### Scaling
- Run multiple Celery workers
- Use MongoDB replica sets
- Implement Redis clustering
- Add load balancer for API

## 📚 Documentation

- **[LangGraph Architecture](LANGGRAPH_ARCHITECTURE.md)**: Detailed technical documentation
- **[Migration Guide](migrate_to_langgraph.py)**: Migration from legacy system
- **API Documentation**: Available at http://localhost:8000/docs (FastAPI auto-docs)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **LangGraph**: For the excellent agent orchestration framework
- **Google Gemini**: For AI-powered content analysis
- **FastAPI**: For the robust web framework
- **Celery**: For reliable background task processing