/**
 * Biomechanics Lab Agent - Main Entry Point
 *
 * A2A-compliant agent for exercise physiology and workout planning.
 */

import { createA2AServer } from "./a2a/server.js";

const PORT = parseInt(process.env.BIOMECHANICS_PORT || "8082");

async function main() {
  const app = createA2AServer();

  app.listen(PORT, () => {
    console.log(`Biomechanics Lab Agent running on port ${PORT}`);
    console.log(`A2A Endpoint: http://localhost:${PORT}/`);
    console.log(`Agent Card: http://localhost:${PORT}/.well-known/agent.json`);
    console.log(`Health Check: http://localhost:${PORT}/health`);
  });
}

main().catch(console.error);
