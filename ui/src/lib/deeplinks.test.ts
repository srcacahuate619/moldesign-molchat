import { describe, expect, it, vi } from "vitest";
import {
  HOST_ENVELOPE,
  isHostMessage,
  linksForReport,
  postToHost,
} from "./deeplinks";

describe("isHostMessage", () => {
  it("accepts exactly the five closed actions", () => {
    expect(isHostMessage({ kind: "open_evaluation", molecule_id: "m-1" })).toBe(
      true,
    );
    expect(isHostMessage({ kind: "open_report", molecule_id: "m-1" })).toBe(true);
    expect(isHostMessage({ kind: "open_case", case_id: "c-1" })).toBe(true);
    expect(isHostMessage({ kind: "open_molcy", job_id: "j-1" })).toBe(true);
    expect(
      isHostMessage({ kind: "request_platform_approval", proposal_id: "p-1" }),
    ).toBe(true);
  });

  it("rejects unknown kinds, extra fields and empty ids", () => {
    expect(isHostMessage({ kind: "open_shell", cmd: "x" })).toBe(false);
    expect(
      isHostMessage({ kind: "open_case", case_id: "c-1", extra: 1 }),
    ).toBe(false);
    expect(isHostMessage({ kind: "open_case", case_id: "" })).toBe(false);
    expect(isHostMessage({ kind: "open_case" })).toBe(false);
    expect(isHostMessage(null)).toBe(false);
    expect(isHostMessage("open_case")).toBe(false);
  });
});

describe("postToHost", () => {
  it("returns false when unhosted", () => {
    expect(
      postToHost({ kind: "open_case", case_id: "c-1" }),
    ).toBe(false);
  });

  it("posts the envelope to a parent frame", () => {
    const parent = { postMessage: vi.fn() };
    const ok = postToHost({ kind: "open_report", molecule_id: "m-9" }, parent);
    expect(ok).toBe(true);
    expect(parent.postMessage).toHaveBeenCalledWith(
      { type: HOST_ENVELOPE, kind: "open_report", molecule_id: "m-9" },
      "*",
    );
  });
});

describe("linksForReport", () => {
  it("extracts molecule links once each, never from task ids", () => {
    const report = {
      outcomes: [
        { result: { molecule_id: "m-1", task_id: "t-1" } },
        { result: { molecule_id: "m-1" } },
        { result: { task_id: "t-2" } },
        { result: null },
      ],
    };
    expect(linksForReport(report)).toEqual([
      { kind: "open_evaluation", molecule_id: "m-1" },
      { kind: "open_report", molecule_id: "m-1" },
    ]);
  });

  it("returns nothing for reports without outcomes", () => {
    expect(linksForReport(null)).toEqual([]);
    expect(linksForReport({})).toEqual([]);
    expect(linksForReport({ outcomes: "no" })).toEqual([]);
  });
});
