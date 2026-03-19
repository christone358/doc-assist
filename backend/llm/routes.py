"""
LLM Configuration API routes.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid

from llm.service import LLMConfig, LLMProvider, LLMConfigManager, _encrypt_key, _decrypt_key

router = APIRouter(prefix="/api/v1/llm", tags=["LLM Configuration"])
_manager = LLMConfigManager.get_instance()


class LLMConfigCreate(BaseModel):
    name: str
    provider: LLMProvider
    model_name: str
    api_base: str
    api_key: str              # Plain text - encrypted before storing
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    is_default: bool = False


class LLMConfigUpdate(BaseModel):
    name: Optional[str] = None
    model_name: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None   # If provided, update the key
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    is_active: Optional[bool] = None


class LLMConfigView(BaseModel):
    """Config as seen by the frontend (API key is masked)."""
    id: str
    name: str
    provider: str
    model_name: str
    api_base: str
    api_key_masked: str     # e.g. "sk-****1234"
    temperature: float
    max_tokens: int
    top_p: float
    is_default: bool
    is_active: bool


def _provider_value(provider) -> str:
    """Return provider string whether it's an enum or plain str."""
    return provider.value if hasattr(provider, "value") else str(provider)


def _mask_key(encrypted_key: str) -> str:
    """Return a masked version of the API key for display."""
    try:
        plain = _decrypt_key(encrypted_key)
        if len(plain) <= 8:
            return "****"
        return plain[:4] + "****" + plain[-4:]
    except Exception:
        return "****"


@router.get("/configs", response_model=List[LLMConfigView])
async def list_configs():
    """List all LLM configurations."""
    return [
        LLMConfigView(
            id=c.id,
            name=c.name,
            provider=_provider_value(c.provider),
            model_name=c.model_name,
            api_base=c.api_base,
            api_key_masked=_mask_key(c.api_key_encrypted),
            temperature=c.temperature,
            max_tokens=c.max_tokens,
            top_p=c.top_p,
            is_default=c.is_default,
            is_active=c.is_active,
        )
        for c in _manager.list_all()
    ]


@router.post("/configs", response_model=LLMConfigView, status_code=201)
async def create_config(body: LLMConfigCreate):
    """Add a new LLM configuration."""
    config = LLMConfig(
        id=str(uuid.uuid4()),
        name=body.name,
        provider=body.provider,
        model_name=body.model_name,
        api_base=body.api_base,
        api_key_encrypted=_encrypt_key(body.api_key),
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        top_p=body.top_p,
        is_default=body.is_default,
        is_active=True,
    )

    if body.is_default:
        # Unset default on others
        for existing in _manager.list_all():
            existing.is_default = False

    _manager.add(config)
    return LLMConfigView(
        id=config.id,
        name=config.name,
        provider=_provider_value(config.provider),
        model_name=config.model_name,
        api_base=config.api_base,
        api_key_masked=_mask_key(config.api_key_encrypted),
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        top_p=config.top_p,
        is_default=config.is_default,
        is_active=config.is_active,
    )


@router.patch("/configs/{config_id}", response_model=LLMConfigView)
async def update_config(config_id: str, body: LLMConfigUpdate):
    """Update an existing LLM configuration."""
    config = _manager.get(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    if body.name is not None:
        config.name = body.name
    if body.model_name is not None:
        config.model_name = body.model_name
    if body.api_base is not None:
        config.api_base = body.api_base
    if body.api_key is not None:
        config.api_key_encrypted = _encrypt_key(body.api_key)
    if body.temperature is not None:
        config.temperature = body.temperature
    if body.max_tokens is not None:
        config.max_tokens = body.max_tokens
    if body.top_p is not None:
        config.top_p = body.top_p
    if body.is_active is not None:
        config.is_active = body.is_active

    _manager.update(config)
    return LLMConfigView(
        id=config.id,
        name=config.name,
        provider=_provider_value(config.provider),
        model_name=config.model_name,
        api_base=config.api_base,
        api_key_masked=_mask_key(config.api_key_encrypted),
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        top_p=config.top_p,
        is_default=config.is_default,
        is_active=config.is_active,
    )


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(config_id: str):
    """Delete an LLM configuration."""
    if not _manager.delete(config_id):
        raise HTTPException(status_code=404, detail="Config not found")


@router.post("/configs/{config_id}/set-default")
async def set_default(config_id: str):
    """Set a configuration as the default model."""
    if not _manager.set_default(config_id):
        raise HTTPException(status_code=404, detail="Config not found")
    return {"message": "Default set"}


@router.post("/configs/{config_id}/test")
async def test_connection(config_id: str):
    """Test if an LLM configuration is reachable."""
    from llm.service import LLMService
    config = _manager.get(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    service = LLMService()
    try:
        response = await service.complete(
            system_prompt="You are a helpful assistant.",
            messages=[],
            user_message="Reply with exactly: OK",
            config_id=config_id,
        )
        if response.startswith("⚠️"):
            return {"success": False, "error": response}
        success = "ok" in response.lower()
        return {"success": success, "response": response[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)}
