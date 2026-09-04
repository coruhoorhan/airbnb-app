import React, { useState } from "react";
import { X, Check, ArrowRight, ArrowLeft, Home, MapPin, Users, Sparkles, Image, Tag, DollarSign, CheckCircle2 } from "lucide-react";

export function RentModal({ isOpen, onClose, onCreateListing, hostId }) {
  const [step, setStep] = useState(1);
  const [category, setCategory] = useState("Lüks Villa");
  const [propertyType, setPropertyType] = useState("Müstakil Villa");
  const [city, setCity] = useState("Muğla");
  const [address, setAddress] = useState("");
  const [maxGuests, setMaxGuests] = useState(4);
  const [bedrooms, setBedrooms] = useState(2);
  const [beds, setBeds] = useState(2);
  const [baths, setBaths] = useState(2);
  const [amenities, setAmenities] = useState(["wifi", "pool", "kitchen"]);
  const [imageUrl, setImageUrl] = useState("https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1200&q=80");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [pricePerNight, setPricePerNight] = useState(3500);
  const [cleaningFee, setCleaningFee] = useState(500);
  const [instantBook, setInstantBook] = useState(true);

  if (!isOpen) return null;

  const toggleAmenity = (key) => {
    setAmenities((prev) => 
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const handlePublish = () => {
    onCreateListing({
      hostId,
      title: title || "Harika Tatil Villası",
      description: description || "Doğa ile iç içe, konforlu ve huzurlu bir konaklama deneyimi.",
      category,
      propertyType,
      city,
      address: address || `${city} Merkez`,
      country: "Türkiye",
      lat: 37.0,
      lng: 27.4,
      maxGuests,
      bedrooms,
      beds,
      baths,
      amenities,
      images: [imageUrl],
      pricePerNight: Number(pricePerNight),
      cleaningFee: Number(cleaningFee),
      serviceFee: Math.round(Number(pricePerNight) * 0.1),
      instantBook,
      isPublished: true,
      avgRating: 5.0,
      reviewCount: 0,
      cancellationPolicy: "flexible"
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white w-full max-w-xl rounded-3xl p-6 shadow-2xl flex flex-col gap-6 relative max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-charcoal-border/50 pb-3">
          <div>
            <h3 className="text-lg font-bold text-charcoal">Evinizi Airbnb ye Taşıyın</h3>
            <p className="text-xs text-charcoal-light font-medium">Adım {step} / 6</p>
          </div>
          <button aria-label="X" onClick={onClose} className="p-2 rounded-full hover:bg-charcoal-bg"> <X /> </button>
        </div>

        {/* Step 1: Category & Property Type */}
        {step === 1 && (
          <div className="flex flex-col gap-4 animate-in fade-in">
            <h4 className="font-extrabold text-base text-charcoal">Mekanınızı en iyi hangi kategori tanımlıyor?</h4>
            <div className="grid grid-cols-2 gap-3">
              {["Lüks Villa", "Plaj", "Tarihi Evler", "Kulübe", "Göl Kenarı", "Tiny House"].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setCategory(cat)}
                  className={`p-4 rounded-2xl border-2 text-left font-bold text-sm transition-all ${
                    category === cat ? "border-airbnb bg-airbnb/5 text-airbnb" : "border-charcoal-border text-charcoal hover:border-charcoal"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Location */}
        {step === 2 && (
          <div className="flex flex-col gap-4 animate-in fade-in">
            <h4 className="font-extrabold text-base text-charcoal">Eviniz nerede bulunuyor?</h4>
            <div>
              <label className="block text-xs font-bold text-charcoal uppercase mb-1">Şehir</label>
              <input 
                type="text"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full border border-charcoal-border rounded-xl px-3.5 py-2.5 text-sm font-semibold text-charcoal outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-charcoal uppercase mb-1">Açık Adres</label>
              <input 
                type="text"
                placeholder="Örn: Yalıkavak Mah. Değirmenler Cad."
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full border border-charcoal-border rounded-xl px-3.5 py-2.5 text-sm font-semibold text-charcoal outline-none"
              />
            </div>
          </div>
        )}

        {/* Step 3: Capacity & Amenities */}
        {step === 3 && (
          <div className="flex flex-col gap-4 animate-in fade-in">
            <h4 className="font-extrabold text-base text-charcoal">Kapasite ve Temel Olanaklar</h4>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-charcoal uppercase mb-1">Misafir</label>
                <input 
                  type="number"
                  value={maxGuests}
                  onChange={(e) => setMaxGuests(Number(e.target.value))}
                  className="w-full border border-charcoal-border rounded-xl p-2 text-sm font-bold text-charcoal"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-charcoal uppercase mb-1">Yatak Odası</label>
                <input 
                  type="number"
                  value={bedrooms}
                  onChange={(e) => setBedrooms(Number(e.target.value))}
                  className="w-full border border-charcoal-border rounded-xl p-2 text-sm font-bold text-charcoal"
                />
              </div>
            </div>

            <div className="pt-2">
              <label className="block text-xs font-bold text-charcoal uppercase mb-2">Olanaklar</label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { key: "wifi", label: "Wi-Fi" },
                  { key: "pool", label: "Yüzme Havuzu" },
                  { key: "kitchen", label: "Mutfak" },
                  { key: "ac", label: "Klima" },
                  { key: "fireplace", label: "Şömine" },
                  { key: "parking", label: "Otopark" }
                ].map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => toggleAmenity(item.key)}
                    className={`p-2.5 rounded-xl border text-xs font-bold flex items-center justify-between ${
                      amenities.includes(item.key) ? "border-airbnb bg-airbnb/10 text-airbnb" : "border-charcoal-border text-charcoal"
                    }`}
                  >
                    <span>{item.label}</span>
                    {amenities.includes(item.key) && <Check className="w-3.5 h-3.5" />}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Photo URL */}
        {step === 4 && (
          <div className="flex flex-col gap-4 animate-in fade-in">
            <h4 className="font-extrabold text-base text-charcoal">Fotoğraf Ekleyin</h4>
            <div>
              <label className="block text-xs font-bold text-charcoal uppercase mb-1">Görsel URL (Unsplash veya CDN)</label>
              <input 
                type="text"
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                className="w-full border border-charcoal-border rounded-xl px-3.5 py-2.5 text-xs font-medium text-charcoal outline-none"
              />
            </div>
            {imageUrl && (
              <div className="aspect-video w-full rounded-2xl overflow-hidden bg-charcoal-bg">
                <img src={imageUrl} alt="Önizleme" className="w-full h-full object-cover" />
              </div>
            )}
          </div>
        )}

        {/* Step 5: Title & Description */}
        {step === 5 && (
          <div className="flex flex-col gap-4 animate-in fade-in">
            <h4 className="font-extrabold text-base text-charcoal">Başlık ve Açıklama</h4>
            <div>
              <label className="block text-xs font-bold text-charcoal uppercase mb-1">İlan Başlığı</label>
              <input 
                type="text"
                placeholder="Örn: Deniz Manzaralı Müstakil Taş Ev"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full border border-charcoal-border rounded-xl px-3.5 py-2.5 text-sm font-semibold text-charcoal outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-charcoal uppercase mb-1">Açıklama</label>
              <textarea 
                rows={3}
                placeholder="Evinizin öne çıkan özelliklerinden bahsedin..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full border border-charcoal-border rounded-xl px-3.5 py-2 text-sm font-normal text-charcoal outline-none"
              />
            </div>
          </div>
        )}

        {/* Step 6: Price & Finish */}
        {step === 6 && (
          <div className="flex flex-col gap-4 animate-in fade-in">
            <h4 className="font-extrabold text-base text-charcoal">Fiyatlandırma</h4>
            <div className="flex items-center gap-3">
              <div className="w-1/2">
                <label className="block text-xs font-bold text-charcoal uppercase mb-1">Gecelik Fiyat (₺)</label>
                <input 
                  type="number"
                  value={pricePerNight}
                  onChange={(e) => setPricePerNight(Number(e.target.value))}
                  className="w-full border border-charcoal-border rounded-xl p-3 text-lg font-extrabold text-charcoal"
                />
              </div>
              <div className="w-1/2">
                <label className="block text-xs font-bold text-charcoal uppercase mb-1">Temizlik Ücreti (₺)</label>
                <input 
                  type="number"
                  value={cleaningFee}
                  onChange={(e) => setCleaningFee(Number(e.target.value))}
                  className="w-full border border-charcoal-border rounded-xl p-3 text-lg font-extrabold text-charcoal"
                />
              </div>
            </div>

            <div className="flex items-center justify-between p-3.5 bg-charcoal-bg rounded-2xl border border-charcoal-border">
              <div>
                <p className="font-bold text-sm text-charcoal">Anında Rezervasyon</p>
                <p className="text-xs text-charcoal-light">Misafirler onay beklemeden rezerve edebilir.</p>
              </div>
              <input 
                type="checkbox"
                checked={instantBook}
                onChange={(e) => setInstantBook(e.target.checked)}
                className="w-5 h-5 accent-airbnb cursor-pointer"
              />
            </div>
          </div>
        )}

        {/* Wizard Navigation Footer */}
        <div className="flex items-center justify-between pt-4 border-t border-charcoal-border/50">
          {step > 1 ? (
            <button 
              onClick={() => setStep((s) => s - 1)}
              className="px-4 py-2.5 rounded-xl font-bold text-sm text-charcoal hover:bg-charcoal-bg flex items-center gap-1.5"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Geri</span>
            </button>
          ) : <div />}

          {step < 6 ? (
            <button 
              onClick={() => setStep((s) => s + 1)}
              className="px-6 py-2.5 bg-charcoal text-white rounded-xl font-bold text-sm hover:bg-black flex items-center gap-1.5"
            >
              <span>İleri</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button 
              onClick={handlePublish}
              className="px-6 py-2.5 bg-airbnb text-white rounded-xl font-bold text-sm hover:bg-airbnb-dark flex items-center gap-1.5 shadow-md"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>İlanı Yayınla</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
