from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "CitiFlow API"
    debug: bool = True
    port: int = 8000
    secret_key: str = "change-me-in-production"
    api_key: str = "citiflow-dev-api-key-2026"

    # Database
    database_url: str = "postgresql://citiflow:citiflow@localhost:5432/citiflow_db"

    # Blockchain
    web3_provider_url: str = "http://127.0.0.1:8545"
    contract_address: str = "0x0000000000000000000000000000000000000000"
    contract_owner_private_key: str = ""

    # FX
    fx_api_key: str = "mock"
    fx_refresh_interval_sec: int = 30

    # ML
    risk_model_path: str = "ml/models/risk_model.pkl"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
