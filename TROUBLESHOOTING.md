# Troubleshooting — BC Backcountry Scout

## Fire Bans Not Displaying

### Problem
Fire bans are intermittently empty or never appear, despite active bans being in place in BC.

### Root Cause
The fire ban fetcher queries two BC government endpoints:
1. **Primary:** BCWS ArcGIS REST API (`services6.arcgis.com`)
2. **Fallback:** DataBC WFS (`openmaps.gov.bc.ca`)

When run from **Oracle Cloud**, requests to both endpoints may receive **403 Forbidden** responses due to IP reputation filtering. The code handles this gracefully by returning empty results, but users see "no fire bans" instead of the real data.

### Why This Happens
BC government geospatial services use IP reputation filters to prevent abuse. Oracle Cloud IP ranges may be flagged as:
- High-risk due to shared infrastructure
- Suspicious due to unusual request patterns
- Associated with automated/bot activity

Your Oracle Cloud VM's public IP is treated as potentially risky by these services.

---

## Solutions

### Option 1: Allow-list Oracle Cloud IP on BC Government Services (Preferred)

**Contact BC government's OGC (Office of the Chief Information Officer)** to request allow-listing your specific Oracle Cloud VM public IP or Oracle Cloud's ASN ranges for the fire ban endpoints.

**What to provide them:**
- Your current public IP: `curl https://ifconfig.me` (run on your VM)
- Oracle Cloud ASN numbers: `131958` (main), `131959` (secondary)
- Use case: Automated backcountry trip planner bot

**Expected outcome:** Direct, permanent fix. No code changes needed.

---

### Option 2: Use a Proxy through a Whitelisted IP

If you have access to an external server with a non-cloud IP (or one already on BC government's allowlist), route requests through it.

**Steps:**
1. Set up a proxy on a whitelisted IP (e.g., residential ISP, academic institution, or private VPS on datacenter not flagged by BC services)
2. Update `fetchers/wildfire.py` to route fire ban requests through the proxy:
   ```python
   # In _fetch_fire_bans_arcgis() and _fetch_fire_bans_wfs()
   proxies = {
       "https://": "http://your-proxy-ip:port",
       "http://": "http://your-proxy-ip:port",
   }
   response = httpx.get(..., proxies=proxies, timeout=_FIREBANS_TIMEOUT)
   ```

**Effort:** Medium (requires proxy infrastructure, adds latency ~200ms per request)

---

### Option 3: Change Hosting Provider

Move the bot to a non-cloud provider where IP reputation is better:
- **Linode** (Akamai) — generally well-reputed
- **DigitalOcean** — similar to Linode
- **Residential VPS** (avoid datacenter-only providers)
- **Home/office internet** with port forwarding (simplest but least reliable)

**Effort:** High (requires VM migration, DNS updates, redeployment)

---

### Option 4: Graceful Degradation (Current Behavior)

The code already does this: fire bans simply return empty lists on network errors. Users see:
```
✅ No immediate hazards or alerts
```

This is safe (users aren't harmed by missing fire bans), but incomplete. Not ideal long-term, but acceptable as a temporary workaround while investigating Option 1.

---

## Quick Check: Is It a Network Block?

Run this on your Oracle Cloud VM to diagnose:

```bash
# Test BCWS ArcGIS endpoint
curl -v "https://services6.arcgis.com/ubm4tcTYICKBpist/arcgis/rest/services/BCWS_FireBans_PublicView/FeatureServer/0/query?geometry=-123.1558%2C49.7016&geometryType=esriGeometryPoint&f=json"

# Test DataBC WFS endpoint  
curl -v "https://openmaps.gov.bc.ca/geo/pub/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName=pub:WHSE_LAND_AND_NATURAL_RESOURCE.PROT_BANS_AND_PROHIBITIONS_SP&outputFormat=json"
```

**Expected:** 200 OK with GeoJSON response  
**Actual (likely):** 403 Forbidden or timeout

If both fail, IP filtering is the cause.

---

## Recommended Path Forward

1. **First:** Run the diagnostics above to confirm the block
2. **Second:** Try **Option 1** (contact BC government) — lowest effort, permanent fix
3. **If stuck:** Use **Option 4** (graceful degradation) temporarily while pursuing Option 1
4. **Last resort:** Evaluate Options 2–3 based on your infrastructure setup

---

## Code Handling (No Changes Needed)

The fire ban fetcher already handles failures correctly:

```python
# fetchers/wildfire.py — fetch_fire_bans()
def fetch_fire_bans(destination: tuple[float, float]) -> list[FireBan]:
    lat, lon = destination
    result = _fetch_fire_bans_arcgis(lat, lon)  # Returns None on error
    if result is None:
        result = _fetch_fire_bans_wfs(lat, lon)  # Fallback
    return result  # Empty list if both fail
```

If both endpoints are blocked by the same IP filter, users see no fire bans but the bot continues operating normally.
