import pytest

from src.config import ConfigurationError, load_config


def test_loads_required_variables():
    config = load_config({"FACEIT_API_KEY": "faceit-secret", "DISCORD_TOKEN": "discord-secret"})
    assert config.faceit_api_key == "faceit-secret"
    assert config.discord_token == "discord-secret"


@pytest.mark.parametrize("environment", [
    {},
    {"FACEIT_API_KEY": "present"},
    {"DISCORD_TOKEN": "present"},
    {"FACEIT_API_KEY": " ", "DISCORD_TOKEN": "present"},
])
def test_missing_required_variable_raises_without_echoing_secrets(environment):
    with pytest.raises(ConfigurationError) as error:
        load_config(environment)
    assert "FACEIT_API_KEY" in str(error.value) or "DISCORD_TOKEN" in str(error.value)
    assert "secret" not in str(error.value)
