# docker-compose.yaml 模板
# 佔位符：{project_name}, {health_port}
#
# 使用方式：
#   docker compose up -d
#   docker compose logs -f team-agent

version: "3.8"

services:
  team-agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {project_name}-team-agent
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "{health_port}:{health_port}"
    volumes:
      - ./team.yaml:/app/team.yaml:ro
      - ./scheduler.yaml:/app/scheduler.yaml:ro
      - ./agents:/app/agents
      - ./knowledge:/app/knowledge
      - team-state:/app/state
    environment:
      - ARK_TEAM_AGENT_HOME=/app
      - TZ=Asia/Taipei
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{health_port}/api/status"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

volumes:
  team-state:
    driver: local

# ─── 選用服務 ───────────────────────────────────
# 取消註解以啟用

#  redis:
#    image: redis:7-alpine
#    container_name: {project_name}-redis
#    restart: unless-stopped
#    ports:
#      - "6379:6379"
#    volumes:
#      - redis-data:/data

#  postgres:
#    image: postgres:16-alpine
#    container_name: {project_name}-postgres
#    restart: unless-stopped
#    environment:
#      POSTGRES_DB: team_agent
#      POSTGRES_USER: agent
#      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
#    ports:
#      - "5432:5432"
#    volumes:
#      - pg-data:/var/lib/postgresql/data

# volumes:
#   redis-data:
#   pg-data:
