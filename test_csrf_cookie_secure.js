import fs from 'fs';
const authJs = fs.readFileSync('src/lib/auth.js', 'utf8');
const expectedFlags = "secure: process.env.NODE_ENV === \"production\"";
console.log(authJs.includes(expectedFlags));
