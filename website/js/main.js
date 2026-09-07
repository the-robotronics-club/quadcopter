(function () {
  'use strict';

  var navToggle = document.getElementById('nav-toggle');
  var navLinks = document.getElementById('nav-links');

  function closeNav() {
    navLinks.classList.remove('open');
    navToggle.setAttribute('aria-expanded', 'false');
  }

  if (navToggle) {
    navToggle.addEventListener('click', function () {
      var open = navLinks.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', String(open));
    });
  }

  document.querySelectorAll('.nav-links a').forEach(function (link) {
    link.addEventListener('click', closeNav);
  });

  document.addEventListener('click', function (event) {
    if (!navLinks) return;
    var inHeader = navLinks.contains(event.target) || navToggle.contains(event.target);
    if (!inHeader && navLinks.classList.contains('open')) {
      closeNav();
    }
  });

  var header = document.getElementById('site-header');
  var backToTop = document.getElementById('back-to-top');
  if (header && backToTop) {
    var scrolled = function () {
      header.classList.toggle('scrolled', window.scrollY > 8);
      backToTop.classList.toggle('show', window.scrollY > 480);
    };
    window.addEventListener('scroll', scrolled, { passive: true });
    scrolled();
  }

  var year = document.getElementById('year');
  if (year) {
    year.textContent = String(new Date().getFullYear());
  }

  var revealSelectors = '.section-head, .about-card, .feature-item, .arch-card, .spec-table, .chip, .step, .sponsor-card';
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function staggerWithin(elements) {
    var seen = 0;
    var bucket = {};
    elements.forEach(function (el) {
      var parent = el.parentNode;
      if (!bucket[parent]) {
        bucket[parent] = seen++;
      }
      var delay = Math.min(bucket[parent] * 90, 540);
      el.style.transitionDelay = delay + 'ms';
    });
  }

  var revealEls = Array.prototype.slice.call(document.querySelectorAll(revealSelectors));
  if (reduceMotion) {
    revealEls.forEach(function (el) { el.classList.add('in-view'); });
  } else {
    staggerWithin(revealEls);
    revealEls.forEach(function (el) { el.classList.add('reveal'); });
    if ('IntersectionObserver' in window) {
      var revealObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('in-view');
            revealObserver.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
      revealEls.forEach(function (el) { revealObserver.observe(el); });
    } else {
      revealEls.forEach(function (el) { el.classList.add('in-view'); });
    }
  }

  var navAnchors = Array.prototype.slice.call(document.querySelectorAll('.nav-links a[href^="#"]'));
  var sections = navAnchors
    .map(function (a) { return document.querySelector(a.getAttribute('href')); })
    .filter(Boolean);

  function setActive(id) {
    navAnchors.forEach(function (a) {
      var active = a.getAttribute('href') === '#' + id;
      a.classList.toggle('active', active);
    });
  }

  if ('IntersectionObserver' in window && sections.length) {
    var sectionObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          setActive(entry.target.id);
        }
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    sections.forEach(function (s) { sectionObserver.observe(s); });
  }

  var typed = document.querySelector('.typewriter');
  if (typed && !reduceMotion) {
    var text = typed.textContent;
    var speed = 18;
    var i = 0;
    typed.classList.add('typing');
    typed.textContent = '';
    function typeNext() {
      if (i < text.length) {
        typed.textContent = text.slice(0, ++i);
        setTimeout(typeNext, speed);
      } else {
        typed.classList.remove('typing');
      }
    }
    setTimeout(typeNext, 400);
  }
})();

