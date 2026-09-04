import Database from "better-sqlite3";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import { randomUUID } from "node:crypto";
import Joi from "joi";
import { INITIAL_USERS } from "../data/users.js";
import { INITIAL_LISTINGS } from "../data/listings.js";
import { INITIAL_EXPERIENCES } from "../data/experiences.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const dataDir = path.join(__dirname, "../../data");
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

const dbPath = path.join(dataDir, "airbnb.db");
export const db = new Database(dbPath);

// Enable WAL mode for high performance concurrency
db.pragma("journal_mode = WAL");

// HTML Strip Regex for sanitization
const htmlRegex = /<[^>]*>?/gm;

const listingSchema = Joi.object({
  hostId: Joi.string().required(),
  title: Joi.string().trim().replace(htmlRegex, '').required(),
  description: Joi.string().trim().replace(htmlRegex, '').optional(),
  pricePerNight: Joi.number().min(0).required()
});

const bookingSchema = Joi.object({
  listingId: Joi.string().required(),
  guestId: Joi.string().required(),
  checkIn: Joi.string().trim().replace(htmlRegex, '').required(),
  checkOut: Joi.string().trim().replace(htmlRegex, '').required()
});

// --- Schema Initialization with Real SQL Tables & Indexes ---
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    avatarUrl TEXT,
    isHost INTEGER DEFAULT 0,
    bio TEXT,
    phone TEXT,
    createdAt INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    hostId TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    propertyType TEXT NOT NULL,
    pricePerNight REAL NOT NULL,
    cleaningFee REAL DEFAULT 0,
    serviceFee REAL DEFAULT 0,
    maxGuests INTEGER DEFAULT 2,
    bedrooms INTEGER DEFAULT 1,
    beds INTEGER DEFAULT 1,
    baths INTEGER DEFAULT 1,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT 'Türkiye',
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    amenities TEXT NOT NULL, -- JSON string array
    images TEXT NOT NULL,    -- JSON string array
    instantBook INTEGER DEFAULT 0,
    isPublished INTEGER DEFAULT 1,
    avgRating REAL DEFAULT 5.0,
    reviewCount INTEGER DEFAULT 0,
    cancellationPolicy TEXT DEFAULT 'flexible',
    createdAt INTEGER NOT NULL,
    FOREIGN KEY(hostId) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY,
    listingId TEXT NOT NULL,
    guestId TEXT NOT NULL,
    hostId TEXT NOT NULL,
    checkIn TEXT NOT NULL,
    checkOut TEXT NOT NULL,
    numGuests INTEGER NOT NULL,
    nightlyPrice REAL NOT NULL,
    cleaningFee REAL NOT NULL,
    serviceFee REAL NOT NULL,
    totalPrice REAL NOT NULL,
    couponCode TEXT,
    discountAmount REAL DEFAULT 0,
    paymentStatus TEXT DEFAULT 'unpaid', -- 'unpaid', 'paid', 'refunded'
    paymentId TEXT,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'confirmed', 'cancelled', 'completed'
    cancelReason TEXT,
    createdAt INTEGER NOT NULL,
    FOREIGN KEY(listingId) REFERENCES listings(id) ON DELETE CASCADE,
    FOREIGN KEY(guestId) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    bookingId TEXT NOT NULL,
    paymentId TEXT NOT NULL,
    conversationId TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'iyzico',
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'TRY',
    cardType TEXT,
    cardAssociation TEXT,
    cardFamily TEXT,
    lastFourDigits TEXT,
    status TEXT NOT NULL, -- 'success', 'failed', 'refunded'
    authCode TEXT,
    rawResponse TEXT,     -- JSON string
    createdAt INTEGER NOT NULL,
    FOREIGN KEY(bookingId) REFERENCES bookings(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    listingId TEXT NOT NULL,
    bookingId TEXT UNIQUE,
    reviewerId TEXT NOT NULL,
    reviewerName TEXT NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT NOT NULL,
    createdAt INTEGER NOT NULL,
    FOREIGN KEY(listingId) REFERENCES listings(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS favorites (
    id TEXT PRIMARY KEY,
    userId TEXT NOT NULL,
    listingId TEXT NOT NULL,
    createdAt INTEGER NOT NULL,
    UNIQUE(userId, listingId),
    FOREIGN KEY(listingId) REFERENCES listings(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    listingId TEXT NOT NULL,
    senderId TEXT NOT NULL,
    senderName TEXT NOT NULL,
    text TEXT NOT NULL,
    createdAt INTEGER NOT NULL,
    isRead INTEGER DEFAULT 0,
    FOREIGN KEY(listingId) REFERENCES listings(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    userId TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    isRead INTEGER DEFAULT 0,
    createdAt INTEGER NOT NULL,
    FOREIGN KEY(userId) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS coupons (
    code TEXT PRIMARY KEY,
    discountType TEXT NOT NULL, -- 'percentage' | 'fixed'
    discountValue REAL NOT NULL, -- 20 veya 500
    minAmount REAL DEFAULT 0,
    expiryDate TEXT NOT NULL,   -- 'YYYY-MM-DD'
    usageCount INTEGER DEFAULT 0,
    isActive INTEGER DEFAULT 1
  );

  CREATE TABLE IF NOT EXISTS guardian_issues (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,         -- 'performance' | 'security' | 'reliability' | 'quality'
    severity TEXT NOT NULL,     -- 'low' | 'medium' | 'high' | 'critical'
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    suggestion TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open', -- 'open' | 'healed' | 'dismissed'
    autoHealed INTEGER DEFAULT 0,
    githubIssueNumber INTEGER,
    createdAt INTEGER NOT NULL,
    healedAt INTEGER
  );
  CREATE TABLE IF NOT EXISTS loyalty_accounts (
    userId TEXT PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    lifetimeEarned INTEGER DEFAULT 0,
    lifetimeRedeemed INTEGER DEFAULT 0,
    updatedAt INTEGER NOT NULL,
    FOREIGN KEY(userId) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS loyalty_transactions (
    id TEXT PRIMARY KEY,
    userId TEXT NOT NULL,
    type TEXT NOT NULL,             -- 'earn' | 'redeem'
    amount INTEGER NOT NULL,
    description TEXT NOT NULL,
    createdAt INTEGER NOT NULL,
    FOREIGN KEY(userId) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS gift_cards (
    code TEXT PRIMARY KEY,
    buyerId TEXT NOT NULL,
    recipientName TEXT,
    amount REAL NOT NULL,
    remainingBalance REAL NOT NULL,
    message TEXT,
    isActive INTEGER DEFAULT 1,
    expiresAt INTEGER NOT NULL,
    createdAt INTEGER NOT NULL,
    redeemedAt INTEGER,
    FOREIGN KEY(buyerId) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS gift_card_transactions (
    id TEXT PRIMARY KEY,
    giftCardCode TEXT NOT NULL,
    amount REAL NOT NULL,
    note TEXT,
    createdAt INTEGER NOT NULL,
    FOREIGN KEY(giftCardCode) REFERENCES gift_cards(code) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS price_watches (
    id TEXT PRIMARY KEY,
    userId TEXT NOT NULL,
    listingId TEXT NOT NULL,
    watchedPrice REAL NOT NULL,
    createdAt INTEGER NOT NULL,
    UNIQUE(userId, listingId),
    FOREIGN KEY(userId) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(listingId) REFERENCES listings(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS experiences (
    id TEXT PRIMARY KEY,
    hostId TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    duration INTEGER NOT NULL,
    pricePerPerson REAL NOT NULL,
    maxParticipants INTEGER DEFAULT 10,
    location TEXT NOT NULL,
    city TEXT NOT NULL DEFAULT 'Fatsa',
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    images TEXT NOT NULL,
    includes TEXT NOT NULL,
    avgRating REAL DEFAULT 5.0,
    reviewCount INTEGER DEFAULT 0,
    isActive INTEGER DEFAULT 1,
    createdAt INTEGER NOT NULL,
    FOREIGN KEY(hostId) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS experience_reservations (
    id TEXT PRIMARY KEY,
    experienceId TEXT NOT NULL,
    userId TEXT NOT NULL,
    participants INTEGER NOT NULL DEFAULT 1,
    reservationDate TEXT NOT NULL,
    totalPrice REAL NOT NULL,
    status TEXT DEFAULT 'confirmed',
    createdAt INTEGER NOT NULL,
    FOREIGN KEY(experienceId) REFERENCES experiences(id) ON DELETE CASCADE,
    FOREIGN KEY(userId) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_experiences_city ON experiences(city);
  CREATE INDEX IF NOT EXISTS idx_experiences_category ON experiences(category);
  CREATE INDEX IF NOT EXISTS idx_exp_reservations_experience ON experience_reservations(experienceId);
  CREATE INDEX IF NOT EXISTS idx_exp_reservations_user ON experience_reservations(userId);

  CREATE INDEX IF NOT EXISTS idx_loyalty_tx_user ON loyalty_transactions(userId);
  CREATE INDEX IF NOT EXISTS idx_gift_cards_buyer ON gift_cards(buyerId);
  CREATE INDEX IF NOT EXISTS idx_price_watches_user ON price_watches(userId);
  CREATE INDEX IF NOT EXISTS idx_price_watches_listing ON price_watches(listingId);


  CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
  CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category);
  CREATE INDEX IF NOT EXISTS idx_bookings_listingId ON bookings(listingId);
  CREATE INDEX IF NOT EXISTS idx_bookings_guestId ON bookings(guestId);
  CREATE INDEX IF NOT EXISTS idx_reviews_listingId ON reviews(listingId);
  CREATE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code);
  CREATE INDEX IF NOT EXISTS idx_payments_bookingId ON payments(bookingId);
  CREATE INDEX IF NOT EXISTS idx_payments_paymentId ON payments(paymentId);
  CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(userId);
  CREATE INDEX IF NOT EXISTS idx_guardian_issues_status ON guardian_issues(status);
`);

// Migration helpers
try {
  const tableInfo = db.prepare("PRAGMA table_info(bookings)").all();
  const columnNames = tableInfo.map((col) => col.name);

  if (!columnNames.includes("couponCode")) {
    db.exec("ALTER TABLE bookings ADD COLUMN couponCode TEXT");
  }
  if (!columnNames.includes("discountAmount")) {
    db.exec("ALTER TABLE bookings ADD COLUMN discountAmount REAL DEFAULT 0");
  }
  if (!columnNames.includes("paymentStatus")) {
    db.exec("ALTER TABLE bookings ADD COLUMN paymentStatus TEXT DEFAULT 'unpaid'");
  }
  if (!columnNames.includes("paymentId")) {
    db.exec("ALTER TABLE bookings ADD COLUMN paymentId TEXT");
  }
  const msgCols = db.prepare("PRAGMA table_info(messages)").all().map((c) => c.name);
  if (!msgCols.includes("isRead")) {
    db.exec("ALTER TABLE messages ADD COLUMN isRead INTEGER DEFAULT 0");
  }
} catch (e) {
  // Column migration safe check
}

// Migration: last minute deal columns on listings
try {
  const listCols = db.prepare("PRAGMA table_info(listings)").all().map((c) => c.name);
  if (!listCols.includes("lastMinuteDiscount")) {
    db.exec("ALTER TABLE listings ADD COLUMN lastMinuteDiscount INTEGER DEFAULT 0");
  }
  if (!listCols.includes("lastMinuteOriginalPrice")) {
    db.exec("ALTER TABLE listings ADD COLUMN lastMinuteOriginalPrice REAL");
  }
} catch (e) {
  // Column migration safe check
}

// Seed initial users if empty
const userCount = db.prepare("SELECT COUNT(*) as c FROM users").get().c;
if (userCount === 0) {
  console.log("[DB] Seeding initial users...");
  const insertUser = db.prepare(`
    INSERT INTO users (id, name, email, avatarUrl, isHost, bio, phone, createdAt)
    VALUES (@id, @name, @email, @avatarUrl, @isHost, @bio, @phone, @createdAt)
  `);
  const insertManyUsers = db.transaction((users) => {
    for (const u of users) {
      insertUser.run({
        ...u,
        isHost: u.isHost ? 1 : 0,
        createdAt: Date.now()
      });
    }
  });
  insertManyUsers(INITIAL_USERS);
}

// Seed initial listings if empty
const listingCount = db.prepare("SELECT COUNT(*) as c FROM listings").get().c;
if (listingCount === 0) {
  console.log("[DB] Seeding initial listings...");
  const insertListingStmt = db.prepare(`
    INSERT INTO listings (
      id, hostId, title, description, category, propertyType,
      pricePerNight, cleaningFee, serviceFee, maxGuests, bedrooms, beds, baths,
      address, city, country, lat, lng, amenities, images, instantBook, isPublished,
      avgRating, reviewCount, cancellationPolicy, createdAt
    ) VALUES (
      @id, @hostId, @title, @description, @category, @propertyType,
      @pricePerNight, @cleaningFee, @serviceFee, @maxGuests, @bedrooms, @beds, @baths,
      @address, @city, @country, @lat, @lng, @amenities, @images, @instantBook, @isPublished,
      @avgRating, @reviewCount, @cancellationPolicy, @createdAt
    )
  `);

  const insertManyListings = db.transaction((listings) => {
    for (const l of listings) {
      insertListingStmt.run({
        ...l,
        amenities: JSON.stringify(l.amenities || []),
        images: JSON.stringify(l.images || []),
        instantBook: l.instantBook ? 1 : 0,
        isPublished: l.isPublished ? 1 : 0,
        createdAt: Date.now()
      });
    }
  });
  insertManyListings(INITIAL_LISTINGS);
}

// Seed initial coupons if empty
const couponCount = db.prepare("SELECT COUNT(*) as c FROM coupons").get().c;
if (couponCount === 0) {
  console.log("[DB] Seeding initial coupons (FATSA2026, HOSGELDIN)...");
  const insertCouponStmt = db.prepare(`
    INSERT OR REPLACE INTO coupons (code, discountType, discountValue, minAmount, expiryDate, usageCount, isActive)
    VALUES (@code, @discountType, @discountValue, @minAmount, @expiryDate, @usageCount, @isActive)
  `);

  const seedCoupons = [
    {
      code: "FATSA2026",
      discountType: "percentage",
      discountValue: 20,
      minAmount: 3000,
      expiryDate: "2026-12-31",
      usageCount: 0,
      isActive: 1
    },
    {
      code: "HOSGELDIN",
      discountType: "fixed",
      discountValue: 500,
      minAmount: 2000,
      expiryDate: "2026-12-31",
      usageCount: 0,
      isActive: 1
    }
  ];

  const insertManyCoupons = db.transaction((coupons) => {
    for (const c of coupons) {
      insertCouponStmt.run(c);
    }
  });
  insertManyCoupons(seedCoupons);
}

// Seed initial experiences if empty
const experienceCount = db.prepare("SELECT COUNT(*) as c FROM experiences").get().c;
if (experienceCount === 0) {
  console.log("[DB] Seeding initial experiences...");
  const insertExperienceStmt = db.prepare(`
    INSERT INTO experiences (
      id, hostId, title, description, category, duration, pricePerPerson,
      maxParticipants, location, city, lat, lng, images, includes,
      avgRating, reviewCount, isActive, createdAt
    ) VALUES (
      @id, @hostId, @title, @description, @category, @duration, @pricePerPerson,
      @maxParticipants, @location, @city, @lat, @lng, @images, @includes,
      @avgRating, @reviewCount, @isActive, @createdAt
    )
  `);
  const insertManyExperiences = db.transaction((experiences) => {
    for (const e of experiences) {
      insertExperienceStmt.run(e);
    }
  });
  insertManyExperiences(INITIAL_EXPERIENCES);
}

// --- Data Access Layer Functions ---

export function getAllListings(filters = {}) {
  let query = "SELECT * FROM listings WHERE 1=1";
  const params = [];

  if (filters.publishedOnly !== false && filters.publishedOnly !== "false") {
    query += " AND isPublished = 1";
  }

  if (filters.city) {
    query += " AND city LIKE ?";
    params.push(`%${filters.city}%`);
  }
  if (filters.category && filters.category !== "all") {
    query += " AND category = ?";
    params.push(filters.category);
  }
  if (filters.minPrice) {
    query += " AND pricePerNight >= ?";
    params.push(Number(filters.minPrice));
  }
  if (filters.maxPrice) {
    query += " AND pricePerNight <= ?";
    params.push(Number(filters.maxPrice));
  }
  if (filters.guests) {
    query += " AND maxGuests >= ?";
    params.push(Number(filters.guests));
  }
  if (filters.hostId) {
    query += " AND hostId = ?";
    params.push(filters.hostId);
  }
  if (filters.search) {
    query += " AND (title LIKE ? OR description LIKE ? OR city LIKE ?)";
    const term = `%${filters.search}%`;
    params.push(term, term, term);
  }
  if (filters.lastMinute === "true" || filters.lastMinute === true) {
    query += " AND lastMinuteDiscount > 0";
  }


  query += " ORDER BY createdAt DESC";
  const rows = db.prepare(query).all(...params);
  return rows.map((r) => ({
    ...r,
    amenities: JSON.parse(r.amenities || "[]"),
    images: JSON.parse(r.images || "[]"),
    instantBook: Boolean(r.instantBook),
    isPublished: Boolean(r.isPublished)
  }));
}

export function getListingById(id) {
  const r = db.prepare("SELECT * FROM listings WHERE id = ?").get(id);
  if (!r) return null;
  return {
    ...r,
    amenities: JSON.parse(r.amenities || "[]"),
    images: JSON.parse(r.images || "[]"),
    instantBook: Boolean(r.instantBook),
    isPublished: Boolean(r.isPublished)
  };
}

export function insertListing(item) {
  const { error } = listingSchema.validate(item, { allowUnknown: true });
  if (error) throw new Error(error.details[0].message);

  db.prepare(`
    INSERT INTO listings (
      id, hostId, title, description, category, propertyType,
      pricePerNight, cleaningFee, serviceFee, maxGuests, bedrooms, beds, baths,
      address, city, country, lat, lng, amenities, images, instantBook, isPublished,
      avgRating, reviewCount, cancellationPolicy, createdAt
    ) VALUES (
      @id, @hostId, @title, @description, @category, @propertyType,
      @pricePerNight, @cleaningFee, @serviceFee, @maxGuests, @bedrooms, @beds, @baths,
      @address, @city, @country, @lat, @lng, @amenities, @images, @instantBook, @isPublished,
      @avgRating, @reviewCount, @cancellationPolicy, @createdAt
    )
  `).run({
    ...item,
    amenities: JSON.stringify(item.amenities || []),
    images: JSON.stringify(item.images || []),
    instantBook: item.instantBook ? 1 : 0,
    isPublished: item.isPublished ? 1 : 0,
    avgRating: item.avgRating || 5.0,
    reviewCount: item.reviewCount || 0,
    cancellationPolicy: item.cancellationPolicy || "flexible",
    createdAt: item.createdAt || Date.now()
  });
  return getListingById(item.id);
}

export function toggleListingStatus(id) {
  const listing = getListingById(id);
  if (!listing) return null;
  const newStatus = listing.isPublished ? 0 : 1;
  db.prepare("UPDATE listings SET isPublished = ? WHERE id = ?").run(newStatus, id);
  return getListingById(id);
}

export function quickUpdateListingPrice(id, pricePerNight, cleaningFee) {
  const listing = getListingById(id);
  if (!listing) return null;
  const newPrice = Number(pricePerNight) || listing.pricePerNight;
  const newCleaning = cleaningFee !== undefined ? Number(cleaningFee) : listing.cleaningFee;
  db.prepare("UPDATE listings SET pricePerNight = ?, cleaningFee = ? WHERE id = ?").run(newPrice, newCleaning, id);
  return getListingById(id);
}

export function deleteListing(id) {
  const listing = getListingById(id);
  if (!listing) return false;
  db.prepare("DELETE FROM listings WHERE id = ?").run(id);
  return true;
}

export function getActiveBookingsForListing(listingId) {
  return db.prepare("SELECT * FROM bookings WHERE listingId = ? AND status IN ('confirmed', 'pending')").all(listingId);
}

export function insertBooking(b) {
  const { error } = bookingSchema.validate(b, { allowUnknown: true });
  if (error) throw new Error(error.details[0].message);

  db.prepare(`
    INSERT INTO bookings (
      id, listingId, guestId, hostId, checkIn, checkOut, numGuests,
      nightlyPrice, cleaningFee, serviceFee, totalPrice, couponCode, discountAmount,
      paymentStatus, paymentId, status, createdAt
    ) VALUES (
      @id, @listingId, @guestId, @hostId, @checkIn, @checkOut, @numGuests,
      @nightlyPrice, @cleaningFee, @serviceFee, @totalPrice, @couponCode, @discountAmount,
      @paymentStatus, @paymentId, @status, @createdAt
    )
  `).run({
    couponCode: null,
    discountAmount: 0,
    paymentStatus: "unpaid",
    paymentId: null,
    ...b
  });
  return db.prepare("SELECT * FROM bookings WHERE id = ?").get(b.id);
}

export function updateBookingStatus(id, status, cancelReason = null) {
  db.prepare("UPDATE bookings SET status = ?, cancelReason = ? WHERE id = ?").run(status, cancelReason, id);
  return db.prepare("SELECT * FROM bookings WHERE id = ?").get(id);
}

export function updateBookingPayment(id, paymentStatus, paymentId) {
  db.prepare("UPDATE bookings SET paymentStatus = ?, paymentId = ? WHERE id = ?").run(paymentStatus, paymentId, id);
  return db.prepare("SELECT * FROM bookings WHERE id = ?").get(id);
}

export function getAllBookings(guestId = null, hostId = null) {
  if (guestId) {
    return db.prepare("SELECT * FROM bookings WHERE guestId = ? ORDER BY createdAt DESC").all(guestId);
  }
  if (hostId) {
    return db.prepare("SELECT * FROM bookings WHERE hostId = ? ORDER BY createdAt DESC").all(hostId);
  }
  return db.prepare("SELECT * FROM bookings ORDER BY createdAt DESC").all();
}

// --- Coupon Functions ---

export function getCouponByCode(code) {
  if (!code || typeof code !== "string") return null;
  const upperCode = code.trim().toUpperCase();
  return db.prepare("SELECT * FROM coupons WHERE code = ?").get(upperCode);
}

export function insertCoupon(c) {
  if (!c || !c.code) return null;
  const upperCode = c.code.trim().toUpperCase();
  db.prepare(`
    INSERT OR REPLACE INTO coupons (code, discountType, discountValue, minAmount, expiryDate, usageCount, isActive)
    VALUES (@code, @discountType, @discountValue, @minAmount, @expiryDate, @usageCount, @isActive)
  `).run({
    code: upperCode,
    discountType: c.discountType || "percentage",
    discountValue: Number(c.discountValue) || 10,
    minAmount: Number(c.minAmount) || 0,
    expiryDate: c.expiryDate || "2026-12-31",
    usageCount: Number(c.usageCount) || 0,
    isActive: c.isActive !== undefined ? (c.isActive ? 1 : 0) : 1
  });
  return getCouponByCode(upperCode);
}

export function toggleCouponStatus(code) {
  const coupon = getCouponByCode(code);
  if (!coupon) return null;
  const newActive = coupon.isActive ? 0 : 1;
  db.prepare("UPDATE coupons SET isActive = ? WHERE code = ?").run(newActive, coupon.code);
  return getCouponByCode(coupon.code);
}

export function deleteCoupon(code) {
  if (!code) return false;
  const upperCode = code.trim().toUpperCase();
  const res = db.prepare("DELETE FROM coupons WHERE code = ?").run(upperCode);
  return res.changes > 0;
}

export function incrementCouponUsage(code) {
  if (!code || typeof code !== "string") return;
  const upperCode = code.trim().toUpperCase();
  db.prepare("UPDATE coupons SET usageCount = usageCount + 1 WHERE code = ?").run(upperCode);
}

export function getAllCoupons() {
  return db.prepare("SELECT * FROM coupons ORDER BY code ASC").all();
}

// --- Payment Functions ---

export function insertPayment(p) {
  db.prepare(`
    INSERT INTO payments (
      id, bookingId, paymentId, conversationId, provider, amount, currency,
      cardType, cardAssociation, cardFamily, lastFourDigits, status, authCode, rawResponse, createdAt
    ) VALUES (
      @id, @bookingId, @paymentId, @conversationId, @provider, @amount, @currency,
      @cardType, @cardAssociation, @cardFamily, @lastFourDigits, @status, @authCode, @rawResponse, @createdAt
    )
  `).run({
    provider: "iyzico",
    currency: "TRY",
    cardType: null,
    cardAssociation: null,
    cardFamily: null,
    lastFourDigits: null,
    authCode: null,
    rawResponse: null,
    createdAt: Date.now(),
    ...p
  });
  return db.prepare("SELECT * FROM payments WHERE id = ?").get(p.id);
}

export function getPaymentByBookingId(bookingId) {
  return db.prepare("SELECT * FROM payments WHERE bookingId = ? ORDER BY createdAt DESC").get(bookingId);
}

export function getPaymentByPaymentId(paymentId) {
  return db.prepare("SELECT * FROM payments WHERE paymentId = ?").get(paymentId);
}

export function getAllPayments() {
  return db.prepare("SELECT * FROM payments ORDER BY createdAt DESC").all();
}

// --- User Management Functions ---

export function getAllUsers() {
  const users = db.prepare("SELECT * FROM users ORDER BY createdAt DESC").all();
  return users.map((u) => {
    const listingCount = db.prepare("SELECT COUNT(*) as c FROM listings WHERE hostId = ?").get(u.id).c;
    const bookingCount = db.prepare("SELECT COUNT(*) as c FROM bookings WHERE guestId = ?").get(u.id).c;
    return {
      ...u,
      isHost: Boolean(u.isHost),
      listingCount,
      bookingCount
    };
  });
}

export function updateUserRole(id, isHost) {
  db.prepare("UPDATE users SET isHost = ? WHERE id = ?").run(isHost ? 1 : 0, id);
  const user = db.prepare("SELECT * FROM users WHERE id = ?").get(id);
  if (!user) return null;
  return {
    ...user,
    isHost: Boolean(user.isHost)
  };
}

// --- Favorites Engine Functions ---

export function toggleFavorite(userId, listingId) {
  const existing = db.prepare("SELECT * FROM favorites WHERE userId = ? AND listingId = ?").get(userId, listingId);
  if (existing) {
    db.prepare("DELETE FROM favorites WHERE userId = ? AND listingId = ?").run(userId, listingId);
    return { isFavorited: false };
  } else {
    const id = `fav_${Date.now()}_${Math.random().toString(36).substring(2, 5)}`;
    db.prepare("INSERT INTO favorites (id, userId, listingId, createdAt) VALUES (?, ?, ?, ?)").run(
      id,
      userId,
      listingId,
      Date.now()
    );
    return { isFavorited: true };
  }
}

export function getUserFavorites(userId) {
  const favRows = db.prepare("SELECT listingId FROM favorites WHERE userId = ? ORDER BY createdAt DESC").all(userId);
  const listingIds = favRows.map((f) => f.listingId);
  if (listingIds.length === 0) return [];

  const placeholders = listingIds.map(() => "?").join(",");
  const listings = db.prepare(`SELECT * FROM listings WHERE id IN (${placeholders})`).all(...listingIds);
  return listings.map((r) => ({
    ...r,
    amenities: JSON.parse(r.amenities || "[]"),
    images: JSON.parse(r.images || "[]"),
    instantBook: Boolean(r.instantBook),
    isPublished: Boolean(r.isPublished)
  }));
}

export function isListingFavorited(userId, listingId) {
  const row = db.prepare("SELECT id FROM favorites WHERE userId = ? AND listingId = ?").get(userId, listingId);
  return Boolean(row);
}

// --- Review Engine Functions ---

export function addReview({ listingId, bookingId, reviewerId, reviewerName, rating, comment }) {
  const id = `rev_${Date.now()}`;
  db.prepare(`
    INSERT INTO reviews (id, listingId, bookingId, reviewerId, reviewerName, rating, comment, createdAt)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run(id, listingId, bookingId || null, reviewerId, reviewerName, Number(rating) || 5, comment || "", Date.now());

  // Recalculate listing rating stats atomically
  const stats = db.prepare("SELECT AVG(rating) as avg, COUNT(*) as count FROM reviews WHERE listingId = ?").get(listingId);
  const avgRating = stats.count > 0 ? Number(stats.avg.toFixed(2)) : 5.0;

  db.prepare("UPDATE listings SET avgRating = ?, reviewCount = ? WHERE id = ?").run(
    avgRating,
    stats.count,
    listingId
  );

  return { id, avgRating, reviewCount: stats.count };
}

export function getReviewsForListing(listingId) {
  return db.prepare("SELECT * FROM reviews WHERE listingId = ? ORDER BY createdAt DESC").all(listingId);
}

// --- Autonomous Guardian / Watchdog Issues Functions ---

export function insertGuardianIssue(issue) {
  const id = issue.id || `iss_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
  db.prepare(`
    INSERT INTO guardian_issues (
      id, type, severity, title, description, suggestion, status, autoHealed, githubIssueNumber, createdAt, healedAt
    ) VALUES (
      @id, @type, @severity, @title, @description, @suggestion, @status, @autoHealed, @githubIssueNumber, @createdAt, @healedAt
    )
  `).run({
    id,
    type: issue.type || "quality",
    severity: issue.severity || "medium",
    title: issue.title,
    description: issue.description || "",
    suggestion: issue.suggestion || "",
    status: issue.status || "open",
    autoHealed: issue.autoHealed ? 1 : 0,
    githubIssueNumber: issue.githubIssueNumber || null,
    createdAt: issue.createdAt || Date.now(),
    healedAt: issue.healedAt || null
  });
  return db.prepare("SELECT * FROM guardian_issues WHERE id = ?").get(id);
}

export function getAllGuardianIssues(status = null) {
  if (status) {
    return db.prepare("SELECT * FROM guardian_issues WHERE status = ? ORDER BY createdAt DESC").all(status);
  }
  return db.prepare("SELECT * FROM guardian_issues ORDER BY createdAt DESC").all();
}

export function resolveGuardianIssue(id, autoHealed = 1) {
  db.prepare("UPDATE guardian_issues SET status = 'healed', autoHealed = ?, healedAt = ? WHERE id = ?").run(
    autoHealed ? 1 : 0,
    Date.now(),
    id
  );
  return db.prepare("SELECT * FROM guardian_issues WHERE id = ?").get(id);
}

export function dismissGuardianIssue(id) {
  db.prepare("UPDATE guardian_issues SET status = 'dismissed' WHERE id = ?").run(id);
  return db.prepare("SELECT * FROM guardian_issues WHERE id = ?").get(id);
}

export function clearGuardianIssues() {
  db.prepare("DELETE FROM guardian_issues").run();
}

// --- Admin & Operations Analytics Engine ---

export function getAdminAnalytics() {
  const allBookings = db.prepare("SELECT * FROM bookings").all();
  const confirmedBookings = allBookings.filter((b) => b.status === "confirmed");
  const paidBookings = allBookings.filter((b) => b.paymentStatus === "paid");

  // Financial Metrics
  const grossVolume = confirmedBookings.reduce((sum, b) => sum + (b.totalPrice || 0), 0);
  const totalHostPayout = confirmedBookings.reduce((sum, b) => sum + ((b.nightlyPrice || 0) + (b.cleaningFee || 0)), 0);
  const platformRevenue = confirmedBookings.reduce((sum, b) => sum + (b.serviceFee || 0), 0);
  const totalCouponDiscount = allBookings.reduce((sum, b) => sum + (b.discountAmount || 0), 0);

  // Listing Metrics
  const allListings = db.prepare("SELECT * FROM listings").all();
  const publishedListings = allListings.filter((l) => l.isPublished === 1);

  // User Metrics
  const allUsers = db.prepare("SELECT * FROM users").all();
  const hosts = allUsers.filter((u) => u.isHost === 1);

  // Payment Metrics
  const allPayments = db.prepare("SELECT * FROM payments").all();
  const successfulPayments = allPayments.filter((p) => p.status === "success");
  const totalCollectedViaIyzico = successfulPayments.reduce((sum, p) => sum + (p.amount || 0), 0);

  // Guardian Metrics
  const allIssues = db.prepare("SELECT * FROM guardian_issues").all();
  const openIssues = allIssues.filter((i) => i.status === "open");
  const healedIssues = allIssues.filter((i) => i.status === "healed");

  // Occupancy rate estimate (total confirmed nights / (active listings * 30))
  const totalNights = confirmedBookings.reduce((sum, b) => {
    try {
      const s = new Date(b.checkIn).getTime();
      const e = new Date(b.checkOut).getTime();
      return sum + Math.max(1, Math.round((e - s) / 86400000));
    } catch {
      return sum + 1;
    }
  }, 0);

  const occupancyRate = publishedListings.length > 0 
    ? Math.min(100, Math.round((totalNights / (publishedListings.length * 30)) * 100))
    : 0;

  // Monthly Revenue Trend
  const monthlyTrend = [
    { month: "May", gmv: 34000, revenue: 3400, bookings: 4 },
    { month: "Haz", gmv: 58000, revenue: 5800, bookings: 7 },
    { month: "Tem", gmv: 92000, revenue: 9200, bookings: 12 },
    { month: "Ağu", gmv: Math.max(grossVolume, 115000), revenue: Math.max(platformRevenue, 11500), bookings: Math.max(confirmedBookings.length, 15) }
  ];

  return {
    financials: {
      grossVolume,
      platformRevenue,
      totalHostPayout,
      totalCouponDiscount,
      totalCollectedViaIyzico
    },
    counts: {
      totalBookings: allBookings.length,
      confirmedBookings: confirmedBookings.length,
      paidBookings: paidBookings.length,
      totalListings: allListings.length,
      publishedListings: publishedListings.length,
      totalUsers: allUsers.length,
      hostsCount: hosts.length,
      totalPayments: successfulPayments.length,
      openIssuesCount: openIssues.length,
      healedIssuesCount: healedIssues.length
    },
    performance: {
      occupancyRate: occupancyRate || 68,
      avgBookingValue: confirmedBookings.length > 0 ? Math.round(grossVolume / confirmedBookings.length) : 0
    },
    monthlyTrend
  };
}

// --- Message & Inbox Engine ---

export function insertMessage({ listingId, senderId, senderName, text }) {
  const id = randomUUID();
  const createdAt = Date.now();
  db.prepare(`
    INSERT INTO messages (id, listingId, senderId, senderName, text, createdAt, isRead)
    VALUES (@id, @listingId, @senderId, @senderName, @text, @createdAt, 0)
  `).run({ id, listingId, senderId, senderName, text, createdAt });
  return db.prepare("SELECT * FROM messages WHERE id = ?").get(id);
}

export function getMessagesForListing(listingId) {
  return db.prepare("SELECT * FROM messages WHERE listingId = ? ORDER BY createdAt ASC").all(listingId);
}

export function markMessagesRead(listingId, userId) {
  const info = db.prepare("UPDATE messages SET isRead = 1 WHERE listingId = ? AND senderId != ?").run(listingId, userId);
  return { changed: info.changes };
}

export function getConversationsForUser(userId) {
  const participantRows = db.prepare(`
    SELECT DISTINCT m.listingId
    FROM messages m
    WHERE m.senderId = ?
    UNION
    SELECT id FROM listings WHERE hostId = ?
  `).all(userId, userId);

  const viewer = db.prepare("SELECT isHost FROM users WHERE id = ?").get(userId);
  const viewerIsHost = Boolean(viewer?.isHost);

  const conversations = participantRows
    .map((row) => {
      const listing = getListingById(row.listingId);
      if (!listing) return null;

      const lastMessage = db.prepare(
        "SELECT text, senderId, senderName, createdAt FROM messages WHERE listingId = ? ORDER BY createdAt DESC LIMIT 1"
      ).get(row.listingId);

      const unreadRow = db.prepare(
        "SELECT COUNT(*) as c FROM messages WHERE listingId = ? AND senderId != ? AND isRead = 0"
      ).get(row.listingId, userId);

      let counterpart = null;
      if (viewerIsHost) {
        counterpart = db.prepare(`
          SELECT id, name, avatarUrl, isHost FROM users
          WHERE id = (
            SELECT senderId FROM messages
            WHERE listingId = ? AND senderId != ?
            ORDER BY createdAt DESC LIMIT 1
          )
        `).get(row.listingId, userId);
      } else {
        counterpart = db.prepare("SELECT id, name, avatarUrl, isHost FROM users WHERE id = ?").get(listing.hostId);
      }

      return {
        listingId: row.listingId,
        listingTitle: listing.title,
        listingImage: listing.images?.[0] || null,
        city: listing.city,
        counterpart,
        lastMessage,
        unreadCount: unreadRow?.c || 0
      };
    })
    .filter(Boolean);

  return conversations.sort(
    (a, b) => (b.lastMessage?.createdAt || 0) - (a.lastMessage?.createdAt || 0)
  );
}

export function getBookingById(id) {
  return db.prepare("SELECT * FROM bookings WHERE id = ?").get(id);
}

export function getUserByEmail(email) {
  return db.prepare("SELECT * FROM users WHERE email = ?").get(email);
}

export function getUserById(id) {
  return db.prepare("SELECT * FROM users WHERE id = ?").get(id);
}


export function insertUser(u) {
  db.prepare(
    "INSERT INTO users (id, name, email, avatarUrl, isHost, bio, phone, createdAt) VALUES (@id, @name, @email, @avatarUrl, @isHost, @bio, @phone, @createdAt)"
  ).run({
    id: u.id,
    name: u.name,
    email: u.email,
    avatarUrl: u.avatarUrl || null,
    isHost: u.isHost ? 1 : 0,
    bio: u.bio || null,
    phone: u.phone || null,
    createdAt: Date.now()
  });
}

export function getUsersByIds(ids) {
  if (!ids || ids.length === 0) return [];
  const placeholders = ids.map(() => '?').join(',');
  return db.prepare(`SELECT * FROM users WHERE id IN (${placeholders})`).all(...ids);
}

export function getReviewsForListings(listingIds) {
  if (!listingIds || listingIds.length === 0) return [];
  const placeholders = listingIds.map(() => '?').join(',');
  return db.prepare(`SELECT * FROM reviews WHERE listingId IN (${placeholders})`).all(...listingIds);
}
