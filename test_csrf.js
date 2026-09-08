import fs from 'fs';
const code = fs.readFileSync('server.js', 'utf8');

const regex = /app\.(post|put|delete)\("([^"]+)",\s*([^)]*)\s*=>/g;
let match;
while ((match = regex.exec(code)) !== null) {
  const method = match[1];
  const endpoint = match[2];
  const middlewares = match[3];
  if (!middlewares.includes('csrfMiddleware') && !endpoint.includes('iyzico/callback')) {
    console.log(`Missing csrfMiddleware: app.${method}("${endpoint}") - ${middlewares.trim()}`);
  }
}
