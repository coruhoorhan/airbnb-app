import fs from 'fs';

let content = fs.readFileSync('server.js', 'utf8');

// Update login to generate and set csrf
content = content.replace(
  '  res.cookie("token", token, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });\n  res.json({ success: true, token, user });',
  '  res.cookie("token", token, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });\n  const csrfToken = generateCsrfToken();\n  res.cookie("_csrf_secret", csrfToken, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });\n  res.setHeader("x-csrf-token", csrfToken);\n  res.json({ success: true, token, user });'
);

// Update oauth callback to generate and set csrf
// Wait, oauth already has res.cookie token, res.json in block
content = content.replace(
  '  res.cookie("token", token, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });\n  res.json({ success: true, token, user });',
  '  res.cookie("token", token, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });\n  const csrfToken = generateCsrfToken();\n  res.cookie("_csrf_secret", csrfToken, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });\n  res.setHeader("x-csrf-token", csrfToken);\n  res.json({ success: true, token, user });'
);

// Now apply csrfMiddleware to endpoints
const regex = /app\.(post|put|delete)\("([^"]+)",\s*(.*?)\s*\(\s*(async\s*)?req\s*,\s*res\s*\)\s*=>/g;
content = content.replace(regex, (match, method, endpoint, prefix, isAsync) => {
  if (endpoint.includes('iyzico/callback') || endpoint === '/api/auth/login' || endpoint === '/api/auth/oauth/callback') {
    return match; // Skip these
  }
  if (prefix.includes('csrfMiddleware')) {
    return match; // Already has it
  }

  if (prefix.length > 0 && !prefix.endsWith(',')) {
     prefix += ', ';
  }

  return `app.${method}("${endpoint}", ${prefix}csrfMiddleware, ${isAsync || ''}(req, res) =>`;
});

content = content.replace(
  'app.use("/graphql", authRateLimiter, authMiddleware, createHandler({',
  'app.use("/graphql", authRateLimiter, authMiddleware, csrfMiddleware, createHandler({'
);

fs.writeFileSync('server.js', content);
