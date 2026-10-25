// node names_js_runner.js <names.js> <data.json.gz> < lines "addr[ galaxy]"  ->  one name per line
const fs = require("fs"), zlib = require("zlib");
const N = require(require("path").resolve(process.argv[2]));
N.init(JSON.parse(zlib.gunzipSync(fs.readFileSync(process.argv[3]))));
const out = fs.readFileSync(0, "utf8").split("\n").filter(Boolean).map(l => { const [a, g] = l.split(" "); return N.name(a, g === undefined ? undefined : Number(g)); });
process.stdout.write(out.join("\n") + "\n");
