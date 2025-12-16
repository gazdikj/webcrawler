"""
Refactored hash manager with proper error handling and logging.
"""
import os
import hashlib
import json
from pathlib import Path
from typing import Optional

from logging_config import get_logger

logger = get_logger(__name__)

# Configuration
HASH_FILE = "hashes.json"


def calculate_sha256(file_path: str) -> Optional[str]:
    """
    Calculate SHA-256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA-256 hash as hex string, or None if error
    """
    logger.debug(f"Calculating SHA-256 for: {file_path}")
    
    try:
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        hash_value = sha256_hash.hexdigest()
        logger.debug(f"SHA-256 calculated: {hash_value}")
        return hash_value
    
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return None
    
    except PermissionError:
        logger.error(f"Permission denied reading file: {file_path}")
        return None
    
    except Exception as e:
        logger.error(f"Error calculating hash for {file_path}: {e}", exc_info=True)
        return None


def save_hashes(file_name: str, hash_value: str) -> bool:
    """
    Save file hash to JSON file.
    
    Args:
        file_name: Name of the file
        hash_value: SHA-256 hash value
        
    Returns:
        True if saved successfully, False otherwise
    """
    logger.debug(f"Saving hash for file: {file_name}")
    
    try:
        # Load existing data
        data = {}
        if os.path.exists(HASH_FILE):
            try:
                with open(HASH_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in {HASH_FILE}, creating new file")
                data = {}
            except Exception as e:
                logger.error(f"Error reading {HASH_FILE}: {e}", exc_info=True)
                data = {}
        
        # Add new hash
        data[file_name] = hash_value
        
        # Save updated data
        with open(HASH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        logger.info(f"Hash saved for: {file_name}")
        return True
    
    except PermissionError:
        logger.error(f"Permission denied writing to {HASH_FILE}")
        return False
    
    except Exception as e:
        logger.error(f"Error saving hash for {file_name}: {e}", exc_info=True)
        return False


def load_hashes() -> dict:
    """
    Load all hashes from JSON file.
    
    Returns:
        Dictionary of filename -> hash mappings
    """
    try:
        if not os.path.exists(HASH_FILE):
            logger.debug(f"Hash file does not exist: {HASH_FILE}")
            return {}
        
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        logger.info(f"Loaded {len(data)} hashes from {HASH_FILE}")
        return data
    
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {HASH_FILE}")
        return {}
    
    except Exception as e:
        logger.error(f"Error loading hashes: {e}", exc_info=True)
        return {}


def get_hash(file_name: str) -> Optional[str]:
    """
    Get hash for a specific file.
    
    Args:
        file_name: Name of the file
        
    Returns:
        SHA-256 hash if found, None otherwise
    """
    hashes = load_hashes()
    return hashes.get(file_name)


def hash_exists(file_name: str) -> bool:
    """
    Check if hash exists for a file.
    
    Args:
        file_name: Name of the file
        
    Returns:
        True if hash exists, False otherwise
    """
    return get_hash(file_name) is not None


if __name__ == "__main__":
    # Test functionality
    test_file = "test.txt"
    
    # Create test file
    with open(test_file, "w") as f:
        f.write("Test content")
    
    # Calculate and save hash
    hash_value = calculate_sha256(test_file)
    if hash_value:
        save_hashes(test_file, hash_value)
        logger.info(f"Test hash: {hash_value}")
        
        # Verify
        loaded_hash = get_hash(test_file)
        logger.info(f"Loaded hash: {loaded_hash}")
        logger.info(f"Hashes match: {hash_value == loaded_hash}")
    
    # Cleanup
    os.remove(test_file)