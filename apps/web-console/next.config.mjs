/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    BACKEND_URL: process.env.BACKEND_URL || "http://localhost:8000",
  },

  // ==========================================================================
  // 长期顽疾: Next 15 webpack dev 偶发 "Cannot find module './XYZ.js'"
  //   - 根因: webpack 的 in-memory chunk graph 与 .next/server/ 磁盘文件不一致
  //   - 触发: 频繁热改 server-side route 时, 旧 chunk 被新 chunk 覆盖前没卸载干净
  //   - 真正修法: dev 改用 Turbopack (next dev --turbopack), 完全绕开 webpack
  //              已在 package.json#scripts.dev 启用 --turbopack
  //   - 兜底:  保留 next dev (webpack) 在 dev:webpack script, 排障时切回
  //   - build 用默认 webpack (Turbopack 还不支持 build 的所有优化)
  //
  // Turbopack 用空配置占位 — 否则 build 时 "Webpack is configured while Turbopack
  // is not" 警告会出现 (尽管 build 用 webpack, dev 配置 Turbo 不影响).
  // ==========================================================================
  experimental: {
    turbo: {
      rules: {},
    },
  },
};

export default nextConfig;
