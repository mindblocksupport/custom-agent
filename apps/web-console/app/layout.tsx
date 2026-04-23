import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Custom Agent · Console",
  description: "Enterprise Agent Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="m-0">{children}</body>
    </html>
  );
}
