/* LogikosLoader — estado de espera Logikos Vision (conceito C2 "tranca de cofre")
   Uso: <lk-loader variant="fullscreen|tile|spinner" state="entering|waiting|retry|resolving|idle" label="..." retries="0" size="112"></lk-loader> */
(function () {
  if (customElements.get('lk-loader')) return;
  let uid = 0;
  function keyholeSvg(id, fill) {
    return '<svg viewBox="0 0 100 100" class="lg" aria-hidden="true"><defs><mask id="' + id + '"><rect width="100" height="100" fill="white"/><g transform="translate(24,22.4) scale(0.52)"><path d="M40 55.3 A20 20 0 1 1 60 55.3 L67 88 L33 88 Z" fill="black"/></g></mask></defs><circle cx="50" cy="50" r="44" fill="' + fill + '" mask="url(#' + id + ')"/></svg>';
  }
  function monogramSvg(id, fill) {
    return '<svg viewBox="0 0 100 100" class="lg" aria-hidden="true"><defs><mask id="' + id + '"><rect x="-20" y="-20" width="140" height="140" fill="white"/><polyline points="27,79 50,27 73,79" fill="none" stroke="black" stroke-width="10" stroke-linejoin="miter" stroke-miterlimit="8"/></mask></defs><circle cx="50" cy="50" r="46" fill="' + fill + '" mask="url(#' + id + ')"/></svg>';
  }
  function ringSvg() {
    var t = '';
    for (var i = 0; i < 8; i++) {
      var a = i * 45 * Math.PI / 180;
      var r1 = 52, r2 = i === 0 ? 44 : 48;
      var x1 = 60 + r1 * Math.cos(a), y1 = 60 + r1 * Math.sin(a);
      var x2 = 60 + r2 * Math.cos(a), y2 = 60 + r2 * Math.sin(a);
      t += '<line x1="' + x1.toFixed(1) + '" y1="' + y1.toFixed(1) + '" x2="' + x2.toFixed(1) + '" y2="' + y2.toFixed(1) + '" stroke="' + (i === 0 ? '#8A8F98' : '#23242F') + '" stroke-width="' + (i === 0 ? 3 : 2) + '"/>';
    }
    return '<svg viewBox="0 0 120 120" class="ring" aria-hidden="true"><circle cx="60" cy="60" r="55" fill="none" stroke="#23242F" stroke-width="1.5"/>' + t + '</svg>';
  }
  var CSS = [
    ':host{display:block;font-family:"JetBrains Mono",monospace}',
    ':host([variant="fullscreen"]),:host([variant="tile"]){width:100%;height:100%}',
    ':host([variant="spinner"]){display:inline-block;vertical-align:middle}',
    '.wrap{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;width:100%;height:100%;box-sizing:border-box}',
    ':host([variant="fullscreen"]) .wrap{background:#0A0A0F;background-image:repeating-linear-gradient(66deg,transparent 0 54px,#14141C 54px 55px),repeating-linear-gradient(-66deg,transparent 0 54px,#14141C 54px 55px)}',
    ':host([variant="tile"]) .wrap{background:#0A0A0F}',
    '.stage{position:relative;width:var(--lk-size,112px);height:var(--lk-size,112px);perspective:600px}',
    '.ring{position:absolute;inset:-14%;width:128%;height:128%;transform:translateZ(-12px)}',
    '.wrap.spin .ring{animation:lk-tick var(--lk-tick-dur,1.2s) steps(var(--lk-steps,8),end) infinite}',
    '@keyframes lk-tick{from{transform:translateZ(-12px) rotate(0)}to{transform:translateZ(-12px) rotate(360deg)}}',
    '.stack{position:absolute;inset:0}',
    '.lg{position:absolute;inset:0;width:100%;height:100%}',
    '.g{opacity:0;pointer-events:none}',
    '.wrap.burst .base{animation:lk-j var(--lk-glitch-dur,.5s) steps(1,end) 1}',
    '.wrap.burst .gc{animation:lk-ga var(--lk-glitch-dur,.5s) steps(1,end) 1}',
    '.wrap.burst .gm{animation:lk-gb var(--lk-glitch-dur,.5s) steps(1,end) 1}',
    '@keyframes lk-j{0%{transform:translateX(1px)}30%{transform:translateX(-2px)}60%{transform:translateX(1px)}100%{transform:none}}',
    '@keyframes lk-ga{0%{opacity:1;clip-path:inset(10% 0 76% 0);transform:translateX(3px)}28%{opacity:1;clip-path:inset(58% 0 28% 0);transform:translateX(-3px)}55%{opacity:1;clip-path:inset(32% 0 52% 0);transform:translateX(4px)}80%{opacity:1;clip-path:inset(72% 0 10% 0);transform:translateX(-2px)}100%{opacity:0}}',
    '@keyframes lk-gb{0%{opacity:1;clip-path:inset(64% 0 22% 0);transform:translateX(-3px)}28%{opacity:1;clip-path:inset(14% 0 72% 0);transform:translateX(3px)}55%{opacity:1;clip-path:inset(78% 0 8% 0);transform:translateX(-4px)}80%{opacity:1;clip-path:inset(26% 0 60% 0);transform:translateX(2px)}100%{opacity:0}}',
    '.wrap.resolved .ring{transform:translateZ(-12px) rotate(0)}',
    '.label{margin-top:calc(var(--lk-size,112px)*.82);position:absolute;top:50%;left:0;right:0;text-align:center;text-transform:uppercase;letter-spacing:.18em;color:#8A8F98;font-size:13px;white-space:nowrap}',
    ':host([variant="tile"]) .label{font-size:11px;letter-spacing:.16em}',
    ':host([variant="spinner"]) .wrap{width:var(--lk-size,22px);height:var(--lk-size,22px)}',
    ':host([variant="spinner"]) .stage{width:100%;height:100%;perspective:none}',
    ':host([variant="spinner"]) .wrap.spin .stack{animation:lk-tick var(--lk-tick-dur,1.2s) steps(var(--lk-steps,8),end) infinite}',
    ':host([variant="spinner"]) .label,:host([variant="spinner"]) .ring{display:none}',
    '@media (prefers-reduced-motion:reduce){.ring,.stack{animation:none!important}.g{display:none}.wrap.spin .stack{animation:lk-pulse 1.6s steps(2,end) infinite!important}}',
    '@keyframes lk-pulse{0%{opacity:.6}50%{opacity:1}100%{opacity:.6}}'
  ].join('\n');

  class LkLoader extends HTMLElement {
    static get observedAttributes() { return ['state', 'label', 'retries', 'size', 'variant']; }
    connectedCallback() {
      if (!this.shadowRoot) {
        var sr = this.attachShadow({ mode: 'open' });
        var v = this.getAttribute('variant') || 'fullscreen';
        var n = ++uid;
        var logos = v === 'spinner'
          ? monogramSvg('m' + n, '#F4F6F8')
          : keyholeSvg('b' + n, '#F4F6F8') +
            keyholeSvg('c' + n, '#00E5FF').replace('class="lg"', 'class="lg g gc"') +
            keyholeSvg('g' + n, '#FF2E63').replace('class="lg"', 'class="lg g gm"');
        logos = logos.replace('class="lg"', 'class="lg base"');
        sr.innerHTML = '<style>' + CSS + '</style><div class="wrap" role="status"><div class="stage">' + (v === 'spinner' ? '' : ringSvg()) + '<div class="stack">' + logos + '</div></div><div class="label"></div></div>';
        this._w = sr.querySelector('.wrap');
        this._l = sr.querySelector('.label');
      }
      this._syncSize(); this._syncLabel(); this._apply();
    }
    attributeChangedCallback(n) {
      if (!this._w) return;
      if (n === 'label') this._syncLabel();
      else if (n === 'size') this._syncSize();
      else if (n === 'retries') { this._burst(); }
      else if (n === 'state') this._apply();
    }
    _syncSize() { var s = this.getAttribute('size'); if (s) this.style.setProperty('--lk-size', s + 'px'); }
    _syncLabel() { if (this._l) this._l.textContent = this.getAttribute('label') || ''; }
    _spin(on) { this._w.classList.toggle('spin', !!on); }
    _burst(dur) {
      if ((this.getAttribute('variant') || 'fullscreen') === 'spinner') return;
      var w = this._w; dur = dur || 500;
      w.classList.remove('burst'); void w.offsetWidth;
      w.style.setProperty('--lk-glitch-dur', dur + 'ms');
      w.classList.add('burst');
      clearTimeout(this._bt);
      this._bt = setTimeout(function () { w.classList.remove('burst'); }, dur + 40);
    }
    _apply() {
      var st = this.getAttribute('state') || 'waiting';
      var w = this._w; w.dataset.state = st; w.classList.remove('resolved');
      clearTimeout(this._rt);
      if (st === 'entering') { this._burst(); this._spin(true); }
      else if (st === 'waiting') { this._spin(true); }
      else if (st === 'retry') { this._burst(); this._spin(true); }
      else if (st === 'resolving') {
        var self = this; this._spin(false); this._burst(300);
        this._rt = setTimeout(function () { w.classList.add('resolved'); self.dispatchEvent(new CustomEvent('lk-resolved', { bubbles: true })); }, 360);
      } else { this._spin(false); }
    }
  }
  customElements.define('lk-loader', LkLoader);
  if (typeof window !== 'undefined') window.LkLoader = undefined; /* tag-based only */
})();
