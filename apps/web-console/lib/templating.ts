/** 极简 Mustache 风格变量替换 (仅用于 skill 启动模板).
 * 仅支持 {{var}}, 不支持 {{#each}} 之类 (避免引大库).
 */

const VAR_RE = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g;

export function extractVars(s: string): string[] {
  const out = new Set<string>();
  let m: RegExpExecArray | null;
  VAR_RE.lastIndex = 0;
  while ((m = VAR_RE.exec(s)) !== null) {
    if (m[1]) out.add(m[1]);
  }
  return [...out];
}

export function applyVars(s: string, values: Record<string, string>): string {
  return s.replace(VAR_RE, (_, key) => {
    return values[key] ?? `{{${key}}}`;
  });
}

/** 从 starter_examples 数组里收集所有变量, 去重. */
export function collectStarterVars(examples: string[]): string[] {
  const out = new Set<string>();
  for (const ex of examples) {
    extractVars(ex).forEach((v) => out.add(v));
  }
  return [...out];
}
