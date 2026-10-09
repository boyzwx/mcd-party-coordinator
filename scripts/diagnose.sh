#!/usr/bin/env bash
# 麦当劳 MCP 服务器连通性诊断
# 用途：确认 fetch failed 的根因是证书链缺失，而非 Token 或网络问题
# 用法：./diagnose.sh

set -u
URL="https://mcp.mcd.cn"
CFG="$HOME/.workbuddy/mcp.json"

echo "=============================================="
echo " 麦当劳 MCP 连接诊断"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

echo ""
echo "[1] DNS 解析"
if nslookup mcp.mcd.cn 2>&1 | grep -A2 "^Name:" | grep Address; then
    echo "  ✓ 解析正常"
else
    echo "  ✗ 解析失败"
fi

echo ""
echo "[2] TCP 端口可达性"
if nc -z -G 5 mcp.mcd.cn 443 2>/dev/null; then
    echo "  ✓ 443 端口可达"
else
    echo "  ✗ 443 端口不可达"
fi

echo ""
echo "[3] 证书链完整性（关键步骤）"
CERT_OUT=$(echo | openssl s_client -connect mcp.mcd.cn:443 -servername mcp.mcd.cn 2>/dev/null)
VERIFY=$(echo "$CERT_OUT" | grep "Verify return code")
CHAIN_COUNT=$(echo "$CERT_OUT" | grep -cE "^ [0-9]+ s:")

echo "  下发证书数量: $CHAIN_COUNT 张"
echo "  校验结果    : ${VERIFY:-未返回}"

if echo "$CERT_OUT" | grep -q "Verify return code: 0"; then
    echo "  ✓ 证书链完整，可正常连接"
elif echo "$VERIFY" | grep -q "21"; then
    echo "  ✗ 证书链不完整：只下发叶子证书，缺失中间 CA"
    echo "     这是服务器端配置问题，与本机环境无关"
    echo ""
    echo "     受影响的客户端：所有启用严格 TLS 校验的 MCP 客户端"
    echo "     典型表现：fetch failed / SSL certificate problem"
elif echo "$VERIFY" | grep -q "unable to get local issuer"; then
    echo "  ✗ 本机缺少签发链所需的中间 CA 证书"
fi

echo ""
echo "[4] 直连测试（绕过代理）"
CODE=$(curl -s -o /dev/null -w "%{http_code}" --noproxy '*' --max-time 12 \
    -X POST "$URL" -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}' 2>/dev/null)
echo "  HTTP 状态: ${CODE:-连接失败}"

echo ""
echo "[5] Token 配置检查"
if [ -f "$CFG" ]; then
    TOKEN=$(python3 -c "
import json
d = json.load(open('$CFG'))
t = d.get('mcpServers', {}).get('mcd-mcp', {}).get('headers', {}).get('Authorization', '')
print(t.replace('Bearer ', ''))
" 2>/dev/null)
    if [ -z "$TOKEN" ]; then
        echo "  ✗ 配置中未找到 Token"
    elif echo "$TOKEN" | grep -q "YOUR_"; then
        echo "  ✗ Token 仍是占位符，未替换"
    else
        echo "  ✓ Token 已填写 (长度 ${#TOKEN})"
    fi
else
    echo "  ✗ 未找到 $CFG"
fi

echo ""
echo "=============================================="
echo " 结论"
echo "=============================================="
if echo "$VERIFY" | grep -q "21"; then
    cat <<'EOF'
 根因：麦当劳 MCP 服务器证书链配置不完整

 该问题无法在本地修复，需等待服务器侧补全中间证书。

 临时方案：
   1. 联系麦当劳顾客中心 400-920-0205 反馈证书问题
   2. 期间用非 MCP 方式开发：本地算法与流程已完备
   3. 在 MCP_INTEGRATION.md 中说明，将真实调用列为待验证项

 注意：不要为绕过校验而关闭 TLS 验证，这会带来安全隐患
EOF
fi
echo ""