# ============================================
# Sanic Demo - Makefile
# ============================================
# Makefile 是什么？
#   - 命令快捷方式集合，把复杂命令封装成简短的 make xxx
#   - 避免记住长命令，提高开发效率
#
# 使用方式：
#   make install    - 安装依赖
#   make run        - 启动服务（生产模式，4个worker）
#   make dev        - 开发模式启动（热重载，代码修改自动重启）
#   make test       - 运行测试
#   make lint       - 代码检查（flake8 + mypy）
#   make format     - 代码格式化（black + isort）
#   make clean      - 清理缓存文件
#   make docker-build   - 构建 Docker 镜像
#   make docker-run     - 运行 Docker 容器（后台模式）
#   make docker-stop    - 停止并删除 Docker 容器
#   make docker-logs    - 查看容器日志
#   make help       - 显示帮助信息
# ============================================

# ============================================
# 变量定义（统一管理，修改一处全局生效）
# ============================================
APP_NAME = sanic-demo                # 应用名称，用于容器命名
PORT = 8002                          # 服务端口号
PYTHON = python                      # Python 解释器命令
PIP = pip                            # 包管理器命令
DOCKER_IMAGE = $(APP_NAME):latest    # Docker 镜像名称:标签

# ============================================
# 本地开发命令
# ============================================

## install: 安装项目依赖
# 等价于: pip install -r requirements.txt
# 使用场景: 首次搭建环境或依赖更新后
install:
	$(PIP) install -r requirements.txt

## run: 启动服务（生产模式）
# 等价于: python -m sanic main.app --host=0.0.0.0 --port=8002 --workers=4
# 参数说明:
#   main.app          模块名.应用实例（main.py 中的 app 对象）
#   --host=0.0.0.0    监听所有网卡（允许外部访问）
#   --port=8002       监听端口
#   --workers=4       启动4个工作进程（多进程处理请求）
# 与 FastAPI 的区别: Sanic 使用自带的 sanic CLI，而非 uvicorn
# 使用场景: 生产环境部署
run:
	$(PYTHON) -m sanic main.app --host=0.0.0.0 --port=$(PORT) --workers=4

## dev: 开发模式启动（热重载）
# 等价于: python main.py
# 特点: 代码修改后自动重启服务（Sanic 内置 auto_reload）
# 使用场景: 日常开发调试
dev:
	$(PYTHON) main.py

## test: 运行测试
# 等价于: python -m pytest tests/ -v
# 参数: -v 显示详细测试信息
# 使用场景: 提交代码前验证功能
test:
	$(PYTHON) -m pytest tests/ -v

## lint: 代码质量检查
# flake8: 检查代码风格（PEP8）
# mypy: 静态类型检查
# 使用场景: 提交代码前确保代码质量
lint:
	$(PYTHON) -m flake8 app/ main.py
	$(PYTHON) -m mypy app/

## format: 代码格式化
# black: 自动格式化代码风格
# isort: 自动排序 import 语句
# 使用场景: 统一团队代码风格
format:
	$(PYTHON) -m black app/ main.py
	$(PYTHON) -m isort app/ main.py

## clean: 清理缓存文件
# 删除 __pycache__、.pyc、.pytest_cache、.mypy_cache
# 使用场景: 解决缓存导致的奇怪问题
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

# ============================================
# Docker 命令
# ============================================

## docker-build: 构建 Docker 镜像
# 等价于: docker build -t sanic-demo:latest .
# 参数: -t 给镜像打标签
# 使用场景: 代码修改后重新构建镜像
docker-build:
	docker build -t $(DOCKER_IMAGE) .

## docker-run: 运行 Docker 容器（后台模式）
# 等价于: docker run -d --name sanic-demo -p 8002:8002 -e APP_ENV=production sanic-demo:latest
# 参数说明:
#   -d                    后台运行（detached mode）
#   --name sanic-demo     容器名称
#   -p 8002:8002          端口映射（宿主机端口:容器端口）
#   -e APP_ENV=production 设置环境变量
# 使用场景: 部署到服务器
docker-run:
	docker run -d \
		--name $(APP_NAME) \
		-p $(PORT):$(PORT) \
		-e APP_ENV=production \
		$(DOCKER_IMAGE)

## docker-stop: 停止并删除 Docker 容器
# docker stop: 优雅停止容器（发送 SIGTERM 信号）
# docker rm: 删除容器
# || true: 即使容器不存在也不报错
# 使用场景: 停止服务或重新部署前清理
docker-stop:
	docker stop $(APP_NAME) || true
	docker rm $(APP_NAME) || true

## docker-logs: 查看容器日志
# -f: 实时跟踪日志（类似 tail -f）
# 使用场景: 排查问题、监控运行状态
docker-logs:
	docker logs -f $(APP_NAME)

# ============================================
# 帮助信息
# ============================================

## help: 显示所有可用命令
# @echo: 输出文本（@ 符号避免显示命令本身）
# 使用方式: make help 或 make
help:
	@echo "可用命令："
	@echo "  make install        - 安装依赖"
	@echo "  make run            - 启动服务（生产模式）"
	@echo "  make dev            - 开发模式启动（热重载）"
	@echo "  make test           - 运行测试"
	@echo "  make lint           - 代码检查"
	@echo "  make format         - 代码格式化"
	@echo "  make clean          - 清理缓存"
	@echo "  make docker-build   - 构建 Docker 镜像"
	@echo "  make docker-run     - 运行 Docker 容器"
	@echo "  make docker-stop    - 停止 Docker 容器"
	@echo "  make docker-logs    - 查看容器日志"

# .PHONY: 声明伪目标
# 作用: 告诉 make 这些是命令，不是文件名
# 原因: 如果当前目录有个文件叫 "test"，make test 会认为目标已达成而不执行
# 声明 .PHONY 后，无论是否存在同名文件，都会执行命令
.PHONY: install run dev test lint format clean docker-build docker-run docker-stop docker-logs help
