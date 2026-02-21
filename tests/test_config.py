"""Tests for configuration module."""

from agent_stack.config import AppConfig, CosmosConfig, EntraConfig, OpenAIConfig, Settings, StorageConfig, _env


def test_env_returns_value(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "hello")
    assert _env("TEST_KEY") == "hello"


def test_env_returns_default_when_missing(monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    assert _env("TEST_KEY", "fallback") == "fallback"


def test_env_returns_empty_string_default(monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    assert _env("TEST_KEY") == ""


def test_entra_authority():
    config = EntraConfig.__new__(EntraConfig)
    object.__setattr__(config, "tenant_id", "my-tenant")
    assert config.authority == "https://login.microsoftonline.com/my-tenant"


def test_app_config_is_development_true():
    config = AppConfig.__new__(AppConfig)
    object.__setattr__(config, "env", "development")
    assert config.is_development is True


def test_app_config_is_development_false():
    config = AppConfig.__new__(AppConfig)
    object.__setattr__(config, "env", "production")
    assert config.is_development is False


def test_cosmos_config_defaults(monkeypatch):
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://cosmos.example.com")
    monkeypatch.setenv("COSMOS_KEY", "secret")
    monkeypatch.delenv("COSMOS_DATABASE", raising=False)
    config = CosmosConfig()
    assert config.endpoint == "https://cosmos.example.com"
    assert config.key == "secret"
    assert config.database == "agent-stack"


def test_openai_config(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://oai.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
    config = OpenAIConfig()
    assert config.endpoint == "https://oai.example.com"
    assert config.deployment == "gpt-4"


def test_storage_config_default_container(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "conn")
    monkeypatch.delenv("AZURE_STORAGE_CONTAINER", raising=False)
    config = StorageConfig()
    assert config.container == "$web"


def test_settings_creates_all_sub_configs(monkeypatch):
    # Set minimum required env vars
    for key in [
        "COSMOS_ENDPOINT",
        "COSMOS_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_STORAGE_CONNECTION_STRING",
        "ENTRA_TENANT_ID",
        "ENTRA_CLIENT_ID",
        "ENTRA_CLIENT_SECRET",
    ]:
        monkeypatch.setenv(key, "test")
    settings = Settings()
    assert isinstance(settings.cosmos, CosmosConfig)
    assert isinstance(settings.openai, OpenAIConfig)
    assert isinstance(settings.storage, StorageConfig)
    assert isinstance(settings.entra, EntraConfig)
    assert isinstance(settings.app, AppConfig)
