"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownMessageProps = {
  content: string;
  streaming?: boolean;
  className?: string;
};

const mdComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mt-4 mb-2 border-b border-white/10 pb-1 text-lg font-bold text-white first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-3 mb-2 text-base font-semibold text-white/95 first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-3 mb-1.5 text-sm font-semibold text-blue-200/95 first:mt-0">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="my-2 leading-relaxed text-zinc-200 [&:first-child]:mt-0 [&:last-child]:mb-0">{children}</p>
  ),
  strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
  em: ({ children }) => <em className="italic text-zinc-100">{children}</em>,
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5 text-zinc-200">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5 text-zinc-200">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed [&>p]:my-1">{children}</li>,
  a: ({ href, children }) => (
    <a
      href={href}
      className="break-all text-blue-400 underline underline-offset-2 hover:text-blue-300"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-4 border-white/15" />,
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-red-500/45 pl-3 italic text-zinc-300">{children}</blockquote>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-lg border border-white/12">
      <table className="w-full border-collapse text-left text-xs sm:text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-white/10">{children}</thead>,
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => <tr className="border-b border-white/10 hover:bg-white/[0.04]">{children}</tr>,
  th: ({ children }) => (
    <th className="whitespace-nowrap px-3 py-2 align-top text-sm font-semibold text-blue-100/90">{children}</th>
  ),
  td: ({ children }) => (
    <td className="whitespace-nowrap px-3 py-2 align-top text-zinc-200 sm:whitespace-normal">{children}</td>
  ),
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-lg border border-white/10 bg-black/50 p-3 text-[0.85em] leading-relaxed">
      {children}
    </pre>
  ),
  code: ({ className, children, ...props }) => {
    const isBlock = Boolean(className?.includes("language-"));
    if (!isBlock) {
      return (
        <code
          className="break-words rounded bg-black/50 px-1.5 py-0.5 font-mono text-[0.88em] text-blue-200/95"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className={`block break-words font-mono whitespace-pre text-zinc-200 ${className ?? ""}`} {...props}>
        {children}
      </code>
    );
  },
};

export function MarkdownMessage({ content, streaming, className = "" }: MarkdownMessageProps) {
  return (
    <div className={`markdown-message min-w-0 max-w-full ${className}`.trim()}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
        {content}
      </ReactMarkdown>
      {streaming ? (
        <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-blue-400 align-middle" />
      ) : null}
    </div>
  );
}
