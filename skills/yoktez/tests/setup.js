// Expose a browser-compatible DOMParser to lib.js when running under Node.
const { JSDOM } = require("jsdom");
global.DOMParser = new JSDOM("").window.DOMParser;
