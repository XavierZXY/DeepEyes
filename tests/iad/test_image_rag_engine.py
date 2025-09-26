import logging
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from rich.logging import RichHandler

# Configure rich logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

log = logging.getLogger("rich")

# Import the module to test
from verl.workers.agent.envs.rag_engine.image_rag_engine import (
    ImageRAGEngine,
    query_class_image,
)


class TestImageRAGEngine:
    """Test cases for ImageRAGEngine"""

    def test_engine_initialization(self):
        """Test that the ImageRAGEngine can be initialized successfully"""
        log.info("Testing ImageRAGEngine initialization...")

        engine = ImageRAGEngine(base_path="/tmp")

        assert engine.name == "image_rag"
        assert engine.base_path == "/tmp"
        assert engine._image_cache == {}
        assert hasattr(engine, "IMAGE_PATHS")

        log.info("✓ ImageRAGEngine initialization test passed")

    def test_get_available_classes(self):
        """Test that available classes are returned correctly"""
        log.info("Testing get_available_classes...")

        engine = ImageRAGEngine()
        classes = engine.get_available_classes()

        expected_classes = ["grid", "hazelnut", "transistor"]
        assert set(classes) == set(expected_classes)

        log.info("✓ get_available_classes test passed")

    def test_reset_functionality(self):
        """Test that reset clears the cache"""
        log.info("Testing reset functionality...")

        engine = ImageRAGEngine()
        # Add something to cache
        engine._image_cache["test"] = "dummy_image"

        # Reset should clear cache
        engine.reset()
        assert engine._image_cache == {}

        log.info("✓ reset functionality test passed")

    @patch("os.path.exists")
    @patch("PIL.Image.open")
    def test_query_image_success(self, mock_image_open, mock_exists):
        """Test successful image query with mocked file operations"""
        log.info("Testing successful image query...")

        # Mock file exists
        mock_exists.return_value = True

        # Mock PIL Image
        mock_image = MagicMock()
        mock_image.size = (256, 256)
        mock_image.mode = "RGB"
        mock_image_open.return_value = mock_image

        engine = ImageRAGEngine(base_path="/tmp")
        result = engine.query_image("grid")

        assert result is not None
        assert result.size == (256, 256)
        assert result.mode == "RGB"

        log.info("✓ successful image query test passed")

    def test_query_image_invalid_class(self):
        """Test query with invalid class name"""
        log.info("Testing invalid class name query...")

        engine = ImageRAGEngine()
        result = engine.query_image("invalid_class")

        assert result is None

        log.info("✓ invalid class name query test passed")

    @patch("os.path.exists")
    def test_query_image_file_not_found(self, mock_exists):
        """Test query when image file doesn't exist"""
        log.info("Testing file not found scenario...")

        # Mock file doesn't exist
        mock_exists.return_value = False

        engine = ImageRAGEngine(base_path="/tmp")
        result = engine.query_image("grid")

        assert result is None

        log.info("✓ file not found scenario test passed")

    @patch(
        "verl.workers.agent.envs.rag_engine.image_rag_engine.extract_tool_call_contents"
    )
    def test_execute_with_answer(self, mock_extract):
        """Test execute method when answer is found"""
        log.info("Testing execute with answer...")

        # Mock extract_tool_call_contents to return answer
        mock_extract.side_effect = [
            ["some answer"],
            [],
        ]  # First call returns answer, second returns empty

        engine = ImageRAGEngine()
        result = engine.execute("some action string")

        # Should return empty string, 0.0 reward, True (done), empty info
        assert result == ("", 0.0, True, {})

        log.info("✓ execute with answer test passed")

    @patch(
        "verl.workers.agent.envs.rag_engine.image_rag_engine.extract_tool_call_contents"
    )
    def test_execute_no_query(self, mock_extract):
        """Test execute method when no query is found"""
        log.info("Testing execute with no query...")

        # Mock extract_tool_call_contents to return no queries
        mock_extract.return_value = []

        engine = ImageRAGEngine()
        result = engine.execute("some action string")

        # Should return empty string, 0.0 reward, True (done), empty info
        assert result == ("", 0.0, True, {})

        log.info("✓ execute with no query test passed")

    def test_convenience_function(self):
        """Test the convenience function query_class_image"""
        log.info("Testing convenience function...")

        # This should not raise an exception even if image doesn't exist
        with patch("os.path.exists", return_value=False):
            result = query_class_image("grid", "/tmp")
            assert result is None

        log.info("✓ convenience function test passed")

    def test_get_full_path(self):
        """Test _get_full_path method"""
        log.info("Testing _get_full_path method...")

        engine = ImageRAGEngine(base_path="/test/path")
        full_path = engine._get_full_path("grid")

        expected_path = os.path.join("/test/path", "grid/test/good/000.png")
        assert full_path == expected_path

        log.info("✓ _get_full_path method test passed")


def test_module_import():
    """Test that the module can be imported successfully"""
    log.info("Testing module import...")

    try:
        from verl.workers.agent.envs.rag_engine.image_rag_engine import (
            ImageRAGEngine,
        )

        assert ImageRAGEngine is not None
        log.info("✓ Module import test passed")
    except ImportError as e:
        pytest.fail(f"Failed to import module: {e}")


if __name__ == "__main__":
    log.info("Running minimal test for ImageRAGEngine...")

    # Run a basic smoke test
    try:
        # Test basic initialization
        engine = ImageRAGEngine(base_path="/tmp")
        log.info("✓ Engine initialization successful")

        # Test getting available classes
        classes = engine.get_available_classes()
        log.info(f"✓ Available classes: {classes}")

        # Test reset
        engine.reset()
        log.info("✓ Reset successful")

        # Test invalid query (should not crash)
        result = engine.query_image("invalid_class")
        assert result is None
        log.info("✓ Invalid query handled gracefully")

        log.info(
            "🎉 All basic tests passed! The ImageRAGEngine can execute successfully."
        )

    except Exception as e:
        log.error(f"❌ Test failed with error: {e}")
        raise
