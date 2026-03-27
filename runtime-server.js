#!/usr/bin/env node

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const ROOT_DIR = __dirname;
const DEFAULT_PORT = Number.parseInt(process.env.PORT || '3000', 10);

const CONTENT_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.csv': 'text/csv; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
};

// Extensionless and clean-URL aliases for deployment-style deep links.
// Note: '/' is intentionally absent — it is handled by an explicit 302
// redirect in the request handler. Adding it here would serve a 200
// instead and silently break redirect semantics.
const ROUTE_ALIASES = new Map([
  ['/cards/rookies', '/cards/rookies/index.html'],
  ['/cards/rookies/board', '/cards/rookies/board/index.html'],
  ['/cards/rookies/player', '/cards/rookies/player.html'],
  ['/cards/rookies/compare', '/cards/rookies/compare/index.html'],
]);

function sendJson(response, statusCode, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  });
  response.end(body);
}

function sendText(response, statusCode, body) {
  response.writeHead(statusCode, {
    'Content-Type': 'text/plain; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
  });
  response.end(body);
}

function resolveStaticPath(requestPath) {
  let decodedPath;
  try {
    decodedPath = decodeURIComponent(requestPath);
  } catch {
    return null;
  }

  const decodedSegments = decodedPath.split('/').filter(Boolean);
  if (decodedSegments.includes('..')) {
    return null;
  }

  const normalizedPath = path.posix.normalize(decodedPath);
  const relativePath = normalizedPath.startsWith('/') ? normalizedPath.slice(1) : normalizedPath;
  const absolutePath = path.resolve(ROOT_DIR, relativePath);

  if (!absolutePath.startsWith(ROOT_DIR)) {
    return null;
  }

  return absolutePath;
}

function toPublicPath(inputPath) {
  if (ROUTE_ALIASES.has(inputPath)) {
    return ROUTE_ALIASES.get(inputPath);
  }

  return inputPath;
}

function resolveFilePath(requestPath, callback) {
  const publicPath = toPublicPath(requestPath);
  const targetPath = resolveStaticPath(publicPath);

  if (!targetPath) {
    callback(new Error('BAD_REQUEST'));
    return;
  }

  fs.stat(targetPath, (error, stats) => {
    if (!error && stats.isDirectory()) {
      callback(null, path.join(targetPath, 'index.html'));
      return;
    }

    callback(null, targetPath);
  });
}

function writeFileHeaders(response, filePath, size) {
  const extension = path.extname(filePath).toLowerCase();
  const contentType = CONTENT_TYPES[extension] || 'application/octet-stream';

  response.writeHead(200, {
    'Content-Type': contentType,
    'Content-Length': size,
    'Cache-Control': extension === '.html' ? 'no-cache' : 'public, max-age=300',
  });
}

function serveFile(filePath, response) {
  fs.stat(filePath, (statError, stats) => {
    if (statError || !stats.isFile()) {
      sendText(response, 404, 'Not found');
      return;
    }

    writeFileHeaders(response, filePath, stats.size);

    const stream = fs.createReadStream(filePath);
    stream.on('error', () => sendText(response, 500, 'Failed to read file'));
    stream.pipe(response);
  });
}

function createServer() {
  return http.createServer((request, response) => {
    const url = new URL(request.url || '/', `http://${request.headers.host || 'localhost'}`);
    const requestPath = url.pathname;

    if (request.method !== 'GET' && request.method !== 'HEAD') {
      sendText(response, 405, 'Method not allowed');
      return;
    }

    if (requestPath === '/health') {
      const payload = {
        status: 'ok',
        service: 'tiber-rookies',
        mode: 'standalone-static-lab',
      };

      if (request.method === 'HEAD') {
        response.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        response.end();
        return;
      }

      sendJson(response, 200, payload);
      return;
    }

    if (requestPath === '/') {
      response.writeHead(302, { Location: '/cards/rookies/board/index.html' });
      response.end();
      return;
    }

    resolveFilePath(requestPath, (resolveError, filePath) => {
      if (resolveError) {
        sendText(response, 400, 'Bad request');
        return;
      }

      if (request.method === 'HEAD') {
        fs.stat(filePath, (error, stats) => {
          if (error || !stats.isFile()) {
            response.writeHead(404);
            response.end();
            return;
          }

          writeFileHeaders(response, filePath, stats.size);
          response.end();
        });
        return;
      }

      serveFile(filePath, response);
    });
  });
}

function startServer(port = DEFAULT_PORT) {
  const server = createServer();

  server.listen(port, () => {
    const address = server.address();
    const boundPort = typeof address === 'object' && address ? address.port : port;
    // eslint-disable-next-line no-console
    console.log(`TIBER-Rookies static lab listening on port ${boundPort}`);
  });

  return server;
}

if (require.main === module) {
  startServer();
}

module.exports = {
  createServer,
  startServer,
};
