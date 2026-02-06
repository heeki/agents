/**
 * A2A JSON-RPC Server for Biomechanics Lab Agent
 *
 * Implements the Google A2A protocol with streaming support.
 * All A2A methods are handled at POST / (root endpoint).
 */

import express, { Request, Response } from "express";
import { v4 as uuidv4 } from "uuid";
import {
  AgentCard,
  Task,
  TaskStatus,
  JsonRpcRequest,
  JsonRpcResponse,
  ErrorCode,
  getTextFromMessage,
  createTextPart,
  createDataPart,
  createMessage,
  createSuccessResponse,
  createErrorResponse,
} from "./types.js";
import { generateWorkout, streamWorkout, WorkoutRequest } from "../agent.js";

// In-memory task store
const tasks = new Map<string, Task>();

// Agent configuration
const AGENT_CARD: AgentCard = {
  name: "biomechanics-lab",
  description:
    "Expert in exercise physiology and strength & conditioning. Provides structured workout routines based on physiological goals.",
  url: process.env.AGENT_URL || "http://localhost:8082",
  version: "1.0.0",
  capabilities: {
    streaming: true,
    pushNotifications: false,
  },
  skills: [
    {
      id: "create-workout",
      name: "Create Workout Plan",
      description:
        "Creates a structured workout plan based on training goals, available equipment, and time constraints",
    },
    {
      id: "modify-workout",
      name: "Modify Workout Plan",
      description:
        "Adjusts an existing workout plan to accommodate new constraints while maintaining training stimulus",
    },
  ],
};

export function createA2AServer() {
  const app = express();
  app.use(express.json());

  // Root GET for basic health check
  app.get("/", (_req: Request, res: Response) => {
    res.json({ status: "healthy", agent: "biomechanics-lab" });
  });

  // Root POST endpoint for all A2A JSON-RPC requests
  app.post("/", async (req: Request, res: Response) => {
    const rpcRequest = req.body as JsonRpcRequest;

    // Handle streaming requests
    if (rpcRequest.method === "tasks/sendSubscribe") {
      res.setHeader("Content-Type", "text/event-stream");
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("Connection", "keep-alive");

      try {
        await handleStreamingRequest(rpcRequest, res);
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : "Unknown error";
        res.write(
          `event: error\ndata: ${JSON.stringify({ error: errorMessage })}\n\n`
        );
      } finally {
        res.end();
      }
      return;
    }

    // Handle non-streaming requests
    try {
      const response = await handleRpcRequest(rpcRequest);
      res.json(response);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      res.json(
        createErrorResponse(
          rpcRequest.id,
          ErrorCode.INTERNAL_ERROR,
          errorMessage
        )
      );
    }
  });

  // Agent Card endpoint
  app.get("/.well-known/agent.json", (_req: Request, res: Response) => {
    res.json(AGENT_CARD);
  });

  // Health check
  app.get("/health", (_req: Request, res: Response) => {
    res.json({ status: "healthy" });
  });

  // Ping endpoint for AgentCore health checks
  app.get("/ping", (_req: Request, res: Response) => {
    res.json({ status: "ok" });
  });

  return app;
}

async function handleRpcRequest(
  request: JsonRpcRequest
): Promise<JsonRpcResponse> {
  switch (request.method) {
    case "tasks/send":
      return handleTaskSend(request);
    case "tasks/get":
      return handleTaskGet(request);
    case "tasks/cancel":
      return handleTaskCancel(request);
    default:
      return createErrorResponse(
        request.id,
        ErrorCode.METHOD_NOT_FOUND,
        `Method not found: ${request.method}`
      );
  }
}

async function handleTaskSend(
  request: JsonRpcRequest
): Promise<JsonRpcResponse> {
  const params = request.params as { task: Task };
  const task = params.task;

  // Store the task
  tasks.set(task.id, { ...task, status: TaskStatus.WORKING });

  // Extract the workout request from the message
  const messageText = getTextFromMessage(task.message);
  const workoutRequest = parseWorkoutRequest(messageText, task.message);

  try {
    // Generate the workout
    const workoutResponse = await generateWorkout(workoutRequest);

    // Create the result message
    const resultMessage = createMessage("assistant", [
      createTextPart(
        `Here is your ${workoutResponse.workout.name} workout plan (${workoutResponse.workout.estimatedDuration} minutes):`
      ),
      createDataPart({ workout: workoutResponse.workout }),
    ]);

    // Update the task
    const completedTask: Task = {
      ...task,
      status: TaskStatus.COMPLETED,
      result: resultMessage,
    };
    tasks.set(task.id, completedTask);

    return createSuccessResponse(request.id, {
      taskId: task.id,
      status: TaskStatus.COMPLETED,
      result: resultMessage,
    });
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Failed to generate workout";

    const failedTask: Task = {
      ...task,
      status: TaskStatus.FAILED,
    };
    tasks.set(task.id, failedTask);

    return createErrorResponse(
      request.id,
      ErrorCode.INTERNAL_ERROR,
      errorMessage
    );
  }
}

