import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "public goods manage",
    template: "%s | public goods manage",
  },
  description: "학교·주민센터 공동 물품을 지도에서 찾고 예약·대여하는 서비스",
};

// 한글 웹 글꼴 Pretendard (OFL). 필요한 글자만 나눠 받는 버전이라 가볍다.
const PRETENDARD =
  "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css";

export const viewport: Viewport = {
  themeColor: "#0d1b33",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className="h-full antialiased">
      <head>
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="anonymous" />
        <link rel="stylesheet" href={PRETENDARD} crossOrigin="anonymous" />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
