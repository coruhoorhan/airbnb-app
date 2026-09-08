const fs = require('fs');

const path = 'src/App.jsx';
let appStr = fs.readFileSync(path, 'utf8');

// 1. Add import
if (!appStr.includes('PushNotificationProvider')) {
    appStr = appStr.replace(
        "import React, { useState, useEffect, useCallback } from \"react\";",
        "import React, { useState, useEffect, useCallback } from \"react\";\nimport { PushNotificationProvider, usePushNotifications } from \"./components/PushNotificationProvider.jsx\";"
    );
}

// 2. Add Toggle into user settings. Let's find where to put it.
// We will create a small wrapper component inside App.jsx that uses the hook.
const toggleComponent = `
const PushNotificationToggle = () => {
  const { isSupported, permission, isSubscribed, toggleSubscription } = usePushNotifications();
  if (!isSupported) return null;

  return (
    <div className="flex items-center justify-between p-4 bg-white dark:bg-charcoal-light rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm mt-4">
      <div>
        <p className="text-sm font-bold text-charcoal dark:text-white">Anlık Bildirimler</p>
        <p className="text-xs text-charcoal-light dark:text-gray-400">Yeni mesajlar ve rezervasyon güncellemeleri</p>
      </div>
      <button
        onClick={toggleSubscription}
        className={\`px-4 py-2 rounded-lg text-xs font-bold transition-colors \${isSubscribed ? 'bg-red-50 text-red-600 hover:bg-red-100 dark:bg-red-500/10 dark:text-red-400' : 'bg-charcoal text-white hover:bg-black dark:bg-white dark:text-charcoal'}\`}
      >
        {isSubscribed ? 'Devre Dışı Bırak' : 'Aktifleştir'}
      </button>
    </div>
  );
};
`;

if (!appStr.includes('PushNotificationToggle')) {
    appStr = appStr.replace("export function App() {", toggleComponent + "\nexport function App() {");
}

// 3. Wrap with <PushNotificationProvider currentUserId={currentUserId}>
// Wait, currentUserId is state inside App. App is the root.
// We can't wrap <PushNotificationProvider currentUserId={currentUserId}> OUTSIDE of App, because currentUserId is INSIDE App.
// So we wrap the contents of return (...) in App.
fs.writeFileSync(path, appStr);
