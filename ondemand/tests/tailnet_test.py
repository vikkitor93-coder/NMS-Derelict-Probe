"""Relay listener / X-Relay-Client trust test (2026-10-24). Nothing leaves loopback: the "tailnet" listener is bound to
127.0.0.2 in-process (the real start_tailnet() refuses anything but Tailscale addresses, which is also tested).
  1 start_tailnet refuses empty config, non-tailnet bind, non-tailnet relay ip           (no socket opened)
  2 tailnet listener serves a peer listed in relay_ips and closes any other peer
  3 X-Relay-Client is trusted only from relay_ips: different values = different rate buckets from a relay peer;
    the same header from a non-relay peer is ignored (one bucket) and a bad value (not 18 hex) is ignored
Run: python -I ondemand/tests/tailnet_test.py"""
import http.client
import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import ondemand_server as S  # noqa: E402

FAILS = []


def say(name, ok, note=""):
    print(("PASS  " if ok else "FAIL  ") + name + (("  -- " + str(note)) if note else ""), flush=True)
    if not ok:
        FAILS.append(name)


def get(host, port, path, headers=None, bind=None):
    c = http.client.HTTPConnection(host, port, timeout=5, source_address=(bind, 0) if bind else None)
    c.request("GET", path, headers=headers or {})
    try:
        r = c.getresponse()
        r.read()
        return r.status
    except (OSError, http.client.HTTPException) as e:
        return type(e).__name__
    finally:
        c.close()


def main():
    cfg = S.load_config(["--port", "18791", "--cache-db", "D:/Orca/Temp/claude/od/tests/tailnet-test.sqlite", "--workers", "1", "--rate-any", "3"])
    # 1. refusals (no sockets)
    eng = S.Engine(cfg, S.Stats())
    srv = S.AppServer(cfg, eng)
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
    try:
        bad = []
        for b, ips in (("", []), ("192.168.1.5", ["100.100.1.1"]), ("100.100.9.9", ["10.0.0.9"]), ("100.100.9.9", [])):
            c2 = dict(cfg, tailnet_bind=b, relay_ips=ips)
            if S.start_tailnet(c2, eng, srv) is not None:
                bad.append((b, ips))
        say("start_tailnet refuses an empty config, a non-tailnet bind or a non-tailnet relay ip", not bad, bad)
        say("tailnet_ok: 100.64.0.0/10 and fd7a:115c:a1e0::/48 only",
            S.tailnet_ok("100.100.9.9") and S.tailnet_ok("fd7a:115c:a1e0::1") and not S.tailnet_ok("100.128.0.1") and not S.tailnet_ok("192.168.0.1") and not S.tailnet_ok("127.0.0.1"))
        say("default config: tailnet listener off", S.DEFAULTS["tailnet_bind"] == "" and S.DEFAULTS["relay_ips"] == [] and cfg["host"] == "127.0.0.1")

        # 2. relay listener on 127.0.0.2:18791, relay peer = 127.0.0.1 (the source address we connect from)
        tcfg = dict(cfg, relay_ips=["127.0.0.1"])
        tail = S.AppServer(tcfg, eng, host="127.0.0.2", twin=srv)
        threading.Thread(target=tail.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
        say("tailnet listener serves the listed relay peer", get("127.0.0.2", 18791, "/api/health", bind="127.0.0.1") == 200)
        tail.relay_ips = {"127.0.0.9"}
        r = get("127.0.0.2", 18791, "/api/health", bind="127.0.0.1")
        say("tailnet listener closes a peer that is not in relay_ips", r != 200, r)
        tail.relay_ips = {"127.0.0.1"}

        # 3. X-Relay-Client trust (limiter: 3 requests / minute / key, shared between both listeners)
        srv.relay_ips = {"127.0.0.1"}                    # the loopback listener's own peer is 127.0.0.1 here
        keys = ["%018x" % i for i in range(1, 6)]
        codes = [get("127.0.0.1", 18791, "/api/health", {"X-Relay-Client": k}) for k in keys]
        say("from a relay peer, each X-Relay-Client value is its own bucket (5 keys x 1 request all 200)", codes == [200] * 5, codes)
        one = [get("127.0.0.1", 18791, "/api/health", {"X-Relay-Client": "a" * 18}) for _ in range(5)]
        say("the same relay key is limited after 3 requests (429)", one[:3] == [200] * 3 and one[3] == 429, one)
        srv.relay_ips = set()                            # now the peer is NOT a relay: the header must be ignored
        two = [get("127.0.0.1", 18791, "/api/health", {"X-Relay-Client": "%018x" % (100 + i)}) for i in range(5)]
        say("from a non-relay peer the header is ignored (one bucket, 429 after 3)", two[:3] == [200] * 3 and 429 in two[3:], two)
        srv.relay_ips = {"127.0.0.1"}
        three = [get("127.0.0.1", 18791, "/api/health", {"X-Relay-Client": v}) for v in ("zz" * 9, "A" * 18, "1" * 17, "1" * 19)]
        say("malformed X-Relay-Client values are ignored (fall back to the peer key: 429 after the bucket is used)", three.count(200) <= 3 and 429 in three, three)
        tail.shutdown()
        tail.server_close()
    finally:
        srv.shutdown()
        srv.server_close()
        eng.shutdown()
    print("FAILS", FAILS)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
