import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Progress, ErrorBox, Empty } from "../src/components";
import { pct, todayInZone } from "../src/types";

describe("real data states", () => {
  it("renders unknown attendance without fabricating a percentage", () => {
    expect(pct(null)).toBe("—");
    render(
      <Progress
        subject={
          {
            name: "Maths",
            percentage: null,
            on_track: false,
            attended: 0,
            conducted: 0,
          } as any
        }
      />,
    );
    expect(screen.getByText("0 / 0 classes")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });
  it("shows errors visibly", () => {
    render(<ErrorBox error={new Error("Request failed")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Request failed");
  });
  it("explains an empty screen", () => {
    render(<Empty>No classes scheduled.</Empty>);
    expect(screen.getByText("No classes scheduled.")).toBeVisible();
  });
  it("returns ISO local dates", () => {
    expect(todayInZone("Asia/Kolkata")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
