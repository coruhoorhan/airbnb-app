import { authMiddleware, csrfMiddleware } from './src/lib/auth.js';
console.log(authMiddleware.toString());
console.log(csrfMiddleware.toString());