async function handleTaskGet(
  request: JsonRpcRequest
): Promise<JsonRpcResponse> {
  const params = request.params as { taskId: string };
  const task = tasks.get(params.taskId);

  if (!task) {
    return createErrorResponse(
      request.id,
      ErrorCode.TASK_NOT_FOUND,
      `Task not found: ${params.taskId}`
    );
  }

  return createSuccessResponse(request.id, {
    taskId: task.id,
    status: task.status,
    result: task.result,
  });
}

async function handleTaskCancel(
  request: JsonRpcRequest
): Promise<JsonRpcResponse> {
  const params = request.params as { taskId: string };
  const task = tasks.get(params.taskId);

  if (!task) {
    return createErrorResponse(
      request.id,
      ErrorCode.TASK_NOT_FOUND,
      `Task not found: ${params.taskId}`
    );
  }

  const canceledTask: Task = {
    ...task,
    status: TaskStatus.CANCELED,
  };
  tasks.set(params.taskId, canceledTask);

  return createSuccessResponse(request.id, {
    taskId: task.id,
    status: TaskStatus.CANCELED,
  });
}

async function handleStreamingRequest(
  request: JsonRpcRequest,
  res: Response
): Promise<void> {
  const params = request.params as { task: Task };
  const task = params.task;

  // Send initial status
  res.write(
    `event: task-status\ndata: ${JSON.stringify({
      taskId: task.id,
      status: TaskStatus.WORKING,
      message: "Analyzing workout requirements...",
    })}\n\n`
  );

  const messageText = getTextFromMessage(task.message);
  const workoutRequest = parseWorkoutRequest(messageText, task.message);

  // Send progress update
  res.write(
    `event: task-status\ndata: ${JSON.stringify({
      taskId: task.id,
      status: TaskStatus.WORKING,
      message: "Searching exercise database...",
    })}\n\n`
  );

  try {
    let fullContent = "";

    // Stream the workout generation
    for await (const chunk of streamWorkout(workoutRequest)) {
      fullContent += chunk;
      res.write(
        `event: task-chunk\ndata: ${JSON.stringify({
          taskId: task.id,
          chunk,
        })}\n\n`
      );
    }

    // Parse and send final result
    const jsonMatch = fullContent.match(/\{[\s\S]*"workout"[\s\S]*\}/);
    let workoutData = null;
    if (jsonMatch) {
      try {
        workoutData = JSON.parse(jsonMatch[0]);
      } catch {
        // Continue with text-only response
      }
    }

    const resultMessage = createMessage("assistant", [
      createTextPart(fullContent),
      ...(workoutData ? [createDataPart(workoutData)] : []),
    ]);

    res.write(
      `event: task-result\ndata: ${JSON.stringify({
        taskId: task.id,
        status: TaskStatus.COMPLETED,
        result: resultMessage,
      })}\n\n`
    );
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Failed to generate workout";
    res.write(
      `event: task-error\ndata: ${JSON.stringify({
        taskId: task.id,
        status: TaskStatus.FAILED,
        error: errorMessage,
      })}\n\n`
    );
  }
}

function parseWorkoutRequest(
  messageText: string,
  message: { parts: Array<{ type: string; data?: Record<string, unknown> }> }
): WorkoutRequest {
  // Check for structured data in message parts
  const dataPart = message.parts.find((p) => p.type === "data");
  if (dataPart?.data) {
    const data = dataPart.data as Record<string, unknown>;
    return {
      goal: (data.goal as string) || messageText,
      constraints: data.constraints as WorkoutRequest["constraints"],
      isCompromise: data.isCompromise as boolean,
    };
  }

  // Parse from text
  const isCompromise =
    messageText.toLowerCase().includes("compromise") ||
    messageText.toLowerCase().includes("adjust") ||
    messageText.toLowerCase().includes("modify") ||
    messageText.toLowerCase().includes("alternative");

  // Extract duration if mentioned
  const durationMatch = messageText.match(/(\d+)\s*min/i);
  const duration = durationMatch ? parseInt(durationMatch[1]) : undefined;

  // Extract equipment mentions
  const equipmentKeywords = [
    "dumbbell",
    "barbell",
    "bodyweight",
    "resistance band",
    "kettlebell",
    "cable",
    "machine",
  ];
  const equipment: string[] = [];
  for (const keyword of equipmentKeywords) {
    if (messageText.toLowerCase().includes(keyword)) {
      equipment.push(keyword.replace(" ", "_"));
    }
  }
  if (
    messageText.toLowerCase().includes("bodyweight") ||
    messageText.toLowerCase().includes("no equipment")
  ) {
    equipment.length = 0; // Empty means bodyweight only
  }

  // Extract muscle groups
  const muscleGroups: string[] = [];
  const muscleKeywords = [
    "chest",
    "back",
    "shoulders",
    "arms",
    "legs",
    "core",
    "upper body",
    "lower body",
  ];
  for (const keyword of muscleKeywords) {
    if (messageText.toLowerCase().includes(keyword)) {
      muscleGroups.push(keyword);
    }
  }

  return {
    goal: messageText,
    constraints: {
      duration,
      equipment: equipment.length > 0 ? equipment : undefined,
      muscleGroups: muscleGroups.length > 0 ? muscleGroups : undefined,
    },
    isCompromise,
  };
}
