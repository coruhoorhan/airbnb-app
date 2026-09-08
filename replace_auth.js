import fs from 'fs';
let content = fs.readFileSync('src/lib/auth.js', 'utf8');
content = content.replace(
  /res\.cookie\("_csrf_secret", newToken, \{ httpOnly: true, sameSite: "lax", secure: false \}\);/g,
  'res.cookie("_csrf_secret", newToken, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });'
);
fs.writeFileSync('src/lib/auth.js', content);
