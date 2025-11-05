from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import secrets

# Import domain entities
from ...domain.entities.channel import Channel
from ...domain.entities.settings import ChannelSettings
from ...domain.entities.publication import Publication

# Import use cases
from ...application.use_cases.collect_and_filter_products import CollectAndFilterProductsUseCase
from ...application.use_cases.generate_affiliate_links import GenerateAffiliateLinksUseCase
from ...application.use_cases.generate_content_and_publish import GenerateContentAndPublishUseCase

# Import infrastructure interfaces
from ...infrastructure.database.repositories import (
    IChannelRepository, ISettingsRepository, IProductRepository, IPublicationRepository
)
from ...infrastructure.external.interfaces import IPartnerApi, ITelegramPublisher, IAiRewriter
from ...infrastructure.external.rule_based_generator import RuleBasedContentGenerator


app = FastAPI(
    title="Telegram Affiliate Publisher API",
    description="API для управления автоматизированной системой публикации контента с партнерскими ссылками",
    version="1.0.0"
)


# Authentication
security = HTTPBasic()
ADMIN_USERNAME = "admin"  # In production, use environment variables
ADMIN_PASSWORD = "changeme123"  # In production, use environment variables

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    """Basic authentication for admin endpoints."""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Lazy initialization - dependencies are created only when needed
def get_channel_repo() -> IChannelRepository:
    """Lazy initialization of channel repository."""
    if not hasattr(get_channel_repo, '_instance'):
        # For Vercel/serverless, use a simple approach
        # In production, this would use proper DI container
        get_channel_repo._instance = None  # Placeholder
    return get_channel_repo._instance

def get_settings_repo() -> ISettingsRepository:
    """Lazy initialization of settings repository."""
    if not hasattr(get_settings_repo, '_instance'):
        get_settings_repo._instance = None  # Placeholder
    return get_settings_repo._instance

def get_product_repo() -> IProductRepository:
    """Lazy initialization of product repository."""
    if not hasattr(get_product_repo, '_instance'):
        get_product_repo._instance = None  # Placeholder
    return get_product_repo._instance

def get_publication_repo() -> IPublicationRepository:
    """Lazy initialization of publication repository."""
    if not hasattr(get_publication_repo, '_instance'):
        get_publication_repo._instance = None  # Placeholder
    return get_publication_repo._instance

def get_partner_api() -> IPartnerApi:
    """Lazy initialization of partner API."""
    if not hasattr(get_partner_api, '_instance'):
        get_partner_api._instance = None  # Placeholder
    return get_partner_api._instance

def get_telegram_publisher() -> ITelegramPublisher:
    """Lazy initialization of Telegram publisher."""
    if not hasattr(get_telegram_publisher, '_instance'):
        get_telegram_publisher._instance = None  # Placeholder
    return get_telegram_publisher._instance

def get_ai_rewriter() -> IAiRewriter:
    """Lazy initialization of AI rewriter."""
    if not hasattr(get_ai_rewriter, '_instance'):
        # Use rule-based generator as default (free)
        get_ai_rewriter._instance = RuleBasedContentGenerator()
    return get_ai_rewriter._instance

# Use cases - lazy initialization
def get_collect_use_case() -> CollectAndFilterProductsUseCase:
    """Lazy initialization of collect use case."""
    if not hasattr(get_collect_use_case, '_instance'):
        get_collect_use_case._instance = None  # Placeholder
    return get_collect_use_case._instance

def get_affiliate_use_case() -> GenerateAffiliateLinksUseCase:
    """Lazy initialization of affiliate use case."""
    if not hasattr(get_affiliate_use_case, '_instance'):
        get_affiliate_use_case._instance = None  # Placeholder
    return get_affiliate_use_case._instance

def get_publish_use_case() -> GenerateContentAndPublishUseCase:
    """Lazy initialization of publish use case."""
    if not hasattr(get_publish_use_case, '_instance'):
        get_publish_use_case._instance = None  # Placeholder
    return get_publish_use_case._instance


# Pydantic models for API
class ChannelCreateRequest(BaseModel):
    name: str
    telegram_chat_id: str
    product_source_url: str
    is_active: bool = True


