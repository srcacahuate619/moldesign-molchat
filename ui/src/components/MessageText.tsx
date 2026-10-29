import { Fragment, type ReactNode } from "react";

// Render the common Markdown emitted by models as React elements; HTML is always text.
function inline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\]\(https?:\/\/[^\s)]+\))/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    const link = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(part);
    if (link) return <a key={index} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a>;
    return <Fragment key={index}>{part}</Fragment>;
  });
}

export default function MessageText({ text }: { text: string }) {
  const lines = text.split("\n");
  return <div className="message-text">{lines.map((line, index) => {
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) return <p className="message-heading" key={index}>{inline(heading[2])}</p>;
    const list = /^\s*[-*]\s+(.+)$/.exec(line);
    if (list) return <div className="message-list-item" key={index}>• {inline(list[1])}</div>;
    if (!line) return <div className="message-gap" key={index} />;
    return <div key={index}>{inline(line)}</div>;
  })}</div>;
}
