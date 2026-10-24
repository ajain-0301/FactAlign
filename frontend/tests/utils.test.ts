import { describe, expect, it } from "vitest";
import { countWords, ms, num, pct } from "@/lib/utils";

describe("utils", () => {
  it("counts Hindi (with matras), English and mixed words", () => {
    expect(countWords("भारत में प्रदूषण बढ़ रहा है।")).toBe(6);
    expect(countWords("The rate rose 6.5% today")).toBe(5);
    expect(countWords("भारत में pollution का level")).toBe(5);
    expect(countWords("   ")).toBe(0);
  });
  it("formats metrics and never fabricates missing values", () => {
    expect(pct(0.256, 1)).toBe("25.6%");
    expect(pct(null)).toBe("—");
    expect(num(undefined)).toBe("—");
    expect(ms(850)).toBe("850 ms");
    expect(ms(2500)).toBe("2.50 s");
  });
});
