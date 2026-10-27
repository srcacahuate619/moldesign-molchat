import { describe, expect, it } from "vitest";
import { createSseParser } from "./sse";

describe("createSseParser", () => {
  it("parses one event per data block", () => {
    const parser = createSseParser();
    const events = parser.push(
      'data: {"type": "intent"}\n\ndata: {"type": "result"}\n\n',
    );
    expect(events).toEqual([{ type: "intent" }, { type: "result" }]);
  });

  it("reassembles events split across chunks", () => {
    const parser = createSseParser();
    expect(parser.push('data: {"type": "res')).toEqual([]);
    expect(parser.push('ult", "n": 1}\n\n')).toEqual([
      { type: "result", n: 1 },
    ]);
  });

  it("ignores event lines and skips malformed payloads", () => {
    const parser = createSseParser();
    const events = parser.push(
      "event: ping\ndata: {oops}\n\ndata: [1, 2]\n\n",
    );
    expect(events).toEqual([[1, 2]]);
  });
});
