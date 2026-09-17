# Insightyfy Backend

AI-powered scam detection platform with community features, gamification, and monetization.

## Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Storage**: Cloudflare R2 (S3-compatible)
- **Auth**: Firebase Authentication
- **AI**: Hive API (text/audio/video moderation)

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Firebase project with Authentication enabled

### Local Development

1. **Clone and setup environment:**
```bash
cd insightify
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
copy .env.example .env
# Edit .env with your credentials
```

3. **Run database migrations:**
```bash
alembic upgrade head
```

4. **Start development server:**
```bash
uvicorn app.main:app --reload
```

5. **Or use Docker:**
```bash
docker-compose up -d
```

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
app/
├── main.py              # FastAPI application
├── config.py            # Configuration settings
├── core/                # Core infrastructure
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── api/v1/              # API routes
├── services/            # Business logic
└── utils/               # Utilities
```

## Environment Variables

See `.env.example` for all required variables.

## License

Proprietary - Insightyfy
