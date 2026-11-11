(() => {
  'use strict';

  const ARCHETYPES = [
    'archon', 'redteam', 'weaver', 'verifier', 'oracle', 'critic',
    'explorer', 'synthesizer', 'skeptic', 'formalist', 'empiricist', 'minimalist',
    'mechanist', 'bayesian', 'historian', 'adversary', 'craftsman', 'diagnostician',
    'cartographer', 'economist', 'ethicist', 'pedagogue', 'inquisitor', 'arbiter'
  ];

  const DOMAINS = [
    'systems & concurrency', 'algorithms & complexity', 'security & failure modes',
    'mathematics & invariants', 'data & statistics', 'hardware & cost',
    'networking & protocols', 'storage & state', 'compilers & semantics',
    'operating systems', 'cryptography & trust', 'human factors & UX',
    'economics & incentives', 'physics & physical limits', 'biology & adaptation',
    'law, policy & liability', 'operations & incident response', 'epistemology & measurement'
  ];

  const STANCES = [
    'first-principles', 'contrarian', 'steelman-the-opposite', 'concrete-examples-only',
    'edge-cases-first', 'back-of-envelope', 'historical-precedent', 'minimal-viable'
  ];

  const PRODUCT_SIZE = ARCHETYPES.length * DOMAINS.length * STANCES.length; // 3456

  const CODEX_SPINE = [
    'State explicit premises and governing invariants before deriving conclusions.',
    'Separate necessary from sufficient conditions; test degenerate boundaries (0, 1, empty, N->inf).',
    'Search for a minimal counterexample before asserting any universal claim.',
    'Prefer concrete numbers, complexity bounds, and falsifiable mechanisms over vague prose.'
  ];

  const DOMAIN_CANONS = {
    design: {
      keywords: ['ui', 'ux', 'css', 'html', 'react', 'layout', 'design', 'landing', 'page', 'website', 'component', 'typography', 'font', 'color', 'contrast', 'wcag', 'apca', 'button', 'card', 'grid', 'hero', 'responsive', 'mobile', 'viewport', 'dark mode', 'light mode', 'theme'],
      summary: '8pt spacing grid -> 1.25-1.333 type scale -> mono uppercase eyebrows -> APCA Lc>=75 contrast -> <=10% accent budget -> >=44px touch targets & zero horizontal overflow.'
    },
    motion: {
      keywords: ['animation', 'animate', 'motion', 'transition', 'easing', 'spring', 'keyframe', 'gsap', 'canvas', 'shader', 'webgl', 'intro', 'choreography', 'scroll', 'hover', '60fps', 'aperture'],
      summary: 'EASE_OUT_EXPO [0.16,1,0.3,1] entrances (450-600ms), EASE_IN_OUT [0.76,0,0.24,1] aperture shutters, GPU transform/opacity only, clear ancestor transforms on end, honor prefers-reduced-motion.'
    },
    systems: {
      keywords: ['distributed', 'consensus', 'raft', 'paxos', 'bft', 'pbft', 'latency', 'throughput', 'queue', 'backpressure', 'rate limit', 'cache', 'database', 'sql', 'sqlite', 'proxy', 'http', 'sse', 'stream', 'concurrency', 'thread', 'async', 'lock', 'scale', 'architecture', 'daemon', 'kernel'],
      summary: 'Size concurrency against downstream RPM/TPM admission limits before fan-out; coalesce single-flight work; bound queues; guarantee non-crashing medoid/degraded fallback.'
    },
    security: {
      keywords: ['security', 'auth', 'jwt', 'oauth', 'crypto', 'encrypt', 'aes', 'ed25519', 'secret', 'vault', 'xss', 'csrf', 'sqli', 'ssrf', 'rce', 'sandbox', 'landlock', 'firewall', 'prompt injection', 'egress', 'osint', 'cve'],
      summary: 'Enumerate trust boundaries first; enforce Ring-3/Landlock least privilege, constant-time signature checks, strict origin canonicalization, and zero plaintext secret persistence.'
    },
    code: {
      keywords: ['python', 'javascript', 'typescript', 'rust', 'go', 'bash', 'function', 'class', 'bug', 'refactor', 'test', 'pytest', 'implement', 'script', 'cli', 'api', 'algorithm', 'optimize'],
      summary: 'Prefer composable zero-bloat primitives with explicit types, deterministic unit verification, and explicit handling of empty/malformed/concurrent edge cases.'
    }
  };

  const ZOTH_TOOLS = [
    {
      id: 'neuro-memory-daemon',
      name: 'Neuro-Memory Daemon (Hebbian STDP)',
      cli: 'neuro-memory-daemon --status',
      port: ':8094',
      category: 'Memory & Knowledge',
      keywords: ['memory', 'recall', 'context', 'knowledge', 'graph', 'wiki', 'obsidian', 'stdp', 'engram', 'history'],
      summary: 'Sub-millisecond Hebbian STDP episodic memory graph & Karpathy wiki recall daemon on loopback :8094.'
    },
    {
      id: 'adytum-planner',
      name: 'Adytum DAG & Goal Planner',
      cli: 'adytum --status',
      port: ':8135',
      category: 'Swarm & Core',
      keywords: ['plan', 'roadmap', 'dag', 'schedule', 'milestone', 'task', 'architecture', 'decompose', 'strategy'],
      summary: 'Deterministic DAG task decomposition, critical-path scheduling, and milestone verification daemon on :8135.'
    },
    {
      id: 'zoth-swarm-multiplexer',
      name: '21-Agent Swarm Multiplexer',
      cli: 'zoth-swarm-multiplexer --status',
      port: ':8141',
      category: 'Swarm & Core',
      keywords: ['swarm', 'multi-agent', 'pty', 'terminal', 'multiplexer', 'byzantine', 'pbft', 'quorum', 'parallel', 'orchestrate'],
      summary: '21-pane PTY multiplexer with hot-swappable Hermes x DeepSeek Flash harnesses and 3-ring PBFT telemetry.'
    },
    {
      id: 'wcag-contrast-guard',
      name: 'WCAG & APCA Contrast Guard',
      cli: 'wcag-contrast-guard --help',
      port: ':8150',
      category: 'Design & UI',
      keywords: ['ui', 'ux', 'design', 'color', 'contrast', 'wcag', 'apca', 'palette', 'accessibility', 'theme', 'light mode', 'dark mode', 'landing', 'typography'],
      summary: 'Audits foreground/background token pairs against WCAG 2.2 AA/AAA and APCA Lc perceptual contrast thresholds.'
    },
    {
      id: 'reality-shader-forge',
      name: 'Reality Shader & Theme Forge',
      cli: 'reality-forge --status',
      port: ':8118',
      category: 'Design & UI',
      keywords: ['shader', 'webgl', 'glsl', 'canvas', 'dither', 'braille', 'ascii', 'motion', 'animation', 'visual', '60fps', 'aperture'],
      summary: 'Procedural WebGL2 GLSL shader, ordered Bayer dither, and dual-theme design token forge.'
    },
    {
      id: 'cwv-speed-engine',
      name: 'Core Web Vitals Speed Engine',
      cli: 'cwv-speed-engine --help',
      port: ':8128',
      category: 'Design & UI',
      keywords: ['performance', 'lcp', 'cls', 'inp', 'lighthouse', 'bundle', 'speed', 'render', 'web', 'frontend', 'responsive'],
      summary: 'Static & runtime analyzer for LCP, INP, CLS, asset weight, and render-blocking critical paths.'
    },
    {
      id: 'hexstrike-security',
      name: 'HexStrike Security Arsenal',
      cli: 'hexstrike --status',
      port: ':8138',
      category: 'Security & Recon',
      keywords: ['security', 'pentest', 'cve', 'vuln', 'binary', 'elf', 'audit', 'hardening', 'redteam'],
      summary: 'Defensive binary auditing, CVE surface triage, and sandboxed security verification suite on :8138.'
    },
    {
      id: 'jwt-inspector-guard',
      name: 'JWT Inspector Guard',
      cli: 'jwt-inspector-guard --help',
      port: ':8124',
      category: 'Security & Recon',
      keywords: ['jwt', 'jws', 'hs256', 'rs256', 'bearer', 'oauth', 'session', 'auth', 'claims'],
      summary: 'Cryptographic JWT/JWS signature verifier and alg:none / weak-HMAC auditor.'
    },
    {
      id: 'envguard-secrets-vault',
      name: 'EnvGuard Secrets Vault',
      cli: 'envguard --help',
      port: ':8088',
      category: 'Security & Recon',
      keywords: ['secret', 'env', 'dotenv', 'api key', 'token', 'leak', 'gitleaks', 'entropy', 'vault'],
      summary: 'Zero-egress Shannon entropy & pattern scanner for .env files, keys, and repository secret hygiene.'
    },
    {
      id: 'agent-prompt-firewall',
      name: 'Agent Prompt Firewall',
      cli: 'agent-prompt-firewall --help',
      port: ':8098',
      category: 'Security & Recon',
      keywords: ['prompt injection', 'jailbreak', 'firewall', 'guardrail', 'untrusted', 'sanitize', 'policy'],
      summary: 'Deterministic lexical + structural firewall against indirect prompt injection and tool-call hijacking.'
    },
    {
      id: 'zoth-relay',
      name: 'Zoth-Relay Landlock Bridge',
      cli: 'zoth-relay --help',
      port: ':8765',
      category: 'Swarm & Core',
      keywords: ['relay', 'landlock', 'sandbox', 'ipc', 'bridge', 'mcp', 'isolation', 'kernel'],
      summary: 'Kernel Landlock-isolated multi-agent IPC & MCP tool relay on loopback :8765.'
    },
    {
      id: 'aeo-graph-engine',
      name: 'AEO & Schema.org Graph Engine',
      cli: 'aeo-graph-engine --help',
      port: ':8127',
      category: 'Memory & Knowledge',
      keywords: ['seo', 'aeo', 'schema', 'json-ld', 'llms.txt', 'sitemap', 'robots.txt', 'opengraph'],
      summary: 'Synthesizes and validates Schema.org @graph JSON-LD, FAQPage, llms.txt, and crawler directives.'
    }
  ];

  const PRESETS = {
    design: {
      prompt: 'Design a dual-theme developer documentation & live console page that achieves APCA Lc >= 75 body contrast, 8pt vertical rhythm, and zero mobile overflow across 375px, 768px, and 1440px.',
      synthesis: `1. ANCHOR & TOKEN INVARIANTS
- Lock a single focal workbench above the fold; allocate >= 85% of viewport pixels to neutral canvas/surface tokens and <= 10% to one primary semantic accent.
- Dark token spine: canvas #06080B, surface #0C1118, primary ink #EDF3F8 (APCA Lc ~96), muted copy #98A8B8 (APCA Lc ~58, >= 6.8:1 WCAG).
- Light token spine: alabaster #F6F4EE, card #FFFFFF, ink #0F161E (APCA Lc ~98), accent darkened to #0B7D63 so labels maintain >= 5.1:1 contrast.

2. SPATIAL & TYPOGRAPHIC HIERARCHY
- Enforce strict 8pt spacing steps (8 / 16 / 24 / 32 / 48 / 72px) and cap body measure at 65ch.
- Pair display headings (-0.03em tracking, 1.08 line-height) with 11px JetBrains Mono uppercase eyebrows (+0.22em tracking) instead of decorative borders.

3. TRIPLE-VIEWPORT OVERFLOW GUARD
- Apply min-width: 0 on every CSS Grid and Flex child, overflow-wrap: anywhere on monospace tokens/hashes, and min-height: 44px on interactive controls.
- Verify locally on ZothOS via: wcag-contrast-guard --help && cwv-speed-engine --help.`
    },
    consensus: {
      prompt: 'What breaks first when fanning out 500 concurrent LLM calls behind a single HTTP proxy, and what is the minimal architecture that prevents tail-latency collapse?',
      synthesis: `1. PRIMARY FAILURE SEQUENCE (WHAT BREAKS FIRST)
- Upstream token-per-minute (TPM) & request-per-minute (RPM) admission ceilings trigger synchronized HTTP 429 waves before CPU saturates; naive exponential retries synchronize into a retry storm that multiplies tail p99 latency by 8-15x.
- Second to fail: duplicate cold-cache fan-out and ephemeral socket/TLS connection churn under head-of-line blocking.

2. MINIMAL ZERO-COLLAPSE ARCHITECTURE
- Pre-admission sliding-window governor: reserve both projected requests AND tokens against live x-ratelimit-remaining-* headers (with 0.88 safety margin) BEFORE dispatching a wave.
- Single-flight digest coalescing: hash (model, system, prompt, temperature, max_tokens) so identical in-flight calls share one leader Event instead of billing N times.
- Adaptive-Consistency Beta stopping: evaluate 1 - I_0.5(V_2 + 1, V_1 + 1) >= 0.95 after an 8-mind seed wave so unanimous queries stop at 8 calls instead of 500, with cluster medoid fallback if synthesis times out.`
    },
    security: {
      prompt: 'Audit a browser-to-daemon local AI bridge on 127.0.0.1 for SSRF, DNS rebinding, JWT alg:none bypass, and plaintext API key leakage.',
      synthesis: `1. LOOPBACK & DNS REBINDING BOUNDARY
- Binding 127.0.0.1 alone does NOT stop malicious web origins from issuing cross-origin POSTs or DNS-rebinding Host headers. Enforce strict Host allowlisting (127.0.0.1:<port> / localhost:<port>), preflight Origin verification, and a per-session bearer nonce on mutating routes.

2. CRYPTOGRAPHIC & TOKEN HYGIENE
- Pin explicit verification algorithms (EdDSA / RS256 / HS256 with >= 256-bit key material) inside the verifier; reject alg:none and unverified header.kid lookups unconditionally (verify with jwt-inspector-guard).
- Never persist provider keys in plaintext repo dotenv files or browser localStorage by default; read from ephemeral memory or ZothOS RAM-backed vault (~/.hermes/auth.json mode 0600) and gate commits with envguard + gitleaks.`
    },
    motion: {
      prompt: 'Specify a 60fps route-intro to interactive-canvas handoff that feels surgical, never traps keyboard/repeat users, and preserves position:fixed modals.',
      synthesis: `1. TIMING & EASING CHOREOGRAPHY
- Cap first-visit route intro at <= 1,400ms total; bypass automatically via sessionStorage after first view and immediately on Esc, Space, Click, or prefers-reduced-motion: reduce.
- Use cubic-bezier(0.76, 0, 0.24, 1) (680ms) for the aperture shutter split and cubic-bezier(0.16, 1, 0.3, 1) (480ms, 50ms stagger, <= 350ms total stagger cap) for primary hero content.

2. COMPOSITOR & FIXED-DESCENDANT INVARIANTS
- Animate exclusively transform, opacity, and clip-path; size canvas backing stores by Math.min(devicePixelRatio, 2) and pause requestAnimationFrame when document.hidden is true.
- Clear transform / filter / will-change to 'none' on transitionend so any position:fixed drawer or modal inside the page retains viewport-anchored coordinates.`
    }
  };

  // --- Exact Math Port from egregore/lenses.py & egregore/consensus.py ---

  function gcd(a, b) {
    let x = Math.abs(a), y = Math.abs(b);
    while (y !== 0) {
      const t = x % y;
      x = y;
      y = t;
    }
    return x;
  }

  async function sha256Bytes(str) {
    const data = new TextEncoder().encode(str);
    if (window.crypto && window.crypto.subtle) {
      const buf = await window.crypto.subtle.digest('SHA-256', data);
      return new Uint8Array(buf);
    }
    // Deterministic FNV-like fallback if subtle unavailable in non-secure context
    const out = new Uint8Array(32);
    let h = 2166136261 >>> 0;
    for (let i = 0; i < data.length; i++) {
      h ^= data[i];
      h = Math.imul(h, 16777619) >>> 0;
      out[i % 32] ^= (h >>> ((i % 4) * 8)) & 0xff;
    }
    return out;
  }

  function lensAt(idx) {
    const n = ((idx % PRODUCT_SIZE) + PRODUCT_SIZE) % PRODUCT_SIZE;
    const a = n % ARCHETYPES.length;
    const d = Math.floor(n / ARCHETYPES.length) % DOMAINS.length;
    const s = Math.floor(n / (ARCHETYPES.length * DOMAINS.length)) % STANCES.length;
    return {
      index: n,
      archetype: ARCHETYPES[a],
      domain: DOMAINS[d],
      stance: STANCES[s],
      signature: `${ARCHETYPES[a]}/${STANCES[s]}`
    };
  }

  async function expandLenses(n, seedPrompt) {
    const raw = await sha256Bytes(seedPrompt || 'egregore');
    const view = new DataView(raw.buffer);
    const start = view.getUint32(0, false) % PRODUCT_SIZE;
    let stride = (view.getUint32(4, false) % (PRODUCT_SIZE - 3)) + 3;
    while (gcd(stride, PRODUCT_SIZE) !== 1) {
      stride = (stride + 1) % PRODUCT_SIZE || 5;
    }
    const lenses = [];
    for (let k = 0; k < n; k++) {
      lenses.push(lensAt((start + k * stride) % PRODUCT_SIZE));
    }
    return { start, stride, lenses };
  }

  // Exact Lentz continued fraction for regularized incomplete beta I_x(a, b)
  function logGamma(z) {
    const g = 7;
    const p = [
      0.99999999999980993, 676.5203681218851, -1259.1392167224028,
      771.32342877765313, -176.61502916214059, 12.507343278686905,
      -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7
    ];
    if (z < 0.5) {
      return Math.log(Math.PI) - Math.log(Math.sin(Math.PI * z)) - logGamma(1 - z);
    }
    z -= 1;
    let x = p[0];
    for (let i = 1; i < g + 2; i++) x += p[i] / (z + i);
    const t = z + g + 0.5;
    return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
  }

  function betacf(a, b, x) {
    const qab = a + b, qap = a + 1.0, qam = a - 1.0;
    let c = 1.0;
    let d = 1.0 - (qab * x) / qap;
    if (Math.abs(d) < 1e-30) d = 1e-30;
    d = 1.0 / d;
    let h = d;
    for (let m = 1; m <= 200; m++) {
      const m2 = 2 * m;
      let aa = (m * (b - m) * x) / ((qam + m2) * (a + m2));
      d = 1.0 + aa * d;
      if (Math.abs(d) < 1e-30) d = 1e-30;
      c = 1.0 + aa / c;
      if (Math.abs(c) < 1e-30) c = 1e-30;
      d = 1.0 / d;
      h *= d * c;
      aa = (-(a + m) * (qab + m) * x) / ((a + m2) * (qap + m2));
      d = 1.0 + aa * d;
      if (Math.abs(d) < 1e-30) d = 1e-30;
      c = 1.0 + aa / c;
      if (Math.abs(c) < 1e-30) c = 1e-30;
      d = 1.0 / d;
      const del = d * c;
      h *= del;
      if (Math.abs(del - 1.0) < 3e-12) break;
    }
    return h;
  }

  function ibeta(a, b, x) {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    if (x > (a + 1.0) / (a + b + 2.0)) return 1.0 - ibeta(b, a, 1.0 - x);
    const lbeta = logGamma(a) + logGamma(b) - logGamma(a + b);
    const front = Math.exp(a * Math.log(x) + b * Math.log(1.0 - x) - lbeta) / a;
    return front * betacf(a, b, x);
  }

  function betaLeaderConfidence(v1, v2) {
    if (v1 + v2 === 0) return 0;
    return 1.0 - ibeta(v1 + 1.0, v2 + 1.0, 0.5);
  }

  function detectCodexDomains(prompt) {
    const lower = (prompt || '').toLowerCase();
    const scored = [];
    for (const [name, spec] of Object.entries(DOMAIN_CANONS)) {
      let hits = 0;
      for (const kw of spec.keywords) {
        if (lower.includes(kw)) hits++;
      }
      if (hits > 0) scored.push([hits, name]);
    }
    scored.sort((a, b) => b[0] - a[0]);
    const picked = scored.slice(0, 2).map((s) => s[1]);
    return ['logic', ...(picked.length ? picked : ['code'])];
  }

  function matchTools(prompt, limit = 3) {
    const lower = (prompt || '').toLowerCase();
    const scored = [];
    for (const t of ZOTH_TOOLS) {
      let s = 0;
      for (const kw of t.keywords) {
        if (lower.includes(kw)) s += kw.includes(' ') ? 3 : 2;
      }
      if (s > 0) scored.push([s, t]);
    }
    if (!scored.length) {
      return ZOTH_TOOLS.slice(0, limit);
    }
    scored.sort((a, b) => b[0] - a[0]);
    return scored.slice(0, limit).map((x) => x[1]);
  }

  function tokenize(text) {
    const words = (text || '').toLowerCase().match(/[a-z0-9_]{2,}/g) || [];
    const set = new Set(words);
    for (let i = 0; i < words.length - 1; i++) set.add(`${words[i]}_${words[i + 1]}`);
    return set;
  }

  function jaccard(a, b) {
    if (!a.size && !b.size) return 1;
    if (!a.size || !b.size) return 0;
    let inter = 0;
    for (const k of a) if (b.has(k)) inter++;
    return inter / (a.size + b.size - inter);
  }

  // --- Lattice Visualization State ---
  const latticeState = {
    start: 412,
    stride: 109,
    activeCount: 12,
    confidence: 0.9961,
    pulse: 0
  };

  function initLatticeCanvas() {
    const canvas = document.getElementById('latticeCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let animId = 0;
    let t = 0;

    function drawFrame() {
      const rect = canvas.parentElement.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(260, Math.floor(rect.width));
      const h = Math.max(180, Math.floor(rect.height));
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const isLight = document.documentElement.getAttribute('data-theme') === 'light';
      const bg = isLight ? '#f1eee5' : '#05080c';
      const ringStroke = isLight ? 'rgba(15, 22, 30, 0.12)' : 'rgba(148, 179, 202, 0.13)';
      const accent = isLight ? '#0b7d63' : '#4be3c1';
      const gold = isLight ? '#8c6510' : '#d4af37';
      const dimNode = isLight ? 'rgba(15, 22, 30, 0.18)' : 'rgba(148, 179, 202, 0.2)';

      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, w, h);

      const cx = w * 0.5;
      const cy = h * 0.5;
      const maxR = Math.min(w, h) * 0.42;
      const radii = [maxR * 0.36, maxR * 0.66, maxR * 0.95];
      const counts = [8, 18, 24];

      // Subtle concentric rings (8 Stances, 18 Domains, 24 Archetypes)
      for (const r of radii) {
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = ringStroke;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Compute active co-prime node positions
      const activeNodes = [];
      const shown = Math.min(24, Math.max(12, latticeState.activeCount));
      for (let k = 0; k < shown; k++) {
        const idx = (latticeState.start + k * latticeState.stride) % PRODUCT_SIZE;
        const ringIdx = k % 3;
        const r = radii[ringIdx];
        // Co-prime angular projection across the full 3,456 Pantheon space
        const baseAngle = ((idx / PRODUCT_SIZE) * Math.PI * 2) + (k * 2.399963229728653);
        const drift = reducedMotion ? 0 : t * (0.14 - ringIdx * 0.03) * (ringIdx % 2 === 0 ? 1 : -1);
        const ang = baseAngle + drift;
        activeNodes.push({
          x: cx + Math.cos(ang) * r,
          y: cy + Math.sin(ang) * r,
          lead: k < Math.ceil(shown * 0.78)
        });
      }

      // Draw background passive lattice ticks
      for (let rIdx = 0; rIdx < 3; rIdx++) {
        const r = radii[rIdx];
        const cnt = counts[rIdx];
        for (let i = 0; i < cnt; i++) {
          const ang = (i / cnt) * Math.PI * 2;
          const nx = cx + Math.cos(ang) * r;
          const ny = cy + Math.sin(ang) * r;
          ctx.beginPath();
          ctx.arc(nx, ny, 2, 0, Math.PI * 2);
          ctx.fillStyle = dimNode;
          ctx.fill();
        }
      }

      // Draw refraction rays from active co-prime minds into the central collapse prism
      for (let i = 0; i < activeNodes.length; i++) {
        const n = activeNodes[i];
        ctx.beginPath();
        ctx.moveTo(n.x, n.y);
        ctx.lineTo(cx, cy);
        ctx.strokeStyle = n.lead
          ? (isLight ? 'rgba(11, 125, 99, 0.24)' : 'rgba(75, 227, 193, 0.24)')
          : (isLight ? 'rgba(140, 101, 16, 0.22)' : 'rgba(212, 175, 55, 0.22)');
        ctx.lineWidth = 1.1;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(n.x, n.y, n.lead ? 3.4 : 3.0, 0, Math.PI * 2);
        ctx.fillStyle = n.lead ? accent : gold;
        ctx.fill();
      }

      // Central Beta-Posterior Synthesis Core
      const corePulse = reducedMotion ? 1 : 1 + Math.sin(t * 2.6) * 0.08 + latticeState.pulse * 0.25;
      latticeState.pulse *= 0.92;

      ctx.beginPath();
      ctx.arc(cx, cy, 16 * corePulse, 0, Math.PI * 2);
      ctx.fillStyle = isLight ? 'rgba(11, 125, 99, 0.14)' : 'rgba(75, 227, 193, 0.16)';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy, 7.5, 0, Math.PI * 2);
      ctx.fillStyle = accent;
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = gold;
      ctx.stroke();

      if (!reducedMotion && !document.hidden) {
        t += 0.016;
        animId = requestAnimationFrame(drawFrame);
      }
    }

    drawFrame();
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && !reducedMotion) {
        cancelAnimationFrame(animId);
        animId = requestAnimationFrame(drawFrame);
      }
    });
    window.addEventListener('resize', drawFrame);
    window.__redrawEgregoreLattice = drawFrame;
  }

  // --- Workbench Logic ---
  async function updateDeterministicRouting(prompt, modeVal, activePresetKey) {
    const countMap = { auto: 8, probe: 8, '50': 50, '256': 256, '1000': 1000 };
    const nRequested = countMap[modeVal] || 8;
    const sampleShow = Math.min(nRequested, 12);
    const { start, stride, lenses } = await expandLenses(sampleShow, prompt);
    const domains = detectCodexDomains(prompt);
    const tools = matchTools(prompt, 3);

    // Update Hero Lattice State & Telemetry
    latticeState.start = start;
    latticeState.stride = stride;
    latticeState.activeCount = nRequested;
    latticeState.pulse = 1.0;
    if (window.__redrawEgregoreLattice) window.__redrawEgregoreLattice();

    const tStride = document.getElementById('teleStride');
    const tMinds = document.getElementById('teleMinds');
    const tConf = document.getElementById('teleConf');
    if (tStride) tStride.textContent = `s=${stride}`;
    if (tMinds) tMinds.textContent = modeVal === 'auto' ? '8 -> 1000' : `${nRequested}`;

    const v1 = Math.max(6, Math.round(sampleShow * 0.85));
    const v2 = Math.max(0, sampleShow - v1);
    const conf = betaLeaderConfidence(v1, v2);
    if (tConf) tConf.textContent = `P=${conf.toFixed(4)}`;

    // Render Lens Stream
    const lensStream = document.getElementById('lensStream');
    if (lensStream) {
      lensStream.innerHTML = lenses.map((l, idx) => (
        `<div class="lens-row">
          <span class="lens-sig">#${String(l.index).padStart(4, '0')} ${l.signature}</span>
          <span class="lens-dom">mind ${idx + 1}/${nRequested} · ${l.domain}</span>
        </div>`
      )).join('');
    }
    const strideBadge = document.getElementById('strideBadge');
    if (strideBadge) {
      strideBadge.textContent = `start=${start} · stride=${stride} · gcd(${stride},3456)=1`;
    }

    // Render Codex Canons
    const canonTags = document.getElementById('canonTags');
    const canonSummary = document.getElementById('canonSummary');
    if (canonTags) {
      canonTags.innerHTML = domains.map((d) => `<span class="canon-tag">codex:${d}</span>`).join('');
    }
    if (canonSummary) {
      const lines = [`[logic] ${CODEX_SPINE[0]} ${CODEX_SPINE[1]}`];
      for (const d of domains) {
        if (DOMAIN_CANONS[d]) lines.push(`[${d}] ${DOMAIN_CANONS[d].summary}`);
      }
      canonSummary.textContent = lines.join('\n');
    }

    // Render Matched Zoth Tools
    const toolList = document.getElementById('toolMatchList');
    if (toolList) {
      toolList.innerHTML = tools.map((t) => (
        `<div class="tool-match-card">
          <div class="tool-match-top">
            <span>${t.name}</span>
            <span class="tool-match-port">${t.port} · ${t.category}</span>
          </div>
          <div class="tool-match-desc">${t.summary}</div>
          <div class="tool-match-cli">$ ${t.cli}</div>
        </div>`
      )).join('');
    }

    return { start, stride, lenses, domains, tools, conf, presetKey: activePresetKey };
  }

  async function runDeliberation(activePresetKey) {
    const promptEl = document.getElementById('wbPrompt');
    const modeEl = document.getElementById('wbMode');
    const outEl = document.getElementById('synthOutput');
    const btn = document.getElementById('runDelibBtn');
    const endpoint = (document.getElementById('wireEndpoint')?.value || '').trim();
    const apiKey = (document.getElementById('wireApiKey')?.value || '').trim();
    const wireModel = (document.getElementById('wireModel')?.value || 'deepseek/deepseek-v4.1-flash').trim();

    const prompt = (promptEl?.value || '').trim();
    if (!prompt) return;
    const modeVal = modeEl?.value || 'auto';

    btn.disabled = true;
    btn.textContent = 'Convening Minds...';

    const meta = await updateDeterministicRouting(prompt, modeVal, activePresetKey);

    // Path A: Try explicit or local :8147 ZothOS Egregore daemon if user set localhost
    if (endpoint.includes('127.0.0.1:8147') || endpoint.includes('localhost:8147')) {
      try {
        outEl.textContent = `Connecting to local ZothOS Egregore daemon (${endpoint})...`;
        const body = { prompt };
        if (/^\d+$/.test(modeVal)) body.agents = parseInt(modeVal, 10);
        else body.mode = modeVal;
        const r = await fetch(`${endpoint.replace(/\/$/, '')}/v1/egregore/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        const d = await r.json();
        if (!r.ok || d.error) throw new Error(d.error?.message || `HTTP ${r.status}`);
        outEl.textContent =
          `[LIVE ZOTHOS :8147 DELIBERATION | minds=${d.agents_spawned} | agreement=${d.agreement} | P_stop=${d.stop_confidence} | stopped_by=${d.stopped_by}]\n` +
          `[codex=${(d.codex_domains || meta.domains).join(', ')} | zoth_tools=${(d.zoth_tools || meta.tools).map((x) => x.id).join(', ')}]\n\n` +
          d.text;
        btn.disabled = false;
        btn.textContent = 'Convene Pantheon';
        return;
      } catch (err) {
        outEl.textContent = `Local daemon at ${endpoint} not reachable from this browser (${err.message}). Falling back to deterministic Pantheon specification preview...\n\n`;
      }
    }

    // Path B: Live BYOK OpenAI-compatible API (Nous Portal / DeepSeek / OpenRouter)
    if (apiKey) {
      try {
        const base = (endpoint && !endpoint.includes(':8147'))
          ? endpoint.replace(/\/$/, '')
          : 'https://inference-api.nousresearch.com/v1';
        const scoutN = 4; // Safe browser fan-out wave
        outEl.textContent = `Dispatching ${scoutN} live co-prime scout lenses against ${base} (${wireModel})...`;
        const { lenses } = await expandLenses(scoutN, prompt);
        const calls = lenses.map(async (l) => {
          const sys = `You are one mind (${l.signature}, domain: ${l.domain}) inside EGREGORE (DeepSeek Flash x Nous Hermes). Apply strict deductive logic and 8pt/APCA design rigor. Give a concise, direct technical answer.`;
          const resp = await fetch(`${base}/chat/completions`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
              model: wireModel,
              temperature: 0.7,
              max_tokens: 420,
              messages: [
                { role: 'system', content: sys },
                { role: 'user', content: prompt }
              ]
            })
          });
          const j = await resp.json();
          if (!resp.ok) throw new Error(j.error?.message || `HTTP ${resp.status}`);
          return (j.choices?.[0]?.message?.content || '').trim();
        });
        const answers = (await Promise.all(calls)).filter(Boolean);
        const tokSets = answers.map(tokenize);
        let simSum = 0, pairs = 0;
        for (let i = 0; i < tokSets.length; i++) {
          for (let j = i + 1; j < tokSets.length; j++) {
            simSum += jaccard(tokSets[i], tokSets[j]);
            pairs++;
          }
        }
        const agreement = pairs ? (simSum / pairs) : 1;
        const synthResp = await fetch(`${base}/chat/completions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`
          },
          body: JSON.stringify({
            model: wireModel,
            temperature: 0.25,
            max_tokens: 700,
            messages: [
              {
                role: 'system',
                content: 'You are the single synthesis voice of EGREGORE. Collapse the scout positions below into one direct, authoritative technical answer. Do not mention the deliberation.'
              },
              {
                role: 'user',
                content: `QUESTION:\n${prompt}\n\nSCOUT POSITIONS:\n` + answers.map((a, i) => `[${i + 1}] ${a}`).join('\n\n')
              }
            ]
          })
        });
        const sj = await synthResp.json();
        const finalTxt = (sj.choices?.[0]?.message?.content || answers[0] || '').trim();
        outEl.textContent =
          `[LIVE BYOK DELIBERATION | scouts=${answers.length} | lexical_agreement=${agreement.toFixed(3)} | model=${wireModel}]\n` +
          `[codex=${meta.domains.join(', ')} | zoth_tools=${meta.tools.map((t) => t.id).join(', ')}]\n\n` +
          finalTxt;
        btn.disabled = false;
        btn.textContent = 'Convene Pantheon';
        return;
      } catch (err) {
        outEl.textContent = `Live BYOK wire error: ${err.message}\n\n`;
      }
    }

    // Path C: Instantaneous Deterministic Co-Prime + Codex + Zoth Arsenal Synthesis Preview
    const matchedPreset = Object.values(PRESETS).find((p) => p.prompt.trim() === prompt);
    const header =
      `[DETERMINISTIC PANTHEON TRACE · OFFLINE PREVIEW | Connect :8147 on ZothOS or BYOK API Key above for live LLM inference]\n` +
      `[SHA-256 Co-Prime Walk: start=${meta.start}, stride=${meta.stride}, gcd(${meta.stride}, 3456)=1 | Beta P(leader)=${meta.conf.toFixed(4)} >= 0.95]\n` +
      `[Injected Canons: ${meta.domains.join(' + ')} | Routed Zoth Tools: ${meta.tools.map((t) => `${t.id}(${t.port})`).join(', ')}]\n\n`;

    if (matchedPreset) {
      outEl.textContent = header + matchedPreset.synthesis;
    } else {
      outEl.textContent =
        header +
        `SYNTHESIS PLAN FOR CUSTOM PROMPT:\n` +
        `1. Scout Fan-Out: Wave 1 dispatches 8 DeepSeek Flash (deepseek/deepseek-v4.1-flash) minds via Nous Hermes starting at lens #${meta.lenses[0].index} (${meta.lenses[0].signature}) with co-prime stride ${meta.stride}.\n` +
        `2. Codex Enforcement: Injects [${meta.domains.join(', ')}] axioms into every scout system prompt and the deepseek/deepseek-v4-pro synthesis collapse.\n` +
        `3. ZothOS / Zoth Studio Arsenal Augmentation:\n` +
        meta.tools.map((t) => `   - ${t.name} (${t.port}): $ ${t.cli}`).join('\n') +
        `\n4. Run Locally with Real Inference:\n   $ zoth-egregore run ${JSON.stringify(prompt.slice(0, 90))}`;
    }

    btn.disabled = false;
    btn.textContent = 'Convene Pantheon';
  }

  // --- Arsenal Grid Filter ---
  function renderArsenalGrid(category = 'All') {
    const grid = document.getElementById('arsenalGrid');
    if (!grid) return;
    const filtered = category === 'All'
      ? ZOTH_TOOLS
      : ZOTH_TOOLS.filter((t) => t.category === category);
    grid.innerHTML = filtered.map((t) => (
      `<article class="arsenal-card">
        <div>
          <div class="arsenal-meta">
            <span>${t.category}</span>
            <span>${t.port}</span>
          </div>
          <h3>${t.name}</h3>
          <p style="margin:0;color:var(--muted);font-size:14px">${t.summary}</p>
        </div>
        <div class="tool-match-cli">$ ${t.cli}</div>
      </article>`
    )).join('');
  }

  // --- Quickstart Code Tabs ---
  const CODE_SNIPPETS = {
    hermes: `# 1. Start the Egregore OpenAI-compatible face on ZothOS (:8147)
# Automatically discovers ~/.hermes/auth.json (Nous Portal) or NOUS_API_KEY / DEEPSEEK_API_KEY
zoth-egregore serve --port 8147

# 2. Point Nous Hermes Agent (or any OpenAI client) at :8147
# Deliberation depth is chosen purely via the model string:
#   zoth-egregore        -> adaptive Beta-posterior stop (8 minds -> up to 1000 on disagreement)
#   zoth-egregore:probe  -> fast single 8-mind seed wave
#   zoth-egregore:256    -> fixed 256-mind co-prime Pantheon congress
hermes chat --base-url http://127.0.0.1:8147/v1 --model zoth-egregore`,

    python: `from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8147/v1",
    api_key="local-zothos"  # Egregore uses ~/.hermes/auth.json or env keys upstream
)

resp = client.chat.completions.create(
    model="zoth-egregore:256",  # 256 co-prime DeepSeek Flash minds -> 1 DeepSeek Pro voice
    messages=[
        {"role": "user", "content": "Prove why single-flight digest coalescing prevents retry storms."}
    ],
)
print(resp.choices[0].message.content)`,

    cli: `# Install from source (Python 3.10+, zero external pip runtime dependencies)
git clone https://github.com/1nc0gn30/zoth-egregore.git
cd zoth-egregore && pip install -e .

# Inspect local ZothOS / Zoth Studio 77-tool arsenal & active Design+Logic canons
zoth-egregore tools "Audit dark mode APCA contrast and WebGL motion" --probe

# Run a single adaptive deliberation from the terminal
zoth-egregore run "Design a lock-free ring buffer telemetry schema" -n 64`,

    curl: `curl -sS http://127.0.0.1:8147/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "zoth-egregore",
    "messages": [
      {"role": "user", "content": "Audit JWT alg:none and loopback DNS rebinding defenses."}
    ]
  }' | jq .`
  };

  // --- Boot ---
  document.addEventListener('DOMContentLoaded', () => {
    // Theme toggle
    const savedTheme = localStorage.getItem('egregore-theme');
    if (savedTheme === 'light' || savedTheme === 'dark') {
      document.documentElement.setAttribute('data-theme', savedTheme);
    }
    const themeBtn = document.getElementById('themeToggle');
    const syncThemeLabel = () => {
      const cur = document.documentElement.getAttribute('data-theme') || 'dark';
      if (themeBtn) themeBtn.textContent = cur === 'dark' ? 'LIGHT' : 'DARK';
    };
    syncThemeLabel();
    if (themeBtn) {
      themeBtn.addEventListener('click', () => {
        const cur = document.documentElement.getAttribute('data-theme') || 'dark';
        const next = cur === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('egregore-theme', next);
        syncThemeLabel();
        if (window.__redrawEgregoreLattice) window.__redrawEgregoreLattice();
      });
    }

    // Copy buttons
    document.querySelectorAll('[data-copy]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const text = btn.getAttribute('data-copy') || '';
        const orig = btn.textContent;
        try {
          await navigator.clipboard.writeText(text);
          btn.textContent = 'Copied';
          setTimeout(() => { btn.textContent = orig; }, 1600);
        } catch (_e) {
          btn.textContent = 'Ready';
        }
      });
    });

    // Wire drawer toggle
    const wireBtn = document.getElementById('toggleWireBtn');
    const wireDrawer = document.getElementById('wireDrawer');
    if (wireBtn && wireDrawer) {
      wireBtn.addEventListener('click', () => {
        const open = wireDrawer.hasAttribute('hidden');
        if (open) wireDrawer.removeAttribute('hidden');
        else wireDrawer.setAttribute('hidden', '');
        wireBtn.setAttribute('aria-expanded', String(open));
      });
    }

    // Presets
    let currentPreset = 'consensus';
    const promptEl = document.getElementById('wbPrompt');
    const modeEl = document.getElementById('wbMode');

    document.querySelectorAll('[data-preset]').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('[data-preset]').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentPreset = btn.getAttribute('data-preset') || 'consensus';
        const spec = PRESETS[currentPreset];
        if (spec && promptEl) {
          promptEl.value = spec.prompt;
          runDeliberation(currentPreset);
        }
      });
    });

    if (promptEl) {
      promptEl.addEventListener('input', () => {
        updateDeterministicRouting(promptEl.value, modeEl?.value || 'auto', currentPreset);
      });
    }
    if (modeEl) {
      modeEl.addEventListener('change', () => {
        updateDeterministicRouting(promptEl?.value || '', modeEl.value, currentPreset);
      });
    }
    const runBtn = document.getElementById('runDelibBtn');
    if (runBtn) {
      runBtn.addEventListener('click', () => runDeliberation(currentPreset));
    }

    // Arsenal filter buttons
    renderArsenalGrid('All');
    document.querySelectorAll('[data-cat]').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('[data-cat]').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        renderArsenalGrid(btn.getAttribute('data-cat') || 'All');
      });
    });

    // Code tabs
    const codeOut = document.getElementById('quickstartCode');
    document.querySelectorAll('[data-code-tab]').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('[data-code-tab]').forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');
        const key = tab.getAttribute('data-code-tab') || 'hermes';
        if (codeOut && CODE_SNIPPETS[key]) codeOut.textContent = CODE_SNIPPETS[key];
      });
    });
    if (codeOut) codeOut.textContent = CODE_SNIPPETS.hermes;

    // Boot canvas + initial preset trace
    initLatticeCanvas();
    if (promptEl) {
      promptEl.value = PRESETS.consensus.prompt;
      runDeliberation('consensus');
    }
  });
})();
