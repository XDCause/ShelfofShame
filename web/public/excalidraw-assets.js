// Where the drawing canvas loads its fonts from: the app itself (copied into /fonts at build time
// by scripts/copy-excalidraw-fonts.js), not a CDN - the content security policy only allows our
// own files. A plain script in index.html, because Excalidraw works out its font addresses as
// soon as its code runs, and plain scripts run before the app's modules.
window.EXCALIDRAW_ASSET_PATH = '/'
