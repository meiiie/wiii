#!/bin/bash
# Fix nginx config: process envsubst and reload
export EMBED_ALLOWED_ORIGINS="https://holilihu.online https://wiii.holilihu.online"
envsubst '$EMBED_ALLOWED_ORIGINS' < /tmp/nginx.conf.template > /tmp/nginx-final.conf
echo "=== Checking substitution ==="
grep 'frame-ancestors' /tmp/nginx-final.conf | head -1
grep 'subdomain_header' /tmp/nginx-final.conf | head -5
echo "=== Copying to nginx container ==="
docker cp /tmp/nginx-final.conf wiii-nginx:/etc/nginx/conf.d/default.conf
echo "=== Testing nginx config ==="
docker exec wiii-nginx nginx -t
echo "=== Reloading nginx ==="
docker exec wiii-nginx nginx -s reload
echo "=== Done ==="
