# ============================================
# Flask Demo - Dockerfile
# ============================================
# Dockerfile 是什么？
#   - 构建指令文件，告诉 Docker 如何打包应用成镜像
#   - 类比：食谱（告诉厨师怎么做菜）
#
# 构建镜像：docker build -t flask-demo .
# 运行容器：docker run -p 8003:8003 flask-demo
#
# 多阶段构建的优势：
#   阶段1 (base)         → 几乎不变，缓存命中率高
#   阶段2 (dependencies) → 只有改 requirements.txt 才重新构建
#   阶段3 (production)   → 每次代码修改都重新构建
#   结果：加速后续构建，减小最终镜像体积
#
# 与 FastAPI/Sanic Dockerfile 的区别：
#   - 端口不同：8003 vs 8001/8002
#   - 启动命令不同：gunicorn（WSGI） vs uvicorn/sanic（ASGI）
#   - 其他配置完全相同
# ============================================

# ============================================
# 阶段1：基础镜像（设置通用环境）
# ============================================

# FROM: 指定基础镜像
# python:3.11-slim: Python 3.11 精简版（约 120MB，完整版约 900MB）
# AS base: 给这个阶段命名，后续可以引用
FROM python:3.11-slim AS base

# ENV: 设置环境变量（整个构建过程有效）
ENV PYTHONDONTWRITEBYTECODE=1 \
    # 不生成 .pyc 字节码文件（减小镜像体积）
    PYTHONUNBUFFERED=1 \
    # Python 输出不缓冲（日志实时可见，方便调试）
    PIP_NO_CACHE_DIR=1 \
    # pip 安装不缓存（减小镜像体积）
    PIP_DISABLE_PIP_VERSION_CHECK=1
    # 不检查 pip 版本更新（加速安装）

# WORKDIR: 设置工作目录
# 后续所有命令（COPY、RUN、CMD）都在这个目录下执行
# 如果目录不存在会自动创建
WORKDIR /app

# ============================================
# 阶段2：安装依赖（独立阶段，利用缓存）
# ============================================

# 基于 base 阶段继续构建
FROM base AS dependencies

# COPY: 复制文件到镜像
# 只复制 requirements.txt，不复制整个项目
# 原因: 依赖不常变，代码经常变，分开复制可以充分利用 Docker 层缓存
COPY requirements.txt .

# RUN: 在构建时执行命令
# --no-cache-dir: 不缓存下载的包（减小镜像体积）
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# 阶段3：生产环境（最终镜像）
# ============================================

# 基于 dependencies 阶段继续构建（已包含 Python + 依赖）
FROM dependencies AS production

# 复制整个项目代码到镜像的 /app 目录
# . 表示当前目录（构建上下文）
# 注意: .dockerignore 中指定的文件不会被复制
COPY . .

# ============================================
# 安全配置：创建非 root 用户
# ============================================

# 为什么不用 root？
#   - 安全: 容器被攻破后，攻击者只有普通用户权限
#   - 最佳实践: 生产环境禁止 root 运行
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# USER: 切换到非 root 用户（后续命令和运行时都用这个用户）
USER appuser

# ============================================
# 网络配置
# ============================================

# EXPOSE: 声明容器监听的端口
# 注意: 这只是文档说明，实际端口映射靠 docker run -p
EXPOSE 8003

# ============================================
# 健康检查配置
# ============================================

# HEALTHCHECK: 定义容器健康检查
# Docker 会定期执行检查命令，判断容器是否健康
# 参数说明:
#   --interval=30s     每 30 秒检查一次
#   --timeout=10s      单次检查超时 10 秒算失败
#   --start-period=5s  容器启动后 5 秒开始检查（给应用启动时间）
#   --retries=3        连续失败 3 次标记为 unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/api/health')"

# ============================================
# 启动命令
# ============================================

# CMD: 容器启动时执行的命令
# 与 FastAPI/Sanic 的核心区别：
#   Flask 是 WSGI 框架 → 需要 Gunicorn（WSGI 服务器）
#   FastAPI/Sanic 是 ASGI 框架 → 用 uvicorn/sanic（ASGI 服务器）
#
# gunicorn 参数:
#   app:create_app()    调用工厂函数创建 Flask 应用实例
#   -b 0.0.0.0:8003     绑定地址和端口
#   -w 4                启动 4 个 worker 进程
CMD ["gunicorn", "app:create_app()", "-b", "0.0.0.0:8003", "-w", "4"]
