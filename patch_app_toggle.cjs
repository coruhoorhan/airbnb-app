const fs = require('fs');
const path = 'src/App.jsx';
let appStr = fs.readFileSync(path, 'utf8');

// Insert PushNotificationToggle inside the user settings dropdown
// The User Dropdown is typically where <button onClick={handleLogout}> is
const search = '<button\n                            onClick={handleLogout}';
const replacement = '<PushNotificationToggle />\n                          <button\n                            onClick={handleLogout}';

if (appStr.includes(search) && !appStr.includes('<PushNotificationToggle />')) {
    appStr = appStr.replace(search, replacement);
    fs.writeFileSync(path, appStr);
}
