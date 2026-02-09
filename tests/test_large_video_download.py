"""
Unit tests for validating the functionality of downloading videos larger than 20MB.
Tests the integration with local Telegram Bot API server for handling large files.
"""
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import os
import pytest

# Add parent directory to path to import bot module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestLargeVideoDownload(unittest.TestCase):
    """Test cases for downloading and uploading videos larger than 20MB."""

    def setUp(self):
        """Set up test fixtures."""
        # Set required environment variables
        os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token'
        os.environ['IMMICH_API_KEY'] = 'test_key'
        os.environ['IMMICH_API_URL'] = 'http://test-immich/api'
        os.environ['ALLOWED_USER_IDS'] = '123456789'
        
    def tearDown(self):
        """Clean up after tests."""
        # Clean up environment variables
        for key in ['TELEGRAM_BOT_TOKEN', 'IMMICH_API_KEY', 'IMMICH_API_URL', 
                    'ALLOWED_USER_IDS', 'TELEGRAM_API_URL']:
            if key in os.environ:
                del os.environ[key]
    
    def test_max_file_size_with_local_api(self):
        """Test that MAX_FILE_SIZE is set to 2GB when using local Telegram Bot API."""
        os.environ['TELEGRAM_API_URL'] = 'http://telegram-bot-api:8081'
        
        # Re-import module to pick up environment variable
        import importlib
        import app.bot as bot
        importlib.reload(bot)
        
        # 2GB in bytes
        expected_size = 2000 * 1024 * 1024
        self.assertEqual(bot.MAX_FILE_SIZE, expected_size)
        
    def test_max_file_size_without_local_api(self):
        """Test that MAX_FILE_SIZE is set to 20MB when NOT using local Telegram Bot API."""
        # Ensure TELEGRAM_API_URL is not set
        if 'TELEGRAM_API_URL' in os.environ:
            del os.environ['TELEGRAM_API_URL']
        
        # Re-import module to pick up environment variable
        import importlib
        import app.bot as bot
        importlib.reload(bot)
        
        # 20MB in bytes
        expected_size = 20 * 1024 * 1024
        self.assertEqual(bot.MAX_FILE_SIZE, expected_size)

    def test_telegram_api_url_configuration(self):
        """Test that TELEGRAM_API_URL is properly configured when set."""
        test_url = 'http://telegram-bot-api:8081'
        os.environ['TELEGRAM_API_URL'] = test_url
        
        # Re-import module
        import importlib
        import app.bot as bot
        importlib.reload(bot)
        
        self.assertEqual(bot.TELEGRAM_API_URL, test_url)
        
    def test_telegram_api_url_not_set(self):
        """Test that TELEGRAM_API_URL is None when not configured."""
        # Ensure TELEGRAM_API_URL is not set
        if 'TELEGRAM_API_URL' in os.environ:
            del os.environ['TELEGRAM_API_URL']
        
        # Re-import module
        import importlib
        import app.bot as bot
        importlib.reload(bot)
        
        self.assertIsNone(bot.TELEGRAM_API_URL)


@pytest.mark.asyncio
class TestLargeVideoDownloadAsync:
    """Async test cases for video download handlers."""
    
    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Set up environment variables for each test."""
        os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token'
        os.environ['IMMICH_API_KEY'] = 'test_key'
        os.environ['IMMICH_API_URL'] = 'http://test-immich/api'
        os.environ['ALLOWED_USER_IDS'] = '123456789'
        yield
        # Clean up
        for key in ['TELEGRAM_BOT_TOKEN', 'IMMICH_API_KEY', 'IMMICH_API_URL', 
                    'ALLOWED_USER_IDS', 'TELEGRAM_API_URL']:
            if key in os.environ:
                del os.environ[key]
    
    async def test_handle_large_video_with_local_api(self):
        """Test handling a video larger than 20MB with local API server."""
        # Set up environment for local API
        os.environ['TELEGRAM_API_URL'] = 'http://telegram-bot-api:8081'
        
        # Re-import to get updated MAX_FILE_SIZE
        import importlib
        import app.bot as bot
        importlib.reload(bot)
        
        # Verify MAX_FILE_SIZE is set correctly
        assert bot.MAX_FILE_SIZE == 2000 * 1024 * 1024, "MAX_FILE_SIZE should be 2GB with local API"
        
        # Create mock update with large video (50MB)
        update = Mock()
        update.message = Mock()
        update.message.from_user = Mock()
        update.message.from_user.id = 123456789
        update.message.from_user.username = 'test_user'
        update.message.video = Mock()
        update.message.video.file_size = 50 * 1024 * 1024  # 50MB
        update.message.video.file_id = 'test_file_id'
        update.message.video.file_name = 'large_video.mp4'
        update.message.date = Mock()
        update.message.reply_text = AsyncMock()
        
        # Create mock context
        context = Mock()
        context.bot = Mock()
        context.bot.get_file = AsyncMock()
        
        mock_file = Mock()
        mock_file.download_to_drive = AsyncMock()
        context.bot.get_file.return_value = mock_file
        
        # Mock necessary functions
        with patch('app.bot.check_immich_connection', return_value=True), \
             patch('app.bot.os.path.exists', return_value=True), \
             patch('app.bot.os.remove'), \
             patch('app.bot.upload_to_immich', new_callable=AsyncMock):
            
            # Call the handler
            await bot.handle_video(update, context)
            
            # Verify that the file was processed (not rejected for size)
            # The file should NOT be rejected since we're using local API (2GB limit)
            context.bot.get_file.assert_called_once_with('test_file_id')
            mock_file.download_to_drive.assert_called_once()
            
    async def test_handle_large_video_without_local_api(self):
        """Test that videos larger than 20MB are rejected without local API server."""
        # Ensure TELEGRAM_API_URL is not set
        if 'TELEGRAM_API_URL' in os.environ:
            del os.environ['TELEGRAM_API_URL']
        
        # Re-import to get updated MAX_FILE_SIZE
        import importlib
        import app.bot as bot
        importlib.reload(bot)
        
        # Verify MAX_FILE_SIZE is set correctly
        assert bot.MAX_FILE_SIZE == 20 * 1024 * 1024, "MAX_FILE_SIZE should be 20MB without local API"
        
        # Create mock update with large video (50MB)
        update = Mock()
        update.message = Mock()
        update.message.from_user = Mock()
        update.message.from_user.id = 123456789
        update.message.from_user.username = 'test_user'
        update.message.video = Mock()
        update.message.video.file_size = 50 * 1024 * 1024  # 50MB
        update.message.video.file_id = 'test_file_id'
        update.message.video.file_name = 'large_video.mp4'
        update.message.reply_text = AsyncMock()
        
        # Create mock context
        context = Mock()
        
        # Mock check_immich_connection
        with patch('app.bot.check_immich_connection', return_value=True):
            # Call the handler
            await bot.handle_video(update, context)
        
            # Verify that the file was rejected for being too large
            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert 'too big' in call_args.lower()
            assert '20' in call_args  # Should mention 20MB limit


if __name__ == '__main__':
    unittest.main()
