# 安装指南（面向 AI Agent）

本指南为 AI agent（Codex、Claude Code 等）编写，用于自动安装 CodexComp CPA 插件。

## 安装前（可选）：A/B 降智测试

安装插件前，可以先跑一次 [codex-candy-eval](https://github.com/haowang02/codex-candy-eval) 降智测试，记录无插件时的基线表现。安装完成后再跑一次，对比插件效果。

**询问用户**：安装前是否要先跑降智测试记录基线？如果用户同意，执行：

```bash
python3 scripts/candy_eval_cpa.py --url http://your-cpa:port/v1/responses --key YOUR_KEY -n 5 -r high
```

保存结果，安装插件后再跑一次对比。如果用户不需要，跳过此步骤。

## 前置条件

- 一个运行中的 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) 实例（需 CGO 编译，建议使用[最新 release](https://github.com/router-for-me/CLIProxyAPI/releases/latest)）
- CPA 部署目录的访问权限
- CPA 的 `config.yaml` 中 `plugins.enabled` 需为 `true`

## 安装步骤

### 1. 下载成品

```bash
# 下载最新 release（根据平台选择）
# Linux x86_64（最常见）：
wget -qO /tmp/codexcomp.so "https://github.com/uf-hy/cpa-plugin-codexcomp/releases/latest/download/codexcomp-linux-amd64.so"

# Linux ARM64：
wget -qO /tmp/codexcomp.so "https://github.com/uf-hy/cpa-plugin-codexcomp/releases/latest/download/codexcomp-linux-arm64.so"
```

如果没有匹配的成品，可以从源码编译：

```bash
git clone https://github.com/uf-hy/cpa-plugin-codexcomp.git
cd cpa-plugin-codexcomp
# 自动获取 CPA 最新 release tag
CPA_TAG=$(curl -s https://api.github.com/repos/router-for-me/CLIProxyAPI/releases/latest | python3 -c "import sys,json;print(json.load(sys.stdin)['tag_name'])")
git clone --depth 1 --branch "$CPA_TAG" https://github.com/router-for-me/CLIProxyAPI.git ../CLIProxyAPI
go build -buildmode=c-shared -o codexcomp.so
```

### 2. 创建插件目录（如不存在）

```bash
mkdir -p <CPA_DIR>/plugins
```

### 3. 复制插件

```bash
cp /tmp/codexcomp.so <CPA_DIR>/plugins/codexcomp.so
```

### 4. 在 config.yaml 中启用插件

检查 `<CPA_DIR>/config.yaml`。如果没有 `plugins` 段，添加：

```yaml
plugins:
  enabled: true
  dir: plugins
  configs:
    codexcomp:
      enabled: true
      priority: 1
```

如果 `plugins.enabled` 已经是 `true`，只需确保 `configs.codexcomp.enabled: true` 存在。

### 5. 挂载插件目录（仅 Docker）

如果 CPA 跑在 Docker 里，确保 `docker-compose.yml` 有 plugins 卷映射：

```yaml
volumes:
  - ./plugins:/CLIProxyAPI/plugins:ro
```

### 6. 重启 CPA

```bash
# Docker：
cd <CPA_DIR> && docker compose restart

# 独立部署：
systemctl restart cli-proxy-api
```

### 7. 验证

通过 CPA 发一个简单的 gpt-5.5 流式请求。如果插件已加载，最终 `response.completed` 事件会包含 `metadata.proxy_rounds`：

```bash
curl -sN <CPA_URL>/v1/responses \
  -H "Authorization: Bearer <YOUR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.5","stream":true,"input":[{"type":"message","role":"user","content":[{"type":"input_text","text":"Hi"}]}],"reasoning":{"effort":"low"}}' \
  | grep proxy_rounds
```

如果输出中看到 `proxy_rounds`，说明插件正常工作。

## 卸载

```bash
rm <CPA_DIR>/plugins/codexcomp.so
# 重启 CPA
cd <CPA_DIR> && docker compose restart
```

## 排障

- **插件没加载**：检查 CPA 日志中是否有 `codexcomp` 相关条目。确保 `plugins.enabled: true` 且 `.so` 文件在 `plugins` 目录中。
- **CGO 未启用**：CPA 必须用 CGO 编译。官方 Docker 镜像 `eceasy/cli-proxy-api:latest` 支持插件。
- **架构不匹配**：`.so` 必须匹配 CPA 运行时的架构，不是宿主机的架构。Apple Silicon 上跑 Docker 需要用 `linux/amd64` 模拟或编译 `linux/arm64` 版本。
