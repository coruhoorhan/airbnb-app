const fs = require('fs');
const path = 'src/App.jsx';
let appStr = fs.readFileSync(path, 'utf8');

const search = '<Navbar';
const replacement = '<PushNotificationToggle />\n      <Navbar';

if (appStr.includes(search) && !appStr.includes('<PushNotificationToggle />\n      <Navbar')) {
  appStr = appStr.replace(search, replacement);
  fs.writeFileSync(path, appStr);
}
