#!/usr/bin/env node
/**
 * MCP HTTP Server: AI agent <-> LM Studio vision model (HTTP transport).
 * Bypasses Windows stdio pipe issues by using HTTP.
 */
const http = require('http');
const { readFileSync, existsSync } = require('fs');
const { resolve, isAbsolute } = require('path');
const { networkInterfaces } = require('os');

const PORT = parseInt(process.env.MCP_PORT || '3456', 10);
const LM_PORT = parseInt(process.env.LM_STUDIO_PORT || '1234', 10);
const MAX_TOKENS = parseInt(process.env.MAX_TOKENS || '8192', 10);
const TIMEOUT = 60;

let _lmBase = null;
let _model = process.env.VISION_MODEL || '';

async function scanLmStudio() {
  const envUrl = (process.env.MODEL_BASE_URL || '').trim();
  if (envUrl) {
    try {
      const r = await fetch(envUrl.replace(/\/+$/, '') + '/v1/models', { signal: AbortSignal.timeout(2000) });
      if (r.ok) return envUrl.replace(/\/+$/, '');
    } catch {}
  }
  for (const base of ['http://127.0.0.1', 'http://localhost']) {
    try {
      const r = await fetch(base + ':' + LM_PORT + '/v1/models', { signal: AbortSignal.timeout(2000) });
      if (r.ok) return base + ':' + LM_PORT;
    } catch {}
  }
  const nets = networkInterfaces();
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === 'IPv4' && !net.internal) {
        try {
          const r = await fetch('http://' + net.address + ':' + LM_PORT + '/v1/models', { signal: AbortSignal.timeout(2000) });
          if (r.ok) return 'http://' + net.address + ':' + LM_PORT;
        } catch {}
      }
    }
  }
  return null;
}

async function handleRequest(body) {
  const method = body.method;
  const id = body.id;
  const params = body.params || {};

  if (method === 'notifications/initialized') {
    return { jsonrpc: '2.0' };
  }

  if (method === 'ping') {
    return { jsonrpc: '2.0', id, result: {} };
  }

  if (method === 'initialize') {
    return {
      jsonrpc: '2.0', id,
      result: {
        protocolVersion: '2024-11-05',
        capabilities: { tools: {} },
        serverInfo: { name: 'vision-bridge-http', version: '3.0.0' }
      }
    };
  }

  if (method === 'tools/list') {
    return {
      jsonrpc: '2.0', id,
      result: {
        tools: [{
          name: 'read_image_with_model',
          description: 'Read an image using a local LM Studio vision model',
          inputSchema: {
            type: 'object',
            properties: {
              image_path: { type: 'string', description: 'Path to the image file' },
              prompt: { type: 'string', description: 'Instruction for the vision model' }
            },
            required: ['image_path', 'prompt']
          }
        }]
      }
    };
  }

  if (method === 'tools/call') {
    const name = params.name;
    const args = params.arguments || {};

    if (name !== 'read_image_with_model') {
      return { jsonrpc: '2.0', id, error: { code: -32601, message: 'Unknown tool: ' + name } };
    }

    const imagePath = args.image_path || '';
    const prompt = args.prompt || 'Describe this image in detail.';

    if (!imagePath) {
      return { jsonrpc: '2.0', id, error: { code: -32000, message: 'Missing image_path' } };
    }

    const absPath = isAbsolute(imagePath) ? imagePath : resolve(process.cwd(), imagePath);
    if (!existsSync(absPath)) {
      return { jsonrpc: '2.0', id, result: { isError: true, content: [{ type: 'text', text: 'File not found: ' + absPath }] } };
    }

    // Find LM Studio
    if (!_lmBase) _lmBase = await scanLmStudio();
    if (!_lmBase) {
      return { jsonrpc: '2.0', id, result: { isError: true, content: [{ type: 'text', text: 'LM Studio not found.' }] } };
    }

    // Use pre-set model or auto-detect (DON'T change the model - user manually selected it)
    if (!_model) {
      try {
        const r = await fetch(_lmBase + '/v1/models', { signal: AbortSignal.timeout(5000) });
        if (r.ok) {
          const d = await r.json();
          const all = (d.data || []).map(x => x.id);
          const thinking = all.filter(m => m.toLowerCase().includes("thinking"));
          const vision = all.filter(m => !m.toLowerCase().includes("embed") && !thinking.includes(m));
          _model = (thinking.concat(vision))[0] || (all[0] || "");
        }
      } catch {}
    }
    if (!_model) {
      return { jsonrpc: '2.0', id, result: { isError: true, content: [{ type: 'text', text: 'No vision model loaded.' }] } };
    }

    // Read image and call LM Studio
    const data = readFileSync(absPath);
    const b64 = data.toString('base64');

    const payload = {
      model: _model,
      max_tokens: MAX_TOKENS,
      temperature: 0.01,
      messages: [{
        role: 'user',
        content: [
          { type: 'image_url', image_url: { url: 'data:image/png;base64,' + b64 } },
          { type: 'text', text: prompt }
        ]
      }]
    };

    let lastErr = '';
    for (let i = 0; i < 3; i++) {
      try {
        const r = await fetch(_lmBase + '/v1/chat/completions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal: AbortSignal.timeout(TIMEOUT * 1000)
        });
        if (!r.ok) {
          lastErr = 'LM Studio HTTP ' + r.status + ': ' + (await r.text());
          continue;
        }
        const resp = await r.json();
        const text = (resp.choices && resp.choices[0] && resp.choices[0].message && resp.choices[0].message.content || '').trim() || '(empty)';
        return { jsonrpc: '2.0', id, result: { content: [{ type: 'text', text }] } };
      } catch (e) {
        lastErr = 'Error: ' + e.message;
        if (i < 2) await new Promise(r => setTimeout(r, 1000));
      }
    }
    return { jsonrpc: '2.0', id, result: { isError: true, content: [{ type: 'text', text: lastErr }] } };
  }

  return { jsonrpc: '2.0', id, error: { code: -32601, message: 'Unknown method: ' + method } };
}

// HTTP server
const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', 'application/json');

  if (req.method !== 'POST') {
    res.statusCode = 405;
    res.end(JSON.stringify({ error: 'Method not allowed' }));
    return;
  }

  let body = '';
  req.on('data', chunk => body += chunk.toString());
  req.on('end', async () => {
    try {
      const msg = JSON.parse(body);
      const result = await handleRequest(msg);
      res.end(JSON.stringify(result));
    } catch (e) {
      res.statusCode = 400;
      res.end(JSON.stringify({ jsonrpc: '2.0', error: { code: -32700, message: 'Parse error: ' + e.message } }));
    }
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('MCP HTTP server listening on http://127.0.0.1:' + PORT);
});