/* ===== AEROXMD live systems (mission-control layer, adapted from RMD.SYS) ===== */
(function () {
  'use strict';

  var AEROXMD_CONFIG = {
    org: 'the-robotronics-club',
    primaryRepo: 'quadcopter',
    galleryRepo: 'quadcopter',
    galleryPath: 'website/assets/gallery',
    featuredRepositories: ['quadcopter'],
    cacheDuration: 900000,
    topicsToDomain: {
      'ros2': 'autonomy', 'ros': 'autonomy', 'px4': 'flight', 'mavlink': 'flight',
      'opencv': 'vision', 'yolo': 'vision', 'detection': 'vision', 'tracking': 'vision',
      'gazebo': 'sim', 'sitl': 'sim', 'simulation': 'sim',
      'jetson': 'compute', 'cuda': 'compute', 'tensorrt': 'compute', 'edge': 'compute',
      'ekf': 'autonomy', 'vio': 'autonomy', 'planning': 'autonomy', 'control': 'flight'
    }
  };

  var CURATED = {
    'quadcopter': {
      mission: 'AXM-001', title: 'AEROXMD Full-Stack Autonomy', domain: 'autonomy',
      status: 'ACTIVE', blurb: 'Flagship open-source aerial navigation framework for mountain terrain.',
      tech: 'ros2 px4 jetson gazebo', objective: 'Deliver a rugged, reproducible autonomy stack on Pixhawk 6C + Jetson Orin Nano.',
      arch: 'Pixhawk 6C (PX4) over uXRCE-DDS to Jetson; VIO+EKF, occupancy-grid planning, YOLOv8 perception.',
      results: 'SITL-verified bringup; keyboard teleop with offboard arm sequence; bench-tested failsafes.',
      challenges: 'GPS-denied drift, Jetson thermal envelope, TELEM2 baud reliability.'
    },
    'vio-ekf': {
      mission: 'AXM-011', title: 'VIO + EKF State Estimation', domain: 'autonomy',
      status: 'BENCH-TESTED', blurb: 'RealSense D435i visual-inertial odometry fused for GPS-denied hold.',
      tech: 'ros2 vio ekf realsense', objective: 'Stable odometry without GPS for indoor and valley flights.',
      arch: 'D435i depth+IMU into VIO frontend, EKF fusion, /fmu/out attitude cross-check.',
      results: 'Bench drift within test envelope; SITL hold verified.', challenges: 'Vibration coupling, exposure swings.'
    },
    'planner': {
      mission: 'AXM-012', title: '3D Trajectory Planning', domain: 'autonomy',
      status: 'SIM-VERIFIED', blurb: 'Dynamic occupancy-grid mapping with real-time 3D path optimization.',
      tech: 'ros2 planning occupancy-grid', objective: 'Collision-free trajectories in cluttered mountain proxies.',
      arch: 'Voxel grid updater, kinodynamic planner, trajectory optimizer over ROS 2 graph.',
      results: 'Gazebo obstacle courses cleared in SITL.', challenges: 'Replan latency vs map resolution.'
    },
    'yolov8-edge': {
      mission: 'AXM-013', title: 'YOLOv8 Edge Perception', domain: 'vision',
      status: 'ACTIVE', blurb: 'Onboard detection, landing-zone recognition and visual tracking on Jetson GPU.',
      tech: 'yolo opencv cuda tensorrt', objective: 'Real-time detection at the edge without a ground link.',
      arch: 'IMX219 CSI feed, TensorRT-optimized YOLOv8, tracker handoff to planner.',
      results: 'Live detection overlay in field trials prep.', challenges: 'Frame-rate vs power budget.'
    },
    'failsafe-rtl': {
      mission: 'AXM-014', title: 'Fail-Safe + RTL Triggers', domain: 'flight',
      status: 'BENCH-TESTED', blurb: 'Return-to-launch, obstacle fallback and low-battery management.',
      tech: 'px4 mavlink failsafe', objective: 'Deterministic safe recovery on link, obstacle or battery faults.',
      arch: 'PX4 failsafe params + companion monitor node commanding RTL/offboard hold.',
      results: 'SITL RTL and low-battery triggers verified.', challenges: 'RC override arbitration.'
    },
    'sitl-gazebo': {
      mission: 'AXM-015', title: 'SITL + Gazebo Pipeline', domain: 'sim',
      status: 'ACTIVE', blurb: 'Full software-in-the-loop loop with PX4 SITL, Gazebo and MicroXRCE agent.',
      tech: 'gazebo sitl px4 micro-ros', objective: 'One-command simulated flight before any hardware arm.',
      arch: 'Agent on UDP 8888, PX4 SITL client, bringup launch, teleop velocity setpoints.',
      results: 'Documented 3-terminal bringup; CI-friendly.', challenges: 'Gazebo/PX4 version pinning.'
    }
  };

  var FALLBACK_REPOS = [
    { name: 'quadcopter', description: 'Autonomous quadcopter framework (ROS 2 + PX4 + Jetson).', stargazers_count: 0, forks_count: 0, language: 'Python', topics: ['ros2', 'px4'], updated_at: new Date().toISOString(), html_url: 'https://github.com/the-robotronics-club/quadcopter', homepage: '' },
    { name: 'vio-ekf', description: 'VIO + EKF state estimation bench.', stargazers_count: 0, forks_count: 0, language: 'C++', topics: ['vio'], updated_at: new Date().toISOString(), html_url: '#missions', homepage: '' },
    { name: 'planner', description: '3D trajectory planning notes.', stargazers_count: 0, forks_count: 0, language: 'Python', topics: ['planning'], updated_at: new Date().toISOString(), html_url: '#missions', homepage: '' },
    { name: 'yolov8-edge', description: 'Edge perception pipeline.', stargazers_count: 0, forks_count: 0, language: 'Python', topics: ['yolo'], updated_at: new Date().toISOString(), html_url: '#missions', homepage: '' },
    { name: 'failsafe-rtl', description: 'Fail-safe triggers.', stargazers_count: 0, forks_count: 0, language: 'C', topics: ['px4'], updated_at: new Date().toISOString(), html_url: '#missions', homepage: '' },
    { name: 'sitl-gazebo', description: 'SITL simulation support.', stargazers_count: 0, forks_count: 0, language: 'CMake', topics: ['gazebo'], updated_at: new Date().toISOString(), html_url: '#missions', homepage: '' }
  ];

  var EXPERIMENTS = [
    { id: 'T-01', name: 'Offboard arm sequence', result: 'Arms after ~30 setpoints at 20 Hz; RC override held.' },
    { id: 'T-02', name: 'RTL trigger', result: 'SITL return verified; QGC preflight green.' },
    { id: 'T-03', name: 'VIO bench', result: 'Indoor hold within envelope; vibration isolation next.' }
  ];

  var SKILL_TREE = [
    { name: 'ROS 2 Humble', cat: 'autonomy', tech: 'ros2' },
    { name: 'PX4 v1.14+', cat: 'flight', tech: 'px4' },
    { name: 'Jetson Orin', cat: 'compute', tech: 'jetson' },
    { name: 'YOLOv8', cat: 'vision', tech: 'yolo' },
    { name: 'Gazebo SITL', cat: 'sim', tech: 'gazebo' },
    { name: 'OpenCV', cat: 'vision', tech: 'opencv' },
    { name: 'uXRCE-DDS', cat: 'flight', tech: 'micro-ros' },
    { name: 'EKF / VIO', cat: 'autonomy', tech: 'ekf' }
  ];

  function $(s, r) { return (r || document).querySelector(s); }
  function $all(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }

  function toast(msg) {
    var t = $('#toast');
    if (!t) return;
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.hidden = true; }, 2600);
  }

  function timeAgo(iso) {
    try {
      var d = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
      if (d < 60) return d + 's ago';
      if (d < 3600) return Math.floor(d / 60) + 'm ago';
      if (d < 86400) return Math.floor(d / 3600) + 'h ago';
      return Math.floor(d / 86400) + 'd ago';
    } catch (e) { return ''; }
  }

  function storeGet(k) {
    try {
      var v = JSON.parse(localStorage.getItem(k) || 'null');
      return v;
    } catch (e) { return null; }
  }
  function storeSet(k, v) {
    try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {}
  }

  function fetchJSON(url, accept) {
    return fetch(url, { headers: { 'Accept': accept || 'application/vnd.github+json' } }).then(function (r) {
      if (!r.ok) {
        var err = new Error('HTTP ' + r.status);
        err.status = r.status;
        throw err;
      }
      return r.json();
    });
  }

  /* ---------- Boot ---------- */
  var Boot = {
    run: function () {
      var boot = $('#boot');
      if (!boot) return;
      var log = $('#boot-log');
      var seen = null;
      try { seen = localStorage.getItem('aeroxmd_boot_seen'); } catch (e) {}
      function lines(extra) {
        var base = ['AEROXMD GROUND STATION v2.4.1', 'Mounting autonomy stack.... OK', 'Linking ROS2/Humble.... OK'];
        if (extra) base.push(extra);
        base.push('Press ENTER or click below.');
        if (log) log.textContent = base.join('\n');
      }
      GitHub.ping().then(function () { lines('Establishing GitHub connection.... OK'); }, function () { lines('Establishing GitHub connection.... CACHED'); });
      if (seen) { boot.hidden = true; return; }
      boot.hidden = false;
      function enter() {
        var cb = $('#boot-remember');
        try { if (cb && cb.checked) localStorage.setItem('aeroxmd_boot_seen', '1'); } catch (e) {}
        boot.hidden = true;
      }
      var btn = $('#boot-enter');
      if (btn) btn.addEventListener('click', enter);
      boot.addEventListener('keydown', function (e) { if (e.key === 'Enter') enter(); });
    },
    replay: function () {
      var boot = $('#boot');
      if (boot) { boot.hidden = false; try { localStorage.removeItem('aeroxmd_boot_seen'); } catch (e) {} }
    }
  };

  /* ---------- Telemetry strip (simulated CPU/MEM + real FPS/clock/NET) ---------- */
  var Telemetry = {
    init: function () {
      var cpu = 34, mem = 48, fps = 0, frames = 0, last = performance.now();
      function raf(t) {
        frames++;
        if (t - last >= 1000) {
          fps = frames; frames = 0; last = t;
          var f = $('#ts-fps'); if (f) f.textContent = String(fps);
        }
        requestAnimationFrame(raf);
      }
      requestAnimationFrame(raf);
      setInterval(function () {
        cpu = Math.max(8, Math.min(96, cpu + (Math.random() * 10 - 5)));
        mem = Math.max(20, Math.min(92, mem + (Math.random() * 6 - 3)));
        var c = $('#ts-cpu'); if (c) c.textContent = cpu.toFixed(0) + '%';
        var m = $('#ts-mem'); if (m) m.textContent = mem.toFixed(0) + '%';
        var k = $('#ts-clock'); if (k) k.textContent = new Date().toLocaleTimeString();
      }, 1000);
      function net() {
        var n = $('#ts-net');
        if (n) n.textContent = navigator.onLine ? 'ONLINE' : 'OFFLINE';
      }
      window.addEventListener('online', net);
      window.addEventListener('offline', net);
      net();
    }
  };

  /* ---------- Particles ---------- */
  var Particles = {
    ptr: { x: 0.5, y: 0.5 },
    init: function () {
      var cv = $('#particles');
      if (!cv || !cv.getContext) return;
      var ctx = cv.getContext('2d');
      var hero = $('#home');
      var W = 0, H = 0, pts = [], mx = -999, my = -999, visible = true;
      var dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      function size() {
        var r = hero.getBoundingClientRect();
        W = r.width; H = r.height;
        cv.width = W * dpr; cv.height = H * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        var n = Math.max(90, Math.min(300, Math.floor(W * H / 7000)));
        pts = [];
        for (var i = 0; i < n; i++) pts.push({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4 });
      }
      size();
      window.addEventListener('resize', size);
      hero.addEventListener('pointermove', function (e) {
        var r = cv.getBoundingClientRect();
        mx = e.clientX - r.left; my = e.clientY - r.top;
      });
      if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (en) { visible = en[0].isIntersecting; }, { threshold: 0 }).observe(hero);
      }
      document.addEventListener('visibilitychange', function () { visible = !document.hidden && visible; });
      var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      var last = 0;
      function frame(t) {
        requestAnimationFrame(frame);
        if (!visible || document.hidden) return;
        if (reduce || document.body.classList.contains('reduced-motion')) return;
        if (t - last < 33) return;
        last = t;
        ctx.clearRect(0, 0, W, H);
        var px = Particles.ptr.x * W, py = Particles.ptr.y * H;
        for (var i = 0; i < pts.length; i++) {
          var p = pts[i];
          var dx = p.x - mx, dy = p.y - my, d = Math.sqrt(dx * dx + dy * dy);
          if (d < 110 && d > 1) { p.vx += dx / d * 0.06; p.vy += dy / d * 0.06; }
          var sx = p.x - px, sy = p.y - py;
          p.vx += sx * 0.00002; p.vy += sy * 0.00002;
          p.vx *= 0.985; p.vy *= 0.985;
          p.x += p.vx; p.y += p.vy;
          if (p.x < 0 || p.x > W) p.vx *= -1;
          if (p.y < 0 || p.y > H) p.vy *= -1;
          ctx.fillStyle = 'rgba(255,160,46,0.7)';
          ctx.fillRect(p.x, p.y, 2, 2);
        }
        ctx.strokeStyle = 'rgba(255,160,46,0.14)';
        for (var a = 0; a < pts.length; a++) for (var b = a + 1; b < pts.length; b++) {
          var ax = pts[a].x - pts[b].x, ay = pts[a].y - pts[b].y;
          if (ax * ax + ay * ay < 110 * 110) {
            ctx.beginPath(); ctx.moveTo(pts[a].x, pts[a].y); ctx.lineTo(pts[b].x, pts[b].y); ctx.stroke();
          }
        }
      }
      requestAnimationFrame(frame);
    }
  };
  window.Particles = Particles;

  /* ---------- Environment telemetry (real) ---------- */
  var EnvTelemetry = {
    init: function () {
      var grid = $('#env-grid');
      if (!grid) return;
      function webgl() {
        try {
          var c = document.createElement('canvas');
          var g = c.getContext('webgl');
          return g ? g.getParameter(g.VERSION) : 'unavailable';
        } catch (e) { return 'unavailable'; }
      }
      function cells() {
        var conn = navigator.connection || {};
        return [
          ['Resolution', screen.width + '×' + screen.height],
          ['Viewport', window.innerWidth + '×' + window.innerHeight],
          ['DPR', String(window.devicePixelRatio || 1)],
          ['Orientation', (screen.orientation && screen.orientation.type) || 'unknown'],
          ['CPU threads', String(navigator.hardwareConcurrency || 'n/a')],
          ['WebGL', webgl()],
          ['Network', (conn.effectiveType || (navigator.onLine ? 'online' : 'offline'))],
          ['Locale', navigator.language || 'n/a'],
          ['Scheme', window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'],
          ['Load', Math.round(performance.now()) + ' ms'],
          ['Touch', ('ontouchstart' in window) ? 'yes' : 'no'],
          ['Motion', EnvTelemetry.live ? 'LIVE' : 'idle (opt-in)']
        ];
      }
      function paint() {
        grid.innerHTML = '';
        cells().forEach(function (c) {
          var d = document.createElement('div');
          d.className = 'env-cell';
          var s = document.createElement('span'); s.textContent = c[0];
          var b = document.createElement('b'); b.textContent = String(c[1]).slice(0, 48);
          d.appendChild(s); d.appendChild(b);
          grid.appendChild(d);
        });
      }
      paint();
      window.addEventListener('resize', paint);
      var logEl = $('#env-log');
      var lastLog = 0;
      function log(msg) {
        var t = Date.now();
        if (t - lastLog < 120) return;
        lastLog = t;
        if (logEl) {
          logEl.textContent += new Date().toLocaleTimeString() + ' ' + msg + '\n';
          logEl.scrollTop = logEl.scrollHeight;
        }
      }
      window.addEventListener('pointermove', function (e) { log('pointer ' + e.clientX + ',' + e.clientY); });
      window.addEventListener('scroll', function () { log('scroll y=' + Math.round(window.scrollY)); }, { passive: true });
      var btn = $('#motion-btn');
      if (btn) btn.addEventListener('click', function () {
        function enable() {
          EnvTelemetry.live = true;
          window.addEventListener('deviceorientation', function (e) {
            if (e.gamma == null) return;
            Particles.ptr.x = Math.min(1, Math.max(0, (e.gamma + 45) / 90));
            Particles.ptr.y = Math.min(1, Math.max(0, (e.beta + 45) / 90));
            log('gyro ' + Math.round(e.alpha || 0) + '/' + Math.round(e.beta || 0) + '/' + Math.round(e.gamma || 0));
          });
          paint();
          toast('Motion sensors LIVE — tilt steers particles');
        }
        var DOE = window.DeviceOrientationEvent;
        if (DOE && typeof DOE.requestPermission === 'function') {
          DOE.requestPermission().then(function (s) { if (s === 'granted') enable(); else toast('Motion denied'); }).catch(function () { toast('Motion unavailable'); });
        } else { enable(); }
      });
    }
  };

  /* ---------- Section FX (one shared rAF) ---------- */
  var SectionFX = {
    init: function () {
      var cvs = $all('canvas.fx');
      if (!cvs.length) return;
      var items = [];
      cvs.forEach(function (cv) {
        var ctx = cv.getContext('2d');
        function fit() {
          var r = cv.parentElement.getBoundingClientRect();
          cv.width = r.width; cv.height = 120;
        }
        fit();
        if ('ResizeObserver' in window) new ResizeObserver(fit).observe(cv.parentElement);
        items.push({ cv: cv, ctx: ctx, kind: cv.getAttribute('data-fx'), vis: true, t: Math.random() * 100 });
      });
      if ('IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (en) {
          en.forEach(function (e) {
            items.forEach(function (it) { if (it.cv === e.target) it.vis = e.isIntersecting; });
          });
        }, { threshold: 0 });
        items.forEach(function (it) { io.observe(it.cv); });
      }
      function draw(it) {
        var ctx = it.ctx, W = it.cv.width, H = it.cv.height;
        ctx.clearRect(0, 0, W, H);
        it.t += 0.02;
        var i, x, y;
        if (it.kind === 'waves' || it.kind === 'trace') {
          ctx.strokeStyle = 'rgba(255,160,46,0.5)';
          ctx.beginPath();
          for (x = 0; x < W; x += 6) {
            y = H / 2 + Math.sin(x / 40 + it.t * 2) * 18;
            if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
          }
          ctx.stroke();
        } else if (it.kind === 'scan') {
          var sx = (it.t * 60) % W;
          var g = ctx.createLinearGradient(sx - 60, 0, sx, 0);
          g.addColorStop(0, 'rgba(255,160,46,0)');
          g.addColorStop(1, 'rgba(255,160,46,0.5)');
          ctx.fillStyle = g;
          ctx.fillRect(sx - 60, 0, 60, H);
        } else if (it.kind === 'embers') {
          ctx.fillStyle = 'rgba(255,158,44,0.6)';
          for (i = 0; i < 24; i++) {
            x = (i * 97 + it.t * 30) % W;
            y = H - ((i * 53 + it.t * 40) % H);
            ctx.fillRect(x, y, 2, 2);
          }
        } else if (it.kind === 'radar') {
          ctx.strokeStyle = 'rgba(255,160,46,0.5)';
          var cx = W / 2;
          ctx.beginPath(); ctx.arc(cx, H, 60 + (it.t * 20) % 50, Math.PI, 0); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(cx, H); ctx.lineTo(cx + Math.cos(it.t) * 90, H + Math.sin(it.t) * 90); ctx.stroke();
        } else {
          ctx.strokeStyle = 'rgba(255,160,46,0.5)';
          var r = (it.t * 30) % 70;
          ctx.beginPath(); ctx.arc(W / 2, H / 2, r, 0, Math.PI * 2); ctx.stroke();
        }
      }
      (function loop() {
        requestAnimationFrame(loop);
        if (document.hidden || document.body.classList.contains('reduced-motion')) return;
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        items.forEach(function (it) { if (it.vis) draw(it); });
      })();
    }
  };

  /* ---------- GitHub client ---------- */
  var GitHub = {
    data: null,
    ping: function () {
      return fetchJSON('https://api.github.com/orgs/' + AEROXMD_CONFIG.org).then(function () { return true; });
    },
    refresh: function (force) {
      var self = this;
      var KEY = 'aeroxmd_gh_v1';
      var cached = storeGet(KEY);
      var fresh = cached && (Date.now() - cached.at < AEROXMD_CONFIG.cacheDuration);
      if (fresh && !force && !navigator.onLine === false) {
        self.data = cached.data;
        self.paint('CACHED ' + new Date(cached.at).toLocaleTimeString(), false);
        Missions.setRepos(cached.data.repos);
        return Promise.resolve();
      }
      if (!navigator.onLine && cached) {
        self.data = cached.data;
        self.paint('CACHED (offline)', false);
        Missions.setRepos(cached.data.repos);
        return Promise.resolve();
      }
      return Promise.all([
        fetchJSON('https://api.github.com/orgs/' + AEROXMD_CONFIG.org),
        fetchJSON('https://api.github.com/orgs/' + AEROXMD_CONFIG.org + '/repos?per_page=100&sort=updated'),
        fetchJSON('https://api.github.com/repos/' + AEROXMD_CONFIG.org + '/' + AEROXMD_CONFIG.primaryRepo + '/commits?per_page=5')
      ]).then(function (res) {
        var org = res[0], repos = res[1], commits = res[2];
        var featured = repos.filter(function (r) { return AEROXMD_CONFIG.featuredRepositories.indexOf(r.name) !== -1; }).slice(0, 6);
        var need = featured.length ? featured : repos.slice(0, 6);
        return Promise.all(need.map(function (r) {
          return fetchJSON('https://api.github.com/repos/' + AEROXMD_CONFIG.org + '/' + r.name + '/topics', 'application/vnd.github.mercy-preview+json')
            .then(function (t) { r.topics = t.names || []; })
            .catch(function () {});
        })).then(function () {
          var data = { org: org, repos: repos, commits: commits, at: Date.now() };
          storeSet(KEY, { at: data.at, data: data });
          self.data = data;
          self.paint('LIVE ✓ ' + new Date(data.at).toLocaleTimeString(), true);
          Missions.setRepos(repos);
        });
      }).catch(function (err) {
        var reason = err && err.status === 404 ? 'NOT FOUND' : (err && (err.status === 403 || err.status === 429) ? 'RATE_LIMITED' : 'OFFLINE');
        if (cached) {
          self.data = cached.data;
          self.paint('CACHED ' + new Date(cached.at).toLocaleTimeString() + ' · ' + reason, false);
          Missions.setRepos(cached.data.repos);
        } else {
          self.data = { org: null, repos: FALLBACK_REPOS, commits: [], at: Date.now() };
          self.paint('OFFLINE — CURATED FALLBACK · ' + reason, false);
          Missions.setRepos(FALLBACK_REPOS);
        }
      });
    },
    paint: function (label, live) {
      var s = $('#gh-sync-state'); if (s) s.textContent = label;
      var g = $('#ts-gh'); if (g) { g.textContent = live ? '●' : '○'; g.style.color = live ? '#ffa02e' : '#e0a63b'; }
      var mn = $('#mission-sync-note'); if (mn) mn.textContent = label;
      if (!this.data) return;
      var repos = this.data.repos || [];
      var stars = repos.reduce(function (a, r) { return a + (r.stargazers_count || 0); }, 0);
      var forks = repos.reduce(function (a, r) { return a + (r.forks_count || 0); }, 0);
      var cutoff = Date.now() - 90 * 86400 * 1000;
      var active = repos.filter(function (r) { return new Date(r.updated_at || r.pushed_at || 0).getTime() > cutoff; }).length;
      function set(id, v) { var e = $(id); if (e) e.textContent = String(v); }
      set('#gh-repos', this.data.org ? this.data.org.public_repos : repos.length);
      set('#gh-stars', stars);
      set('#gh-forks', forks);
      set('#gh-active', active);
      var langs = {};
      repos.forEach(function (r) { if (r.language) langs[r.language] = (langs[r.language] || 0) + 1; });
      var top = Object.keys(langs).sort(function (a, b) { return langs[b] - langs[a]; }).slice(0, 6);
      var lb = $('#lang-bars');
      if (lb) {
        lb.innerHTML = '';
        var max = top.length ? langs[top[0]] : 1;
        top.forEach(function (L) {
          var row = document.createElement('div'); row.className = 'lang-row';
          var a = document.createElement('span'); a.textContent = L;
          var bar = document.createElement('div'); bar.className = 'lang-bar';
          var fill = document.createElement('i'); fill.style.width = Math.round(langs[L] / max * 100) + '%';
          bar.appendChild(fill);
          var n = document.createElement('span'); n.textContent = String(langs[L]);
          row.appendChild(a); row.appendChild(bar); row.appendChild(n);
          lb.appendChild(row);
        });
        if (!top.length) lb.innerHTML = '<p class="muted">No language data.</p>';
      }
      var tx = $('#gh-transmission');
      if (tx) {
        var c = (this.data.commits || [])[0];
        if (c) tx.textContent = (c.commit.author ? c.commit.author.date.slice(0, 10) + ' ' : '') + (c.commit.message || '').split('\n')[0] + '\n' + (c.sha || '').slice(0, 7) + ' · ' + AEROXMD_CONFIG.primaryRepo;
        else tx.textContent = 'No recent commits found.';
      }
      var rl = $('#gh-recent');
      if (rl) {
        rl.innerHTML = '';
        repos.slice().sort(function (a, b) { return new Date(b.updated_at) - new Date(a.updated_at); }).slice(0, 5).forEach(function (r) {
          var li = document.createElement('li');
          var a = document.createElement('a');
          a.href = r.html_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = r.name;
          li.appendChild(a);
          li.appendChild(document.createTextNode(' ★' + (r.stargazers_count || 0) + ' · ' + timeAgo(r.updated_at)));
          rl.appendChild(li);
        });
      }
      var cn = $('#gh-cache-note');
      if (cn) cn.textContent = 'Synced ' + new Date(this.data.at).toLocaleTimeString() + ' · unauthenticated (60 req/hr shared)';
    }
  };

  /* ---------- Missions ---------- */
  var Missions = {
    repos: [], filter: 'all', shown: 10,
    enrich: function (repo) {
      var key = String(repo.name || '').toLowerCase();
      if (CURATED[key]) {
        var c = CURATED[key];
        return { repo: repo, num: c.mission, title: c.title, domain: c.domain, status: c.status, blurb: c.blurb, tech: c.tech, objective: c.objective, arch: c.arch, results: c.results, featured: AEROXMD_CONFIG.featuredRepositories.indexOf(repo.name) !== -1 };
      }
      var topics = (repo.topics || []).join(' ').toLowerCase();
      var hay = (repo.name + ' ' + (repo.description || '') + ' ' + topics).toLowerCase();
      var domain = 'autonomy';
      Object.keys(AEROXMD_CONFIG.topicsToDomain).forEach(function (t) {
        if (hay.indexOf(t) !== -1) domain = AEROXMD_CONFIG.topicsToDomain[t];
      });
      return { repo: repo, num: 'AXM-' + String(100 + (repo.name || '?').length * 7 % 800), title: repo.name, domain: domain, status: 'TRACKED', blurb: repo.description || 'Tracked upstream repository.', tech: topics || (repo.language || '').toLowerCase(), objective: 'Track upstream development for the AEROXMD stack.', arch: 'Upstream module; interface via documented topics/services.', results: 'Updated ' + timeAgo(repo.updated_at) + '.', featured: AEROXMD_CONFIG.featuredRepositories.indexOf(repo.name) !== -1 };
    },
    setRepos: function (repos) {
      var feat = AEROXMD_CONFIG.featuredRepositories;
      this.repos = (repos || []).slice().sort(function (a, b) {
        var fa = feat.indexOf(a.name) !== -1, fb = feat.indexOf(b.name) !== -1;
        if (fa !== fb) return fa ? -1 : 1;
        return new Date(b.updated_at) - new Date(a.updated_at);
      });
      this.shown = 10;
      this.render();
    },
    filtered: function () {
      var self = this;
      return this.repos.map(function (r) { return self.enrich(r); }).filter(function (m) {
        return self.filter === 'all' || m.domain === self.filter;
      });
    },
    render: function () {
      var grid = $('#mission-grid');
      if (!grid) return;
      var list = this.filtered();
      grid.innerHTML = '';
      list.slice(0, this.shown).forEach(function (m) {
        var b = document.createElement('button');
        b.className = 'mission-card';
        b.setAttribute('data-tech', m.tech);
        b.setAttribute('data-domain', m.domain);
        b.innerHTML = '';
        var top = document.createElement('div'); top.className = 'mission-top';
        var n = document.createElement('span'); n.textContent = m.num + ' · ' + m.domain.toUpperCase();
        var f = document.createElement('span'); f.textContent = m.featured ? '◆ FEATURED' : m.status;
        top.appendChild(n); top.appendChild(f);
        var h = document.createElement('h3'); h.textContent = m.title;
        var p = document.createElement('p'); p.textContent = m.blurb;
        var meta = document.createElement('div'); meta.className = 'mission-meta';
        meta.textContent = '★' + (m.repo.stargazers_count || 0) + '  ⑂' + (m.repo.forks_count || 0) + '  ' + (m.repo.language || '') + '  ·  ' + timeAgo(m.repo.updated_at);
        b.appendChild(top); b.appendChild(h); b.appendChild(p); b.appendChild(meta);
        b.addEventListener('click', function () { Missions.open(m); });
        grid.appendChild(b);
      });
      var more = $('#mission-more');
      if (more) {
        var rest = list.length - this.shown;
        more.style.display = rest > 0 ? '' : 'none';
        more.textContent = rest > 0 ? 'Show more — ' + rest + ' more ▸' : 'Show more ▸';
      }
    },
    open: function (m) {
      var modal = $('#mission-modal');
      if (!modal) return;
      function set(id, v) { var e = $(id); if (e) e.textContent = v; }
      set('#mm-num', m.num + ' · ' + m.domain.toUpperCase() + ' · ' + m.status);
      set('#mm-title', m.title);
      set('#mm-meta', '★' + (m.repo.stargazers_count || 0) + ' ⑂' + (m.repo.forks_count || 0) + ' · ' + (m.repo.language || '') + ' · updated ' + timeAgo(m.repo.updated_at));
      set('#mm-blurb', m.blurb);
      set('#mm-objective', m.objective);
      set('#mm-arch', m.arch);
      set('#mm-results', m.results);
      var code = $('#mm-code'); if (code) code.href = m.repo.html_url || '#missions';
      var demo = $('#mm-demo'); if (demo) { demo.href = m.repo.homepage || m.repo.html_url || '#missions'; demo.style.display = m.repo.homepage ? '' : 'none'; }
      modal.hidden = false;
      Missions._last = document.activeElement;
      var c = $('#mission-close'); if (c) c.focus();
      document.body.style.overflow = 'hidden';
    },
    close: function () {
      var modal = $('#mission-modal');
      if (modal) modal.hidden = true;
      document.body.style.overflow = '';
      if (Missions._last && Missions._last.focus) Missions._last.focus();
    },
    highlightByTech: function (tech) {
      $all('.mission-card').forEach(function (card) {
        var has = (card.getAttribute('data-tech') || '').indexOf(tech) !== -1;
        card.classList.toggle('flash', has);
        card.classList.toggle('dim', !has);
      });
      var sec = $('#missions');
      if (sec) sec.scrollIntoView({ behavior: 'smooth' });
    },
    init: function () {
      var self = this;
      var sel = $('#mission-filter');
      if (sel) sel.addEventListener('change', function () { self.filter = sel.value; self.shown = 10; self.render(); });
      var more = $('#mission-more');
      if (more) more.addEventListener('click', function () { self.shown += 10; self.render(); });
      var c = $('#mission-close');
      if (c) c.addEventListener('click', function () { self.close(); });
      var modal = $('#mission-modal');
      if (modal) modal.addEventListener('click', function (e) { if (e.target === modal) self.close(); });
      document.addEventListener('keydown', function (e) { if (e.key === 'Escape') self.close(); });
      var rs = $('#mission-resync');
      if (rs) rs.addEventListener('click', function () { GitHub.refresh(true).then(function () { toast('GitHub resynced'); }); });
    }
  };

  /* ---------- Gallery ---------- */
  var Gallery = {
    photos: [], idx: 0,
    apiBase: function () {
      return 'https://api.github.com/repos/' + AEROXMD_CONFIG.org + '/' + AEROXMD_CONFIG.galleryRepo + '/contents/' + AEROXMD_CONFIG.galleryPath;
    },
    sync: function () {
      var note = $('#gallery-note'), wall = $('#gallery-wall');
      var KEY = 'aeroxmd_gallery_v1';
      var cached = storeGet(KEY);
      function paint(list, msg) {
        Gallery.photos = list;
        Gallery.render();
        if (note) note.textContent = msg;
      }
      if (cached && cached.list) paint(cached.list, 'GALLERY CACHED · ' + cached.list.length + ' frames');
      var host = location.hostname;
      var local = (host === 'localhost' || host === '127.0.0.1' || location.protocol === 'file:');
      return fetchJSON(this.apiBase()).then(function (entries) {
        var list = (entries || []).filter(function (e) { return e.type === 'file' && /\.(jpe?g|png|webp|avif)$/i.test(e.name); })
          .map(function (e) { return { name: e.name, url: e.download_url }; })
          .sort(function (a, b) { return a.name.localeCompare(b.name); });
        var join = list.map(function (p) { return p.name; }).join('|');
        if (!cached || cached.join !== join) {
          storeSet(KEY, { join: join, list: list });
          paint(list, list.length ? ('GALLERY LIVE ✓ · ' + list.length + ' frames') : 'GALLERY EMPTY — drop photos into assets/gallery/ and push.');
        } else if (note && !list.length) {
          note.textContent = 'GALLERY EMPTY — drop photos into assets/gallery/ and push.';
        } else if (note && note.textContent.indexOf('CACHED') === 0) {
          note.textContent = 'GALLERY LIVE ✓ · ' + list.length + ' frames';
        }
        if (local && note && list.length) note.textContent += ' · (pushed copy; local-only files appear after push)';
      }).catch(function (err) {
        var reason = err && (err.status === 403 || err.status === 429) ? 'RATE_LIMITED' : 'UNREACHABLE';
        if (note) note.textContent = cached && cached.list ? ('GALLERY OFFLINE — cached frames shown · ' + reason) : ('GALLERY ' + reason + ' — push assets/gallery/ to GitHub first.');
      });
    },
    render: function () {
      var wall = $('#gallery-wall');
      if (!wall) return;
      wall.innerHTML = '';
      this.photos.forEach(function (p, i) {
        var b = document.createElement('button');
        b.className = 'g-frame';
        var img = document.createElement('img');
        img.loading = 'lazy';
        img.src = p.url;
        img.alt = p.name.replace(/\.[a-z]+$/i, '').replace(/[-_]+/g, ' ');
        b.appendChild(img);
        b.addEventListener('click', function () { Gallery.open(i); });
        wall.appendChild(b);
      });
    },
    open: function (i) {
      var v = $('#viewer');
      if (!v || !this.photos.length) return;
      this.idx = (i + this.photos.length) % this.photos.length;
      var p = this.photos[this.idx];
      var img = $('#viewer-img');
      if (img) { img.src = p.url; img.alt = p.name; }
      var cap = $('#viewer-cap');
      if (cap) cap.textContent = (this.idx + 1) + '/' + this.photos.length + ' · ' + p.name;
      v.hidden = false;
      document.body.style.overflow = 'hidden';
      Gallery._last = document.activeElement;
      var c = $('#viewer-close'); if (c) c.focus();
    },
    close: function () {
      var v = $('#viewer');
      if (v) v.hidden = true;
      document.body.style.overflow = '';
      if (Gallery._last && Gallery._last.focus) Gallery._last.focus();
    },
    init: function () {
      var self = this;
      var c = $('#viewer-close'); if (c) c.addEventListener('click', function () { self.close(); });
      var p = $('#viewer-prev'); if (p) p.addEventListener('click', function () { self.open(self.idx - 1); });
      var n = $('#viewer-next'); if (n) n.addEventListener('click', function () { self.open(self.idx + 1); });
      var v = $('#viewer');
      if (v) v.addEventListener('click', function (e) { if (e.target === v) self.close(); });
      document.addEventListener('keydown', function (e) {
        if (!v || v.hidden) return;
        if (e.key === 'Escape') self.close();
        if (e.key === 'ArrowLeft') self.open(self.idx - 1);
        if (e.key === 'ArrowRight') self.open(self.idx + 1);
      });
      var sx = null;
      if (v) {
        v.addEventListener('touchstart', function (e) { sx = e.touches[0].clientX; }, { passive: true });
        v.addEventListener('touchend', function (e) {
          if (sx == null) return;
          var dx = e.changedTouches[0].clientX - sx;
          if (dx > 40) self.open(self.idx - 1);
          if (dx < -40) self.open(self.idx + 1);
          sx = null;
        });
      }
    }
  };

  /* ---------- Skill graph ---------- */
  var SkillGraph = {
    init: function () {
      var g = $('#skill-graph');
      if (!g) return;
      g.innerHTML = '';
      SKILL_TREE.forEach(function (s) {
        var b = document.createElement('button');
        b.className = 'skill-node';
        b.setAttribute('aria-pressed', 'false');
        var t = document.createElement('b'); t.textContent = s.name;
        var c = document.createElement('span'); c.textContent = s.cat + ' · ' + s.tech;
        b.appendChild(t); b.appendChild(c);
        function pick() {
          var on = b.getAttribute('aria-pressed') === 'true';
          $all('.skill-node').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
          b.setAttribute('aria-pressed', String(!on));
          if (!on) Missions.highlightByTech(s.tech);
          else $all('.mission-card').forEach(function (x) { x.classList.remove('dim', 'flash'); });
        }
        b.addEventListener('click', pick);
        b.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); }
        });
        g.appendChild(b);
      });
    }
  };

  /* ---------- Terminal ---------- */
  var Terminal = {
    clearance: false,
    init: function () {
      var term = $('#terminal');
      if (!term) return;
      var out = $('#term-out'), inp = $('#term-in');
      function print(s) { if (out) { out.textContent += s + '\n'; out.scrollTop = out.scrollHeight; } }
      function toggle(show) {
        term.hidden = (show === undefined) ? !term.hidden : !show;
        if (!term.hidden && inp) inp.focus();
      }
      document.addEventListener('keydown', function (e) {
        if (e.key === '`' && document.activeElement !== inp) { e.preventDefault(); toggle(); }
        if (e.key === 'Escape' && !term.hidden && document.activeElement === inp) toggle(false);
      });
      var c = $('#term-close');
      if (c) c.addEventListener('click', function () { toggle(false); });
      var seq = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
      var ki = 0;
      document.addEventListener('keydown', function (e) {
        ki = (e.key === seq[ki]) ? ki + 1 : 0;
        if (ki === seq.length) { Terminal.clearance = true; ki = 0; toast('Clearance granted — Konami accepted'); print('CLEARANCE GRANTED'); }
      });
      if (inp) inp.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        var raw = inp.value.trim();
        inp.value = '';
        print('> ' + raw);
        Terminal.exec(raw, print, toggle);
      });
      Terminal.print = print;
      Terminal.toggle = toggle;
    },
    exec: function (raw, print, toggle) {
      var parts = raw.split(/\s+/).filter(Boolean);
      var cmd = (parts[0] || '').toLowerCase();
      var arg = parts.slice(1).join(' ');
      function missions() {
        var list = Missions.filtered().slice(0, 10);
        list.forEach(function (m) { print(m.num + ' ' + m.title + ' [' + m.domain + '] ★' + (m.repo.stargazers_count || 0)); });
      }
      switch (cmd) {
        case 'help': print('help status missions mission <name> lab skills gallery [sync] github [resync] env telemetry ls open <section> motion boot [replay] clear sudo'); break;
        case 'status': print('repos=' + Missions.repos.length + ' photos=' + Gallery.photos.length + ' net=' + (navigator.onLine ? 'online' : 'offline') + (Terminal.clearance ? ' clearance=GRANTED' : '')); break;
        case 'missions': missions(); break;
        case 'mission': {
          var q = arg.toLowerCase();
          var m = Missions.repos.map(function (r) { return Missions.enrich(r); }).filter(function (x) { return (x.title + ' ' + x.num).toLowerCase().indexOf(q) !== -1; })[0];
          if (m) { Missions.open(m); print('Opening ' + m.num); } else print('Mission not found: ' + arg);
          break;
        }
        case 'lab': EXPERIMENTS.forEach(function (x) { print(x.id + ' ' + x.name + ' — ' + x.result); }); break;
        case 'skills': SKILL_TREE.forEach(function (s) { print(s.name + ' [' + s.cat + ']'); }); break;
        case 'gallery': if (arg === 'sync') { Gallery.sync().then(function () { print('Gallery synced: ' + Gallery.photos.length); }); } else print('photos=' + Gallery.photos.length); break;
        case 'github': if (arg === 'resync' || arg === 'resync'.slice(0, arg.length)) { GitHub.refresh(true).then(function () { print('GitHub resynced'); }); } else print($('#gh-sync-state') ? $('#gh-sync-state').textContent : 'n/a'); break;
        case 'env': print('viewport=' + window.innerWidth + 'x' + window.innerHeight + ' dpr=' + (window.devicePixelRatio || 1) + ' threads=' + (navigator.hardwareConcurrency || 'n/a')); break;
        case 'telemetry': print('strip=simulation; env panel=real device data'); break;
        case 'ls': print('missions gallery live telemetry stack get-started sponsors contact'); break;
        case 'open': { var t = document.getElementById(arg); if (t) { t.scrollIntoView({ behavior: 'smooth' }); print('Opening #' + arg); } else print('Unknown section: ' + arg); break; }
        case 'motion': { var b = $('#motion-btn'); if (b) b.click(); print('Motion requested'); break; }
        case 'boot': Boot.replay(); print('Boot replaying'); break;
        case 'clear': { var o = $('#term-out'); if (o) o.textContent = ''; break; }
        case 'sudo': print('Nice try. This console flies drones, not privilege escalations.'); break;
        case '': break;
        default: print('Unknown: ' + cmd + ' — try help');
      }
    }
  };

  /* ---------- Contact ---------- */
  function initContact() {
    $all('[data-copy]').forEach(function (b) {
      b.addEventListener('click', function () {
        var v = b.getAttribute('data-copy');
        function ok() { toast('Handle copied'); }
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(v).then(ok, function () { toast(v); });
        else { toast(v); }
      });
    });
    var f = $('#contact-form');
    if (f) f.addEventListener('submit', function (e) {
      e.preventDefault();
      var n = ($('#cf-name') || {}).value || '';
      var m = ($('#cf-msg') || {}).value || '';
      var url = 'mailto:robotronics@iitmandi.ac.in?subject=' + encodeURIComponent('AEROXMD contact — ' + n) + '&body=' + encodeURIComponent(m);
      window.location.href = url;
      toast('Opening mail client…');
    });
  }

  /* ---------- Bootstrap ---------- */
  function initChrome() {
    var prog = $('#progress');
    function onScroll() {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      if (prog) prog.style.width = (max > 0 ? (h.scrollTop / max * 100) : 0) + '%';
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    var rb = $('#reduce-motion-btn');
    if (rb) rb.addEventListener('click', function () {
      var on = document.body.classList.toggle('reduced-motion');
      toast(on ? 'Reduced motion ON' : 'Reduced motion OFF');
    });
  }

  Missions.init();
  Gallery.init();
  Terminal.init();
  Telemetry.init();
  Particles.init();
  EnvTelemetry.init();
  SectionFX.init();
  SkillGraph.init();
  initContact();
  initChrome();
  Boot.run();
  GitHub.refresh(false);
  Gallery.sync();
})();