"""
Refactored Streamlit UI with proper error handling and logging.
"""
import streamlit as st
import requests
import time
import pandas as pd
import base64
from typing import Optional, Dict, Any, List

from config import get_settings
from logging_config import setup_logging, get_logger

# Initialize settings and logging
settings = get_settings()
setup_logging(
    log_level=settings.log_level,
    log_file=settings.log_file
)
logger = get_logger(__name__)

# API configuration
API_URL = "http://127.0.0.1:5000" # f"http://{settings.flask_host}:{settings.flask_port}"

# Page configuration
st.set_page_config(
    page_title="Crawler Monitoring",
    page_icon="🕷️",
    layout="wide"
)


def make_api_request(endpoint: str, method: str = "GET", 
                     data: Optional[Dict] = None) -> Optional[requests.Response]:
    """
    Make API request with error handling.
    
    Args:
        endpoint: API endpoint
        method: HTTP method (GET/POST)
        data: Request data for POST
        
    Returns:
        Response object or None if failed
    """
    try:
        url = f"{API_URL}{endpoint}"
        
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        else:
            logger.error(f"Unsupported method: {method}")
            return None
        
        response.raise_for_status()
        return response
    
    except requests.exceptions.Timeout:
        logger.error(f"API request timeout: {endpoint}")
        st.error(f"⏱️ Request timeout: {endpoint}")
        return None
    
    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to API: {API_URL}")
        st.error(f"❌ Cannot connect to API at {API_URL}. Is the server running?")
        return None
    
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error: {e}", exc_info=True)
        st.error(f"❌ API error: {e}")
        return None
    
    except Exception as e:
        logger.error(f"Unexpected error in API request: {e}", exc_info=True)
        st.error(f"❌ Unexpected error: {e}")
        return None


def start_crawl_task(web_url: str, what_to_crawl: str, 
                     driver: str, device: str) -> bool:
    """
    Start a new crawling task.
    
    Args:
        web_url: Target URL
        what_to_crawl: Search keyword
        driver: Browser driver
        device: Device type
        
    Returns:
        True if task started successfully
    """
    logger.info(f"Starting crawl task: {web_url}, keyword: {what_to_crawl}")
    
    data = {
        "web": web_url,
        "filter": what_to_crawl,
        "driver": driver,
        "device": device
    }
    
    response = make_api_request("/start-task", method="POST", data=data)
    
    if response and response.status_code == 202:
        task_id = response.json().get("task_id")
        logger.info(f"Crawl task started: {task_id}")
        return True
    
    return False


def start_analysis_task(uploaded_file) -> bool:
    """
    Start file analysis task.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        True if task started successfully
    """
    logger.info(f"Starting analysis for: {uploaded_file.name}")
    
    try:
        # Read file data
        byte_data = uploaded_file.getvalue()
        encoded_data = base64.b64encode(byte_data).decode("utf-8")
        
        data = {
            "file_name": uploaded_file.name,
            "byte_data": encoded_data
        }
        
        response = make_api_request("/start-analysis", method="POST", data=data)
        
        if response and response.status_code == 202:
            task_id = response.json().get("task_id")
            logger.info(f"Analysis task started: {task_id}")
            return True
        
        return False
    
    except Exception as e:
        logger.error(f"Error starting analysis: {e}", exc_info=True)
        st.error(f"❌ Error starting analysis: {e}")
        return False


def get_tasks_status() -> Optional[List[Dict[str, Any]]]:
    """
    Get status of all active tasks.
    
    Returns:
        List of task statuses or None if failed
    """
    response = make_api_request("/tasks-status")
    
    if response and response.status_code == 200:
        return response.json()
    
    return None


def get_latest_analysis() -> Optional[Dict[str, Any]]:
    """
    Get latest completed analysis.
    
    Returns:
        Analysis data or None if not ready
    """
    response = make_api_request("/get-analysis")
    
    if response and response.status_code == 200:
        return response.json()
    
    return None


def render_analysis_results(analysis_data: Dict[str, Any], 
                           file_name: str) -> None:
    """
    Render analysis results in UI.
    
    Args:
        analysis_data: Analysis data from API
        file_name: Name of analyzed file
    """
    try:
        # Extract data
        data = analysis_data.get("data", {}).get("data", {})
        attributes = data.get("attributes", {})
        stats = attributes.get("stats", {})
        results_raw = attributes.get("results", {})
        meta = data.get("meta", {}).get("file_info", {})
        
        # Extract statistics
        md5 = meta.get("md5", "N/A")
        sha256 = meta.get("sha256", "N/A")
        undetected = stats.get("undetected", "N/A")
        malicious = stats.get("malicious", "N/A")
        harmless = stats.get("harmless", "N/A")
        suspicious = stats.get("suspicious", 0)
        
        # Extract threat results
        threats = []
        for engine_name, result_info in results_raw.items():
            result_text = result_info.get("result")
            category = result_info.get("category", "undetected")
            
            if result_text and category in ["malicious", "suspicious"]:
                threats.append({
                    "engine": engine_name,
                    "result": result_text,
                    "category": category
                })
        
        # Display results
        st.success("✅ Analysis completed!")
        
        # Create two columns
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Analysis Details")
            st.markdown(f"**File name:** `{file_name}`")
            st.markdown(f"**MD5:** `{md5}`")
            st.markdown(f"**SHA256:** `{sha256}`")
            
            st.markdown("---")
            
            # Statistics with color coding
            st.markdown(f"**Undetected:** {undetected}")
            
            if malicious > 0:
                st.markdown(f"**Malicious:** :red[{malicious}] ⚠️")
            else:
                st.markdown(f"**Malicious:** :green[{malicious}] ✅")
            
            if suspicious > 0:
                st.markdown(f"**Suspicious:** :orange[{suspicious}]")
            
            st.markdown(f"**Harmless:** :green[{harmless}]")
        
        with col2:
            st.subheader("🛡️ Detections")
            
            if threats:
                st.warning(f"⚠️ Found {len(threats)} threat(s)")
                
                for threat in threats:
                    category_emoji = "🔴" if threat["category"] == "malicious" else "🟠"
                    st.markdown(f"{category_emoji} **{threat['engine']}:** {threat['result']}")
            else:
                st.success("✅ No threats detected")
        
        # Detailed results in expander
        with st.expander("🔍 View all engine results"):
            if results_raw:
                results_df = pd.DataFrame([
                    {
                        "Engine": engine,
                        "Category": data.get("category", "unknown"),
                        "Result": data.get("result", "Clean")
                    }
                    for engine, data in results_raw.items()
                ])
                st.dataframe(results_df, use_container_width=True)
            else:
                st.info("No detailed results available")
    
    except Exception as e:
        logger.error(f"Error rendering analysis results: {e}", exc_info=True)
        st.error(f"❌ Error displaying results: {e}")


