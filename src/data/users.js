export const INITIAL_USERS = [
  {
    id: "usr_guest_01",
    name: "Ahmet Yılmaz",
    email: "guest@fatsa.bel.tr",
    avatarUrl: "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=200&q=80",
    isHost: false,
    bio: "Doğa aşığı gezgin ve mimar.",
    phone: "+90 532 111 2233",
    createdAt: Date.now() - 30 * 86400000
  },
  {
    id: "usr_host_01",
    name: "Zeynep Kaya",
    email: "host@fatsa.bel.tr",
    avatarUrl: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=200&q=80",
    isHost: true,
    bio: "Süper Ev Sahibi • 5 yıldır Ege ve Akdeniz bölgesinde villa kiralama deneyimi.",
    phone: "+90 533 444 5566",
    createdAt: Date.now() - 365 * 86400000
  }
];
