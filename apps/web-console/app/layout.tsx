import type { Metadata } from "next";
import { UiHost } from "../components/UiHost";
import "./globals.css";

export const metadata: Metadata = {
  title: "Custom Agent · Console",
  description: "Enterprise Agent Platform",
};

// Inline 提前应用主题, 防止刷新闪白
const themeBootScript = `
(function(){try{
  var t = localStorage.getItem('ca:theme:v1');
  if (t !== 'light' && t !== 'dark') {
    t = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.dataset.theme = t;
}catch(_){}})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" data-theme="light">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className="m-0 surface">
        {children}
        <UiHost />
      </body>
    </html>
  );
}
