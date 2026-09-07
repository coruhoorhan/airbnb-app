const fs = require('fs');
const path = 'src/App.jsx';
let appStr = fs.readFileSync(path, 'utf8');

const search = '<div className="min-h-screen';
const replacement = `<PushNotificationProvider currentUserId={currentUserId}>\n      <div className="min-h-screen`;

if (!appStr.includes('<PushNotificationProvider currentUserId')) {
    appStr = appStr.replace(search, replacement);
    // Find the end
    appStr = appStr.replace('</AdminMagdaDashboard>\n      )}', '</AdminMagdaDashboard>\n      )}\n\n      </PushNotificationProvider>');
    fs.writeFileSync(path, appStr);
}
