import runpod
from runpod.serverless.utils import rp_upload
import json
import urllib.request
import urllib.parse
import time
import os
import requests
import base64
from io import BytesIO
import websocket
import uuid
import tempfile
import socket
import traceback
import logging
import sys
import warnings

# CRITICAL: Configure numba BEFORE importing any modules that use numba
# Numba's SSA block analysis and other debug logs can be very verbose
# These print statements bypass logging, so we need to suppress them early

# Set numba environment variables if not already set
os.environ.setdefault('NUMBA_DEBUG', '0')
os.environ.setdefault('NUMBA_DEBUG_TYPEINFER', '0')
os.environ.setdefault('NUMBA_DEBUG_JIT', '0')
os.environ.setdefault('NUMBA_DEBUG_FRONTEND', '0')
os.environ.setdefault('NUMBA_DEBUG_BACKEND', '0')
os.environ.setdefault('NUMBA_DISABLE_PERFORMANCE_WARNINGS', '1')
os.environ.setdefault('NUMBA_LOG_LEVEL', 'ERROR')

# Set AWS region for S3 uploads (if BUCKET_ENDPOINT_URL is set)
# RunPod S3 requires correct region configuration
# Extract region from BUCKET_ENDPOINT_URL if it contains region info
bucket_endpoint = os.environ.get("BUCKET_ENDPOINT_URL", "")
if bucket_endpoint:
    # Try to extract region from endpoint URL
    # Examples:
    # - https://s3api-eu-ro-1.runpod.io/bucket-name -> eu-ro-1
    # - https://bucket.s3.us-east-1.amazonaws.com -> us-east-1
    import re
    region_match = re.search(r's3api-([a-z0-9-]+)\.runpod\.io', bucket_endpoint)
    if region_match:
        aws_region = region_match.group(1)
        os.environ['AWS_DEFAULT_REGION'] = aws_region
        os.environ['AWS_REGION'] = aws_region
        print(f"worker-comfyui: Detected S3 region from endpoint: {aws_region}")
    elif 's3.' in bucket_endpoint and 'amazonaws.com' in bucket_endpoint:
        # AWS S3 format: https://bucket.s3.region.amazonaws.com
        region_match = re.search(r's3\.([a-z0-9-]+)\.amazonaws\.com', bucket_endpoint)
        if region_match:
            aws_region = region_match.group(1)
            os.environ['AWS_DEFAULT_REGION'] = aws_region
            os.environ['AWS_REGION'] = aws_region
            print(f"worker-comfyui: Detected AWS S3 region from endpoint: {aws_region}")

# Set Hugging Face cache directories for BLIP and other transformers models
# Priority: Network Volume > Image default path
# transformers library stores models in cache_dir/models--Salesforce--blip-vqa-base/ structure
blip_cache_network = '/runpod-volume/models/blip'
blip_cache_image = '/comfyui/models/blip'

# Prefer Network Volume, fallback to image default path
if os.path.isdir(blip_cache_network):
    blip_cache_dir = blip_cache_network
    cache_source = "Network Volume"
elif os.path.isdir(blip_cache_image):
    blip_cache_dir = blip_cache_image
    cache_source = "image default path"
else:
    blip_cache_dir = None
    cache_source = None

if blip_cache_dir:
    os.environ['HF_HUB_CACHE'] = blip_cache_dir
    os.environ['TRANSFORMERS_CACHE'] = blip_cache_dir
    os.environ['HF_HOME'] = blip_cache_dir
    os.environ['HUGGINGFACE_HUB_CACHE'] = blip_cache_dir
    print(f"worker-comfyui: Using {cache_source} for BLIP models: {blip_cache_dir}")
    
    # Verify model directories exist
    import glob
    model_dirs = glob.glob(os.path.join(blip_cache_dir, 'models--Salesforce--*'))
    if model_dirs:
        print(f"worker-comfyui: Found {len(model_dirs)} BLIP model directory(ies):")
        for model_dir in model_dirs:
            print(f"worker-comfyui:   - {model_dir}")
    else:
        print(f"worker-comfyui: WARNING: No BLIP model directories found in {blip_cache_dir}")
        if cache_source == "Network Volume":
            print(f"worker-comfyui: Please run download-models-to-volume.sh to download BLIP models")
else:
    print(f"worker-comfyui: WARNING: BLIP cache directory not found (checked Network Volume and image path)")

# Configure logging to reduce numba verbose output
# Set numba logger to CRITICAL level to suppress all messages including type inference errors
numba_logger = logging.getLogger('numba')
numba_logger.setLevel(logging.CRITICAL)

# Also suppress numba.core and all numba sub-loggers
numba_core_logger = logging.getLogger('numba.core')
numba_core_logger.setLevel(logging.CRITICAL)

# Suppress all numba-related loggers (including type inference and compilation messages)
for logger_name in ['numba', 'numba.core', 'numba.core.ssa', 'numba.core.ir', 'numba.core.types', 
                     'numba.core.compiler', 'numba.core.errors', 'numba.cpython', 'numba.core.rewrites',
                     'numba.core.untyped_passes', 'numba.core.typed_passes']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.CRITICAL)
    # Disable propagation to prevent output
    logger.propagate = False

# Suppress numba warnings at Python level
warnings.filterwarnings('ignore', category=UserWarning, module='numba')
warnings.filterwarnings('ignore', category=RuntimeWarning, module='numba')
warnings.filterwarnings('ignore', message='.*numba.*')

