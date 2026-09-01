from unittest.mock import MagicMock, patch

from src.config import TelegramSettings
from src.services.telegram.bot import TelegramBot
from src.services.telegram.factory import make_telegram_service


class TestTelegramBot:
    def test_bot_creation(self):
        agentic_rag = MagicMock()
        bot = TelegramBot(
            bot_token="test_token",
            opensearch_client=MagicMock(),
            embeddings_client=MagicMock(),
            agentic_rag_service=agentic_rag,
        )

        assert bot.bot_token == "test_token"
        assert bot.opensearch is not None
        assert bot.embeddings is not None
        assert bot.agentic_rag is agentic_rag


class TestTelegramSettings:
    def test_default_settings(self):
        settings = TelegramSettings(bot_token="", enabled=False)
        assert settings.enabled is False
        assert settings.bot_token == ""

    def test_custom_settings(self):
        settings = TelegramSettings(bot_token="test", enabled=True)
        assert settings.enabled is True
        assert settings.bot_token == "test"


class TestTelegramFactory:
    @patch("src.services.telegram.factory.get_settings")
    def test_factory_disabled(self, mock_settings):
        mock_settings.return_value.telegram.enabled = False
        bot = make_telegram_service(
            opensearch_client=MagicMock(),
            embeddings_client=MagicMock(),
            agentic_rag_service=MagicMock(),
        )
        assert bot is None

    @patch("src.services.telegram.factory.get_settings")
    def test_factory_no_token(self, mock_settings):
        mock_settings.return_value.telegram.enabled = True
        mock_settings.return_value.telegram.bot_token = ""
        bot = make_telegram_service(
            opensearch_client=MagicMock(),
            embeddings_client=MagicMock(),
            agentic_rag_service=MagicMock(),
        )
        assert bot is None

    @patch("src.services.telegram.factory.get_settings")
    def test_factory_success(self, mock_settings):
        mock_settings.return_value.telegram.enabled = True
        mock_settings.return_value.telegram.bot_token = "test_token"
        agentic_rag = MagicMock()
        bot = make_telegram_service(
            opensearch_client=MagicMock(),
            embeddings_client=MagicMock(),
            agentic_rag_service=agentic_rag,
        )
        assert bot is not None
        assert bot.bot_token == "test_token"
        assert bot.agentic_rag is agentic_rag
