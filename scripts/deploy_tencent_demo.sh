#!/usr/bin/env bash
set -Eeuo pipefail

readonly repository_url="https://github.com/Tongh-de/MarketCraft-AI.git"
readonly deployment_root="/opt/marketcraft-ai"
readonly compose_file="docker-compose.demo.yml"

run_as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "需要 root 权限或 sudo 才能部署到 ${deployment_root}。" >&2
    exit 1
  fi
}

install_command_if_missing() {
  local command_name="$1"
  local package_name="$2"
  if command -v "${command_name}" >/dev/null 2>&1; then
    return
  fi

  if command -v apt-get >/dev/null 2>&1; then
    run_as_root apt-get update
    run_as_root apt-get install -y "${package_name}"
  elif command -v dnf >/dev/null 2>&1; then
    run_as_root dnf install -y "${package_name}"
  elif command -v yum >/dev/null 2>&1; then
    run_as_root yum install -y "${package_name}"
  else
    echo "未找到受支持的包管理器，请先安装 ${package_name}。" >&2
    exit 1
  fi
}

install_command_if_missing git git
install_command_if_missing curl curl

if ! command -v docker >/dev/null 2>&1; then
  echo "未检测到 Docker。请先在腾讯云镜像中安装或启用 Docker CE。" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "未检测到 Docker Compose 插件。请先安装 docker-compose-plugin。" >&2
  exit 1
fi

if [[ ! -d "${deployment_root}" ]]; then
  run_as_root git clone --depth 1 --branch main "${repository_url}" "${deployment_root}"
else
  if [[ ! -d "${deployment_root}/.git" ]]; then
    echo "${deployment_root} 已存在但不是 Git 仓库，为避免覆盖已存在数据，部署已停止。" >&2
    exit 1
  fi

  current_remote="$(run_as_root git -C "${deployment_root}" remote get-url origin)"
  if [[ "${current_remote}" != "${repository_url}" ]]; then
    echo "${deployment_root} 的远程仓库不是 MarketCraft AI，为避免覆盖已存在项目，部署已停止。" >&2
    exit 1
  fi

  run_as_root git -C "${deployment_root}" fetch origin main
  run_as_root git -C "${deployment_root}" checkout main
  run_as_root git -C "${deployment_root}" pull --ff-only origin main
fi

cd "${deployment_root}"
run_as_root docker compose -f "${compose_file}" up -d --build

for attempt in {1..30}; do
  if curl -fsS http://127.0.0.1/health >/dev/null; then
    echo
    echo "MarketCraft AI 已启动。"
    echo "产品入口：http://124.222.64.104/app"
    echo "API 文档：http://124.222.64.104/docs"
    exit 0
  fi
  sleep 2
done

echo "容器已经启动，但健康检查未在 60 秒内通过。最近日志如下：" >&2
run_as_root docker compose -f "${compose_file}" logs --tail 100 api >&2
exit 1
