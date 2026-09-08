import fs from 'fs';
let content = fs.readFileSync('server.js', 'utf8');

const regex = /app\.(post|put|delete)\("([^"]+)",\s*([^)]*?)\s*=>/g;
content = content.replace(regex, (match, method, endpoint, middlewaresAndReqRes) => {
  if (endpoint.includes('iyzico/callback') || endpoint === '/api/auth/login' || endpoint === '/api/auth/oauth/callback') {
    return match;
  }

  if (match.includes('csrfMiddleware')) {
    return match;
  }

  const args = middlewaresAndReqRes.split(',').map(s => s.trim());

  const reqResIndex = args.findIndex(a => a.startsWith('(req') || a.startsWith('async (req'));

  if (reqResIndex !== -1) {
      args.splice(reqResIndex, 0, 'csrfMiddleware');
  } else {
      console.log("Could not find req, res for " + endpoint);
  }

  return `app.${method}("${endpoint}", ${args.join(', ')} =>`;
});

content = content.replace(
  'app.use("/graphql", authRateLimiter, authMiddleware, createHandler({',
  'app.use("/graphql", authRateLimiter, authMiddleware, csrfMiddleware, createHandler({'
);

fs.writeFileSync('server.js', content);
