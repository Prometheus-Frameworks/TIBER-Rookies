#!/usr/bin/env node

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const ROOT_DIR = __dirname;
const PORT = Number.parseInt(process.env.PORT || '3000', 10);

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

function serveFile(filePath, response) {
  fs.stat(filePath, (statError, stats) => {
    if (statError || !stats.isFile()) {
      sendText(response, 404, 'Not found');
      return;
    }

    const extension = path.extname(filePath).toLowerCase();
    const contentType = CONTENT_TYPES[extension] || 'application/octet-stream';

    response.writeHead(200, {
      'Content-Type': contentType,
      'Content-Length': stats.size,
      'Cache-Control': extension === '.html' ? 'no-cache' : 'public, max-age=300',
    });

    const stream = fs.createReadStream(filePath);
    stream.on('error', () => sendText(response, 500, 'Failed to read file'));
    stream.pipe(response);
  });
}

function resolveStaticPath(requestPath) {
  const decodedPath = decodeURIComponent(requestPath);
  const normalizedPath = path.posix.normalize(decodedPath);
  const relativePath = normalizedPath.startsWith('/') ? normalizedPath.slice(1) : normalizedPath;
  const absolutePath = path.resolve(ROOT_DIR, relativePath);

  if (!absolutePath.startsWith(ROOT_DIR)) {
    return null;
  }

  return absolutePath;
}

const server = http.createServer((request, response) => {
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

  const targetPath = resolveStaticPath(requestPath);
  if (!targetPath) {
    sendText(response, 400, 'Bad request');
    return;
  }

  let filePath = targetPath;
  if (requestPath.endsWith('/')) {
    filePath = path.join(targetPath, 'index.html');
  }

  if (request.method === 'HEAD') {
    fs.stat(filePath, (error, stats) => {
      if (error || !stats.isFile()) {
        response.writeHead(404);
      } else {
        response.writeHead(200);
      }
      response.end();
    });
    return;
  }

  serveFile(filePath, response);
});

server.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`TIBER-Rookies static lab listening on port ${PORT}`);
});
