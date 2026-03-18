#!/usr/bin/env bash

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"

# Disable numba verbose debug output (SSA block analysis, etc.)
# This prevents excessive logging that can cause performance issues
export NUMBA_DEBUG=0
export NUMBA_DISABLE_ERROR_MESSAGE_HIGHLIGHTING=1
export NUMBA_DISABLE_JIT=0  # Keep JIT enabled but disable verbose output
export NUMBA_LOG_LEVEL=ERROR  # Set numba logging to ERROR level only
# Redirect numba's internal logging to reduce noise
export PYTHONWARNINGS="ignore::numba.NumbaWarning,ignore::numba.NumbaError"
# Suppress numba's internal print statements (these bypass logging)
export NUMBA_CAPTURED_ERRORS=1
# Disable numba's type inference errors and warnings
export NUMBA_DISABLE_TBB=1
# Suppress numba compilation messages
export NUMBA_DISABLE_JIT_WARNINGS=1
# Disable numba's verbose type checking and SSA analysis output
export NUMBA_DISABLE_PERFORMANCE_WARNINGS=1
# Disable numba's internal debug prints (SSA block analysis, dispatch pc, etc.)
export NUMBA_DEBUG_TYPEINFER=0
export NUMBA_DEBUG_JIT=0
export NUMBA_DEBUG_FRONTEND=0
export NUMBA_DEBUG_BACKEND=0
# Suppress all numba print statements by redirecting to /dev/null if needed
# Note: This is handled in Python code via logging configuration