# Create a custom stdout filter to suppress numba debug prints
# This is a workaround for numba's internal print statements that bypass logging
class NumbaOutputFilter:
    """Filter out numba debug output from stdout/stderr"""
    def __init__(self, original_stream):
        self.original_stream = original_stream
        self.buffer = ''
    
    def write(self, text):
        # Filter out numba debug patterns
        if any(pattern in text for pattern in [
            'SSA block',
            'dispatch pc',
            'on stmt:',
            'State(pc_initial=',
            'RESUME(arg=',
            'NOP(arg=',
            'LOAD_GLOBAL(arg=',
            '==== SSA block',
        ]):
            return  # Suppress numba debug output
        self.original_stream.write(text)
        self.original_stream.flush()
    
    def flush(self):
        self.original_stream.flush()
    
    def __getattr__(self, name):
        return getattr(self.original_stream, name)

# Apply filter to stdout and stderr to catch numba's print statements
if not isinstance(sys.stdout, NumbaOutputFilter):
    sys.stdout = NumbaOutputFilter(sys.stdout)
if not isinstance(sys.stderr, NumbaOutputFilter):
    sys.stderr = NumbaOutputFilter(sys.stderr)

# Time to wait between API check attempts in milliseconds
COMFY_API_AVAILABLE_INTERVAL_MS = 50
# Maximum number of API check attempts
# Increased from 500 to 1000 to allow more time for ComfyUI startup (50 seconds total)
COMFY_API_AVAILABLE_MAX_RETRIES = 1000
# Websocket reconnection behaviour (can be overridden through environment variables)
# NOTE: more attempts and diagnostics improve debuggability whenever ComfyUI crashes mid-job.
#   • WEBSOCKET_RECONNECT_ATTEMPTS sets how many times we will try to reconnect.
#   • WEBSOCKET_RECONNECT_DELAY_S sets the sleep in seconds between attempts.
#
# If the respective env-vars are not supplied we fall back to sensible defaults ("5" and "3").
WEBSOCKET_RECONNECT_ATTEMPTS = int(os.environ.get("WEBSOCKET_RECONNECT_ATTEMPTS", 5))
WEBSOCKET_RECONNECT_DELAY_S = int(os.environ.get("WEBSOCKET_RECONNECT_DELAY_S", 3))

# Extra verbose websocket trace logs (set WEBSOCKET_TRACE=true to enable)
if os.environ.get("WEBSOCKET_TRACE", "false").lower() == "true":
    # This prints low-level frame information to stdout which is invaluable for diagnosing
    # protocol errors but can be noisy in production – therefore gated behind an env-var.
    websocket.enableTrace(True)

