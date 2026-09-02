import { db } from "./db.js";

export function getAllExperiences(category = null, city = null) {
  let sql = "SELECT * FROM experiences WHERE isActive = 1";
  const params = [];
  if (category && category !== "all") {
    sql += " AND category = ?";
    params.push(category);
  }
  if (city) {
    sql += " AND city = ?";
    params.push(city);
  }
  sql += " ORDER BY createdAt DESC";
  return db.prepare(sql).all(...params).map(parseExperience);
}

export function getExperienceById(id) {
  const row = db.prepare("SELECT * FROM experiences WHERE id = ?").get(id);
  return row ? parseExperience(row) : null;
}

export function createExperienceReservation({ experienceId, userId, participants, reservationDate }) {
  const experience = getExperienceById(experienceId);
  if (!experience) return { success: false, error: "Deneyim bulunamadı." };
  if (participants > experience.maxParticipants) {
    return { success: false, error: `Maksimum ${experience.maxParticipants} kişi katılabilir.` };
  }

  const existingCount = db.prepare(
    "SELECT COALESCE(SUM(participants), 0) as total FROM experience_reservations WHERE experienceId = ? AND reservationDate = ? AND status = 'confirmed'"
  ).get(experienceId, reservationDate).total;

  if (existingCount + participants > experience.maxParticipants) {
    return { success: false, error: "Bu tarih için yeterli kontenjan kalmamıştır." };
  }

  const id = `exp_res_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
  const totalPrice = experience.pricePerPerson * participants;

  db.prepare(`
    INSERT INTO experience_reservations (id, experienceId, userId, participants, reservationDate, totalPrice, status, createdAt)
    VALUES (?, ?, ?, ?, ?, ?, 'confirmed', ?)
  `).run(id, experienceId, userId, participants, reservationDate, totalPrice, Date.now());

  return { success: true, id, totalPrice, experience };
}

export function getUserExperienceReservations(userId) {
  const rows = db.prepare(`
    SELECT er.*, e.title, e.category, e.duration, e.images, e.location, e.city
    FROM experience_reservations er
    JOIN experiences e ON e.id = er.experienceId
    WHERE er.userId = ?
    ORDER BY er.createdAt DESC
  `).all(userId);
  return rows.map((r) => ({
    ...r,
    images: JSON.parse(r.images || "[]")
  }));
}

export function cancelExperienceReservation(id, userId) {
  const reservation = db.prepare("SELECT * FROM experience_reservations WHERE id = ? AND userId = ?").get(id, userId);
  if (!reservation) return { success: false, error: "Rezervasyon bulunamadı." };
  if (reservation.status !== "confirmed") return { success: false, error: "Rezervasyon zaten iptal edilmiş." };

  db.prepare("UPDATE experience_reservations SET status = 'cancelled' WHERE id = ?").run(id);
  return { success: true, refundAmount: reservation.totalPrice * 0.8 };
}

function parseExperience(row) {
  return {
    ...row,
    images: JSON.parse(row.images || "[]"),
    includes: JSON.parse(row.includes || "[]"),
    isActive: Boolean(row.isActive)
  };
}