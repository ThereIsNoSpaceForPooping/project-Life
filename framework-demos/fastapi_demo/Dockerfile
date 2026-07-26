# ============================================
# FastAPI Demo - Dockerfile
# ============================================
# Dockerfile 是什么？
#   - 构建指令文件，告诉 Docker 如何打包应用成镜像
#   - 类比：食谱（告诉厨师怎么做菜）
#
# 构建镜像：docker build -t fastapi-demo .
# 运行容器：docker run -p 8001:8001 fastapi-demo
#
# 多阶段构建的优势：
#   阶段1 (base)         → 几乎不变，缓存命中率高
#   阶段2 (dependencies) → 只有改 requirements.txt 才重新构建
#   阶段3 (production)   → 每次代码修改都重新构建
#   结果：加速后续构建，减小最终镜像体积
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
# 语法: COPY <源路径> <目标路径>
# 这里只复制 requirements.txt，不复制整个项目
# 原因: 依赖不常变，代码经常变，分开复制可以充分利用缓存
COPY requirements.txt .

# RUN: 在构建时执行命令
# --no-cache-dir: 不缓存下载的包（减小镜像体积）
# -r requirements.txt: 从文件读取依赖列表
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
#
# useradd 参数:
#   -m: 创建用户主目录
#   -u 1000: 指定用户 ID（避免权限问题）
#
# chown: 修改目录所有者（让 appuser 有权限读写）
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# USER: 切换到非 root 用户（后续命令和运行时都用这个用户）
USER appuser

# ============================================
# 网络配置
# ============================================

# EXPOSE: 声明容器监听的端口
# 注意: 这只是文档说明，实际端口映射靠 docker run -p
EXPOSE 8001

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
#
# 检查命令: 访问 /api/health 接口，成功则健康
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/health')"

# ============================================
# 启动命令
# ============================================

# CMD: 容器启动时执行的命令
# 格式: CMD ["可执行文件", "参数1", "参数2", ...]
#
# uvicorn 参数:
#   main:app       模块名:应用实例（main.py 中的 app 对象）
#   --host 0.0.0.0 监听所有网卡
#   --port 8001    监听端口
#   --workers 4    启动 4 个工作进程（多进程处理请求，提高并发）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4"]
