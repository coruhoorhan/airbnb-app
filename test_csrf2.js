import fs from 'fs';
const code = fs.readFileSync('server.js', 'utf8');
const lines = code.split('\n');
for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  if (line.match(/app\.(post|put|delete)\(/)) {
    if (!line.includes('csrfMiddleware') && !line.includes('iyzico/callback')) {
      console.log(`Missing csrf: ${line.trim()}`);
    }
  }
}