# Detect the effective models root.
# Supports:
# - explicit override via RUNPOD_MODELS_PATH / MODELS_VOLUME_PATH
# - current standard locations
# - customer-preloaded models under /workspace
# - shallow auto-discovery for pre-populated customer volumes/workspaces
detect_volume_models_path() {
    local override_path=""
    local candidate=""
    local search_root=""

    override_path="${RUNPOD_MODELS_PATH:-${MODELS_VOLUME_PATH:-}}"
    if [ -n "$override_path" ]; then
        if [ -d "$override_path" ]; then
            echo "$override_path"
            return 0
        fi
        echo "worker-comfyui: WARNING: override models path does not exist: $override_path" >&2
    fi

    for candidate in \
        "/runpod-volume/storage/models" \
        "/runpod-volume/models" \
        "/runpod-volume/storage/ComfyUI/models" \
        "/runpod-volume/ComfyUI/models" \
        "/workspace/runpod-slim/ComfyUI/models" \
        "/workspace/ComfyUI/models" \
        "/workspace/models"
    do
        if [ -d "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done

    for search_root in /runpod-volume /workspace; do
        if [ ! -d "$search_root" ]; then
            continue
        fi

        candidate="$(find "$search_root" -maxdepth 5 -type d \( -name models -o -name Models \) \
            \( -exec test -d '{}/checkpoints' ';' -o -exec test -d '{}/loras' ';' -o -exec test -d '{}/unet' ';' \) \
            | head -n 1)"
        if [ -n "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}

VOLUME_MODELS_PATH="$(detect_volume_models_path || true)"

# Set Hugging Face cache directory for BLIP and other transformers models
# Priority: detected Network Volume models root > image default path
# transformers library stores models in cache_dir/models--Salesforce--blip-vqa-base/ structure
if [ -n "$VOLUME_MODELS_PATH" ] && [ -d "${VOLUME_MODELS_PATH}/blip" ]; then
    export HF_HUB_CACHE="${VOLUME_MODELS_PATH}/blip"
    export TRANSFORMERS_CACHE="${VOLUME_MODELS_PATH}/blip"
    export HF_HOME="${VOLUME_MODELS_PATH}/blip"
    export HUGGINGFACE_HUB_CACHE="${VOLUME_MODELS_PATH}/blip"
    echo "worker-comfyui: Using Network Volume for BLIP models: ${VOLUME_MODELS_PATH}/blip"
elif [ -d "/comfyui/models/blip" ]; then
    export HF_HUB_CACHE="/comfyui/models/blip"
    export TRANSFORMERS_CACHE="/comfyui/models/blip"
    export HF_HOME="/comfyui/models/blip"
    export HUGGINGFACE_HUB_CACHE="/comfyui/models/blip"
    echo "worker-comfyui: Using image default path for BLIP models: /comfyui/models/blip"
fi

# Ensure ComfyUI-Manager runs in offline network mode inside the container
comfy-manager-set-mode offline || echo "worker-comfyui - Could not set ComfyUI-Manager network_mode" >&2

# Create symlinks from Network Volume to ComfyUI default paths
# This replaces extra_model_paths.yaml with a more transparent approach
# All nodes (including those with hardcoded paths) can find models in Network Volume
# Using symlinks ensures compatibility with all ComfyUI nodes and custom nodes
#
# IMPORTANT: Network Volume mount points differ between environments:
# - Temporary Pod: Network Volume mounts at /workspace
# - Endpoint: Network Volume mounts at /runpod-volume
# This script runs in Endpoint, so it checks /runpod-volume
# Models downloaded in Temporary Pod to /workspace/models/ will be accessible
# at /runpod-volume/models/ in Endpoint (same Volume, different mount point)

# Debug: Check if Network Volume is mounted
echo "worker-comfyui: Checking Network Volume mount..."
if [ -d "/runpod-volume" ]; then
    echo "worker-comfyui: /runpod-volume exists"
    
    if [ -n "$VOLUME_MODELS_PATH" ]; then
        echo "worker-comfyui: Detected models directory: ${VOLUME_MODELS_PATH}"
    else
        echo "worker-comfyui: WARNING: Could not detect a usable models directory under /runpod-volume"
    fi
    
    ls -la /runpod-volume/ | head -5 || echo "worker-comfyui: Cannot list /runpod-volume"
else
    VOLUME_MODELS_PATH=""
    echo "worker-comfyui: WARNING: /runpod-volume does not exist"
fi

if [ -n "$VOLUME_MODELS_PATH" ]; then
    echo "worker-comfyui: Setting up model directory symlinks from ${VOLUME_MODELS_PATH}"
    
    # Function to create symlink for a model directory
    # Maps: /comfyui/models/{dir} -> {VOLUME_MODELS_PATH}/{dir}
    create_model_symlink() {
        local model_dir="$1"
        local source_path="${VOLUME_MODELS_PATH}/${model_dir}"  # Endpoint mount point
        local target_path="/comfyui/models/${model_dir}"         # ComfyUI default path
        
        # Only create symlink if source exists in Network Volume
        if [ -d "$source_path" ]; then
            # Check if target already exists
            if [ -e "$target_path" ]; then
                # If it's already a symlink pointing to the correct location, skip
                if [ -L "$target_path" ]; then
                    # Check if symlink points to the correct location
                    local current_target=$(readlink "$target_path" 2>/dev/null)
                    if [ "$current_target" = "$source_path" ]; then
                        # Symlink already points to correct location, skip
                        return 0
                    fi
                    # Symlink points to wrong location or is broken, remove it
                    rm -f "$target_path"
                elif [ -d "$target_path" ]; then
                    # Target is a directory (may be non-empty), backup and remove
                    local backup_dir="/comfyui/models/.backup"
                    mkdir -p "$backup_dir"
                    local backup_path="${backup_dir}/${model_dir}.$(date +%s)"
                    mv "$target_path" "$backup_path" 2>/dev/null || {
                        rm -rf "$target_path" 2>/dev/null || return 1
                    }
                else
                    rm -f "$target_path"
                fi
            fi
            
            # Create parent directory and symlink
            mkdir -p "$(dirname "$target_path")"
            ln -sf "$source_path" "$target_path" 2>/dev/null && echo "worker-comfyui: Created symlink ${target_path} -> ${source_path}"
        fi
    }
    
    # Core ComfyUI model directories
    create_model_symlink "checkpoints"
    create_model_symlink "clip"
    create_model_symlink "clip_vision"
    create_model_symlink "configs"
    create_model_symlink "controlnet"
    create_model_symlink "diffusers"
    create_model_symlink "embeddings"
    create_model_symlink "gligen"
    create_model_symlink "hypernetworks"
    create_model_symlink "loras"
    create_model_symlink "style_models"
    create_model_symlink "unet"
    create_model_symlink "upscale_models"
    create_model_symlink "vae"
    create_model_symlink "vae_approx"
    
    # AnimateDiff model directories
    create_model_symlink "animatediff_models"
    create_model_symlink "animatediff_motion_lora"
    
    # IP-Adapter and related
    create_model_symlink "ipadapter"
    create_model_symlink "pulid"
    
    # Face-related models
    create_model_symlink "insightface"
    create_model_symlink "facerestore_models"
    create_model_symlink "facedetection"
    create_model_symlink "facexlib"
    create_model_symlink "instantid"
    
    # ReActor and HyperSwap models
    create_model_symlink "reswapper"
    create_model_symlink "hyperswap"
    
    # Vision and detection models
    create_model_symlink "photomaker"
    create_model_symlink "sams"
    create_model_symlink "mmdets"
    create_model_symlink "ultralytics"
    create_model_symlink "grounding-dino"
    create_model_symlink "depthanything"
    create_model_symlink "florence2"
    create_model_symlink "BiRefNet"
    
    # Video models
    create_model_symlink "CogVideo"
    
    # Special: Link VFI models to the specific node directory if needed
    if [ -d "${VOLUME_MODELS_PATH}/vfi" ]; then
        mkdir -p /comfyui/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife
        ln -sf "${VOLUME_MODELS_PATH}/vfi/rife47.pth" /comfyui/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife/rife47.pth
        echo "worker-comfyui: Special symlink created for RIFE VFI"
    fi
    
    # Audio models
    create_model_symlink "audio_encoders"
    
    # BLIP models (for image captioning)
    create_model_symlink "blip"
    
    # Inpainting models
    create_model_symlink "inpaint"
    
    # Diffusion models (alternative location)
    create_model_symlink "diffusion_models"
    
    # Custom model directories (project-specific)
    create_model_symlink "LLM"
    create_model_symlink "bagel"
    create_model_symlink "Ben"
    create_model_symlink "CatVTON"
    create_model_symlink "Janus-Pro"
    create_model_symlink "Flux-version-LayerDiffuse"
    create_model_symlink "prompt_generator"
    
    echo "worker-comfyui: Model directory symlinks setup complete"
    
    # Verify antelopev2 subdirectory for PuLID_ComfyUI
    if [ -d "/runpod-volume/models/insightface/models/antelopev2" ]; then
        echo "worker-comfyui: Found antelopev2 model in Network Volume"
    elif [ -L "/comfyui/models/insightface" ]; then
        echo "worker-comfyui: WARNING: antelopev2 model not found in Network Volume"
        echo "worker-comfyui: PuLID_ComfyUI will attempt to download it automatically"
    fi
fi

# Remove or backup extra_model_paths.yaml if it exists (we use symlinks instead)
if [ -f "/comfyui/extra_model_paths.yaml" ]; then
    echo "worker-comfyui: Found extra_model_paths.yaml, backing it up (using symlinks instead)"
    mv /comfyui/extra_model_paths.yaml /comfyui/extra_model_paths.yaml.backup 2>/dev/null || true
fi

echo "worker-comfyui: Starting ComfyUI"

# Allow operators to tweak verbosity; default is INFO (changed from DEBUG to reduce log volume)
# Set COMFY_LOG_LEVEL=DEBUG only when troubleshooting
: "${COMFY_LOG_LEVEL:=INFO}"

# Serve the API and don't shutdown the container
if [ "$SERVE_API_LOCALLY" == "true" ]; then
    echo "worker-comfyui: Starting ComfyUI in background..."
    python -u /comfyui/main.py --disable-auto-launch --disable-metadata --listen --verbose "${COMFY_LOG_LEVEL}" --log-stdout &
    COMFY_PID=$!
    echo "worker-comfyui: ComfyUI started with PID $COMFY_PID"
    
    # Wait a bit for ComfyUI to initialize before starting handler
    echo "worker-comfyui: Waiting for ComfyUI to initialize..."
    sleep 5

    echo "worker-comfyui: Starting RunPod Handler"
    python -u /handler.py --rp_serve_api --rp_api_host=0.0.0.0
else
    echo "worker-comfyui: Starting ComfyUI in background..."
    python -u /comfyui/main.py --disable-auto-launch --disable-metadata --verbose "${COMFY_LOG_LEVEL}" --log-stdout &
    COMFY_PID=$!
    echo "worker-comfyui: ComfyUI started with PID $COMFY_PID"
    
    # Wait a bit for ComfyUI to initialize before starting handler
    echo "worker-comfyui: Waiting for ComfyUI to initialize..."
    sleep 5

    echo "worker-comfyui: Starting RunPod Handler"
    python -u /handler.py
fi
