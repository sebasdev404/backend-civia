from app.core.config import settings

def asset_base(request):
    return settings.PUBLIC_ASSET_BASE.rstrip('/') if settings.PUBLIC_ASSET_BASE else str(request.base_url).rstrip('/')