# Host where ComfyUI is running
COMFY_HOST = "127.0.0.1:8188"
# Enforce a clean state after each job is done
# see https://docs.runpod.io/docs/handler-additional-controls#refresh-worker
REFRESH_WORKER = os.environ.get("REFRESH_WORKER", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Helper: quick reachability probe of ComfyUI HTTP endpoint (port 8188)
# ---------------------------------------------------------------------------


def _comfy_server_status():
    """Return a dictionary with basic reachability info for the ComfyUI HTTP server."""
    try:
        resp = requests.get(f"http://{COMFY_HOST}/", timeout=5)
        return {
            "reachable": resp.status_code == 200,
            "status_code": resp.status_code,
        }
    except Exception as exc:
        return {"reachable": False, "error": str(exc)}


def _attempt_websocket_reconnect(ws_url, max_attempts, delay_s, initial_error):
    """
    Attempts to reconnect to the WebSocket server after a disconnect.

    Args:
        ws_url (str): The WebSocket URL (including client_id).
        max_attempts (int): Maximum number of reconnection attempts.
        delay_s (int): Delay in seconds between attempts.
        initial_error (Exception): The error that triggered the reconnect attempt.

    Returns:
        websocket.WebSocket: The newly connected WebSocket object.

    Raises:
        websocket.WebSocketConnectionClosedException: If reconnection fails after all attempts.
    """
    print(
        f"worker-comfyui - Websocket connection closed unexpectedly: {initial_error}. Attempting to reconnect..."
    )
    last_reconnect_error = initial_error
    for attempt in range(max_attempts):
        # Log current server status before each reconnect attempt so that we can
        # see whether ComfyUI is still alive (HTTP port 8188 responding) even if
        # the websocket dropped. This is extremely useful to differentiate
        # between a network glitch and an outright ComfyUI crash/OOM-kill.
        srv_status = _comfy_server_status()
        if not srv_status["reachable"]:
            # If ComfyUI itself is down there is no point in retrying the websocket –
            # bail out immediately so the caller gets a clear "ComfyUI crashed" error.
            print(
                f"worker-comfyui - ComfyUI HTTP unreachable – aborting websocket reconnect: {srv_status.get('error', 'status '+str(srv_status.get('status_code')))}"
            )
            raise websocket.WebSocketConnectionClosedException(
                "ComfyUI HTTP unreachable during websocket reconnect"
            )

        # Otherwise we proceed with reconnect attempts while server is up
        print(
            f"worker-comfyui - Reconnect attempt {attempt + 1}/{max_attempts}... (ComfyUI HTTP reachable, status {srv_status.get('status_code')})"
        )
        try:
            # Need to create a new socket object for reconnect
            new_ws = websocket.WebSocket()
            new_ws.connect(ws_url, timeout=10)  # Use existing ws_url
            print(f"worker-comfyui - Websocket reconnected successfully.")
            return new_ws  # Return the new connected socket
        except (
            websocket.WebSocketException,
            ConnectionRefusedError,
            socket.timeout,
            OSError,
        ) as reconn_err:
            last_reconnect_error = reconn_err
            print(
                f"worker-comfyui - Reconnect attempt {attempt + 1} failed: {reconn_err}"
            )
            if attempt < max_attempts - 1:
                print(
                    f"worker-comfyui - Waiting {delay_s} seconds before next attempt..."
                )
                time.sleep(delay_s)
            else:
                print(f"worker-comfyui - Max reconnection attempts reached.")

    # If loop completes without returning, raise an exception
    print("worker-comfyui - Failed to reconnect websocket after connection closed.")
    raise websocket.WebSocketConnectionClosedException(
        f"Connection closed and failed to reconnect. Last error: {last_reconnect_error}"
    )


def validate_input(job_input):
    """
    Validates the input for the handler function.

    Args:
        job_input (dict): The input data to validate.

    Returns:
        tuple: A tuple containing the validated data and an error message, if any.
               The structure is (validated_data, error_message).
    """
    # Validate if job_input is provided
    if job_input is None:
        return None, "Please provide input"

    # Check if input is a string and try to parse it as JSON
    if isinstance(job_input, str):
        try:
            job_input = json.loads(job_input)
        except json.JSONDecodeError:
            return None, "Invalid JSON format in input"

    # Validate 'workflow' in input
    workflow = job_input.get("workflow")
    if workflow is None:
        return None, "Missing 'workflow' parameter"

    # Validate 'images' in input, if provided
    images = job_input.get("images")
    if images is not None:
        if not isinstance(images, list) or not all(
            "name" in image and "image" in image for image in images
        ):
            return (
                None,
                "'images' must be a list of objects with 'name' and 'image' keys",
            )

    # Optional: API key for Comfy.org API Nodes, passed per-request
    comfy_org_api_key = job_input.get("comfy_org_api_key")

    # Return validated data and no error
    return {
        "workflow": workflow,
        "images": images,
        "comfy_org_api_key": comfy_org_api_key,
    }, None


def check_server(url, retries=500, delay=50):
    """
    Check if a server is reachable via HTTP GET request

    Args:
    - url (str): The URL to check
    - retries (int, optional): The number of times to attempt connecting to the server. Default is 50
    - delay (int, optional): The time in milliseconds to wait between retries. Default is 500

    Returns:
    bool: True if the server is reachable within the given number of retries, otherwise False
    """

    print(f"worker-comfyui - Checking API server at {url}...")
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)

            # If the response status code is 200, the server is up and running
            if response.status_code == 200:
                print(f"worker-comfyui - API is reachable")
                return True
        except requests.Timeout:
            pass
        except requests.RequestException as e:
            pass

        # Wait for the specified delay before retrying
        time.sleep(delay / 1000)

    print(
        f"worker-comfyui - Failed to connect to server at {url} after {retries} attempts."
    )
    return False


