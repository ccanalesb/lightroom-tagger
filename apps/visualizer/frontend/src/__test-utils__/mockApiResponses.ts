import { vi } from "vitest";

export const fetchMock = vi.fn();

export function mockApiResponses(models: { name: string; default: boolean }[]) {
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    if (url.includes("/vision-models")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ models, fallback: false }),
      });
    }
    if (url.includes("/jobs/active")) {
      return Promise.resolve({ ok: true, json: async () => [] });
    }
    if (url.includes("/jobs/") && init?.method === "POST") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          id: "test-job-id",
          type: "vision_match",
          status: "pending",
          metadata: JSON.parse(init.body as string).metadata,
        }),
      });
    }
    if (url.includes("/matches")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ matches: [], match_groups: [], total: 0 }),
      });
    }
    if (url.includes("/cache/status")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          total_images: 10,
          cached_images: 10,
          missing: 0,
          cache_size_mb: 5,
          cache_dir: "/tmp",
        }),
      });
    }
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });
}
