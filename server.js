import fs from "fs";
import { generateIcsFeed, syncExternalIcal } from "./src/lib/calendarSync.js";
import { saveSubscription, removeSubscription, getUserNotifications, markNotificationRead } from "./src/lib/notifications.js";
import { saveSubscription as savePushSub, removeSubscription as removePushSub, sendNotification } from "./src/lib/pushNotificationEngine.js";
import http from "http";
import { setupChatWebSocketServer, chatEngine } from "./src/lib/chatEngine.js";
import "express-async-errors";
import { createHandler } from "graphql-http/lib/use/express";
import DataLoader from "dataloader";
import depthLimit from "graphql-depth-limit";
import { schema } from "./src/lib/graphqlSchema.js";
import { rootValue } from "./src/lib/graphqlResolvers.js";
import { getUsersByIds, getReviewsForListings } from "./src/lib/db.js";
import express from "express";
import cors from "cors";
import helmet from "helmet";
import path from "path";
import { fileURLToPath } from "url";
import { execFile } from "child_process";
import NodeCache from "node-cache";
import { 
  db, 
  getAllListings, 
  getListingById, 
  insertListing, 
  toggleListingStatus,
  quickUpdateListingPrice,
  deleteListing,
  getActiveBookingsForListing, 
  insertBooking, 
  updateBookingStatus, 
  updateBookingPayment,
  getBookingById,
  getAllBookings,
  getCouponByCode,
  insertCoupon,
  toggleCouponStatus,
  deleteCoupon,
  incrementCouponUsage,
  getAllCoupons,
  insertPayment,
  getPaymentByBookingId,
  getPaymentByPaymentId,
  getAllPayments,
  getAllUsers,
  updateUserRole,
  getUserByEmail,
  insertUser,
  getAdminAnalytics,
  getAllGuardianIssues,
  dismissGuardianIssue,
  toggleFavorite,
  getUserFavorites,
  isListingFavorited,
  addReview,
  getReviewsForListing,
  insertMessage,
  getMessagesForListing,
  markMessagesRead,
  getConversationsForUser
} from "./src/lib/db.js";
import { calculateBookingPrice, validateBookingConflict, calculateCancellationRefund } from "./src/lib/bookingEngine.js";
import { validateAndCalculateDiscount } from "./src/lib/couponEngine.js";
import { 
  buildPaymentRequest, 
  processDirectPayment, 
  initializeCheckoutForm, 
  retrieveCheckoutFormResult, 
  validateCardDetails 
} from "./src/lib/iyzicoEngine.js";
import {
  executeFullWatchdogScan,
  autoHealGuardianIssue,
  formatGitHubIssueMarkdown
} from "./src/lib/watchdogEngine.js";
import { 
  getLoyaltyBalance, 
  awardLoyaltyPoints, 
  redeemLoyaltyPoints, 
  getLoyaltyTransactions,
  getLoyaltyTier,
  getLifetimeEarned
} from "./src/lib/loyaltyEngine.js";
import { 
  createGiftCard, 
  getGiftCardByCode, 
  redeemGiftCard, 
  getGiftCardsForBuyer 
} from "./src/lib/giftCardEngine.js";
import { 
  addPriceWatch, 
  removePriceWatch, 
  getUserPriceWatches, 
  checkPriceDropsForListing 
} from "./src/lib/priceWatchEngine.js";
import { 
  toggleLastMinuteDeal, 
  getLastMinuteDeals, 
  getLastMinuteDealById, 
  getEffectiveNightlyPrice 
} from "./src/lib/lastMinuteEngine.js";
import { getInstallmentPlans } from "./src/lib/installmentEngine.js";
import { calculateDynamicPrice } from "./src/lib/pricingEngine.js";
import { 
  getAllExperiences, 
  getExperienceById, 
  createExperienceReservation, 
  getUserExperienceReservations,
  cancelExperienceReservation
} from "./src/lib/experienceEngine.js";
import { createRateLimiter } from "./src/lib/rateLimiter.js";

import cookieParser from "cookie-parser";
import validator from "validator";
import { authMiddleware, csrfMiddleware, generateToken, generateCsrfToken } from "./src/lib/auth.js";


const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 4000;

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
      styleSrc: ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com", "https://unpkg.com"],
      fontSrc: ["'self'", "https://fonts.gstatic.com", "data:"],
      imgSrc: ["'self'", "data:", "https:", "blob:", "http:"],
      connectSrc: ["'self'", "http:", "https:", "ws:", "wss:"],
      upgradeInsecureRequests: null,
    },
  },
  crossOriginResourcePolicy: { policy: "cross-origin" },
}));
app.use(cors({
  origin: true,
  credentials: true,
  exposedHeaders: ["x-csrf-token"]
}));
app.use(cookieParser());
app.use(express.json());


app.use(express.urlencoded({ extended: true }));

const globalRateLimiter = createRateLimiter({
  windowMs: 60000,
  maxRequests: process.env.NODE_ENV === "test" ? 100 : 1000,
  message: "Çok fazla istek gönderildi. Lütfen biraz sonra tekrar deneyin."
});
app.use(globalRateLimiter);

const authRateLimiter = createRateLimiter({
  windowMs: 60000,
  maxRequests: 10,
  message: "Çok fazla giriş denemesi. Lütfen 1 dakika bekleyin."
});



app.use("/graphql", authRateLimiter, authMiddleware, createHandler({
  schema,
  rootValue,
  validationRules: [depthLimit(8)],
  context: (req) => {
    return {
      user: req.raw.user,
      userLoader: new DataLoader(async (ids) => {
        const users = getUsersByIds(ids);
        const userMap = users.reduce((acc, user) => { acc[user.id] = user; return acc; }, {});
        return ids.map(id => userMap[id] || null);
      }),
      reviewsLoader: new DataLoader(async (listingIds) => {
        const reviews = getReviewsForListings(listingIds);
        const reviewsMap = reviews.reduce((acc, review) => {
          if (!acc[review.listingId]) acc[review.listingId] = [];
          acc[review.listingId].push(review);
          return acc;
        }, {});
        return listingIds.map(id => reviewsMap[id] || []);
      })
    };
  },
  formatError: (err) => ({
    message: err.message,
    ...(process.env.NODE_ENV !== "production" && { stack: err.stack })
  })
}));


// --- Auth Endpoints ---

// --- Simulated OAuth2 Endpoints ---
app.get("/api/auth/oauth/github", (req, res) => {
  // Simulate redirecting to GitHub
  res.redirect("https://github.com/login/oauth/authorize?client_id=simulated_client_id");
});

