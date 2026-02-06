/**
 * Biomechanics Lab Agent Tests
 */

import { describe, it, expect } from "vitest";
import { searchExercises } from "../src/tools/searchExercises.js";

describe("searchExercises", () => {
  it("should return exercises for chest muscle group", () => {
    const results = searchExercises({ muscleGroup: "chest" });
    expect(results.length).toBeGreaterThan(0);
    expect(results.every((e) => e.muscleGroup === "chest")).toBe(true);
  });

  it("should filter by goal type", () => {
    const results = searchExercises({ goalType: "hypertrophy" });
    expect(results.length).toBeGreaterThan(0);
  });

  it("should filter by difficulty", () => {
    const results = searchExercises({ difficulty: "beginner" });
    expect(results.length).toBeGreaterThan(0);
    // All returned exercises should have beginner difficulty from the source
  });

  it("should filter by available equipment", () => {
    const results = searchExercises({
      equipment: ["dumbbells", "bench"],
      muscleGroup: "chest",
    });
    expect(results.length).toBeGreaterThan(0);
    // Should include exercises that need only dumbbells and/or bench
    results.forEach((e) => {
      if (e.equipment.length > 0) {
        expect(
          e.equipment.every((eq) =>
            ["dumbbells", "bench"].includes(eq.toLowerCase())
          )
        ).toBe(true);
      }
    });
  });

  it("should return bodyweight exercises when no equipment specified", () => {
    const results = searchExercises({
      muscleGroup: "chest",
      equipment: [], // Empty array means bodyweight only
    });
    // Should include exercises with no equipment requirement
    const bodyweightExercises = results.filter((e) => e.equipment.length === 0);
    expect(bodyweightExercises.length).toBeGreaterThan(0);
  });

  it("should respect limit parameter", () => {
    const results = searchExercises({ limit: 3 });
    expect(results.length).toBeLessThanOrEqual(3);
  });

  it("should return workout exercise format", () => {
    const results = searchExercises({ muscleGroup: "back", limit: 1 });
    expect(results[0]).toHaveProperty("id");
    expect(results[0]).toHaveProperty("name");
    expect(results[0]).toHaveProperty("muscleGroup");
    expect(results[0]).toHaveProperty("equipment");
    expect(results[0]).toHaveProperty("sets");
    expect(results[0]).toHaveProperty("reps");
    expect(results[0]).toHaveProperty("restSeconds");
  });
});

describe("exercise database", () => {
  it("should have exercises for all major muscle groups", () => {
    const muscleGroups = [
      "chest",
      "back",
      "shoulders",
      "arms",
      "legs",
      "core",
    ];
    for (const mg of muscleGroups) {
      const results = searchExercises({ muscleGroup: mg });
      expect(results.length).toBeGreaterThan(0);
    }
  });

  it("should have exercises for all goal types", () => {
    const goalTypes = [
      "hypertrophy",
      "strength",
      "endurance",
      "power",
    ] as const;
    for (const goal of goalTypes) {
      const results = searchExercises({ goalType: goal });
      expect(results.length).toBeGreaterThan(0);
    }
  });
});
