/** Incremental SSE parser: bytes in, JSON payloads out (handles split chunks). */

export interface SseParser {
  push(chunk: string): Record<string, unknown>[];
}

export function createSseParser(): SseParser {
  let buffer = "";
  return {
    push(chunk: string): Record<string, unknown>[] {
      buffer += chunk;
      const events: Record<string, unknown>[] = [];
      let end = buffer.indexOf("\n\n");
      while (end >= 0) {
        const block = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const dataLines = block
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim());
        if (dataLines.length > 0) {
          try {
            events.push(JSON.parse(dataLines.join("\n")) as Record<string, unknown>);
          } catch {
            // Malformed event: skip, never crash the stream.
          }
        }
        end = buffer.indexOf("\n\n");
      }
      return events;
    },
  };
}
