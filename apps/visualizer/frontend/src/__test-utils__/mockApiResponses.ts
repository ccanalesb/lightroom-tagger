import { vi } from "vitest";

export const fetchMock = vi.fn();

interface MockOptions {
  defaultProvider?: string;
  defaultModel?: string | null;
}

export function mockApiResponses(
  _models: { name: string; default: boolean }[] = [],
  options: MockOptions = {},
) {
  const defaultProvider = options.defaultProvider ?? "ollama";
  const defaultModel = options.defaultModel ?? null;

  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    if (url.includes("/providers/defaults")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          vision_comparison: { provider: defaultProvider, model: defaultModel },
          description: { provider: defaultProvider, model: defaultModel },
        }),
      });
    }
    if (url.includes("/providers/fallback-order")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ order: [defaultProvider] }),
      });
    }
    if (url.includes("/providers/") && url.includes("/models")) {
      return Promise.resolve({ ok: true, json: async () => [] });
    }
    if (url.includes("/providers")) {
      return Promise.resolve({
        ok: true,
        json: async () => [
          { id: "ollama", name: "Ollama (Local)", available: true },
        ],
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
        json: async () => ({
          matches: [],
          match_groups: [],
          total: 0,
          total_groups: 0,
          total_matches: 0,
        }),
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
