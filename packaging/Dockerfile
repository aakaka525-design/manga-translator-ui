# Manga Translator Docker Image
# 支持 CPU 和 GPU 版本

ARG CUDA_VERSION=12.8.0
ARG PYTHON_VERSION=3.12
ARG BUILD_TYPE=cpu

# ===== CPU 版本 =====
FROM python:${PYTHON_VERSION}-slim AS base-cpu

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    wget \
    curl \
    build-essential \
    g++ \
    libeigen3-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ===== GPU 版本 =====
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-runtime-ubuntu22.04 AS base-gpu

# 设置非交互式安装
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

# 安装 Python 3.12
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    git \
    wget \
    curl \
    build-essential \
    g++ \
    libeigen3-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 设置 Python 3.12 为默认
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# 升级 pip
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

# ===== 选择基础镜像 =====
FROM base-${BUILD_TYPE} AS base
ARG PYTHON_VERSION=3.12

# 设置工作目录
WORKDIR /app

# 优先使用 pip 安装的 CUDA/cuDNN 12.8 运行库，避免与基础镜像内库版本混用
ENV LD_LIBRARY_PATH=/usr/local/lib/python${PYTHON_VERSION}/dist-packages/nvidia/cudnn/lib:/usr/local/lib/python${PYTHON_VERSION}/dist-packages/nvidia/cublas/lib:/usr/local/lib/python${PYTHON_VERSION}/dist-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python${PYTHON_VERSION}/dist-packages/nvidia/cufft/lib:/usr/local/lib/python${PYTHON_VERSION}/dist-packages/nvidia/curand/lib:/usr/local/lib/python${PYTHON_VERSION}/dist-packages/nvidia/cusolver/lib:/usr/local/lib/python${PYTHON_VERSION}/dist-packages/nvidia/cusparse/lib:/usr/local/lib/python${PYTHON_VERSION}/dist-packages/nvidia/nccl/lib:/usr/local/lib/python${PYTHON_VERSION}/dist-packages/nvidia/nvjitlink/lib:${LD_LIBRARY_PATH}

# 复制项目文件
COPY . /app/

# 安装 Python 依赖
ARG BUILD_TYPE=cpu
RUN if [ "$BUILD_TYPE" = "gpu" ]; then \
    # GPU 版本：从源码编译 pydensecrf
    echo "Building pydensecrf from source for GPU" && \
    pip install --no-cache-dir setuptools wheel && \
    pip install --no-cache-dir Cython numpy && \
    pip install --no-cache-dir --verbose git+https://github.com/lucasb-eyer/pydensecrf.git && \
    grep -v "^pydensecrf" requirements_gpu.txt > /tmp/requirements_gpu_no_pydensecrf.txt && \
    pip install --no-cache-dir -r /tmp/requirements_gpu_no_pydensecrf.txt && \
    ldconfig -p | grep -q "libcudnn_adv.so.9" && \
    python -c "import subprocess, onnxruntime as ort; from pathlib import Path; providers=[str(p) for p in ort.get_available_providers()]; print('onnxruntime providers:', providers); assert 'CUDAExecutionProvider' in providers, 'CUDAExecutionProvider missing; refusing to build GPU image'; lib=Path(ort.__file__).resolve().parent/'capi'/'libonnxruntime_providers_cuda.so'; assert lib.exists(), f'missing CUDA provider library: {lib}'; proc=subprocess.run(['ldd','-r',str(lib)], capture_output=True, text=True, check=False); print(proc.stdout); print(proc.stderr); assert proc.returncode == 0, f'ldd -r failed: {proc.returncode}'; merged=((proc.stdout or '') + '\\n' + (proc.stderr or '')); unresolved=[line.strip() for line in merged.splitlines() if ('not found' in line.lower()) or ('undefined symbol' in line.lower() and 'provider_gethost' not in line.lower())]; assert not unresolved, 'ldd -r detected unresolved CUDA dependencies: ' + '; '.join(unresolved); print('onnxruntime cuda provider ldd check passed:', lib)"; \
    else \
    # CPU 版本：从源码编译 pydensecrf
    echo "Building pydensecrf from source for CPU" && \
    pip install --no-cache-dir setuptools wheel && \
    pip install --no-cache-dir Cython numpy && \
    pip install --no-cache-dir --verbose git+https://github.com/lucasb-eyer/pydensecrf.git && \
    grep -v "^pydensecrf" requirements_cpu.txt > /tmp/requirements_cpu_no_pydensecrf.txt && \
    pip install --no-cache-dir -r /tmp/requirements_cpu_no_pydensecrf.txt; \
    fi

# 爬虫依赖在某些 requirements 变体中可能缺失，镜像内强制补齐
RUN pip install --no-cache-dir beautifulsoup4

# 创建必要的目录（不覆盖已存在的目录）
RUN mkdir -p /app/result /app/models /app/logs

# PPIO 两阶段启动脚本
COPY packaging/ppio_entrypoint.sh /app/ppio_entrypoint.sh
RUN chmod +x /app/ppio_entrypoint.sh && apt-get update && apt-get install -y curl socat && rm -rf /var/lib/apt/lists/*

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV MANGA_TRANSLATOR_WEB_SERVER=true
ENV MANGA_CLOUDRUN_COMPUTE_ONLY=0
ENV GEMINI_MODEL=gemini-3-flash-preview
ENV GEMINI_FALLBACK_MODEL=gemini-2.5-flash

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# 启动命令
# PPIO_MODE=1: 使用两阶段启动（先通过健康检查，再加载模型）
# MANGA_CLOUDRUN_COMPUTE_ONLY=1: 使用 compute-only 入口（直接 uvicorn）
# 默认: 启动完整 web 服务
CMD ["/bin/sh", "-c", "if [ \"${PPIO_MODE:-0}\" = \"1\" ]; then exec /app/ppio_entrypoint.sh; elif [ \"${MANGA_CLOUDRUN_COMPUTE_ONLY:-0}\" = \"1\" ]; then exec uvicorn manga_translator.server.cloudrun_compute_main:app --host 0.0.0.0 --port ${PORT:-8000}; else exec python -m manga_translator web --host 0.0.0.0 --port ${PORT:-8000}; fi"]