class ChannelResponse(BaseModel):
    id: Optional[int]
    name: str
    telegram_chat_id: str
    product_source_url: str
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class ChannelSettingsRequest(BaseModel):
    channel_id: int
    categories: List[str]
    is_best_seller: bool = False
    min_rating: float = 4.0
    min_reviews: int = 10
    items_per_day: int = 5


class ChannelSettingsResponse(BaseModel):
    id: Optional[int]
    channel_id: int
    categories: List[str]
    is_best_seller: bool
    min_rating: float
    min_reviews: int
    items_per_day: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Telegram Affiliate Publisher API", "version": "1.0.0"}


# Channel management endpoints
@app.post("/channels", response_model=ChannelResponse)
async def create_channel(request: ChannelCreateRequest):
    """Создать новый канал."""
    channel_repo = get_channel_repo()
    if not channel_repo:
        raise HTTPException(status_code=503, detail="Service not configured - missing DATABASE_URL")

    channel = Channel(
        name=request.name,
        telegram_chat_id=request.telegram_chat_id,
        product_source_url=request.product_source_url,
        is_active=request.is_active
    )

    saved_channel = await channel_repo.save(channel)
    return ChannelResponse(**saved_channel.__dict__)


@app.get("/channels", response_model=List[ChannelResponse])
async def get_channels():
    """Получить список всех активных каналов."""
    channel_repo = get_channel_repo()
    if not channel_repo:
        raise HTTPException(status_code=503, detail="Service not configured - missing DATABASE_URL")

    channels = await channel_repo.get_all_active()
    return [ChannelResponse(**channel.__dict__) for channel in channels]


@app.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_id: int):
    """Получить канал по ID."""
    channel_repo = get_channel_repo()
    if not channel_repo:
        raise HTTPException(status_code=503, detail="Service not configured - missing DATABASE_URL")

    channel = await channel_repo.get_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ChannelResponse(**channel.__dict__)


# Channel settings endpoints
@app.post("/channels/{channel_id}/settings", response_model=ChannelSettingsResponse)
async def create_channel_settings(channel_id: int, request: ChannelSettingsRequest):
    """Создать настройки для канала."""
    channel_repo = get_channel_repo()
    settings_repo = get_settings_repo()

    if not channel_repo or not settings_repo:
        raise HTTPException(status_code=503, detail="Service not configured - missing DATABASE_URL")

    # Verify channel exists
    channel = await channel_repo.get_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    settings = ChannelSettings(
        channel_id=channel_id,
        categories=request.categories,
        is_best_seller=request.is_best_seller,
        min_rating=request.min_rating,
        min_reviews=request.min_reviews,
        items_per_day=request.items_per_day
    )

    saved_settings = await settings_repo.save(settings)
    return ChannelSettingsResponse(**saved_settings.__dict__)


@app.get("/channels/{channel_id}/settings", response_model=ChannelSettingsResponse)
async def get_channel_settings(channel_id: int):
    """Получить настройки канала."""
    settings_repo = get_settings_repo()
    if not settings_repo:
        raise HTTPException(status_code=503, detail="Service not configured - missing DATABASE_URL")

    settings = await settings_repo.get_by_channel_id(channel_id)
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return ChannelSettingsResponse(**settings.__dict__)


# Process management endpoints
@app.post("/processes/collect-products")
async def trigger_collect_products(background_tasks: BackgroundTasks):
    """Запустить процесс сбора и фильтрации товаров для всех каналов."""
    collect_use_case = get_collect_use_case()
    if not collect_use_case:
        raise HTTPException(status_code=503, detail="Service not configured - missing dependencies")

    background_tasks.add_task(collect_use_case.execute)
    return {"message": "Product collection process started", "status": "running"}


@app.post("/processes/generate-links/{channel_id}")
async def trigger_generate_links(channel_id: int, background_tasks: BackgroundTasks):
    """Запустить процесс генерации партнерских ссылок для канала."""
    affiliate_use_case = get_affiliate_use_case()
    if not affiliate_use_case:
        raise HTTPException(status_code=503, detail="Service not configured - missing dependencies")

    background_tasks.add_task(affiliate_use_case.execute, channel_id)
    return {"message": f"Affiliate link generation started for channel {channel_id}", "status": "running"}


