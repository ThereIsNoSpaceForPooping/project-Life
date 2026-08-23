const { execSync } = require('child_process');
const path = require('path');

const chrome = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const base = 'e:\\008其他\\桌面\\WEB\\project-Life\\简历';

const files = [
  { input: '杨泽众-Agent-单栏-backup.html', output: '杨泽众-Agent-v1.pdf' },
  { input: '杨泽众-Agent-双栏-backup.html', output: '杨泽众-Agent-v2.pdf' },
];

for (const { input, output } of files) {
  const htmlPath = path.join(base, input);
  const pdfPath = path.join(base, output);
  const url = 'file:///' + htmlPath.replace(/\\/g, '/');
  const cmd = `"${chrome}" --headless --disable-gpu --print-to-pdf="${pdfPath}" --print-to-pdf-no-header --run-all-compositor-stages-before-draw "${url}"`;
  try {
    execSync(cmd, { stdio: 'inherit', shell: true });
    console.log(`Done: ${output}`);
  } catch (e) {
    console.error(`Failed: ${output}`, e.message);
  }
}
