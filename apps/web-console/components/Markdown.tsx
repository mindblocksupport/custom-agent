"use client";

/**
 * Markdown 渲染 (assistant 消息里的富文本).
 * - react-markdown + remark-gfm: 表格 / 任务列表 / 删除线
 * - rehype-highlight: 代码块语法高亮 (懒加载 highlight.js 核心)
 * - 安全: 不 render raw HTML (react-markdown 默认行为)
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";
import type { ComponentPropsWithoutRef } from "react";

export function Markdown({ children }: { children: string }) {
  return (
    <div className="md-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          a: (props: ComponentPropsWithoutRef<"a">) => (
            <a
              {...props}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline hover:text-blue-700"
            />
          ),
          code: (props: ComponentPropsWithoutRef<"code"> & { inline?: boolean }) => {
            const { inline, className, children, ...rest } = props;
            if (inline) {
              return (
                <code
                  {...rest}
                  className="px-1 py-0.5 rounded bg-pink-50 text-pink-700 font-mono text-[0.85em]"
                >
                  {children}
                </code>
              );
            }
            return (
              <code {...rest} className={className}>
                {children}
              </code>
            );
          },
          pre: (props: ComponentPropsWithoutRef<"pre">) => (
            <pre
              {...props}
              className="my-2 p-3 rounded-md bg-neutral-900 text-neutral-100 overflow-x-auto text-xs leading-relaxed"
            />
          ),
          table: (props: ComponentPropsWithoutRef<"table">) => (
            <div className="my-2 overflow-x-auto">
              <table
                {...props}
                className="w-full text-xs border-collapse border border-neutral-200"
              />
            </div>
          ),
          th: (props: ComponentPropsWithoutRef<"th">) => (
            <th
              {...props}
              className="border border-neutral-200 bg-neutral-50 px-2 py-1 text-left font-semibold"
            />
          ),
          td: (props: ComponentPropsWithoutRef<"td">) => (
            <td {...props} className="border border-neutral-200 px-2 py-1" />
          ),
          blockquote: (props: ComponentPropsWithoutRef<"blockquote">) => (
            <blockquote
              {...props}
              className="my-2 pl-3 border-l-4 border-neutral-300 text-neutral-600 italic"
            />
          ),
          ul: (props: ComponentPropsWithoutRef<"ul">) => (
            <ul {...props} className="my-1 ml-4 list-disc space-y-0.5" />
          ),
          ol: (props: ComponentPropsWithoutRef<"ol">) => (
            <ol {...props} className="my-1 ml-5 list-decimal space-y-0.5" />
          ),
          h1: (props: ComponentPropsWithoutRef<"h1">) => (
            <h1 {...props} className="mt-3 mb-1 font-semibold text-base" />
          ),
          h2: (props: ComponentPropsWithoutRef<"h2">) => (
            <h2 {...props} className="mt-3 mb-1 font-semibold text-sm" />
          ),
          h3: (props: ComponentPropsWithoutRef<"h3">) => (
            <h3
              {...props}
              className="mt-2 mb-0.5 font-semibold text-sm text-neutral-800"
            />
          ),
          p: (props: ComponentPropsWithoutRef<"p">) => (
            <p {...props} className="my-1 leading-relaxed" />
          ),
          hr: (props: ComponentPropsWithoutRef<"hr">) => (
            <hr {...props} className="my-3 border-neutral-200" />
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
