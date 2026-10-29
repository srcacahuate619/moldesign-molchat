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
  const nodes: ReactNode[] = [];
  const cells = (line: string) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, "|"));
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    const separator = lines[index + 1];
    if (line.includes("|") && separator && /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(separator)) {
      const headers = cells(line);
      const widths = cells(separator);
      if (headers.length === widths.length) {
        const rows: string[][] = [];
        index += 2;
        while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
          rows.push(cells(lines[index]));
          index++;
        }
        index--;
        nodes.push(<div className="markdown-table-scroll" key={`table-${index}`}><table>
          <thead><tr>{headers.map((header, i) => <th key={i} scope="col">{inline(header)}</th>)}</tr></thead>
          <tbody>{rows.map((row, i) => <tr key={i}>{headers.map((_, j) => <td key={j}>{inline(row[j] ?? "")}</td>)}</tr>)}</tbody>
        </table></div>);
        continue;
      }
    }
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) { nodes.push(<p className="message-heading" key={index}>{inline(heading[2])}</p>); continue; }
    const list = /^\s*[-*]\s+(.+)$/.exec(line);
    if (list) { nodes.push(<div className="message-list-item" key={index}>• {inline(list[1])}</div>); continue; }
    if (!line) { nodes.push(<div className="message-gap" key={index} />); continue; }
    nodes.push(<div key={index}>{inline(line)}</div>);
  }
  return <div className="message-text">{nodes}</div>;
}
