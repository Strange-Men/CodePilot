import React from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

type MarkdownContentProps = {
  children: string;
};

export function MarkdownContent({ children }: MarkdownContentProps) {
  return (
    <div className="markdown-body text-sm leading-6 text-foreground">
      <ReactMarkdown rehypePlugins={[rehypeHighlight]} remarkPlugins={[remarkGfm]} skipHtml>
        {children.trim()}
      </ReactMarkdown>
    </div>
  );
}