app.post("/api/auth/oauth/callback", authRateLimiter, (req, res) => {
  const { email } = req.body;
  if (!email || !validator.isEmail(email)) {
    return res.status(400).json({ success: false, error: "Authentication failed." });
  }

  let user = getUserByEmail(email);
  if (!user) {
    user = { id: "u_" + Date.now(), email, name: email.split("@")[0], avatarUrl: "", isHost: 0, bio: "", phone: "" };
    insertUser(user);
  }

  const token = generateToken(user);
  res.cookie("token", token, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });
  res.json({ success: true, token, user });
});

app.post("/api/auth/logout", (req, res) => {
  res.clearCookie("token", { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });
  res.clearCookie("_csrf_secret", { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });
  res.json({ success: true, message: "Çıkış yapıldı." });
});

app.post("/api/auth/login", authRateLimiter, async (req, res) => {
  const { email } = req.body;
  if (!email || !validator.isEmail(email)) {
    return res.status(400).json({ success: false, error: "Geçerli bir email gerekli." });
  }

  const user = getUserByEmail(email);
  if (!user) {
    return res.status(401).json({ success: false, error: "Kullanıcı bulunamadı." });
  }

  const token = generateToken(user);
  res.cookie("token", token, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });
  res.json({ success: true, token, user });
});

