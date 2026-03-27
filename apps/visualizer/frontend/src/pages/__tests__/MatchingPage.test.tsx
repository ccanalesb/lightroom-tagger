import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { MatchingPage } from "../MatchingPage";
import { MatchOptionsProvider } from "../../stores/matchOptionsContext";
import { fetchMock, mockApiResponses } from "../../__test-utils__/mockApiResponses";

describe("MatchingPage model selection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = fetchMock;
  });

  it("should send the first available model when no default exists", async () => {
    mockApiResponses([{ name: "gemma3:27b-cloud", default: false }]);

    render(
      <MemoryRouter>
        <MatchOptionsProvider>
          <MatchingPage />
        </MatchOptionsProvider>
      </MemoryRouter>,
    );

    const runBtn = await screen.findByText("Run Matching");
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText("Start")).toBeTruthy();
    });

    const startBtn = screen.getByText("Start");
    fireEvent.click(startBtn);

    await waitFor(
      () => {
        const postCall = fetchMock.mock.calls.find(
          ([url, opts]: [string, RequestInit?]) =>
            url.includes("/jobs/") && opts?.method === "POST",
        );
        expect(postCall).toBeTruthy();
        const body = JSON.parse(postCall![1].body as string);
        expect(body.metadata.vision_model).toBe("gemma3:27b-cloud");
      },
      { timeout: 3000 },
    );
  });

  it("should send the default model when one exists", async () => {
    mockApiResponses([
      { name: "gemma3:4b", default: false },
      { name: "gemma3:27b", default: true },
    ]);

    render(
      <MemoryRouter>
        <MatchOptionsProvider>
          <MatchingPage />
        </MatchOptionsProvider>
      </MemoryRouter>,
    );

    const runBtn = await screen.findByText("Run Matching");
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText("Start")).toBeTruthy();
    });

    const startBtn = screen.getByText("Start");
    fireEvent.click(startBtn);

    await waitFor(
      () => {
        const postCall = fetchMock.mock.calls.find(
          ([url, opts]: [string, RequestInit?]) =>
            url.includes("/jobs/") && opts?.method === "POST",
        );
        expect(postCall).toBeTruthy();
        const body = JSON.parse(postCall![1].body as string);
        expect(body.metadata.vision_model).toBe("gemma3:27b");
      },
      { timeout: 3000 },
    );
  });
});
