const fs = require('fs');
const path = 'src/App.jsx';
let appStr = fs.readFileSync(path, 'utf8');

if (!appStr.includes('</PushNotificationProvider>')) {
   appStr = appStr.replace('<MagdaConciergeWidget onSelectListing={(id) => setSelectedListing(id)} />\n\n    </div>', '<MagdaConciergeWidget onSelectListing={(id) => setSelectedListing(id)} />\n\n    </PushNotificationProvider>\n    </div>');
   fs.writeFileSync(path, appStr);
}
