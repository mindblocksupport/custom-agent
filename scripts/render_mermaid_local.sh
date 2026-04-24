#!/usr/bin/env bash
# 把 PROJECT-OVERVIEW.md 里的 mermaid URL 替换成本地 PNG.
# 依赖: npm i -g @mermaid-js/mermaid-cli (需要 Chromium)
# 用途: mermaid.ink 挂了时离线渲染; 或导出到离线场景.

set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p docs/assets/mermaid

# 抽取每个 mermaid 源码块 → 单独文件 → mmdc 渲染
python3 - <<'PY'
import re, hashlib
from pathlib import Path

md = Path("docs/PROJECT-OVERVIEW.md").read_text()
blocks = re.findall(r"```mermaid\n(.*?)\n```", md, re.DOTALL)
for i, code in enumerate(blocks):
    h = hashlib.sha256(code.encode()).hexdigest()[:8]
    Path(f"docs/assets/mermaid/diagram-{i:02d}-{h}.mmd").write_text(code)
    print(f"wrote diagram-{i:02d}-{h}.mmd")
PY

echo "==> 用 mmdc 批量渲染..."
for mmd in docs/assets/mermaid/*.mmd; do
  out="${mmd%.mmd}.png"
  mmdc -i "$mmd" -o "$out" -b transparent -w 1200 || echo "skip $mmd"
done

echo "✅ 本地 PNG 生成在 docs/assets/mermaid/"
echo "   手动把 ![](https://mermaid.ink/...) 替换成 ![](./assets/mermaid/diagram-XX.png) 即可离线"
