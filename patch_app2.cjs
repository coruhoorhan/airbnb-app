const fs = require('fs');
const path = 'src/App.jsx';
let appStr = fs.readFileSync(path, 'utf8');

// Find return ( and wrap inside PushNotificationProvider
// we'll look for `<div className="min-h-screen bg-gray-50 dark:bg-charcoal transition-colors duration-300 font-sans font-medium">`
const search = '<div className="min-h-screen bg-gray-50 dark:bg-charcoal transition-colors duration-300 font-sans font-medium">';
const replacement = `<PushNotificationProvider currentUserId={currentUserId}>\n      <div className="min-h-screen bg-gray-50 dark:bg-charcoal transition-colors duration-300 font-sans font-medium">`;

if (appStr.includes(search) && !appStr.includes('<PushNotificationProvider')) {
    appStr = appStr.replace(search, replacement);

    // find the matching closing div. It's the last closing div before the end of the file, actually before `);`
    appStr = appStr.replace(/<\/div>\n  \);\n}/, '</div>\n      </PushNotificationProvider>\n  );\n}');
}

fs.writeFileSync(path, appStr);
