import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "public goods manage",
    template: "%s | public goods manage",
  },
  description: "학교·동아리·학생회 공동 물품 대여 관리",
};

export const viewport: Viewport = {
  themeColor: "#0d1b33",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
