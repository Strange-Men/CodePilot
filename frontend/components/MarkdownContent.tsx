import React from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

type MarkdownContentProps = {
  children: string;
};

export function MarkdownContent({ children }: MarkdownContentProps) {
  const markdown = linkEvidenceReferences(children.trim());

  return (
    <div className="markdown-body text-sm leading-6 text-foreground">
      <ReactMarkdown
        components={{
          a: ({ className, href, ...props }) => (
            <a
              className={cn(href === "#report-evidence-appendix" && "evidence-ref", className)}
              href={href}
              {...props}
            />
          ),
        }}
        rehypePlugins={[rehypeHighlight]}
        remarkPlugins={[remarkGfm]}
        skipHtml
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

function linkEvidenceReferences(markdown: string): string {
  return splitMarkdownCode(markdown)
    .map((segment) => {
      if (segment.isCode) return segment.text;
      return splitInlineCode(segment.text)
        .map((inlineSegment) =>
          inlineSegment.isCode
            ? inlineSegment.text
            : inlineSegment.text.replace(/\[(E\d+)\](?!\()/g, "[[$1]](#report-evidence-appendix)")
        )
        .join("");
    })
    .join("");
}

function splitMarkdownCode(markdown: string): Array<{ isCode: boolean; text: string }> {
  const segments: Array<{ isCode: boolean; text: string }> = [];
  const pattern = /```[\s\S]*?```/g;
  let lastIndex = 0;
  for (const match of markdown.matchAll(pattern)) {
    if (match.index && match.index > lastIndex) {
      segments.push({ isCode: false, text: markdown.slice(lastIndex, match.index) });
    }
    segments.push({ isCode: true, text: match[0] });
    lastIndex = (match.index || 0) + match[0].length;
  }
  if (lastIndex < markdown.length) {
    segments.push({ isCode: false, text: markdown.slice(lastIndex) });
  }
  return segments;
}

function splitInlineCode(text: string): Array<{ isCode: boolean; text: string }> {
  const segments: Array<{ isCode: boolean; text: string }> = [];
  const pattern = /`[^`]*`/g;
  let lastIndex = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index && match.index > lastIndex) {
      segments.push({ isCode: false, text: text.slice(lastIndex, match.index) });
    }
    segments.push({ isCode: true, text: match[0] });
    lastIndex = (match.index || 0) + match[0].length;
  }
  if (lastIndex < text.length) {
    segments.push({ isCode: false, text: text.slice(lastIndex) });
  }
  return segments;
}
