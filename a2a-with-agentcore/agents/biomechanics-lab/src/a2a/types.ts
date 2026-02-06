/**
 * A2A Protocol Type Definitions.
 *
 * Implements the Google A2A (Agent-to-Agent) protocol types for
 * JSON-RPC based agent communication.
 */

export enum TaskStatus {
  PENDING = "pending",
  WORKING = "working",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELED = "canceled",
}

export interface MessagePart {
  type: "text" | "data";
  text?: string;
  data?: Record<string, unknown>;
}

export interface Message {
  role: "user" | "assistant";
  parts: MessagePart[];
}

export interface Task {
  id: string;
  message: Message;
  status?: TaskStatus;
  result?: Message;
}

export interface JsonRpcRequest {
  jsonrpc: string;
  id: string;
  method: string;
  params?: Record<string, unknown>;
}

export interface JsonRpcResponse {
  jsonrpc: string;
  id: string;
  result?: Record<string, unknown>;
  error?: JsonRpcError;
}

export interface JsonRpcError {
  code: number;
  message: string;
  data?: Record<string, unknown>;
}

export const ErrorCode = {
  PARSE_ERROR: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
  TASK_NOT_FOUND: -32000,
  AGENT_UNAVAILABLE: -32001,
  TASK_CANCELED: -32002,
} as const;

export interface AgentSkill {
  id: string;
  name: string;
  description: string;
}

export interface AgentCapabilities {
  streaming: boolean;
  pushNotifications: boolean;
}

export interface AgentCard {
  name: string;
  description: string;
  url: string;
  version: string;
  capabilities: AgentCapabilities;
  skills: AgentSkill[];
}

// Helper functions
export function createTextPart(text: string): MessagePart {
  return { type: "text", text };
}

export function createDataPart(data: Record<string, unknown>): MessagePart {
  return { type: "data", data };
}

export function createMessage(
  role: "user" | "assistant",
  parts: MessagePart[]
): Message {
  return { role, parts };
}

export function getTextFromMessage(message: Message): string {
  return message.parts
    .filter((p) => p.type === "text" && p.text)
    .map((p) => p.text)
    .join(" ");
}

export function createSuccessResponse(
  id: string,
  result: Record<string, unknown>
): JsonRpcResponse {
  return {
    jsonrpc: "2.0",
    id,
    result,
  };
}

export function createErrorResponse(
  id: string,
  code: number,
  message: string,
  data?: Record<string, unknown>
): JsonRpcResponse {
  return {
    jsonrpc: "2.0",
    id,
    error: { code, message, data },
  };
}
