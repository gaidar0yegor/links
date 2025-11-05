# Telegram Affiliate Publisher

A scalable, automated content publishing system for Telegram channels with affiliate links using Clean Architecture principles.

## 🎯 Overview

This system automates the complete cycle of affiliate content publishing:
1. **Collect** products from partner platforms (Amazon)
2. **Filter** products based on channel-specific criteria
3. **Generate** affiliate links
4. **Rewrite** content using AI for better engagement
5. **Publish** to Telegram channels with optimal scheduling

## 🏗️ Architecture

Built using **Clean Architecture** with clear separation of concerns:

```
src/
├── domain/           # Business Logic Layer
│   ├── entities/     # Core business entities
│   └── services/     # Business rules & validation
├── infrastructure/   # External Concerns Layer
│   ├── database/     # Data persistence
│   └── external/     # External API integrations
├── application/      # Use Cases Layer
│   └── use_cases/    # Application business logic
└── interfaces/       # Interface Adapters Layer
    ├── api/          # REST API (FastAPI)
    └── web/          # Web interface (future)
```

## 🚀 Features

### MVP Features ✅ (Budget-Friendly)
- ✅ Automated product collection from Amazon
- ✅ Channel-specific filtering (categories, ratings, reviews, best sellers)
- ✅ Affiliate link generation
- ✅ **Rule-Based Content Generation** (FREE, no LLM costs)
- ✅ Scheduled Telegram publishing
- ✅ Web admin panel with authentication
- ✅ PostgreSQL database with async support
- ✅ Docker containerization + Railway deployment
- ✅ RESTful API with external scheduler support

### Production-Ready Features 🔄
- 🔄 Advanced rule templates for different categories
- 🔄 Multi-platform affiliate support
- 🔄 Analytics and reporting dashboard
- 🔄 Publication history tracking
- 🔄 Automated daily scheduling via UptimeRobot

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | Python 3.11 + FastAPI | REST API & async processing |
| **Database** | PostgreSQL 15 | Data persistence |
| **Content Generation** | **Rule-Based Templates** | FREE content creation |
| **Messaging** | Telegram Bot API | Content publishing |
| **Partner API** | Amazon PA API v5.0 | Product data source |
| **Deployment** | Docker + **Railway** | PaaS deployment |
| **Scheduling** | UptimeRobot | External daily automation |

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose
- OpenAI API key
- Telegram Bot Token
- Amazon Associate Account

## 🚀 Quick Start

### 1. Clone & Setup

```bash
cd telegram-affiliate-publisher
cp .env.example .env
# Edit .env with your API keys
```

### 2. Environment Variables

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
OPENAI_API_KEY=your_openai_key
TELEGRAM_BOT_TOKEN=your_bot_token
AMAZON_ACCESS_KEY=your_amazon_key
AMAZON_SECRET_KEY=your_amazon_secret
AMAZON_ASSOCIATE_TAG=your_associate_tag
```

### 3. Run with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# API will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### 4. Initialize Database

```bash
# Run database setup
docker-compose exec app python -c "
import asyncio
from src.infrastructure.database.database_setup import init_database
asyncio.run(init_database('${DATABASE_URL}'))
"
```

## 📖 API Usage

### Create a Channel

```bash
curl -X POST "http://localhost:8000/channels" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tech Deals",
    "telegram_chat_id": "@mytechdeals",
    "product_source_url": "amazon.com",
    "is_active": true
  }'
```

### Configure Channel Settings

```bash
curl -X POST "http://localhost:8000/channels/1/settings" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": 1,
    "categories": ["Electronics", "Computers"],
    "is_best_seller": true,
    "min_rating": 4.0,
    "min_reviews": 100,
    "items_per_day": 5
  }'
```

### Run Full Publishing Cycle

```bash
# Trigger complete automation cycle
curl -X POST "http://localhost:8000/processes/run-full-cycle"
```

## 🔧 Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
python -c "
import asyncio
from src.infrastructure.database.database_setup import init_database
asyncio.run(init_database('postgresql+asyncpg://localhost/telegram_affiliate'))
"

# Start API server
python main.py
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black src/
isort src/

# Lint code
flake8 src/
```

## 🚀 Deployment

### Railway (PaaS - Recommended)

Railway provides free tier and automatic deployments:

1. **Connect GitHub Repository**
   - Push code to GitHub
   - Connect Railway to your repo

2. **Set Environment Variables in Railway Dashboard:**
   ```
   DATABASE_URL=postgresql://... (provided by Railway)
   TELEGRAM_BOT_TOKEN=your_bot_token
   AMAZON_ACCESS_KEY=your_amazon_key
   AMAZON_SECRET_KEY=your_amazon_secret
   AMAZON_ASSOCIATE_TAG=your_associate_tag
   ADMIN_USERNAME=your_admin_username
   ADMIN_PASSWORD=your_secure_password
   ```

3. **Automatic Deployment**
   - Railway will build and deploy automatically
   - Your app will be available at `https://your-app.railway.app`

4. **Set Up Daily Automation**
   - Use UptimeRobot or similar service
   - Configure daily POST request to: `https://your-app.railway.app/api/v1/run-daily`

### Docker Production

```bash
# Production compose
docker-compose -f docker-compose.prod.yml up -d
```

## 📊 Monitoring & Analytics

- Health checks: `GET /health`
- API documentation: `GET /docs`
- Metrics endpoint: `GET /metrics` (future)

## 🔒 Security

- Environment variables for secrets
- Non-root Docker containers
- Input validation with Pydantic
- SQL injection prevention with SQLAlchemy
- Rate limiting (future)

## 📈 Scaling Strategy

### Current (MVP): 10 channels
- Single container deployment
- Synchronous processing
- Basic caching

### Target (Production): 100+ channels
- AWS Lambda functions
- Event-driven architecture
- Redis caching
- Database connection pooling
- Horizontal scaling

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Clean Architecture by Robert C. Martin
- FastAPI framework
- OpenAI GPT models
- Amazon Associate Program
- Telegram Bot Platform

---

**Built with ❤️ for automated affiliate marketing**
