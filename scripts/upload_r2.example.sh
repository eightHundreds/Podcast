#!/usr/bin/env bash
# 示例：把本地 MP3 上传到 Cloudflare R2（需安装 aws CLI 或 rclone）
# 用法：
#   cp .env.example .env  # 填好密钥
#   set -a && source .env && set +a
#   ./scripts/upload_r2.example.sh ./ep001.mp3 ep001.mp3
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "用法: $0 <本地文件> <对象键，如 ep001.mp3>"
  exit 1
fi

LOCAL_FILE=$1
OBJECT_KEY=$2

: "${R2_ENDPOINT:?请设置 R2_ENDPOINT}"
: "${R2_ACCESS_KEY_ID:?请设置 R2_ACCESS_KEY_ID}"
: "${R2_SECRET_ACCESS_KEY:?请设置 R2_SECRET_ACCESS_KEY}"
: "${R2_BUCKET:?请设置 R2_BUCKET}"

export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"

# R2 兼容 S3 API
aws s3 cp "$LOCAL_FILE" "s3://${R2_BUCKET}/${OBJECT_KEY}" \
  --endpoint-url "$R2_ENDPOINT" \
  --content-type "audio/mpeg" \
  --checksum-algorithm CRC32

echo "已上传: s3://${R2_BUCKET}/${OBJECT_KEY}"
if [[ -n "${R2_PUBLIC_BASE_URL:-}" ]]; then
  base="${R2_PUBLIC_BASE_URL%/}"
  echo "公开 URL: ${base}/${OBJECT_KEY}"
  bytes=$(wc -c <"$LOCAL_FILE" | tr -d ' ')
  echo "写入 podcast.yaml 时 length: ${bytes}"
fi
