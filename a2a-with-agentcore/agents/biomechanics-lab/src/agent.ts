/**
 * Biomechanics Lab Agent - LangGraph Implementation
 *
 * An exercise physiology expert that provides structured workout routines
 * based on specific physiological goals.
 */

import { createReactAgent } from "@langchain/langgraph/prebuilt";
import type { CompiledStateGraph } from "@langchain/langgraph";
import { ChatBedrockConverse } from "@langchain/aws";
import { HumanMessage, AIMessage } from "@langchain/core/messages";
import { searchExercisesTool } from "./tools/searchExercises.js";

const SYSTEM_PROMPT = `You are an expert in exercise physiology and strength & conditioning.

Objective: Provide structured workout routines based on specific physiological goals (hypertrophy, endurance, power, strength).

Instructions:
1. When you receive a goal from the Orchestrator, analyze what type of workout is needed
2. Use the search_exercises tool to find appropriate exercises
3. If muscle group is specified, search for that specific group
4. If equipment constraints are mentioned, include them in the search
5. Return a structured JSON workout plan

If the Orchestrator asks for a "compromise" or adjustment:
- Prioritize intensity over duration to maintain the training stimulus
- Suggest exercise modifications that achieve similar muscle activation
- Reduce volume while maintaining exercise quality

Your response should always include a structured workout in this format:
{
  "workout": {
    "name": "Workout Name",
    "estimatedDuration": 45,
    "exercises": [
      {
        "id": "exercise-id",
        "name": "Exercise Name",
        "muscleGroup": "target-muscle",
        "equipment": ["required", "equipment"],
        "sets": 4,
        "reps": "8-12",
        "restSeconds": 90,
        "notes": "Form cues"
      }
    ]
  }
}

Tone: Clinical, data-driven, and technical.`;

// Create the LangGraph agent
export function createBiomechanicsAgent(): CompiledStateGraph<any, any, any> {
  const model = new ChatBedrockConverse({
    model: process.env.MODEL_ID || "us.amazon.nova-lite-v1:0",
    region: process.env.AWS_REGION || "us-east-1",
    maxTokens: 2000,
    temperature: 0.3,
  });

  const agent = createReactAgent({
    llm: model,
    tools: [searchExercisesTool],
  });

  return agent;
}

export interface WorkoutRequest {
  goal: string;
  constraints?: {
    duration?: number;
    equipment?: string[];
    difficulty?: "beginner" | "intermediate" | "advanced";
    muscleGroups?: string[];
  };
  isCompromise?: boolean;
}

export interface WorkoutResponse {
  workout: {
    name: string;
    estimatedDuration: number;
    exercises: Array<{
      id: string;
      name: string;
      muscleGroup: string;
      equipment: string[];
      sets: number;
      reps: string;
      restSeconds: number;
      notes?: string;
    }>;
  };
  reasoning?: string;
}

export async function generateWorkout(
  request: WorkoutRequest
): Promise<WorkoutResponse> {
  const agent = createBiomechanicsAgent();

  // Build the prompt based on the request
  let prompt = `Create a workout plan for the following goal: ${request.goal}`;

  if (request.constraints) {
    if (request.constraints.duration) {
      prompt += `\nTime available: ${request.constraints.duration} minutes`;
    }
    if (request.constraints.equipment && request.constraints.equipment.length > 0) {
      prompt += `\nAvailable equipment: ${request.constraints.equipment.join(", ")}`;
    }
    if (request.constraints.difficulty) {
      prompt += `\nDifficulty level: ${request.constraints.difficulty}`;
    }
    if (request.constraints.muscleGroups && request.constraints.muscleGroups.length > 0) {
      prompt += `\nTarget muscle groups: ${request.constraints.muscleGroups.join(", ")}`;
    }
  }

  if (request.isCompromise) {
    prompt += `\n\nIMPORTANT: This is a compromise request. The original workout couldn't be done due to constraints. Prioritize intensity over duration. Find alternatives that work within the given equipment and time constraints.`;
  }

  prompt += `\n\nUse the search_exercises tool to find appropriate exercises, then return a structured workout plan as JSON.`;

  // Run the agent
  const result = await agent.invoke({
    messages: [
      {
        role: "system",
        content: SYSTEM_PROMPT,
      },
      new HumanMessage(prompt),
    ],
  });

  // Extract the final response
  const lastMessage = result.messages[result.messages.length - 1];
  let responseText = "";

  if (lastMessage instanceof AIMessage) {
    if (typeof lastMessage.content === "string") {
      responseText = lastMessage.content;
    } else if (Array.isArray(lastMessage.content)) {
      responseText = lastMessage.content
        .filter((part): part is { type: "text"; text: string } =>
          typeof part === "object" && part.type === "text"
        )
        .map((part) => part.text)
        .join("");
    }
  }

  // Parse the workout from the response
  const jsonMatch = responseText.match(/\{[\s\S]*"workout"[\s\S]*\}/);
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[0]);
      return parsed as WorkoutResponse;
    } catch {
      // If JSON parsing fails, create a default response
    }
  }

  // Fallback response if parsing fails
  return {
    workout: {
      name: "Custom Workout",
      estimatedDuration: request.constraints?.duration || 45,
      exercises: [],
    },
    reasoning: responseText,
  };
}

// For streaming responses
export async function* streamWorkout(
  request: WorkoutRequest
): AsyncGenerator<string> {
  const agent = createBiomechanicsAgent();

  let prompt = `Create a workout plan for: ${request.goal}`;
  if (request.constraints) {
    if (request.constraints.duration) {
      prompt += ` (${request.constraints.duration} min)`;
    }
    if (request.constraints.equipment) {
      prompt += ` using ${request.constraints.equipment.join(", ")}`;
    }
  }

  if (request.isCompromise) {
    prompt += ". This is a compromise request - prioritize intensity over duration.";
  }

  const stream = await agent.stream(
    {
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        new HumanMessage(prompt),
      ],
    },
    { streamMode: "messages" }
  );

  for await (const [message] of stream) {
    const m = message as AIMessage;
    if (m.getType?.() === "ai" && !(m as any).tool_call_chunks?.length) {
      if (typeof m.content === "string") {
        yield m.content;
      } else if (Array.isArray(m.content)) {
        for (const part of m.content) {
          if (typeof part === "object" && part.type === "text") {
            yield part.text;
          }
        }
      }
    }
  }
}
