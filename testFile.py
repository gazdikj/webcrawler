"""
Refactored VirusTotal file testing module with proper error handling.
"""
import requests
from typing import Optional, Dict, Any

import dbVTManager as db
from config import get_settings
from logging_config import get_logger
from exceptions import VirusTotalAPIError, VirusTotalRateLimitError

logger = get_logger(__name__)
settings = get_settings()

# VirusTotal API endpoints
VT_FILES_URL = "https://www.virustotal.com/api/v3/files"
VT_ANALYSES_URL = "https://www.virustotal.com/api/v3/analyses/"

# API headers
headers = {
    "accept": "application/json",
    "x-apikey": settings.vt_api_key
}


def testFile(file_name: str, byte_data: bytes) -> str:
    """
    Upload file to VirusTotal for scanning.
    
    Args:
        file_name: Name of the file
        byte_data: File content as bytes
        
    Returns:
        Test ID for tracking analysis
        
    Raises:
        VirusTotalAPIError: If upload fails
    """
    logger.info(f"Uploading file to VirusTotal: {file_name}")
    
    try:
        # Prepare file for upload
        files = {"file": (file_name, byte_data)}
        
        # Upload to VirusTotal
        response = requests.post(VT_FILES_URL, files=files, headers=headers, timeout=30)
        
        # Check for rate limiting
        if response.status_code == 429:
            error_msg = "VirusTotal API rate limit exceeded"
            logger.error(error_msg)
            raise VirusTotalRateLimitError(error_msg)
        
        # Check for other errors
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        test_id = data['data']['id']
        
        logger.info(f"File uploaded successfully, test ID: {test_id}")
        
        # Save to database
        try:
            db.insert_sample(filename=file_name, test_id=test_id)
            logger.debug("Sample saved to database")
        except Exception as e:
            logger.error(f"Failed to save sample to database: {e}", exc_info=True)
        
        return test_id
    
    except requests.exceptions.Timeout:
        error_msg = "VirusTotal API request timeout"
        logger.error(error_msg)
        raise VirusTotalAPIError(error_msg)
    
    except requests.exceptions.RequestException as e:
        error_msg = f"VirusTotal API request failed: {e}"
        logger.error(error_msg, exc_info=True)
        raise VirusTotalAPIError(error_msg)
    
    except KeyError as e:
        error_msg = f"Unexpected API response format: {e}"
        logger.error(error_msg, exc_info=True)
        raise VirusTotalAPIError(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error uploading file: {e}"
        logger.error(error_msg, exc_info=True)
        raise VirusTotalAPIError(error_msg)


def analyseFile(test_id: str) -> Optional[Dict[str, Any]]:
    """
    Check analysis status and retrieve results if completed.
    
    Args:
        test_id: Test ID from file upload
        
    Returns:
        Analysis data if completed, None if still pending
        
    Raises:
        VirusTotalAPIError: If request fails
    """
    logger.debug(f"Checking analysis status for test ID: {test_id}")
    
    try:
        # Build analysis URL
        analysis_url = f"{VT_ANALYSES_URL}{test_id[:-2]}%3D%3D"
        
        # Get analysis results
        response = requests.get(analysis_url, headers=headers, timeout=30)
        
        # Check for rate limiting
        if response.status_code == 429:
            logger.warning("VirusTotal API rate limit hit during analysis check")
            return None
        
        # Check for errors
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        
        # Extract analysis info
        try:
            attributes = data['data']['attributes']
            meta = data['meta']['file_info']
            
            sha256 = meta['sha256']
            status = attributes['status']
            stats = attributes['stats']
            
            harmless = stats['harmless']
            malicious = stats['malicious']
            undetected = stats['undetected']
            
            logger.info(f"Analysis status: {status}")
            logger.debug(f"SHA256: {sha256}, Malicious: {malicious}, Harmless: {harmless}")
            
            # Check if analysis is complete
            if status != 'completed':
                logger.debug("Analysis not yet completed")
                return None
            
            # Save analysis to database
            try:
                analysis_id = db.insert_analysis(
                    status, undetected, malicious, harmless, sha256
                )
                logger.info(f"Analysis saved with ID: {analysis_id}")
                
                # Save antivirus results
                results = attributes.get('results', {})
                for engine_name, engine_data in results.items():
                    engine_category = engine_data.get('category')
                    engine_result = engine_data.get('result')
                    
                    db.insert_antivirus(
                        engine_name, engine_category, 
                        engine_result, analysis_id
                    )
                
                logger.debug(f"Saved {len(results)} antivirus results")
                
                # Update sample as analyzed
                db.update_sample(test_id, analysis_id)
                
            except Exception as e:
                logger.error(f"Failed to save analysis to database: {e}", exc_info=True)
            
            return data
        
        except KeyError as e:
            error_msg = f"Unexpected API response format: {e}"
            logger.error(error_msg, exc_info=True)
            raise VirusTotalAPIError(error_msg)
    
    except requests.exceptions.Timeout:
        logger.warning("VirusTotal API request timeout during analysis check")
        return None
    
    except requests.exceptions.RequestException as e:
        error_msg = f"VirusTotal API request failed: {e}"
        logger.error(error_msg, exc_info=True)
        raise VirusTotalAPIError(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error checking analysis: {e}"
        logger.error(error_msg, exc_info=True)
        raise VirusTotalAPIError(error_msg)


if __name__ == "__main__":
    import os
    import sys
    from time import sleep
    
    # Example usage
    path = "D:\\test\\sample.exe"
    
    if not os.path.exists(path):
        logger.error(f"File not found: {path}")
        sys.exit(1)
    
    try:
        with open(path, "rb") as f:
            byte_data = f.read()
            test_id = testFile(path, byte_data)
        
        # Wait for analysis
        max_attempts = settings.vt_max_wait_time // settings.vt_analysis_check_interval
        attempts = 0
        
        while attempts < max_attempts:
            result = analyseFile(test_id)
            if result:
                logger.info("Analysis completed successfully")
                break
            
            attempts += 1
            logger.info(f"Waiting for analysis... (attempt {attempts}/{max_attempts})")
            sleep(settings.vt_analysis_check_interval)
        
        if not result:
            logger.error("Analysis timeout")
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)