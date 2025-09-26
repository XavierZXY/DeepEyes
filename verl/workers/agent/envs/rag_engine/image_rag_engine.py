import logging
import os
from typing import Optional

from PIL import Image
from rich.logging import RichHandler

from verl.workers.agent.tool_envs import ToolBase, extract_tool_call_contents

# Configure rich logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

log = logging.getLogger("rich")


class ImageRAGEngine(ToolBase):
    """
    A simple RAG engine for image retrieval based on class names.

    This engine can query and return images from three predefined classes:
    - grid
    - hazelnut
    - transistor

    Each class has a corresponding image at: {classname}/test/good/000.png
    """

    name = "image_rag"

    # Predefined image paths for each class
    IMAGE_PATHS = {
        "grid": "grid/test/good/000.png",
        "hazelnut": "hazelnut/test/good/000.png",
        "transistor": "transistor/test/good/000.png",
    }

    action_start = "<image_query>"
    action_end = "</image_query>"
    answer_start = "<answer>"
    answer_end = "</answer>"

    def __init__(
        self,
        base_path: str = "",
        _name=None,
        _desc=None,
        _params=None,
        **kwargs,
    ):
        """
        Initialize the Image RAG Engine.

        Args:
            base_path: Base directory path where the class folders are located
        """
        super().__init__(name=self.name)
        self.base_path = base_path
        self._image_cache = {}
        log.info(f"ImageRAGEngine initialized with base_path: {base_path}")

    def execute(self, action_string: str, **kwargs):
        """
        Execute image query based on action string.

        Args:
            action_string: String containing image query action

        Returns:
            tuple: (result_string, reward, done, info)
        """
        # Check if this is an answer (end of conversation)
        answers = extract_tool_call_contents(
            self.answer_start, self.answer_end, action_string
        )
        if answers:
            log.info("Found answer in action string, ending conversation")
            return "", 0.0, True, {}

        # Extract query from action string
        query_list = extract_tool_call_contents(
            self.action_start, self.action_end, action_string
        )
        if not query_list:
            log.warning("No image query found in action string")
            return "", 0.0, True, {}

        # Process the first query (assuming single query for simplicity)
        class_name = query_list[0].strip().lower()
        log.info(f"Processing image query for class: {class_name}")

        # Query the image
        try:
            image = self.query_image(class_name)
            if image is not None:
                result_info = {
                    "class_name": class_name,
                    "image_shape": image.size,
                    "image_mode": image.mode,
                    "image_path": self._get_full_path(class_name),
                }
                result_string = f"\n\n<image_result>\nFound image for class '{class_name}'\nImage size: {image.size}\nImage mode: {image.mode}\nPath: {self._get_full_path(class_name)}\n</image_result>\n\n"
                return (
                    result_string,
                    1.0,
                    False,
                    {"image": image, "info": result_info},
                )
            else:
                error_msg = f"No image found for class '{class_name}'. Available classes: {list(self.IMAGE_PATHS.keys())}"
                log.warning(error_msg)
                return (
                    f"\n\n<image_result>\n{error_msg}\n</image_result>\n\n",
                    0.0,
                    False,
                    {},
                )

        except Exception as e:
            error_msg = (
                f"Error querying image for class '{class_name}': {str(e)}"
            )
            log.error(error_msg)
            return (
                f"\n\n<image_result>\n{error_msg}\n</image_result>\n\n",
                0.0,
                False,
                {},
            )

    def query_image(self, class_name: str) -> Optional[Image.Image]:
        """
        Query and return image for the specified class name.

        Args:
            class_name: Name of the class to query (grid, hazelnut, transistor)

        Returns:
            PIL Image object if found, None otherwise
        """
        class_name = class_name.lower().strip()

        if class_name not in self.IMAGE_PATHS:
            log.warning(
                f"Class '{class_name}' not found. Available classes: {list(self.IMAGE_PATHS.keys())}"
            )
            return None

        # Check cache first
        if class_name in self._image_cache:
            log.info(f"Returning cached image for class: {class_name}")
            return self._image_cache[class_name]

        # Load image from file
        full_path = self._get_full_path(class_name)

        try:
            if not os.path.exists(full_path):
                log.error(f"Image file not found: {full_path}")
                return None

            image = Image.open(full_path)
            # Cache the image for future queries
            self._image_cache[class_name] = image
            log.info(
                f"Successfully loaded image for class '{class_name}' from {full_path}"
            )
            return image

        except Exception as e:
            log.error(f"Error loading image from {full_path}: {str(e)}")
            return None

    def _get_full_path(self, class_name: str) -> str:
        """Get the full file path for a class image."""
        relative_path = self.IMAGE_PATHS[class_name]
        return os.path.join(self.base_path, relative_path)

    def reset(self, *args, **kwargs):
        """Reset the engine state."""
        log.info("Resetting ImageRAGEngine")
        self._image_cache.clear()

    def get_available_classes(self) -> list:
        """Get list of available class names."""
        return list(self.IMAGE_PATHS.keys())

    def preload_images(self):
        """Preload all images into cache for faster access."""
        log.info("Preloading all images...")
        for class_name in self.IMAGE_PATHS.keys():
            self.query_image(class_name)
        log.info(f"Preloaded {len(self._image_cache)} images")


# Convenience function for direct usage
def query_class_image(
    class_name: str, base_path: str = ""
) -> Optional[Image.Image]:
    """
    Convenience function to directly query an image by class name.

    Args:
        class_name: Name of the class (grid, hazelnut, transistor)
        base_path: Base directory path where class folders are located

    Returns:
        PIL Image object if found, None otherwise
    """
    engine = ImageRAGEngine(base_path=base_path)
    return engine.query_image(class_name)


if __name__ == "__main__":
    # Example usage
    log.info("Testing ImageRAGEngine...")

    # Initialize engine (adjust base_path as needed)
    engine = ImageRAGEngine(base_path="./")

    # Test querying each class
    for class_name in ["grid", "hazelnut", "transistor"]:
        log.info(f"\nTesting query for class: {class_name}")
        image = engine.query_image(class_name)
        if image:
            log.info(
                f"✓ Successfully retrieved image for {class_name}: size={image.size}, mode={image.mode}"
            )
        else:
            log.error(f"✗ Failed to retrieve image for {class_name}")

    # Test invalid class
    log.info("\nTesting invalid class...")
    invalid_image = engine.query_image("invalid_class")
    assert invalid_image is None, "Should return None for invalid class"

    log.info("\nImageRAGEngine testing completed!")
