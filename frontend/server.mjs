import { readFileSync } from "node:fs";
import https from "node:https";
import next from "next";

// A fixed loopback destination, never derived from a request or forwarded header.
const backend = new URL(process.env.CAREFLOW_BACKEND_ORIGIN ?? "https://localhost:8000");
if (backend.protocol !== "https:" || backend.hostname !== "localhost" ||
    backend.username || backend.password || backend.pathname !== "/" ||
    backend.search || backend.hash) {
  throw new Error("CAREFLOW_BACKEND_ORIGIN must be an HTTPS localhost origin.");
}
const ca = readFileSync(process.env.CAREFLOW_BACKEND_CA);
const agent = new https.Agent({ ca, keepAlive: true, rejectUnauthorized: true });
const identifier = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
const routes = [
  [/^\/auth\/(csrf|me)$/, ["GET"]],
  [/^\/auth\/(login|logout)$/, ["POST"]],
  [/^\/chat\/disclosure$/, ["GET"]],
  [/^\/conversations$/, ["POST"]],
  [new RegExp(`^/conversations/${identifier}$`), ["GET", "DELETE"]],
  [new RegExp(`^/conversations/${identifier}/turns$`), ["POST"]],
];

function reject(response, status, code) {
  response.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" });
  response.end(JSON.stringify({ code, message: "Request unavailable." }));
}

async function proxy(request, response) {
  const path = request.url.slice(4);
  const route = routes.find(([pattern]) => pattern.test(path));
  if (!route) return reject(response, 404, "NOT_FOUND");
  if (!route[1].includes(request.method)) return reject(response, 405, "METHOD_NOT_ALLOWED");
  const parts = [];
  let bytes = 0;
  for await (const part of request) {
    bytes += part.length;
    if (bytes > 4096) return reject(response, 413, "REQUEST_TOO_LARGE");
    parts.push(part);
  }
  const body = Buffer.concat(parts);
  const headers = {};
  for (const name of ["origin", "cookie", "x-csrf-token", "content-type", "sec-fetch-site", "sec-fetch-mode"]) {
    if (request.headers[name] !== undefined) headers[name] = request.headers[name];
  }
  if (body.length) headers["content-length"] = String(body.length);
  // No forwarded client identity, redirects, body logs or Next/fetch cache.
  const upstream = https.request(new URL(path, backend), {
    method: request.method, headers, agent, timeout: 35000,
  }, (incoming) => {
    if (incoming.statusCode >= 300 && incoming.statusCode < 400) {
      incoming.resume();
      return reject(response, 502, "API_UNAVAILABLE");
    }
    const outgoing = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" };
    for (const name of ["content-type", "set-cookie", "retry-after"]) {
      if (incoming.headers[name] !== undefined) outgoing[name] = incoming.headers[name];
    }
    response.writeHead(incoming.statusCode ?? 502, outgoing);
    incoming.pipe(response);
    incoming.on("error", () => response.destroy());
  });
  upstream.on("timeout", () => upstream.destroy());
  upstream.on("error", () => {
    if (!response.headersSent) reject(response, 502, "API_UNAVAILABLE");
    else response.destroy();
  });
  response.on("close", () => upstream.destroy());
  upstream.end(body);
}

const application = next({ dev: !process.argv.includes("--production"), hostname: "localhost", port: Number(process.env.PORT ?? 3000) });
await application.prepare();
const handle = application.getRequestHandler();
const server = https.createServer({
  cert: readFileSync(process.env.CAREFLOW_TLS_CERT),
  key: readFileSync(process.env.CAREFLOW_TLS_KEY),
}, (request, response) => {
  if (request.url.startsWith("/api/")) {
    proxy(request, response).catch(() => {
      if (!response.headersSent) reject(response, 502, "API_UNAVAILABLE");
      else response.destroy();
    });
  } else {
    response.setHeader("Cache-Control", "no-store");
    handle(request, response);
  }
});
server.requestTimeout = 40000;
server.headersTimeout = 10000;
server.listen(Number(process.env.PORT ?? 3000), "127.0.0.1", () => {
  console.log("CareFlow HTTPS frontend ready.");
});
