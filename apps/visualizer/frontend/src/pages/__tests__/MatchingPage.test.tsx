import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { MatchingTab } from "../../components/processing/MatchingTab";
import { MatchOptionsProvider } from "../../stores/matchOptionsContext";
import { fetchMock, mockApiResponses } from "../../__test-utils__/mockApiResponses";
import { deleteMatching } from "../../data/cache";

describe("MatchingTab provider selection", () => {
  beforeEach(() => {
    deleteMatching(() => true);
    vi.clearAllMocks();
    globalThis.fetch = fetchMock;
  });

  it("should send the default provider from provider defaults", async () => {
    mockApiResponses([], { defaultProvider: "ollama" });

    render(
      <MemoryRouter>
        <MatchOptionsProvider>
          <MatchingTab />
        </MatchOptionsProvider>
      </MemoryRouter>,
    );

    const startBtn = await screen.findByText("Start Vision Matching");
    fireEvent.click(startBtn);

    await waitFor(
      () => {
        const postCall = fetchMock.mock.calls.find(
          ([url, opts]: [string, RequestInit?]) =>
            url.includes("/jobs/") && opts?.method === "POST",
        );
        expect(postCall).toBeTruthy();
        const body = JSON.parse(postCall![1].body as string);
        expect(body.metadata.provider_id).toBe("ollama");
      },
      { timeout: 3000 },
    );
  });

  it("should include provider_model when a specific model is set", async () => {
    mockApiResponses([], {
      defaultProvider: "openrouter",
      defaultModel: "google/gemini-2.5-flash-lite",
    });

    render(
      <MemoryRouter>
        <MatchOptionsProvider>
          <MatchingTab />
        </MatchOptionsProvider>
      </MemoryRouter>,
    );

    const startBtn = await screen.findByText("Start Vision Matching");
    fireEvent.click(startBtn);

    await waitFor(
      () => {
        const postCall = fetchMock.mock.calls.find(
          ([url, opts]: [string, RequestInit?]) =>
            url.includes("/jobs/") && opts?.method === "POST",
        );
        expect(postCall).toBeTruthy();
        const body = JSON.parse(postCall![1].body as string);
        expect(body.metadata.provider_id).toBe("openrouter");
        expect(body.metadata.provider_model).toBe("google/gemini-2.5-flash-lite");
      },
      { timeout: 3000 },
    );
  });
});