def normalize_workflow_paths(workflow):
    """
    标准化工作流中的路径，将反斜杠转换为正斜杠。
    ComfyUI 运行在 Linux 环境下，需要 Unix 风格的路径分隔符。

    Args:
        workflow (dict): 工作流字典

    Returns:
        dict: 标准化后的工作流字典
    """
    if not isinstance(workflow, dict):
        return workflow

    # 需要标准化的路径字段（包含常见路径相关的字段名）
    path_fields = [
        "ckpt_name", "image", "filename", "path", "file_path", "image_path",
        "clip_name", "lora_name", "model_name", "vae_name", "controlnet_name",
        "upscale_model", "embeddings", "hypernetwork_name"
    ]
    
    # 常见的文件扩展名，用于识别路径字符串
    file_extensions = (".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".bin", 
                       ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm")
    
    def is_likely_path(value):
        """检查字符串是否看起来像一个文件路径"""
        if not isinstance(value, str) or "\\" not in value:
            return False
        # 如果包含反斜杠且包含文件扩展名，很可能是路径
        return any(value.lower().endswith(ext) for ext in file_extensions)
    
    for node_id, node_data in workflow.items():
        if not isinstance(node_data, dict):
            continue
            
        # 处理节点的 inputs 字段
        if "inputs" in node_data and isinstance(node_data["inputs"], dict):
            for key, value in node_data["inputs"].items():
                # 如果值是字符串且包含反斜杠
                if isinstance(value, str) and "\\" in value:
                    # 检查是否是路径字段（字段名匹配或在字段名中包含路径关键字）或看起来像路径
                    is_path_field = key in path_fields or any(field in key.lower() for field in path_fields)
                    is_likely_file_path = is_likely_path(value)
                    
                    if is_path_field or is_likely_file_path:
                        normalized = value.replace("\\", "/")
                        node_data["inputs"][key] = normalized
                        print(f"worker-comfyui - Normalized path in node {node_id}, field '{key}': {value} -> {normalized}")
    
    return workflow


def convert_url_to_base64(image_url, timeout=30):
    """
    从 URL 下载图片并编码为 base64 字符串。

    Args:
        image_url (str): 图片的 URL 地址
        timeout (int): 下载超时时间（秒）

    Returns:
        str: base64 编码的图片字符串，如果失败则返回 None
    """
    try:
        print(f"worker-comfyui - Downloading image from URL: {image_url}")
        response = requests.get(image_url, timeout=timeout, stream=True)
        response.raise_for_status()
        image_bytes = response.content
        base64_encoded = base64.b64encode(image_bytes).decode('utf-8')
        print(f"worker-comfyui - Successfully downloaded and encoded image from URL")
        return base64_encoded
    except requests.RequestException as e:
        print(f"worker-comfyui - Error downloading image from URL {image_url}: {e}")
        return None
    except Exception as e:
        print(f"worker-comfyui - Unexpected error converting URL to base64: {e}")
        return None


def upload_images(images):
    """
    Upload a list of base64 encoded images to the ComfyUI server using the /upload/image endpoint.
    注意: 此函数现在只处理 base64 编码的图片。URL 图片应在调用此函数前先转换为 base64。

    Args:
        images (list): A list of dictionaries, each containing the 'name' of the image and the 'image' as:
            - A base64 encoded string (with optional data URI prefix)

    Returns:
        dict: A dictionary indicating success or error.
    """
    if not images:
        return {"status": "success", "message": "No images to upload", "details": []}

    responses = []
    upload_errors = []

    print(f"worker-comfyui - Uploading {len(images)} image(s)...")

    for image in images:
        try:
            name = image["name"]
            image_data_uri = image["image"]  # Get the full string (should be base64 now)

            # Handle base64 encoded data
            # --- Strip Data URI prefix if present ---
            if "," in image_data_uri:
                # Find the comma and take everything after it
                base64_data = image_data_uri.split(",", 1)[1]
            else:
                # Assume it's already pure base64
                base64_data = image_data_uri
            # --- End strip ---

            blob = base64.b64decode(base64_data)  # Decode the cleaned data
            content_type = "image/png"  # Default for base64

            # Prepare the form data
            files = {
                "image": (name, BytesIO(blob), content_type),
                "overwrite": (None, "true"),
            }

            # POST request to upload the image
            response = requests.post(
                f"http://{COMFY_HOST}/upload/image", files=files, timeout=30
            )
            response.raise_for_status()

            responses.append(f"Successfully uploaded {name}")
            print(f"worker-comfyui - Successfully uploaded {name}")

        except base64.binascii.Error as e:
            error_msg = f"Error decoding base64 for {image.get('name', 'unknown')}: {e}"
            print(f"worker-comfyui - {error_msg}")
            upload_errors.append(error_msg)
        except requests.Timeout:
            error_msg = f"Timeout uploading {image.get('name', 'unknown')}"
            print(f"worker-comfyui - {error_msg}")
            upload_errors.append(error_msg)
        except requests.RequestException as e:
            error_msg = f"Error uploading {image.get('name', 'unknown')}: {e}"
            print(f"worker-comfyui - {error_msg}")
            upload_errors.append(error_msg)
        except Exception as e:
            error_msg = (
                f"Unexpected error uploading {image.get('name', 'unknown')}: {e}"
            )
            print(f"worker-comfyui - {error_msg}")
            upload_errors.append(error_msg)

    if upload_errors:
        print(f"worker-comfyui - image(s) upload finished with errors")
        return {
            "status": "error",
            "message": "Some images failed to upload",
            "details": upload_errors,
        }

    print(f"worker-comfyui - image(s) upload complete")
    return {
        "status": "success",
        "message": "All images uploaded successfully",
        "details": responses,
    }


def get_available_models():
    """
    Get list of available models from ComfyUI

    Returns:
        dict: Dictionary containing available models by type
    """
    try:
        response = requests.get(f"http://{COMFY_HOST}/object_info", timeout=10)
        response.raise_for_status()
        object_info = response.json()

        # Extract available checkpoints from CheckpointLoaderSimple
        available_models = {}
        if "CheckpointLoaderSimple" in object_info:
            checkpoint_info = object_info["CheckpointLoaderSimple"]
            if "input" in checkpoint_info and "required" in checkpoint_info["input"]:
                ckpt_options = checkpoint_info["input"]["required"].get("ckpt_name")
                if ckpt_options and len(ckpt_options) > 0:
                    available_models["checkpoints"] = (
                        ckpt_options[0] if isinstance(ckpt_options[0], list) else []
                    )

        return available_models
    except Exception as e:
        print(f"worker-comfyui - Warning: Could not fetch available models: {e}")
        return {}


def queue_workflow(workflow, client_id, comfy_org_api_key=None):
    """
    Queue a workflow to be processed by ComfyUI

    Args:
        workflow (dict): A dictionary containing the workflow to be processed
        client_id (str): The client ID for the websocket connection
        comfy_org_api_key (str, optional): Comfy.org API key for API Nodes

    Returns:
        dict: The JSON response from ComfyUI after processing the workflow

    Raises:
        ValueError: If the workflow validation fails with detailed error information
    """
    # Include client_id in the prompt payload
    payload = {"prompt": workflow, "client_id": client_id}

    # Optionally inject Comfy.org API key for API Nodes.
    # Precedence: per-request key (argument) overrides environment variable.
    # Note: We use our consistent naming (comfy_org_api_key) but transform to
    # ComfyUI's expected format (api_key_comfy_org) when sending.
    key_from_env = os.environ.get("COMFY_ORG_API_KEY")
    effective_key = comfy_org_api_key if comfy_org_api_key else key_from_env
    if effective_key:
        payload["extra_data"] = {"api_key_comfy_org": effective_key}
    data = json.dumps(payload).encode("utf-8")

    # Use requests for consistency and timeout
    headers = {"Content-Type": "application/json"}
    response = requests.post(
        f"http://{COMFY_HOST}/prompt", data=data, headers=headers, timeout=30
    )

    # Handle validation errors with detailed information
    if response.status_code == 400:
        print(f"worker-comfyui - ComfyUI returned 400. Response body: {response.text}")
        try:
            error_data = response.json()
            print(f"worker-comfyui - Parsed error data: {error_data}")

            # Try to extract meaningful error information
            error_message = "Workflow validation failed"
            error_details = []

            # ComfyUI seems to return different error formats, let's handle them all
            if "error" in error_data:
                error_info = error_data["error"]
                if isinstance(error_info, dict):
                    error_message = error_info.get("message", error_message)
                    if error_info.get("type") == "prompt_outputs_failed_validation":
                        error_message = "Workflow validation failed"
                else:
                    error_message = str(error_info)

            # Check for node validation errors in the response
            if "node_errors" in error_data:
                for node_id, node_error in error_data["node_errors"].items():
                    if isinstance(node_error, dict):
                        for error_type, error_msg in node_error.items():
                            error_details.append(
                                f"Node {node_id} ({error_type}): {error_msg}"
                            )
                    else:
                        error_details.append(f"Node {node_id}: {node_error}")

            # Check if the error data itself contains validation info
            if error_data.get("type") == "prompt_outputs_failed_validation":
                error_message = error_data.get("message", "Workflow validation failed")
                # For this type of error, we need to parse the validation details from logs
                # Since ComfyUI doesn't seem to include detailed validation errors in the response
                # Let's provide a more helpful generic message
                available_models = get_available_models()
                if available_models.get("checkpoints"):
                    error_message += f"\n\nThis usually means a required model or parameter is not available."
                    error_message += f"\nAvailable checkpoint models: {', '.join(available_models['checkpoints'])}"
                else:
                    error_message += "\n\nThis usually means a required model or parameter is not available."
                    error_message += "\nNo checkpoint models appear to be available. Please check your model installation."

                raise ValueError(error_message)

            # If we have specific validation errors, format them nicely
            if error_details:
                detailed_message = f"{error_message}:\n" + "\n".join(
                    f"• {detail}" for detail in error_details
                )

                # Try to provide helpful suggestions for common errors
                if any(
                    "not in list" in detail and "ckpt_name" in detail
                    for detail in error_details
                ):
                    available_models = get_available_models()
                    if available_models.get("checkpoints"):
                        detailed_message += f"\n\nAvailable checkpoint models: {', '.join(available_models['checkpoints'])}"
                    else:
                        detailed_message += "\n\nNo checkpoint models appear to be available. Please check your model installation."

                raise ValueError(detailed_message)
            else:
                # Fallback to the raw response if we can't parse specific errors
                raise ValueError(f"{error_message}. Raw response: {response.text}")

        except (json.JSONDecodeError, KeyError) as e:
            # If we can't parse the error response, fall back to the raw text
            raise ValueError(
                f"ComfyUI validation failed (could not parse error response): {response.text}"
            )

    # For other HTTP errors, raise them normally
    response.raise_for_status()
    return response.json()


def get_history(prompt_id):
    """
    Retrieve the history of a given prompt using its ID

    Args:
        prompt_id (str): The ID of the prompt whose history is to be retrieved

    Returns:
        dict: The history of the prompt, containing all the processing steps and results
    """
    # Use requests for consistency and timeout
    response = requests.get(f"http://{COMFY_HOST}/history/{prompt_id}", timeout=30)
    response.raise_for_status()
    return response.json()


def get_image_data(filename, subfolder, image_type):
    """
    Fetch image bytes from the ComfyUI /view endpoint.

    Args:
        filename (str): The filename of the image.
        subfolder (str): The subfolder where the image is stored.
        image_type (str): The type of the image (e.g., 'output').

    Returns:
        bytes: The raw image data, or None if an error occurs.
    """
    print(
        f"worker-comfyui - Fetching image data: type={image_type}, subfolder={subfolder}, filename={filename}"
    )
    data = {"filename": filename, "subfolder": subfolder, "type": image_type}
    url_values = urllib.parse.urlencode(data)
    try:
        # Use requests for consistency and timeout
        response = requests.get(f"http://{COMFY_HOST}/view?{url_values}", timeout=60)
        response.raise_for_status()
        print(f"worker-comfyui - Successfully fetched image data for {filename}")
        return response.content
    except requests.Timeout:
        print(f"worker-comfyui - Timeout fetching image data for {filename}")
        return None
    except requests.RequestException as e:
        print(f"worker-comfyui - Error fetching image data for {filename}: {e}")
        return None
    except Exception as e:
        print(
            f"worker-comfyui - Unexpected error fetching image data for {filename}: {e}"
        )
        return None


def get_video_data(filename, subfolder, image_type):
    """
    Fetch video bytes from the ComfyUI /view endpoint.
    This function uses the same endpoint as get_image_data since ComfyUI's /view endpoint
    can handle both images and videos.

    Args:
        filename (str): The filename of the video.
        subfolder (str): The subfolder where the video is stored.
        image_type (str): The type of the file (e.g., 'output').

    Returns:
        bytes: The raw video data, or None if an error occurs.
    """
    print(
        f"worker-comfyui - Fetching video data: type={image_type}, subfolder={subfolder}, filename={filename}"
    )
    # Use the same endpoint as images - ComfyUI's /view endpoint handles both
    return get_image_data(filename, subfolder, image_type)


def is_video_file(filename):
    """
    Check if a filename represents a video file based on its extension.

    Args:
        filename (str): The filename to check.

    Returns:
        bool: True if the file is a video, False otherwise.
    """
    video_extensions = ('.mp4', '.webm', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v')
    return filename.lower().endswith(video_extensions)


def handler(job):
    """
    Handles a job using ComfyUI via websockets for status and media file retrieval.
    Supports both image and video outputs from ComfyUI workflows.

    Args:
        job (dict): A dictionary containing job details and input parameters.

    Returns:
        dict: A dictionary containing either an error message or a success status with generated images/videos.
        The output structure includes:
        - "images": Array of media files (images or videos) with filename, type (base64 or s3_url), and data
        - "status": "success_no_images" if workflow completed but produced no output
        - "errors": Array of error messages if any occurred
    """
    job_input = job["input"]
    job_id = job["id"]

    # Make sure that the input is valid
    validated_data, error_message = validate_input(job_input)
    if error_message:
        return {"error": error_message}

    # Extract validated data
    workflow = validated_data["workflow"]
    input_images = validated_data.get("images")

    # 标准化工作流中的路径（将 Windows 风格的路径转换为 Unix 风格）
    workflow = normalize_workflow_paths(workflow)

    # Make sure that the ComfyUI HTTP API is available before proceeding
    if not check_server(
        f"http://{COMFY_HOST}/",
        COMFY_API_AVAILABLE_MAX_RETRIES,
        COMFY_API_AVAILABLE_INTERVAL_MS,
    ):
        return {
            "error": f"ComfyUI server ({COMFY_HOST}) not reachable after multiple retries."
        }

    # 如果输入图片中包含 URL，先下载并转换为 base64
    if input_images:
        for image in input_images:
            image_data = image.get("image", "")
            # 检查是否是 URL
            if isinstance(image_data, str) and (image_data.startswith("http://") or image_data.startswith("https://")):
                print(f"worker-comfyui - Detected URL input for image '{image.get('name')}', converting to base64...")
                base64_image = convert_url_to_base64(image_data)
                if base64_image is None:
                    return {
                        "error": f"Failed to download and convert image from URL: {image_data}",
                    }
                # 将 URL 替换为 base64 编码
                image["image"] = base64_image
                print(f"worker-comfyui - Successfully converted URL to base64 for image '{image.get('name')}'")
            # 如果已经是 base64，保持不变，正常处理

    # Upload input images if they exist
    if input_images:
        upload_result = upload_images(input_images)
        if upload_result["status"] == "error":
            # Return upload errors
            return {
                "error": "Failed to upload one or more input images",
                "details": upload_result["details"],
            }

    ws = None
    client_id = str(uuid.uuid4())
    prompt_id = None
    output_data = []
    errors = []

    try:
        # Establish WebSocket connection
        ws_url = f"ws://{COMFY_HOST}/ws?clientId={client_id}"
        print(f"worker-comfyui - Connecting to websocket: {ws_url}")
        ws = websocket.WebSocket()
        ws.connect(ws_url, timeout=10)
        print(f"worker-comfyui - Websocket connected")

        # Queue the workflow
        try:
            # Pass per-request API key if provided in input
            queued_workflow = queue_workflow(
                workflow,
                client_id,
                comfy_org_api_key=validated_data.get("comfy_org_api_key"),
            )
            prompt_id = queued_workflow.get("prompt_id")
            if not prompt_id:
                raise ValueError(
                    f"Missing 'prompt_id' in queue response: {queued_workflow}"
                )
            print(f"worker-comfyui - Queued workflow with ID: {prompt_id}")
        except requests.RequestException as e:
            print(f"worker-comfyui - Error queuing workflow: {e}")
            raise ValueError(f"Error queuing workflow: {e}")
        except Exception as e:
            print(f"worker-comfyui - Unexpected error queuing workflow: {e}")
            # For ValueError exceptions from queue_workflow, pass through the original message
            if isinstance(e, ValueError):
                raise e
            else:
                raise ValueError(f"Unexpected error queuing workflow: {e}")

        # Wait for execution completion via WebSocket
        print(f"worker-comfyui - Waiting for workflow execution ({prompt_id})...")
        execution_done = False
        while True:
            try:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message.get("type") == "status":
                        status_data = message.get("data", {}).get("status", {})
                        print(
                            f"worker-comfyui - Status update: {status_data.get('exec_info', {}).get('queue_remaining', 'N/A')} items remaining in queue"
                        )
                    elif message.get("type") == "executing":
                        data = message.get("data", {})
                        if (
                            data.get("node") is None
                            and data.get("prompt_id") == prompt_id
                        ):
                            print(
                                f"worker-comfyui - Execution finished for prompt {prompt_id}"
                            )
                            execution_done = True
                            break
                    elif message.get("type") == "execution_error":
                        data = message.get("data", {})
                        if data.get("prompt_id") == prompt_id:
                            error_details = f"Node Type: {data.get('node_type')}, Node ID: {data.get('node_id')}, Message: {data.get('exception_message')}"
                            print(
                                f"worker-comfyui - Execution error received: {error_details}"
                            )
                            errors.append(f"Workflow execution error: {error_details}")
                            break
                else:
                    continue
            except websocket.WebSocketTimeoutException:
                print(f"worker-comfyui - Websocket receive timed out. Still waiting...")
                continue
            except websocket.WebSocketConnectionClosedException as closed_err:
                try:
                    # Attempt to reconnect
                    ws = _attempt_websocket_reconnect(
                        ws_url,
                        WEBSOCKET_RECONNECT_ATTEMPTS,
                        WEBSOCKET_RECONNECT_DELAY_S,
                        closed_err,
                    )

                    print(
                        "worker-comfyui - Resuming message listening after successful reconnect."
                    )
                    continue
                except (
                    websocket.WebSocketConnectionClosedException
                ) as reconn_failed_err:
                    # If _attempt_websocket_reconnect fails, it raises this exception
                    # Let this exception propagate to the outer handler's except block
                    raise reconn_failed_err

            except json.JSONDecodeError:
                print(f"worker-comfyui - Received invalid JSON message via websocket.")

        if not execution_done and not errors:
            raise ValueError(
                "Workflow monitoring loop exited without confirmation of completion or error."
            )

        # Fetch history even if there were execution errors, some outputs might exist
        print(f"worker-comfyui - Fetching history for prompt {prompt_id}...")
        history = get_history(prompt_id)

        if prompt_id not in history:
            error_msg = f"Prompt ID {prompt_id} not found in history after execution."
            print(f"worker-comfyui - {error_msg}")
            if not errors:
                return {"error": error_msg}
            else:
                errors.append(error_msg)
                return {
                    "error": "Job processing failed, prompt ID not found in history.",
                    "details": errors,
                }

        prompt_history = history.get(prompt_id, {})
        outputs = prompt_history.get("outputs", {})

        if not outputs:
            warning_msg = f"No outputs found in history for prompt {prompt_id}."
            print(f"worker-comfyui - {warning_msg}")
            if not errors:
                errors.append(warning_msg)

        print(f"worker-comfyui - Processing {len(outputs)} output nodes...")
        for node_id, node_output in outputs.items():
            # Process "images", "gifs", and "animated" outputs (all are media files)
            media_files = []
            if "images" in node_output:
                media_files.extend(node_output["images"])
            if "gifs" in node_output:
                media_files.extend(node_output["gifs"])
            if "animated" in node_output:
                media_files.extend(node_output["animated"])
            
            if media_files:
                print(
                    f"worker-comfyui - Node {node_id} contains {len(media_files)} media file(s)"
                )
                for image_info in media_files:
                    # Skip non-dict items (e.g., bool values that might be in the list)
                    if not isinstance(image_info, dict):
                        warn_msg = f"Skipping non-dict media file in node {node_id}: {type(image_info).__name__} = {image_info}"
                        print(f"worker-comfyui - {warn_msg}")
                        errors.append(warn_msg)
                        continue
                    
                    filename = image_info.get("filename")
                    subfolder = image_info.get("subfolder", "")
                    img_type = image_info.get("type")

                    # skip temp files
                    if img_type == "temp":
                        print(
                            f"worker-comfyui - Skipping {filename} because type is 'temp'"
                        )
                        continue

                    if not filename:
                        warn_msg = f"Skipping media file in node {node_id} due to missing filename: {image_info}"
                        print(f"worker-comfyui - {warn_msg}")
                        errors.append(warn_msg)
                        continue

                    # Check if this is a video file
                    is_video = is_video_file(filename)
                    media_type = "video" if is_video else "image"
                    
                    # Fetch the file data (works for both images and videos)
                    file_bytes = get_video_data(filename, subfolder, img_type) if is_video else get_image_data(filename, subfolder, img_type)

                    if file_bytes:
                        file_extension = os.path.splitext(filename)[1] or (".mp4" if is_video else ".png")

                        if os.environ.get("BUCKET_ENDPOINT_URL"):
                            try:
                                with tempfile.NamedTemporaryFile(
                                    suffix=file_extension, delete=False
                                ) as temp_file:
                                    temp_file.write(file_bytes)
                                    temp_file_path = temp_file.name
                                print(
                                    f"worker-comfyui - Wrote {media_type} bytes to temporary file: {temp_file_path}"
                                )

                                print(f"worker-comfyui - Uploading {filename} to S3...")
                                # Use upload_image to upload the file
                                # Note: RunPod S3-compatible API does NOT support presigned URLs
                                # The returned URL is the S3 path that requires S3 API Key authentication
                                uploaded_url = rp_upload.upload_image(job_id, temp_file_path)
                                os.remove(temp_file_path)  # Clean up temp file
                                print(
                                    f"worker-comfyui - Uploaded {filename} to S3: {uploaded_url}"
                                )
                                
                                # Remove query parameters from URL for cleaner output
                                # Query parameters are not needed since RunPod S3 doesn't support presigned URLs
                                if "?" in uploaded_url:
                                    s3_url = uploaded_url.split("?")[0]
                                    print(
                                        f"worker-comfyui - Removed query parameters from URL for cleaner output"
                                    )
                                else:
                                    s3_url = uploaded_url
                                
                                print(
                                    f"worker-comfyui - Note: Access this file using S3 API Key credentials"
                                )
                                
                                # Append dictionary with filename and URL
                                output_data.append(
                                    {
                                        "filename": filename,
                                        "type": "s3_url",
                                        "data": s3_url,
                                    }
                                )
                            except Exception as e:
                                error_msg = f"Error uploading {filename} to S3: {e}"
                                print(f"worker-comfyui - {error_msg}")
                                errors.append(error_msg)
                                if "temp_file_path" in locals() and os.path.exists(
                                    temp_file_path
                                ):
                                    try:
                                        os.remove(temp_file_path)
                                    except OSError as rm_err:
                                        print(
                                            f"worker-comfyui - Error removing temp file {temp_file_path}: {rm_err}"
                                        )
                        else:
                            # Return as base64 string
                            try:
                                # Check file size before encoding (videos can be very large)
                                file_size_mb = len(file_bytes) / (1024 * 1024)
                                max_size_mb = 100  # 100MB limit for base64 encoding
                                
                                if is_video and file_size_mb > max_size_mb:
                                    error_msg = (
                                        f"Video file {filename} is too large ({file_size_mb:.2f} MB) "
                                        f"for base64 encoding (max {max_size_mb} MB). "
                                        f"Please configure S3 upload (BUCKET_ENDPOINT_URL) for large files."
                                    )
                                    print(f"worker-comfyui - {error_msg}")
                                    errors.append(error_msg)
                                    continue
                                
                                base64_data = base64.b64encode(file_bytes).decode("utf-8")
                                # For videos, add data URI prefix similar to images
                                if is_video:
                                    # Determine MIME type based on extension
                                    filename_lower = filename.lower()
                                    if filename_lower.endswith('.mp4') or filename_lower.endswith('.m4v'):
                                        mime_type = "video/mp4"
                                    elif filename_lower.endswith('.webm'):
                                        mime_type = "video/webm"
                                    elif filename_lower.endswith('.mov'):
                                        mime_type = "video/quicktime"
                                    elif filename_lower.endswith('.avi'):
                                        mime_type = "video/x-msvideo"
                                    elif filename_lower.endswith('.mkv'):
                                        mime_type = "video/x-matroska"
                                    elif filename_lower.endswith('.flv'):
                                        mime_type = "video/x-flv"
                                    elif filename_lower.endswith('.wmv'):
                                        mime_type = "video/x-ms-wmv"
                                    else:
                                        # Default fallback for unknown video formats
                                        mime_type = "video/mp4"
                                    base64_data = f"data:{mime_type};base64,{base64_data}"
                                
                                # Append dictionary with filename and base64 data
                                output_data.append(
                                    {
                                        "filename": filename,
                                        "type": "base64",
                                        "data": base64_data,
                                    }
                                )
                                print(f"worker-comfyui - Encoded {filename} as base64 ({media_type}, {file_size_mb:.2f} MB)")
                            except MemoryError as e:
                                error_msg = (
                                    f"Out of memory while encoding {filename} to base64. "
                                    f"File size: {len(file_bytes) / (1024 * 1024):.2f} MB. "
                                    f"Please configure S3 upload (BUCKET_ENDPOINT_URL) for large files."
                                )
                                print(f"worker-comfyui - {error_msg}")
                                errors.append(error_msg)
                            except Exception as e:
                                error_msg = f"Error encoding {filename} to base64: {e}"
                                print(f"worker-comfyui - {error_msg}")
                                print(traceback.format_exc())
                                errors.append(error_msg)
                    else:
                        error_msg = f"Failed to fetch {media_type} data for {filename} from /view endpoint."
                        errors.append(error_msg)

            # Check for other output types (excluding images, gifs, and animated which we handle)
            other_keys = [k for k in node_output.keys() if k not in ["images", "gifs", "animated"]]
            if other_keys:
                warn_msg = (
                    f"Node {node_id} produced unhandled output keys: {other_keys}."
                )
                print(f"worker-comfyui - WARNING: {warn_msg}")
                print(
                    f"worker-comfyui - --> If this output is useful, please consider opening an issue on GitHub to discuss adding support."
                )

    except websocket.WebSocketException as e:
        print(f"worker-comfyui - WebSocket Error: {e}")
        print(traceback.format_exc())
        return {"error": f"WebSocket communication error: {e}"}
    except requests.RequestException as e:
        print(f"worker-comfyui - HTTP Request Error: {e}")
        print(traceback.format_exc())
        return {"error": f"HTTP communication error with ComfyUI: {e}"}
    except ValueError as e:
        print(f"worker-comfyui - Value Error: {e}")
        print(traceback.format_exc())
        return {"error": str(e)}
    except Exception as e:
        print(f"worker-comfyui - Unexpected Handler Error: {e}")
        print(traceback.format_exc())
        return {"error": f"An unexpected error occurred: {e}"}
    finally:
        if ws and ws.connected:
            print(f"worker-comfyui - Closing websocket connection.")
            ws.close()

    final_result = {}

    if output_data:
        final_result["images"] = output_data

    if errors:
        final_result["errors"] = errors
        print(f"worker-comfyui - Job completed with errors/warnings: {errors}")

    if not output_data and errors:
        print(f"worker-comfyui - Job failed with no output media files.")
        return {
            "error": "Job processing failed",
            "details": errors,
        }
    elif not output_data and not errors:
        print(
            f"worker-comfyui - Job completed successfully, but the workflow produced no media files."
        )
        final_result["status"] = "success_no_images"
        final_result["images"] = []

    # Count images and videos separately for logging
    image_count = sum(1 for item in output_data if not is_video_file(item.get("filename", "")))
    video_count = sum(1 for item in output_data if is_video_file(item.get("filename", "")))
    
    if video_count > 0:
        print(f"worker-comfyui - Job completed. Returning {len(output_data)} media file(s): {image_count} image(s), {video_count} video(s).")
    else:
        print(f"worker-comfyui - Job completed. Returning {len(output_data)} image(s).")
    
    return final_result


if __name__ == "__main__":
    print("worker-comfyui - Starting handler...")
    runpod.serverless.start({"handler": handler})
