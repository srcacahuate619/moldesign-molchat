import { describe, expect, it } from "vitest";
import { strings } from "./i18n";

describe("strings", () => {
  it("covers the same keys in es and en", () => {
    const es = strings("es");
    const en = strings("en");
    expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort());
    for (const value of [...Object.values(es), ...Object.values(en)]) {
      expect(value.trim().length).toBeGreaterThan(0);
    }
  });

  it("declares the platform source rather than the retired demo dataset", () => {
    for (const locale of ["es", "en"] as const) {
      expect(strings(locale)["settings.dataNote"]).toContain("MolDesign");
      expect(strings(locale)["settings.dataNote"]).not.toMatch(/8 molecules|8 moléculas/i);
    }
  });
});
