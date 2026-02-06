/**
 * SearchExercises Tool - Mock Exercise Database
 *
 * Provides structured exercise recommendations based on search parameters.
 * This is a mocked implementation with realistic exercise data.
 */

import { z } from "zod";
import { tool } from "@langchain/core/tools";

// Exercise database (mocked)
const EXERCISE_DATABASE: Exercise[] = [
  // Chest exercises
  {
    id: "bench-press-001",
    name: "Barbell Bench Press",
    muscleGroup: "chest",
    equipment: ["barbell", "bench"],
    difficulty: "intermediate",
    goalType: ["hypertrophy", "strength"],
    defaultSets: 4,
    defaultReps: "8-12",
    restSeconds: 90,
    notes: "Focus on controlled eccentric phase",
  },
  {
    id: "incline-db-press-001",
    name: "Incline Dumbbell Press",
    muscleGroup: "chest",
    equipment: ["dumbbells", "bench"],
    difficulty: "intermediate",
    goalType: ["hypertrophy"],
    defaultSets: 3,
    defaultReps: "10-12",
    restSeconds: 75,
    notes: "30-45 degree incline angle",
  },
  {
    id: "pushup-001",
    name: "Push-ups",
    muscleGroup: "chest",
    equipment: [],
    difficulty: "beginner",
    goalType: ["endurance", "hypertrophy"],
    defaultSets: 3,
    defaultReps: "15-20",
    restSeconds: 60,
    notes: "Keep core tight throughout movement",
  },
  {
    id: "dips-001",
    name: "Chest Dips",
    muscleGroup: "chest",
    equipment: ["dip_bars"],
    difficulty: "intermediate",
    goalType: ["hypertrophy", "strength"],
    defaultSets: 3,
    defaultReps: "8-12",
    restSeconds: 90,
    notes: "Lean forward slightly to target chest",
  },
  // Back exercises
  {
    id: "pullup-001",
    name: "Pull-ups",
    muscleGroup: "back",
    equipment: ["pullup_bar"],
    difficulty: "intermediate",
    goalType: ["strength", "hypertrophy"],
    defaultSets: 4,
    defaultReps: "6-10",
    restSeconds: 90,
    notes: "Full range of motion, dead hang at bottom",
  },
  {
    id: "barbell-row-001",
    name: "Barbell Bent-Over Row",
    muscleGroup: "back",
    equipment: ["barbell"],
    difficulty: "intermediate",
    goalType: ["hypertrophy", "strength"],
    defaultSets: 4,
    defaultReps: "8-10",
    restSeconds: 90,
    notes: "Keep back flat, pull to lower chest",
  },
  {
    id: "db-row-001",
    name: "Single-Arm Dumbbell Row",
    muscleGroup: "back",
    equipment: ["dumbbells", "bench"],
    difficulty: "beginner",
    goalType: ["hypertrophy"],
    defaultSets: 3,
    defaultReps: "10-12",
    restSeconds: 60,
    notes: "Support on bench, squeeze at top",
  },
  {
    id: "inverted-row-001",
    name: "Inverted Rows",
    muscleGroup: "back",
    equipment: [],
    difficulty: "beginner",
    goalType: ["endurance", "hypertrophy"],
    defaultSets: 3,
    defaultReps: "12-15",
    restSeconds: 60,
    notes: "Can use table or bar at hip height",
  },
  // Shoulder exercises
  {
    id: "ohp-001",
    name: "Overhead Press",
    muscleGroup: "shoulders",
    equipment: ["barbell"],
    difficulty: "intermediate",
    goalType: ["strength", "hypertrophy"],
    defaultSets: 4,
    defaultReps: "6-8",
    restSeconds: 120,
    notes: "Brace core, press straight up",
  },
  {
    id: "lateral-raise-001",
    name: "Lateral Raises",
    muscleGroup: "shoulders",
    equipment: ["dumbbells"],
    difficulty: "beginner",
    goalType: ["hypertrophy"],
    defaultSets: 3,
    defaultReps: "12-15",
    restSeconds: 60,
    notes: "Control the movement, slight bend in elbows",
  },
  {
    id: "pike-pushup-001",
    name: "Pike Push-ups",
    muscleGroup: "shoulders",
    equipment: [],
    difficulty: "beginner",
    goalType: ["endurance", "strength"],
    defaultSets: 3,
    defaultReps: "10-15",
    restSeconds: 60,
    notes: "Hips high, head toward floor",
  },
  {
    id: "face-pull-001",
    name: "Face Pulls",
    muscleGroup: "shoulders",
    equipment: ["cable_machine", "resistance_bands"],
    difficulty: "beginner",
    goalType: ["hypertrophy", "endurance"],
    defaultSets: 3,
    defaultReps: "15-20",
    restSeconds: 45,
    notes: "External rotation at peak contraction",
  },
  // Arm exercises
  {
    id: "bicep-curl-001",
    name: "Barbell Bicep Curl",
    muscleGroup: "arms",
    equipment: ["barbell"],
    difficulty: "beginner",
    goalType: ["hypertrophy"],
    defaultSets: 3,
    defaultReps: "10-12",
    restSeconds: 60,
    notes: "No swinging, controlled tempo",
  },
  {
    id: "tricep-dip-001",
    name: "Bench Tricep Dips",
    muscleGroup: "arms",
    equipment: ["bench"],
    difficulty: "beginner",
    goalType: ["hypertrophy", "endurance"],
    defaultSets: 3,
    defaultReps: "12-15",
    restSeconds: 60,
    notes: "Keep elbows close to body",
  },
  {
    id: "hammer-curl-001",
    name: "Hammer Curls",
    muscleGroup: "arms",
    equipment: ["dumbbells"],
    difficulty: "beginner",
    goalType: ["hypertrophy"],
    defaultSets: 3,
    defaultReps: "10-12",
    restSeconds: 60,
    notes: "Neutral grip, targets brachialis",
  },
  // Leg exercises
  {
    id: "squat-001",
    name: "Barbell Back Squat",
    muscleGroup: "legs",
    equipment: ["barbell", "squat_rack"],
    difficulty: "intermediate",
    goalType: ["strength", "hypertrophy", "power"],
    defaultSets: 4,
    defaultReps: "6-8",
    restSeconds: 180,
    notes: "Depth to parallel or below",
  },
  {
    id: "goblet-squat-001",
    name: "Goblet Squat",
    muscleGroup: "legs",
    equipment: ["dumbbells"],
    difficulty: "beginner",
    goalType: ["hypertrophy", "endurance"],
    defaultSets: 3,
    defaultReps: "12-15",
    restSeconds: 60,
    notes: "Hold dumbbell at chest, elbows between knees",
  },
  {
    id: "bodyweight-squat-001",
    name: "Bodyweight Squat",
    muscleGroup: "legs",
    equipment: [],
    difficulty: "beginner",
    goalType: ["endurance"],
    defaultSets: 3,
    defaultReps: "20-25",
    restSeconds: 45,
    notes: "Focus on form and depth",
  },
  {
    id: "lunges-001",
    name: "Walking Lunges",
    muscleGroup: "legs",
    equipment: [],
    difficulty: "beginner",
    goalType: ["hypertrophy", "endurance"],
    defaultSets: 3,
    defaultReps: "12 each leg",
    restSeconds: 60,
    notes: "Keep torso upright",
  },
  // Core exercises
  {
    id: "plank-001",
    name: "Plank Hold",
    muscleGroup: "core",
    equipment: [],
    difficulty: "beginner",
    goalType: ["endurance"],
    defaultSets: 3,
    defaultReps: "30-60 sec",
    restSeconds: 45,
    notes: "Keep body in straight line",
  },
  {
    id: "deadbug-001",
    name: "Dead Bug",
    muscleGroup: "core",
    equipment: [],
    difficulty: "beginner",
    goalType: ["endurance", "strength"],
    defaultSets: 3,
    defaultReps: "10 each side",
    restSeconds: 45,
    notes: "Press lower back into floor",
  },
];