@app.post("/processes/publish-content/{channel_id}")
async def trigger_publish_content(channel_id: int, background_tasks: BackgroundTasks):
    """Запустить процесс формирования контента и публикации для канала."""
    publish_use_case = get_publish_use_case()
    if not publish_use_case:
        raise HTTPException(status_code=503, detail="Service not configured - missing dependencies")

    background_tasks.add_task(publish_use_case.execute, channel_id)
    return {"message": f"Content generation and publishing started for channel {channel_id}", "status": "running"}


@app.post("/processes/run-full-cycle")
async def run_full_cycle(background_tasks: BackgroundTasks):
    """Запустить полный цикл: сбор товаров → генерация ссылок → публикация."""
    # This would orchestrate all use cases in sequence
    background_tasks.add_task(run_full_cycle_background)
    return {"message": "Full cycle process started", "status": "running"}


async def run_full_cycle_background():
    """Background task for full cycle execution."""
    try:
        collect_use_case = get_collect_use_case()
        affiliate_use_case = get_affiliate_use_case()
        publish_use_case = get_publish_use_case()

        if not collect_use_case or not affiliate_use_case or not publish_use_case:
            print("Error: Services not configured - missing dependencies")
            return

        # 1. Collect and filter products
        collect_results = await collect_use_case.execute()
        print(f"Collection completed: {collect_results}")

        # 2. Generate affiliate links for each channel
        for channel_id in collect_results.keys():
            if 'products' in collect_results[channel_id]:
                await affiliate_use_case.execute(channel_id)

        # 3. Generate content and publish for each channel
        for channel_id in collect_results.keys():
            if 'products' in collect_results[channel_id]:
                await publish_use_case.execute(channel_id)

        print("Full cycle completed successfully")

    except Exception as e:
        print(f"Error in full cycle: {e}")


# Admin panel endpoints (protected)
@app.get("/admin/dashboard", dependencies=[Depends(authenticate)])
async def admin_dashboard():
    """Admin dashboard with system status."""
    channel_repo = get_channel_repo()
    if not channel_repo:
        return {
            "total_channels": 0,
            "active_channels": 0,
            "last_run": datetime.utcnow(),
            "status": "not_configured",
            "message": "Database not configured - missing DATABASE_URL"
        }

    channels = await channel_repo.get_all_active()
    total_channels = len(channels)

    # Get today's publications count (simplified)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    return {
        "total_channels": total_channels,
        "active_channels": total_channels,
        "last_run": datetime.utcnow(),  # In real app, track actual last run
        "status": "operational"
    }


@app.get("/admin/publications/{channel_id}", dependencies=[Depends(authenticate)])
async def get_channel_publications(channel_id: int):
    """Get publication history for a channel."""
    publication_repo = get_publication_repo()
    if not publication_repo:
        raise HTTPException(status_code=503, detail="Service not configured - missing DATABASE_URL")

    publications = await publication_repo.get_recent_by_channel(channel_id, limit=20)
    return {
        "channel_id": channel_id,
        "publications": [
            {
                "id": p.id,
                "product_id": p.product_id,
                "published_at": p.published_at,
                "status": p.status,
                "telegram_message_id": p.telegram_message_id,
                "error_message": p.error_message
            }
            for p in publications
        ]
    }


@app.post("/admin/test-run/{channel_id}", dependencies=[Depends(authenticate)])
async def test_run_channel(channel_id: int, background_tasks: BackgroundTasks):
    """Test run publishing for a specific channel."""
    background_tasks.add_task(run_full_cycle_background)
    return {"message": f"Test run started for channel {channel_id}", "status": "running"}


# External scheduler endpoint (for UptimeRobot, etc.)
@app.post("/api/v1/run-daily")
async def run_daily_cycle():
    """
    External scheduler endpoint for daily automation.
    This endpoint can be called by UptimeRobot or similar services.
    """
    # In production, add API key validation here
    background_tasks = BackgroundTasks()
    background_tasks.add_task(run_full_cycle_background)
    return {"message": "Daily cycle started", "status": "running"}


# Health check - simplified for Railway deployment
@app.get("/health")
async def health_check():
    """Health check endpoint - works without database connection."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "service": "telegram-affiliate-publisher"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