def render_tasks_table(tasks: List[Dict[str, Any]]) -> None:
    """
    Render tasks status table.
    
    Args:
        tasks: List of task statuses
    """
    if not tasks:
        st.info("ℹ️ No active tasks")
        return
    
    try:
        # Extract progress data
        progress_data = []
        for task in tasks:
            progress = task.get("progress", {})
            
            # Handle different progress formats
            if isinstance(progress, dict):
                progress_data.append({
                    "Status": task.get("status", "UNKNOWN"),
                    "File Name": progress.get("file_name", "N/A"),
                    "File Size": progress.get("file_size", "N/A"),
                    "Current": progress.get("current", 0),
                    "Message": progress.get("status", "Processing...")
                })
        
        if progress_data:
            df = pd.DataFrame(progress_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("ℹ️ No progress data available")
    
    except Exception as e:
        logger.error(f"Error rendering tasks table: {e}", exc_info=True)
        st.error(f"❌ Error displaying tasks: {e}")


# Main UI
def main():
    """Main UI function."""
    
    st.title("🕷️ Crawler Monitoring Dashboard")
    st.markdown("---")
    
    # Sidebar with configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.markdown(f"**API URL:** `{API_URL}`")
        
        # Health check
        health_response = make_api_request("/health")
        if health_response:
            st.success("✅ API Connected")
        else:
            st.error("❌ API Disconnected")
        
        st.markdown("---")
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("🔄 Auto-refresh", value=True)
        if auto_refresh:
            refresh_interval = st.slider("Refresh interval (seconds)", 1, 10, 2)
    
    # Crawl configuration section
    st.header("🚀 Start New Crawl")
    
    col1, col2 = st.columns(2)
    
    with col1:
        web_url = st.selectbox(
            "Select website:",
            ["https://datoid.cz", "Option 2", "Option 3"]
        )
        driver = st.selectbox("Browser:", ["chrome", "firefox"])
    
    with col2:
        what_to_crawl = st.text_input("Search keyword:", value="")
        device = st.selectbox("Device:", ["desktop", "mobile"])
    
    if st.button("▶️ Start Crawl", type="primary"):
        if not what_to_crawl:
            st.warning("⚠️ Please enter a search keyword")
        else:
            with st.spinner("Starting crawl task..."):
                if start_crawl_task(web_url, what_to_crawl, driver, device):
                    st.success("✅ Crawl task started successfully!")
                else:
                    st.error("❌ Failed to start crawl task")
    
    st.markdown("---")
    
    # File analysis section
    st.header("🔬 File Analysis")
    
    uploaded_file = st.file_uploader(
        "Upload file for VirusTotal analysis",
        help="Upload a file to scan with VirusTotal"
    )
    
    if uploaded_file:
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.info(f"📄 Selected: **{uploaded_file.name}** ({uploaded_file.size} bytes)")
        
        with col2:
            if st.button("🔍 Analyze File", type="primary"):
                with st.spinner("Starting analysis..."):
                    if start_analysis_task(uploaded_file):
                        st.success("✅ Analysis started!")
                    else:
                        st.error("❌ Failed to start analysis")
    
    st.markdown("---")
    
    # Active tasks section
    st.header("📊 Active Tasks")
    
    tasks_placeholder = st.empty()
    analysis_placeholder = st.empty()
    
    # Main loop
    while True:
        # Get and display tasks
        with tasks_placeholder.container():
            tasks = get_tasks_status()
            if tasks:
                render_tasks_table(tasks)
            else:
                st.info("ℹ️ No active tasks or unable to connect to API")
        
        # Check for completed analysis
        with analysis_placeholder.container():
            if uploaded_file:
                analysis = get_latest_analysis()
                if analysis and analysis.get("message") == "Analysis completed":
                    render_analysis_results(analysis, uploaded_file.name)
        
        # Auto-refresh logic
        if auto_refresh:
            time.sleep(refresh_interval)
            st.rerun()
        else:
            break


if __name__ == "__main__":
    try:
        logger.info("Starting Streamlit UI")
        main()
    except KeyboardInterrupt:
        logger.info("UI interrupted by user")
    except Exception as e:
        logger.error(f"UI error: {e}", exc_info=True)
        st.error(f"❌ Fatal error: {e}")
        st.info("Check logs for more details")