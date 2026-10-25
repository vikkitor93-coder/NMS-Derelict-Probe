// node system_names_705_parity.js CASES.json : prints "ok N" or the mismatches. CASES = {"cases":[[addr,galaxy|null],..],"exp":[..]}
const fs = require("fs"), zlib = require("zlib"), path = require("path");
const N = require(path.join(__dirname, "js", "system_names_705.js"));
N.init(JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(__dirname, "system_names_705_data.json.gz")))));
const { cases, exp } = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const bad = [];
cases.forEach(([a, g], i) => { const n = N.name(a, g); if (n !== exp[i]) bad.push([a, g, n, exp[i]]); });
console.log(bad.length ? "MISMATCH " + JSON.stringify(bad.slice(0, 5)) : "ok " + cases.length);
process.exit(bad.length ? 1 : 0);