export interface Exercise {
  id: string;
  name: string;
  muscleGroup: string;
  equipment: string[];
  difficulty: "beginner" | "intermediate" | "advanced";
  goalType: string[];
  defaultSets: number;
  defaultReps: string;
  restSeconds: number;
  notes?: string;
}

export interface SearchParams {
  muscleGroup?: string;
  equipment?: string[];
  difficulty?: "beginner" | "intermediate" | "advanced";
  goalType?: "hypertrophy" | "strength" | "endurance" | "power";
  limit?: number;
}

export interface WorkoutExercise {
  id: string;
  name: string;
  muscleGroup: string;
  equipment: string[];
  sets: number;
  reps: string;
  restSeconds: number;
  notes?: string;
}

function searchExercisesImpl(params: SearchParams): WorkoutExercise[] {
  let results = [...EXERCISE_DATABASE];

  // Filter by muscle group
  if (params.muscleGroup) {
    const mg = params.muscleGroup.toLowerCase();
    results = results.filter(
      (e) =>
        e.muscleGroup.toLowerCase() === mg ||
        e.muscleGroup.toLowerCase().includes(mg)
    );
  }

  // Filter by goal type
  if (params.goalType) {
    results = results.filter((e) =>
      e.goalType.includes(params.goalType as string)
    );
  }

  // Filter by difficulty
  if (params.difficulty) {
    results = results.filter((e) => e.difficulty === params.difficulty);
  }

  // Filter by available equipment
  if (params.equipment && params.equipment.length > 0) {
    const availableEquipment = new Set(
      params.equipment.map((e) => e.toLowerCase())
    );
    results = results.filter((e) => {
      // Exercises with no equipment requirement always match
      if (e.equipment.length === 0) return true;
      // Check if all required equipment is available
      return e.equipment.every((req) =>
        availableEquipment.has(req.toLowerCase())
      );
    });
  }

  // Limit results
  const limit = params.limit || 5;
  results = results.slice(0, limit);

  // Transform to WorkoutExercise format
  return results.map((e) => ({
    id: e.id,
    name: e.name,
    muscleGroup: e.muscleGroup,
    equipment: e.equipment,
    sets: e.defaultSets,
    reps: e.defaultReps,
    restSeconds: e.restSeconds,
    notes: e.notes,
  }));
}

// LangChain tool definition
export const searchExercisesTool = tool(
  async (input: SearchParams): Promise<string> => {
    const exercises = searchExercisesImpl(input);
    return JSON.stringify(exercises, null, 2);
  },
  {
    name: "search_exercises",
    description:
      "Search for exercises based on muscle group, equipment, difficulty, and training goal. Returns a list of exercises with sets, reps, and rest times.",
    schema: z.object({
      muscleGroup: z
        .string()
        .optional()
        .describe(
          "Target muscle group: chest, back, shoulders, arms, legs, core"
        ),
      equipment: z
        .array(z.string())
        .optional()
        .describe(
          "Available equipment: barbell, dumbbells, bench, pullup_bar, cable_machine, resistance_bands, squat_rack, dip_bars"
        ),
      difficulty: z
        .enum(["beginner", "intermediate", "advanced"])
        .optional()
        .describe("Exercise difficulty level"),
      goalType: z
        .enum(["hypertrophy", "strength", "endurance", "power"])
        .optional()
        .describe("Training goal"),
      limit: z
        .number()
        .optional()
        .describe("Maximum number of exercises to return (default: 5)"),
    }),
  }
);

// Direct function for testing
export { searchExercisesImpl as searchExercises };
