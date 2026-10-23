import type { NextConfig } from "next";

// 브라우저는 같은 도메인의 /api/* 로만 요청하고, Next.js가 API 서버로 전달한다.
// 덕분에 로그인 쿠키(httpOnly)를 같은 사이트 쿠키로 안전하게 쓸 수 있다.
const API_URL = (
  process.env.API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