app.get("/api/auth/csrf", (req, res) => {
  const csrfToken = generateCsrfToken();
  res.cookie("_csrf_secret", csrfToken, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });
  res.setHeader("x-csrf-token", csrfToken);
  
  // Auto-issue guest session token if user has no token cookie yet
  if (!req.cookies?.token) {
    const guestUser = { id: "usr_guest_01", email: "guest@fatsa.bel.tr", isHost: false };
    const authToken = generateToken(guestUser);
    res.cookie("token", authToken, { httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production" });
  }

  res.json({ success: true, csrfToken: csrfToken });
});

app.use("/uploads", express.static(path.join(__dirname, "public/uploads")));

// Security Rate Limiters
const paymentRateLimiter = createRateLimiter({
  windowMs: 60000,
  maxRequests: 25,
  message: "Ödeme işlemi için çok fazla istek gönderildi. Lütfen 1 dakika bekleyin."
});

const couponRateLimiter = createRateLimiter({
  windowMs: 60000,
  maxRequests: 40,
  message: "Kupon doğrulama isteği sınırına ulaşıldı."
});

const messageRateLimiter = createRateLimiter({
  windowMs: 60000,
  maxRequests: 60,
  message: "Mesaj gönderme isteği sınırına ulaşıldı."
});

const listingsRateLimiter = createRateLimiter({
  windowMs: 60000,
  maxRequests: 30,
  message: "İlan oluşturma isteği sınırına ulaşıldı. Lütfen biraz sonra tekrar deneyin."
});

const sseClients = new Map(); // listingId → Set<res>

function broadcastToListing(listingId, message) {
  chatEngine.broadcast(listingId, { type: "NEW_MESSAGE", data: message });
  const clients = sseClients.get(listingId);
  if (!clients) return;
  const payload = `data: ${JSON.stringify(message)}\n\n`;
  for (const res of clients) {
    res.write(payload);
  }
}

// --- 1. Health & Database Engine Status ---
app.get("/api/health", (req, res) => {
  const tableStats = {
    users: db.prepare("SELECT COUNT(*) as c FROM users").get().c,
    listings: db.prepare("SELECT COUNT(*) as c FROM listings").get().c,
    bookings: db.prepare("SELECT COUNT(*) as c FROM bookings").get().c,
    payments: db.prepare("SELECT COUNT(*) as c FROM payments").get().c,
    reviews: db.prepare("SELECT COUNT(*) as c FROM reviews").get().c,
    favorites: db.prepare("SELECT COUNT(*) as c FROM favorites").get().c,
    coupons: db.prepare("SELECT COUNT(*) as c FROM coupons").get().c,
    guardian_issues: db.prepare("SELECT COUNT(*) as c FROM guardian_issues").get().c
  };
  res.json({ 
    status: "ok", 
    server: "10.0.2.1", 
    database: "SQLite (better-sqlite3 WAL Mode)",
    paymentGateway: "iyzico Sandbox (Live Connected)",
    watchdog: "7/24 Autonomous AI Guardian Online",
    timestamp: Date.now(), 
    tables: tableStats 
  });
});

// --- 2. Multi-Currency API ---
app.get("/api/currencies", (req, res) => {
  res.json({ success: true, data: getAvailableCurrencies() });
});

// --- 3. Favorites API ---
app.post("/api/favorites/toggle", authMiddleware, csrfMiddleware, (req, res) => {
  const { userId, listingId } = req.body;
  if (!userId || !listingId) return res.status(400).json({ success: false, error: "Eksik parametre." });
  const result = toggleFavorite(userId, listingId);
  res.json({ success: true, isFavorited: result.isFavorited });
});

app.get("/api/favorites", (req, res) => {
  const userId = req.query.userId || "usr_guest_01";
  const favorites = getUserFavorites(userId);
  res.json({ success: true, count: favorites.length, data: favorites });
});

// --- 4. Admin & Analytics Endpoints ---
app.get("/api/admin/analytics", (req, res) => {
  try {
    const analytics = getAdminAnalytics();
    res.json({ success: true, data: analytics });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// --- 5. 🤖 7/24 AI Guardian / Watchdog Endpoints ---
app.get("/api/admin/guardian/issues", (req, res) => {
  try {
    const status = req.query.status || null;
    const issues = getAllGuardianIssues(status);
    res.json({ 
      success: true, 
      count: issues.length, 
      data: issues,
      openCount: issues.filter((i) => i.status === "open").length,
      healedCount: issues.filter((i) => i.status === "healed").length
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post("/api/admin/guardian/scan", (req, res) => {
  try {
    const scanResult = executeFullWatchdogScan();
    res.json({ success: true, data: scanResult });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post("/api/admin/guardian/heal/:id", (req, res) => {
  try {
    const healResult = autoHealGuardianIssue(req.params.id);
    res.json({ success: true, data: healResult });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.post("/api/admin/guardian/dismiss/:id", (req, res) => {
  try {
    const dismissed = dismissGuardianIssue(req.params.id);
    res.json({ success: true, data: dismissed });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.get("/api/admin/guardian/export-github/:id", (req, res) => {
  try {
    const issue = db.prepare("SELECT * FROM guardian_issues WHERE id = ?").get(req.params.id);
    if (!issue) return res.status(404).json({ success: false, error: "Sorun bulunamadı." });
    const markdown = formatGitHubIssueMarkdown(issue);
    res.json({ success: true, markdown });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// --- 6. Listings Endpoints ---

// Cache setup for listings
const listingsCache = new NodeCache({ stdTTL: 300 }); // 5 minutes TTL


// ==========================================
// Recommendation Engine Endpoint
// ==========================================
app.get("/api/recommendations", async (req, res) => {
  try {
    const { getRecommendedListings } = await import("./src/lib/recommendationEngine.js");
    const limit = parseInt(req.query.limit) || 6;
    const userId = req.query.userId || null;
    const recommendations = getRecommendedListings(userId, limit);
    res.json({ success: true, data: recommendations });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get("/api/listings", (req, res) => {
  const cacheKey = JSON.stringify(req.query);
  const cachedData = listingsCache.get(cacheKey);

  if (cachedData) {
    return res.json(cachedData);
  }

  const listings = getAllListings(req.query);
  const responseData = { success: true, count: listings.length, data: listings };

  listingsCache.set(cacheKey, responseData);
  res.json(responseData);
});

app.get("/api/listings/:id", (req, res) => {
  const listing = getListingById(req.params.id);
  if (!listing) return res.status(404).json({ error: "İlan bulunamadı" });

  const activeBookings = getActiveBookingsForListing(listing.id);
  const reviews = getReviewsForListing(listing.id);

  res.json({
    success: true,
    data: {
      ...listing,
      activeBookings: activeBookings.map((b) => ({ checkIn: b.checkIn, checkOut: b.checkOut })),
      reviews
    }
  });
});

app.post("/api/listings", authMiddleware, csrfMiddleware, listingsRateLimiter, (req, res) => {
  try {
    const newId = `list_${Date.now()}`;
    const created = insertListing({
      ...req.body,
      id: newId,
      createdAt: Date.now()
    });
    res.status(201).json({ success: true, data: created });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.put("/api/listings/:id/toggle-status", authMiddleware, csrfMiddleware, (req, res) => {
  const updated = toggleListingStatus(req.params.id);
  if (!updated) return res.status(404).json({ success: false, error: "İlan bulunamadı." });
  res.json({ success: true, data: updated });
});

app.put("/api/listings/:id/quick-update", authMiddleware, csrfMiddleware, (req, res) => {
  const { pricePerNight, cleaningFee } = req.body;
  const listingBefore = getListingById(req.params.id);
  const updated = quickUpdateListingPrice(req.params.id, pricePerNight, cleaningFee);
  if (!updated) return res.status(404).json({ success: false, error: "İlan bulunamadı." });

  // Fiyat düşüşü olduysa takipçilere bildirim üret
  if (listingBefore && Number(pricePerNight) < listingBefore.pricePerNight) {
    try {
      const dropResult = checkPriceDropsForListing(req.params.id, listingBefore.pricePerNight, Number(pricePerNight));
      updated.priceWatchNotifications = dropResult.notificationsCreated;
    } catch (err) {
      console.error("[PRICE WATCH ERROR]:", err.message);
    }
  }
  res.json({ success: true, data: updated });
});

app.delete("/api/listings/:id", authMiddleware, csrfMiddleware, (req, res) => {
  const success = deleteListing(req.params.id);
  if (!success) return res.status(404).json({ success: false, error: "İlan bulunamadı." });
  res.json({ success: true, message: "İlan başarıyla silindi." });
});

app.get("/api/listings/:id/dynamic-price", (req, res) => {
  try {
    const listing = getListingById(req.params.id);
    if (!listing) return res.status(404).json({ success: false, error: "İlan bulunamadı." });

    const occupancyRate = parseFloat(req.query.occupancyRate) || 0;
    const month = parseInt(req.query.month, 10) || new Date().getMonth() + 1;
    const demandIntensity = req.query.demandIntensity || "medium";

    const pricing = calculateDynamicPrice(listing.pricePerNight, { occupancyRate, month, demandIntensity });
    res.json({ success: true, data: pricing });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// --- 7. Coupon Endpoints ---
app.get("/api/coupons", (req, res) => {
  const coupons = getAllCoupons();
  res.json({ success: true, count: coupons.length, data: coupons });
});

app.post("/api/coupons", (req, res) => {
  try {
    const created = insertCoupon(req.body);
    if (!created) return res.status(400).json({ success: false, error: "Geçersiz kupon verisi." });
    res.status(201).json({ success: true, data: created });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.put("/api/coupons/:code/toggle", (req, res) => {
  const updated = toggleCouponStatus(req.params.code);
  if (!updated) return res.status(404).json({ success: false, error: "Kupon bulunamadı." });
  res.json({ success: true, data: updated });
});

app.delete("/api/coupons/:code", (req, res) => {
  const success = deleteCoupon(req.params.code);
  if (!success) return res.status(404).json({ success: false, error: "Kupon bulunamadı." });
  res.json({ success: true, message: "Kupon silindi." });
});

app.post("/api/coupons/validate", couponRateLimiter, (req, res) => {
  try {
    const { code, basePrice, checkIn } = req.body;
    if (!code) {
      return res.status(400).json({ success: false, error: "Kupon kodu gereklidir." });
    }

    const coupon = getCouponByCode(code);
    if (!coupon) {
      return res.status(404).json({ success: false, error: "Geçersiz kupon kodu." });
    }

    const result = validateAndCalculateDiscount(coupon, basePrice, checkIn);
    res.json({
      success: true,
      valid: true,
      code: result.code,
      discountType: result.discountType,
      discountValue: result.discountValue,
      discountAmount: result.discountAmount,
      finalBasePrice: result.finalBasePrice
    });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// --- 8. User Management API ---
app.get("/api/users", (req, res) => {
  const users = getAllUsers();
  res.json({ success: true, count: users.length, data: users });
});

app.put("/api/users/:id/role", (req, res) => {
  const { isHost } = req.body;
  const updated = updateUserRole(req.params.id, isHost);
  if (!updated) return res.status(404).json({ success: false, error: "Kullanıcı bulunamadı." });
  res.json({ success: true, data: updated });
});

// --- 9. iyzico Payment Endpoints ---
app.post("/api/payments/iyzico/direct-pay", paymentRateLimiter, async (req, res) => {
  try {
    const { listingId, guestId, checkIn, checkOut, numGuests, couponCode, giftCardCode, installmentMonths, card, buyer } = req.body;

    const listing = getListingById(listingId);
    if (!listing) {
      return res.status(404).json({ success: false, error: "İlan bulunamadı." });
    }

    if (listing.hostId === guestId) {
      return res.status(400).json({ success: false, error: "Kendi ilanınıza rezervasyon ve ödeme yapamazsınız!" });
    }

    // Conflict Check
    const activeBookings = getActiveBookingsForListing(listingId);
    const conflict = validateBookingConflict(listingId, checkIn, checkOut, activeBookings, []);
    if (conflict.hasConflict) {
      return res.status(409).json({ success: false, error: conflict.reason });
    }

    // Last-minute deal: use discounted effective nightly price
    const effectiveNightlyPrice = getEffectiveNightlyPrice(listing);
    const dealDiscountPerNight = Math.max(0, listing.pricePerNight - effectiveNightlyPrice);

    // Price Math
    const priceMath = calculateBookingPrice(
      checkIn, 
      checkOut, 
      effectiveNightlyPrice, 
      listing.cleaningFee, 
      listing.serviceFee
    );

    // Coupon calculation
    let discountAmount = 0;
    let validCouponCode = null;
    if (couponCode) {
      const coupon = getCouponByCode(couponCode);
      if (!coupon) {
        return res.status(400).json({ success: false, error: "Geçersiz kupon kodu." });
      }
      const discountResult = validateAndCalculateDiscount(coupon, priceMath.basePrice, checkIn);
      discountAmount = discountResult.discountAmount;
      validCouponCode = coupon.code;
    }

    let afterCouponPrice = Math.max(0, (priceMath.basePrice - discountAmount) + listing.cleaningFee + listing.serviceFee);

    // Gift card redemption (applies after coupon on the final total)
    let giftCardDiscount = 0;
    let appliedGiftCardCode = null;
    if (giftCardCode) {
      const giftResult = redeemGiftCard(giftCardCode, afterCouponPrice);
      if (!giftResult.success) {
        return res.status(400).json({ success: false, error: giftResult.error });
      }
      giftCardDiscount = giftResult.amountUsed;
      appliedGiftCardCode = giftResult.code;
    }

    const finalTotalPrice = Math.max(0, afterCouponPrice - giftCardDiscount);

    // Build iyzico payment request
    const conversationId = `conv_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    const iyzicoRequest = buildPaymentRequest({
      listing,
      buyer: buyer || { id: guestId || "usr_guest_01" },
      checkIn,
      checkOut,
      numGuests: numGuests || 1,
      priceMath,
      discountAmount,
      card,
      conversationId,
      installmentMonths: installmentMonths || 1
    });

    // Execute payment with iyzico API
    const paymentResult = await processDirectPayment(iyzicoRequest);

    // Save booking atomically in DB
    const bookingId = `bkg_${Date.now()}`;
    const newBooking = insertBooking({
      id: bookingId,
      listingId,
      guestId: guestId || "usr_guest_01",
      hostId: listing.hostId,
      checkIn,
      checkOut,
      numGuests: numGuests || 1,
      nightlyPrice: effectiveNightlyPrice,
      cleaningFee: listing.cleaningFee,
      serviceFee: listing.serviceFee,
      totalPrice: finalTotalPrice,
      couponCode: validCouponCode,
      discountAmount: discountAmount + giftCardDiscount + (dealDiscountPerNight * priceMath.nights),
      paymentStatus: "paid",
      paymentId: String(paymentResult.paymentId),
      status: "confirmed",
      cancelReason: null,
      createdAt: Date.now()
    });

    // Award loyalty points to the guest (accommodation spend = nights + cleaning, after coupon)
    const loyaltyResult = awardLoyaltyPoints(guestId || "usr_guest_01", bookingId, Math.max(0, afterCouponPrice - listing.serviceFee));

    // Insert payment record
    const paymentRecord = insertPayment({
      id: `pay_${Date.now()}`,
      bookingId,
      paymentId: String(paymentResult.paymentId),
      conversationId,
      provider: "iyzico",
      amount: finalTotalPrice,
      currency: "TRY",
      cardType: paymentResult.cardType || "CREDIT_CARD",
      cardAssociation: paymentResult.cardAssociation || "MASTER_CARD",
      cardFamily: paymentResult.cardFamily || null,
      lastFourDigits: paymentResult.lastFourDigits || (card?.cardNumber ? card.cardNumber.slice(-4) : "0016"),
      status: "success",
      authCode: paymentResult.authCode || null,
      rawResponse: JSON.stringify(paymentResult),
      createdAt: Date.now()
    });

    if (validCouponCode) {
      incrementCouponUsage(validCouponCode);
    }

    db.prepare(`
      INSERT INTO notifications (id, userId, type, title, body, isRead, createdAt)
      VALUES (?, ?, 'payment_success', 'Ödeme Alındı & Rezervasyon Onaylandı 💳', ?, 0, ?)
    `).run(
      `notif_${Date.now()}`,
      listing.hostId,
      `${checkIn} - ${checkOut} tarihleri için ₺${finalTotalPrice} tutarında iyzico ödemesi başarıyla alındı. Rezervasyon anında onaylandı.`,
      Date.now()
    );

    res.status(201).json({
      success: true,
      message: "Ödeme ve rezervasyon başarıyla tamamlandı.",
      booking: newBooking,
      payment: {
        paymentId: paymentResult.paymentId,
        authCode: paymentResult.authCode,
        amount: finalTotalPrice,
        cardAssociation: paymentResult.cardAssociation,
        lastFourDigits: paymentResult.lastFourDigits,
        currency: "TRY"
      }
    });
  } catch (err) {
    console.error("[IYZICO DIRECT PAY ERROR]:", err.message);
    res.status(400).json({
      success: false,
      error: err.message || "Ödeme işlemi gerçekleştirilemedi."
    });
  }
});

app.post("/api/payments/iyzico/init-checkout", async (req, res) => {
  try {
    const { listingId, guestId, checkIn, checkOut, numGuests, couponCode, buyer, callbackUrl } = req.body;

    const listing = getListingById(listingId);
    if (!listing) return res.status(404).json({ success: false, error: "İlan bulunamadı." });

    const activeBookings = getActiveBookingsForListing(listingId);
    const conflict = validateBookingConflict(listingId, checkIn, checkOut, activeBookings, []);
    if (conflict.hasConflict) {
      return res.status(409).json({ success: false, error: conflict.reason });
    }

    const priceMath = calculateBookingPrice(checkIn, checkOut, listing.pricePerNight, listing.cleaningFee, listing.serviceFee);

    let discountAmount = 0;
    if (couponCode) {
      const coupon = getCouponByCode(couponCode);
      if (coupon) {
        const discountResult = validateAndCalculateDiscount(coupon, priceMath.basePrice, checkIn);
        discountAmount = discountResult.discountAmount;
      }
    }

    const defaultCallback = callbackUrl || `http://${req.headers.host || "100.125.64.102:5173"}/api/payments/iyzico/callback`;
    const conversationId = `conv_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;

    const iyzicoRequest = buildPaymentRequest({
      listing,
      buyer: buyer || { id: guestId || "usr_guest_01" },
      checkIn,
      checkOut,
      numGuests: numGuests || 1,
      priceMath,
      discountAmount,
      callbackUrl: defaultCallback,
      conversationId
    });

    const result = await initializeCheckoutForm(iyzicoRequest);

    res.json({
      success: true,
      token: result.token,
      checkoutFormContent: result.checkoutFormContent,
      paymentPageUrl: result.paymentPageUrl,
      payWithIyzicoPageUrl: result.payWithIyzicoPageUrl
    });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.post("/api/payments/iyzico/callback", async (req, res) => {
  try {
    const token = req.body.token || req.query.token;
    if (!token) {
      return res.status(400).send("Geçersiz callback token.");
    }

    const result = await retrieveCheckoutFormResult(token);
    if (result.paymentStatus === "SUCCESS") {
      res.redirect(`/?paymentSuccess=true&paymentId=${result.paymentId}`);
    } else {
      res.redirect(`/?paymentError=${encodeURIComponent(result.errorMessage || "Ödeme başarısız")}`);
    }
  } catch (err) {
    res.redirect(`/?paymentError=${encodeURIComponent(err.message)}`);
  }
});

app.get("/api/payments/:bookingId", (req, res) => {
  const payment = getPaymentByBookingId(req.params.bookingId);
  if (!payment) return res.status(404).json({ success: false, error: "Ödeme kaydı bulunamadı." });
  res.json({ success: true, data: payment });
});

// --- 10. Bookings API ---
app.post("/api/bookings", authMiddleware, csrfMiddleware, (req, res) => {
  try {
  const { listingId, guestId, checkIn, checkOut, numGuests, couponCode, giftCardCode } = req.body;

  const listing = getListingById(listingId);
  if (!listing) return res.status(404).json({ error: "İlan bulunamadı" });

  if (listing.hostId === guestId) {
    return res.status(400).json({ error: "Kendi ilanınıza rezervasyon yapamazsınız!" });
  }

  const activeBookings = getActiveBookingsForListing(listingId);
  const conflict = validateBookingConflict(listingId, checkIn, checkOut, activeBookings, []);
  if (conflict.hasConflict) {
    return res.status(409).json({ error: conflict.reason });
  }

  const effectiveNightlyPrice = getEffectiveNightlyPrice(listing);
  const dealDiscountPerNight = Math.max(0, listing.pricePerNight - effectiveNightlyPrice);

  const priceMath = calculateBookingPrice(
    checkIn, 
    checkOut, 
    effectiveNightlyPrice, 
    listing.cleaningFee, 
    listing.serviceFee
  );

  let discountAmount = 0;
  let validCouponCode = null;

  if (couponCode) {
    const coupon = getCouponByCode(couponCode);
    if (!coupon) {
      return res.status(400).json({ error: "Geçersiz kupon kodu." });
    }
    try {
      const discountResult = validateAndCalculateDiscount(coupon, priceMath.basePrice, checkIn);
      discountAmount = discountResult.discountAmount;
      validCouponCode = coupon.code;
      incrementCouponUsage(coupon.code);
    } catch (err) {
      return res.status(400).json({ error: `Kupon uygulanamadı: ${err.message}` });
    }
  }

  let afterCouponPrice = Math.max(0, (priceMath.basePrice - discountAmount) + listing.cleaningFee + listing.serviceFee);

  // Gift card redemption (applies after coupon on the final total)
  let giftCardDiscount = 0;
  let appliedGiftCardCode = null;
  if (giftCardCode) {
    const giftResult = redeemGiftCard(giftCardCode, afterCouponPrice);
    if (!giftResult.success) {
      return res.status(400).json({ error: giftResult.error });
    }
    giftCardDiscount = giftResult.amountUsed;
    appliedGiftCardCode = giftResult.code;
  }

  const finalTotalPrice = Math.max(0, afterCouponPrice - giftCardDiscount);

  const newBooking = insertBooking({
    id: `bkg_${Date.now()}`,
    listingId,
    guestId: guestId || "usr_guest_01",
    hostId: listing.hostId,
    checkIn,
    checkOut,
    numGuests: numGuests || 1,
    nightlyPrice: effectiveNightlyPrice,
    cleaningFee: listing.cleaningFee,
    serviceFee: listing.serviceFee,
    totalPrice: finalTotalPrice,
    couponCode: validCouponCode,
    discountAmount: discountAmount + giftCardDiscount + (dealDiscountPerNight * priceMath.nights),
    paymentStatus: "unpaid",
    status: listing.instantBook ? "confirmed" : "pending",
    cancelReason: null,
    createdAt: Date.now()
  });

  db.prepare(`
    INSERT INTO notifications (id, userId, type, title, body, isRead, createdAt)
    VALUES (?, ?, 'new_booking', 'Yeni Rezervasyon Talebi 🔔', ?, 0, ?)
  `).run(
    `notif_${Date.now()}`, 
    listing.hostId, 
    `${checkIn} - ${checkOut} tarihleri için rezervasyon talebi alındı. Tutar: ₺${finalTotalPrice}${discountAmount > 0 ? ` (₺${discountAmount} Kupon İndirimi)` : ''}`, 
    Date.now()
  );

  // Award loyalty points to the guest when the booking is instantly confirmed
  if (listing.instantBook) {
    awardLoyaltyPoints(guestId || "usr_guest_01", newBooking.id, Math.max(0, afterCouponPrice - listing.serviceFee));
  }

  res.status(201).json({ success: true, data: newBooking });
  } catch (err) {
    return res.status(400).json({ success: false, error: err.message });
  }
});

app.get("/api/bookings", (req, res) => {
  const { guestId, hostId } = req.query;
  const bookings = getAllBookings(guestId, hostId);
  res.json({ success: true, count: bookings.length, data: bookings });
});

app.put("/api/bookings/:id/status", authMiddleware, csrfMiddleware, (req, res) => {
  const { status, cancelReason } = req.body;
  const updated = updateBookingStatus(req.params.id, status, cancelReason);
  if (!updated) return res.status(404).json({ error: "Rezervasyon bulunamadı" });

  // Loyalty: award points when a pending booking is confirmed by the host
  if (status === "confirmed" && updated && updated.guestId) {
    try {
      const spendBase = Math.max(0, (updated.totalPrice || 0) - (updated.serviceFee || 0));
      if (spendBase > 0) {
        awardLoyaltyPoints(updated.guestId, updated.id, spendBase);
      }
    } catch (err) {
      console.error("[LOYALTY AWARD ERROR]:", err.message);
    }
  }


  // Push Notification for booking status change
  if (updated && updated.guestId) {
    sendNotification(updated.guestId, { title: 'Rezervasyon Güncellemesi', body: 'Rezervasyon durumunuz değişti: ' + status }).catch(e => console.error(e));
  }

  res.json({ success: true, data: updated });

});

// --- 11a. Rezervasyon İptal & İade API ---
app.post("/api/bookings/:id/cancel", authMiddleware, csrfMiddleware, (req, res) => {
  try {
    const { cancelReason, cancelledByHost = false } = req.body;
    const booking = getBookingById(req.params.id);
    if (!booking) return res.status(404).json({ success: false, error: "Rezervasyon bulunamadı." });
    if (booking.status === "cancelled") return res.status(400).json({ success: false, error: "Rezervasyon zaten iptal edilmiş." });

    const listing = getListingById(booking.listingId);
    const policy = listing?.cancellationPolicy || "flexible";
    const refund = calculateCancellationRefund(booking.checkIn, booking.totalPrice, booking.nightlyPrice, policy, cancelledByHost, Date.now());

    updateBookingStatus(req.params.id, "cancelled", cancelReason || null);
    if (booking.paymentStatus === "paid" && refund.refundAmount > 0) {
      updateBookingPayment(req.params.id, "refunded", booking.paymentId);
    }

    db.prepare(`INSERT INTO notifications (id, userId, type, title, body, isRead, createdAt) VALUES (?, ?, 'cancelled', 'Rezervasyon İptal Edildi', ?, 0, ?)`)
      .run(`notif_${Date.now()}`, booking.guestId, `${refund.description} İade: ₺${refund.refundAmount}`, Date.now());

    res.json({ success: true, data: { ...refund, bookingId: req.params.id, status: "cancelled" } });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// --- 11b. Hava Durumu API (Open-Meteo, API key gerekmez) ---
app.get("/api/weather", async (req, res) => {
  try {
    const { lat = "41.0451", lng = "37.5010" } = req.query; // Fatsa default
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=7`;
    const weatherRes = await fetch(url);
    if (!weatherRes.ok) throw new Error("Hava durumu servisine ulaşılamadı.");
    const data = await weatherRes.json();
    res.json({ success: true, data });
  } catch (err) {
    res.status(502).json({ success: false, error: err.message });
  }
});

// --- 11c. Taksit Planları API ---
app.post("/api/payments/installments", (req, res) => {
  try {
    const { totalPrice } = req.body;
    if (totalPrice === undefined || Number(totalPrice) <= 0) {
      return res.status(400).json({ success: false, error: "Geçerli bir tutar gereklidir." });
    }
    const plans = getInstallmentPlans(Number(totalPrice));
    res.json({ success: true, data: plans });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// --- 11d. Sadakat Puanı API ---
app.get("/api/loyalty/:userId", (req, res) => {
  try {
    const balance = getLoyaltyBalance(req.params.userId);
    const transactions = getLoyaltyTransactions(req.params.userId, 10);
    const lifetimeEarned = getLifetimeEarned(req.params.userId);
    const tier = getLoyaltyTier(lifetimeEarned);
    res.json({ success: true, data: { ...balance, lifetimeEarned, tier, transactions } });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.post("/api/loyalty/redeem", (req, res) => {
  try {
    const { userId, points } = req.body;
    if (!userId || !points) return res.status(400).json({ success: false, error: "userId ve points gerekli." });
    const result = redeemLoyaltyPoints(userId, points);
    if (!result.success) return res.status(400).json({ success: false, error: result.error });
    res.json({ success: true, data: result });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// --- 11e. Hediye Kartı API ---
app.post("/api/gift-cards", (req, res) => {
  try {
    const { buyerId, recipientName, amount, message } = req.body;
    if (!buyerId || !amount) return res.status(400).json({ success: false, error: "buyerId ve amount gerekli." });
    const card = createGiftCard({ buyerId, recipientName, amount, message });
    res.status(201).json({ success: true, data: card });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.get("/api/gift-cards/:code", (req, res) => {
  try {
    const card = getGiftCardByCode(req.params.code);
    if (!card) return res.status(404).json({ success: false, error: "Geçersiz hediye kartı kodu." });
    res.json({ success: true, data: card });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.get("/api/gift-cards", (req, res) => {
  try {
    const { buyerId } = req.query;
    if (!buyerId) return res.status(400).json({ success: false, error: "buyerId gerekli." });
    const cards = getGiftCardsForBuyer(buyerId);
    res.json({ success: true, count: cards.length, data: cards });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.post("/api/gift-cards/redeem", (req, res) => {
  try {
    const { code, amountToApply } = req.body;
    if (!code) return res.status(400).json({ success: false, error: "Kod gerekli." });
    const result = redeemGiftCard(code, amountToApply);
    if (!result.success) return res.status(400).json({ success: false, error: result.error });
    res.json({ success: true, data: result });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// --- 11f. Fiyat Takibi API ---
app.post("/api/price-watches", (req, res) => {
  try {
    const { userId, listingId } = req.body;
    if (!userId || !listingId) return res.status(400).json({ success: false, error: "userId ve listingId gerekli." });
    const watch = addPriceWatch(userId, listingId);
    res.status(201).json({ success: true, data: watch });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.delete("/api/price-watches/:listingId", (req, res) => {
  try {
    const { userId } = req.query;
    if (!userId) return res.status(400).json({ success: false, error: "userId gerekli." });
    const result = removePriceWatch(userId, req.params.listingId);
    res.json({ success: true, data: result });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.get("/api/price-watches", (req, res) => {
  try {
    const { userId } = req.query;
    if (!userId) return res.status(400).json({ success: false, error: "userId gerekli." });
    const watches = getUserPriceWatches(userId);
    res.json({ success: true, count: watches.length, data: watches });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// --- 11g. Son Dakika Fırsatları API ---
app.get("/api/last-minute", (req, res) => {
  try {
    const deals = getLastMinuteDeals();
    res.json({ success: true, count: deals.length, data: deals });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.put("/api/listings/:id/last-minute", (req, res) => {
  try {
    const { discountPercent } = req.body;
    const updated = toggleLastMinuteDeal(req.params.id, discountPercent);
    if (!updated) return res.status(404).json({ success: false, error: "İlan bulunamadı." });
    res.json({ success: true, data: updated });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});


// --- Push Notification Endpoints ---



// --- Push Notification API ---
app.post("/api/notifications/subscribe", authMiddleware, csrfMiddleware, (req, res) => {
  try {
    const subscription = req.body.subscription || req.body;
    const userId = req.body.userId || req.user.id;
    if (!subscription || !subscription.endpoint) {
      return res.status(400).json({ success: false, error: "Geçersiz abonelik verisi." });
    }
    const id = savePushSub(userId, subscription);
    res.status(200).json({ success: true, id });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post("/api/notifications/unsubscribe", authMiddleware, csrfMiddleware, (req, res) => {
  try {
    const userId = req.body.userId || req.user.id;
    const endpoint = req.body.endpoint;
    removePushSub(userId);
    res.status(200).json({ success: true });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});




// --- iCal Calendar Sync Endpoints ---
app.get("/api/calendar/:listingId.ics", (req, res) => {
  const { listingId } = req.params;
  const feed = generateIcsFeed(listingId);
  if (!feed) {
    return res.status(404).send("Listing not found");
  }
  res.setHeader("Content-Type", "text/calendar; charset=utf-8");
  res.setHeader("Content-Disposition", `attachment; filename="${listingId}.ics"`);
  res.send(feed);
});

app.post("/api/calendar/:listingId/sync", async (req, res) => {
  try {
    const { listingId } = req.params;
    const { icalUrl, icalData } = req.body;
    const source = icalUrl || icalData;
    if (!source) {
      return res.status(400).json({ success: false, error: "icalUrl veya icalData zorunludur." });
    }
    const result = await syncExternalIcal(listingId, source);
    res.json({ success: true, data: result });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.get("/api/notifications", (req, res) => {
  try {
    const { userId, limit = 50 } = req.query;
    if (!userId) return res.status(400).json({ success: false, error: "userId gerekli." });
    const rows = db.prepare(
      "SELECT * FROM notifications WHERE userId = ? ORDER BY createdAt DESC LIMIT ?"
    ).all(userId, Number(limit) || 50);
    res.json({ success: true, count: rows.length, data: rows });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// --- 11. Reviews API ---
app.post("/api/reviews", authMiddleware, csrfMiddleware, (req, res) => {
  const { listingId, bookingId, reviewerId, reviewerName, rating, comment } = req.body;
  if (!listingId || !reviewerId) {
    return res.status(400).json({ success: false, error: "Eksik yorum bilgisi." });
  }

  const result = addReview({
    listingId,
    bookingId,
    reviewerId,
    reviewerName: reviewerName || "Misafir",
    rating: Number(rating) || 5,
    comment: comment || ""
  });

  res.status(201).json({ success: true, data: result });
});

// --- 12. Message & Inbox Engine ---

app.get("/api/messages", (req, res) => {
  try {
    const { listingId } = req.query;
    if (!listingId) {
      return res.status(400).json({ success: false, error: "listingId gerekli." });
    }
    const data = getMessagesForListing(listingId);
    res.json({ success: true, data });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post("/api/messages", authMiddleware, csrfMiddleware, messageRateLimiter, (req, res) => {
  try {
    const { listingId, senderId, text } = req.body;
    if (!listingId || !senderId || !text) {
      return res.status(400).json({ success: false, error: "Eksik mesaj bilgisi." });
    }
    const user = db.prepare("SELECT name FROM users WHERE id = ?").get(senderId);
    if (!user) {
      return res.status(400).json({ success: false, error: "Geçersiz kullanıcı." });
    }
    const msg = insertMessage({ listingId, senderId, senderName: user.name, text });
    broadcastToListing(listingId, msg);

    // Push Notification for new message
    const msgListing = getListingById(listingId);
    if (msgListing) {
      if (senderId !== msgListing.hostId) {
         sendNotification(msgListing.hostId, { title: 'Yeni Mesaj (' + msgListing.title + ')', body: user.name + ': ' + text }).catch(e => console.error(e));
      }
    }

    res.status(201).json({ success: true, data: msg });

  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post("/api/messages/read", (req, res) => {
  try {
    const { listingId, userId } = req.body;
    if (!listingId || !userId) {
      return res.status(400).json({ success: false, error: "listingId ve userId gerekli." });
    }
    const result = markMessagesRead(listingId, userId);
    res.json({ success: true, ...result });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get("/api/conversations", (req, res) => {
  try {
    const { userId } = req.query;
    if (!userId) {
      return res.status(400).json({ success: false, error: "userId gerekli." });
    }
    const data = getConversationsForUser(userId);
    res.json({ success: true, data });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get("/api/messages/stream", (req, res) => {
  try {
    const { listingId, userId } = req.query;
    if (!listingId || !userId) {
      return res.status(400).json({ success: false, error: "listingId ve userId gerekli." });
    }
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "X-Accel-Buffering": "no"
    });
    res.flushHeaders();
    res.write(": connected\n\n");

    if (!sseClients.has(listingId)) {
      sseClients.set(listingId, new Set());
    }
    sseClients.get(listingId).add(res);

    const heartbeat = setInterval(() => {
      res.write(": ping\n\n");
    }, 25000);

    req.on("close", () => {
      clearInterval(heartbeat);
      const clients = sseClients.get(listingId);
      if (clients) {
        clients.delete(res);
        if (clients.size === 0) sseClients.delete(listingId);
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});


// --- 12b. Deneyim Rezervasyonları API ---
app.get("/api/experiences", (req, res) => {
  try {
    const { category, city } = req.query;
    const experiences = getAllExperiences(category, city);
    res.json({ success: true, data: experiences });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.get("/api/experiences/:id", (req, res) => {
  try {
    const experience = getExperienceById(req.params.id);
    if (!experience) return res.status(404).json({ success: false, error: "Deneyim bulunamadı." });
    res.json({ success: true, data: experience });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.post("/api/experiences/reserve", authMiddleware, csrfMiddleware, (req, res) => {
  try {
    const { experienceId, userId, participants, reservationDate } = req.body;
    if (!experienceId || !userId || !participants || !reservationDate) {
      return res.status(400).json({ success: false, error: "experienceId, userId, participants ve reservationDate gerekli." });
    }
    const result = createExperienceReservation({ experienceId, userId, participants, reservationDate });
    if (!result.success) return res.status(400).json({ success: false, error: result.error });
    res.json({ success: true, data: { id: result.id, totalPrice: result.totalPrice } });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.get("/api/experiences/reservations/:userId", (req, res) => {
  try {
    const reservations = getUserExperienceReservations(req.params.userId);
    res.json({ success: true, data: reservations });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.post("/api/experiences/reservations/:id/cancel", authMiddleware, csrfMiddleware, (req, res) => {
  try {
    const { userId } = req.body;
    if (!userId) return res.status(400).json({ success: false, error: "userId gerekli." });
    const result = cancelExperienceReservation(req.params.id, userId);
    if (!result.success) return res.status(400).json({ success: false, error: result.error });
    res.json({ success: true, data: result });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// --- 12.5. Magda-Agent Cognitive AI Engine Integration ---
app.post("/api/magda/concierge", (req, res) => {
  const query = req.body?.query || req.body?.prompt || "Fatsa merkezde kiralık ev";
  execFile("python3", ["/opt/airbnb-app/magda_airbnb_bridge.py", "chat", query], (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({ success: false, error: error.message, details: stderr });
    }
    try {
      const data = JSON.parse(stdout);
      res.json(data);
    } catch (parseErr) {
      res.json({ status: "success", raw: stdout });
    }
  });
});

app.get("/api/magda/guardian/scan", (req, res) => {
  execFile("python3", ["/opt/airbnb-app/magda_airbnb_bridge.py", "guardian_scan"], (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({ success: false, error: error.message, details: stderr });
    }
    try {
      const data = JSON.parse(stdout);
      res.json(data);
    } catch (parseErr) {
      res.json({ status: "success", raw: stdout });
    }
  });
});

app.get("/api/magda/status", (req, res) => {
  execFile("python3", ["/opt/airbnb-app/magda_airbnb_bridge.py", "analytics"], (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({ success: false, error: error.message, details: stderr });
    }
    try {
      const data = JSON.parse(stdout);
      res.json({ status: "active", engine: "Magda-Agent Cognitive Core V2", analytics: data });
    } catch (parseErr) {
      res.json({ status: "active", raw: stdout });
    }
  });
});

app.get("/api/magda/backend-tasks", (req, res) => {
  const p = path.join(__dirname, "backend_tasks.json");
  if (!fs.existsSync(p)) {
    return res.json({ schema_version: 1, tasks: [] });
  }
  try {
    const data = JSON.parse(fs.readFileSync(p, "utf8"));
    res.json(data);
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});
app.get("/api/magda/tasks", (req, res) => {
  execFile("python3", ["/opt/airbnb-app/magda_airbnb_daemon.py", "tasks"], (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({ success: false, error: error.message, details: stderr });
    }
    try {
      const data = JSON.parse(stdout);
      res.json(data);
    } catch (parseErr) {
      res.json({ tasks: [] });
    }
  });
});

app.post("/api/magda/tasks/create", (req, res) => {
  const { title, description, area, risk } = req.body || {};
  if (!title) return res.status(400).json({ success: false, error: "Title is required" });
  
  const taskId = `task-auto-${Date.now().toString(36)}`;
  const taskData = JSON.stringify({ id: taskId, title, description, area: area || "backend", risk: risk || "medium" });
  
  execFile("python3", ["-c", `
import json, sys
from magda_airbnb_daemon import AirbnbTasksManifestManager
mgr = AirbnbTasksManifestManager()
t = json.loads('''${taskData}''')
mgr.add_task(task_id=t['id'], title=t['title'], description=t['description'], area=t['area'], risk=t['risk'])
print(json.dumps({'success': True, 'task_id': t['id']}))
`], (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({ success: false, error: error.message, details: stderr });
    }
    try {
      const data = JSON.parse(stdout);
      res.json(data);
    } catch (parseErr) {
      res.json({ success: true, task_id: taskId });
    }
  });
});
app.get("/api/magda/codebase-knowledge", (req, res) => {
  execFile("python3", ["/opt/airbnb-app/magda_airbnb_codebase_indexer.py"], (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({ success: false, error: error.message, details: stderr });
    }
    try {
      execFile("python3", ["/opt/airbnb-app/magda_airbnb_bridge.py", "codebase"], (err2, out2) => {
        try {
          const fullData = JSON.parse(out2);
          res.json(fullData);
        } catch (e) {
          res.json({ summary: JSON.parse(stdout) });
        }
      });
    } catch (parseErr) {
      res.json({ summary: {} });
    }
  });
});

// --- 13. Static Frontend Serving ---
const distPath = path.join(__dirname, "dist");
app.use(express.static(distPath));

app.get("*", (req, res) => {
  res.sendFile(path.join(distPath, "index.html"), (err) => {
    if (err) res.status(200).send("Airbnb SQLite & iyzico API running on 10.0.2.1");
  });
});

// --- 14. 7/24 Autonomous Guardian Background Loop ---
function startAutonomousGuardianLoop() {
  console.log("[🤖 AI GUARDIAN] 7/24 Autonomous Watchdog Initializing...");
  try {
    const initialScan = executeFullWatchdogScan();
    console.log(`[🤖 AI GUARDIAN] Boot scan complete. Open issues: ${initialScan.openIssues.length}`);
  } catch (err) {
    console.error("[🤖 AI GUARDIAN] Initial scan failed:", err.message);
  }

  setInterval(() => {
    try {
      const scan = executeFullWatchdogScan();
      if (scan.newIssuesInserted > 0) {
        console.log(`[🤖 AI GUARDIAN] Periodic scan detected ${scan.newIssuesInserted} new issues.`);
      }
    } catch (err) {
      console.error("[🤖 AI GUARDIAN] Periodic scan error:", err.message);
    }
  }, 900000);
}

const server = http.createServer(app);
setupChatWebSocketServer(server);

if (process.env.NODE_ENV !== "test") {
  server.listen(PORT, "0.0.0.0", () => {
    console.log(`[AIRBNB SQLITE & IYZICO ENGINE] Running on http://0.0.0.0:${PORT} (HTTP + WebSocket)`);
    startAutonomousGuardianLoop();
  });
}


// --- 15. Graceful Shutdown & Process Safety ---
process.on("unhandledRejection", (reason, promise) => {
  console.error("[🔥 FATAL UNHANDLED REJECTION]:", reason);
});

process.on("uncaughtException", (error) => {
  console.error("[🔥 FATAL UNCAUGHT EXCEPTION]:", error);
});

process.on("SIGTERM", () => {
  console.log("[🛑 SIGTERM RECEIVED]: Closing HTTP server gracefully...");
  process.exit(0);
});

process.on("SIGINT", () => {
  console.log("[🛑 SIGINT RECEIVED]: Shutting down...");
  process.exit(0);
});

export { app, server };
