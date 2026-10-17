import { type ComponentProps, type RefObject, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import "./laser-flow.css";

/*
 * LaserFlow from React Bits (reactbits.dev), ported to TypeScript. A beam
 * drops from the top of the container, lands on the top edge of `surfaceRef`,
 * splashes along it and spills over its corners. The whole palette is derived
 * from `color`.
 */

const VERTEX = `#version 300 es
in vec2 aPosition;
void main() {
  gl_Position = vec4(aPosition, 0.0, 1.0);
}`;

const FRAGMENT = `#version 300 es
precision highp float;
out vec4 outColor;
uniform vec2 uResolution;
uniform float uDpr;
uniform float uScale;
uniform float uTime;
uniform float uBeamX;
uniform vec4 uSurface;
uniform float uRadius;
uniform vec3 uIntro;
uniform vec4 uPour;
uniform vec2 uRun;
uniform vec4 uLens;
uniform sampler2D uReveal;
uniform vec4 uRevealMap;
uniform vec2 uRevealInfo;
uniform float uAtmosphere;
uniform vec4 uAmount;
uniform vec4 uShape;
uniform vec4 uExtra;
uniform float uTheme;
uniform float uAcross;
uniform float uMirror;
uniform float uFade;
uniform float uBase;
uniform float uBaseGlow;
uniform float uContour;
uniform vec3 uWrap;
uniform vec3 uTint[16];

#define BEAM uTint[0]
#define LEFT uTint[1]
#define RIGHT uTint[2]
#define CYAN uTint[3]
#define PINK uTint[4]
#define LILAC uTint[5]
#define SKY uTint[6]
#define PURPLE uTint[7]
#define DEEP uTint[8]
#define MIST uTint[9]
#define NAVY uTint[10]
#define WARM uTint[11]
#define EMBER uTint[12]
#define WHITE uTint[13]
#define HAZE uTint[14]
#define LAVENDER uTint[15]

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p = m * p;
    a *= 0.5;
  }
  return v;
}

float sq(float x) {
  return x * x;
}

float roundBox(vec2 p, vec2 b, float r) {
  vec2 q = abs(p) - b + r;
  return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

// Depth along the beam at which the near face of the surface sits at lateral
// position x, following its rounded corners; 1e5 where x misses the surface.
float faceAt(float x, float sl, float sr, float sy, float r) {
  float c = clamp(x, sl + r, sr - r);
  float d = abs(x - c);
  if (d >= r) return 1e5;
  return sy + r - sqrt(r * r - d * d);
}

// Arc length along the outline of a rounded box, measured from the middle of
// its near face and signed by side; q is relative to the box centre.
float perimeter(vec2 q, vec2 b, float r) {
  vec2 inner = b - r;
  vec2 k = vec2(abs(q.x), q.y);
  vec2 c = clamp(k, vec2(0.0, -inner.y), inner);
  vec2 d = k - c;
  float quarter = 1.5707963 * r;
  float s;
  if (d.y < 0.0 && d.x <= 0.0) s = c.x;
  else if (d.y < 0.0) s = inner.x + r * atan(d.x, -d.y);
  else if (d.y <= 0.0) s = inner.x + quarter + c.y + inner.y;
  else if (d.x > 0.0) s = inner.x + quarter + 2.0 * inner.y + r * atan(d.y, d.x);
  else s = 2.0 * inner.x + 2.0 * quarter + 2.0 * inner.y - c.x;
  return q.x < 0.0 ? -s : s;
}

vec3 spill(float e, float fall, float strength, float front, float t, out vec3 glow) {
  glow = vec3(0.0);
  if (strength < 0.0005) return vec3(0.0);
  float f = max(fall, 0.0);
  float d = max(e, 0.0);
  float u = d / (6.0 + 0.28 * f);
  float start = smoothstep(-6.0, 12.0, fall);
  float fade = exp(-sq(max(f - 125.0, 0.0) / 40.0));
  float streak = 0.88 + 0.24 * noise(vec2(u * 6.0, f / 22.0 - t * 1.7));
  float bright = pow(strength, 1.5);
  float soft = sqrt(strength);
  float warmth = smoothstep(90.0, 130.0, f);
  vec3 coreK = mix(WHITE, WARM, warmth * exp(-d / 9.0));
  float core = mix(9.0, 2.6, warmth) * exp(-sq(d / (3.5 + 0.04 * f))) * exp(-sq(max(f - 130.0, 0.0) / 38.0));
  float wall = 24.0 * exp(-sq(d / 1.1)) * exp(-sq(max(f - 100.0, 0.0) / 30.0));
  float bandCenter = 0.7 - 0.3 * smoothstep(30.0, 110.0, f);
  float offset = u - bandCenter;
  float decay = (1.05 - bandCenter) / 1.31;
  float profile = offset < 0.0 ? exp(-sq(offset / 0.3)) : exp(-offset / decay);
  profile *= 1.0 - smoothstep(1.0, 1.4, u);
  vec3 bandA = mix(CYAN, PINK, smoothstep(50.0, 75.0, f));
  bandA = mix(bandA, LILAC, smoothstep(100.0, 125.0, f));
  vec3 bandB = mix(SKY, PURPLE, smoothstep(50.0, 75.0, f));
  vec3 fanK = mix(bandA, bandB, smoothstep(0.06, 0.18, offset));
  fanK = mix(fanK, DEEP, smoothstep(0.22, 0.42, offset));
  vec3 thread = WHITE * wall * bright + coreK * core * streak * bright;
  glow += fanK * 4.5 * profile * fade * streak * bright;
  glow += MIST * 0.7 * exp(-max(u - 1.0, 0.0) / 0.9) * smoothstep(0.7, 1.2, u) * fade * soft;
  glow += EMBER * 0.35 * exp(-sq((f - 165.0) / 22.0)) * exp(-d / 25.0) * bright;
  float lag = u * (6.0 + 0.28 * f) * 0.35;
  float reveal = 1.0 - smoothstep(front - 70.0, front + 8.0, f + lag);
  glow *= start * reveal;
  return thread * start * reveal;
}

vec3 easeLight(vec3 light, float amount) {
  return -log(max(1.0 - amount * (1.0 - exp(-light)), vec3(0.0001)));
}

void main() {
  vec2 frag = vec2(gl_FragCoord.x, uResolution.y * uDpr - gl_FragCoord.y) / uDpr;
  // A sideways beam is the same light drawn with the axes swapped.
  // A beam from the right is the same again, mirrored first.
  if (uMirror > 0.5) frag.x = uResolution.x - frag.x;
  if (uAcross > 0.5) frag = frag.yx;
  vec2 p = frag / uScale;
  float t = uTime;
  float bx = uBeamX / uScale;
  float sl = uSurface.x / uScale;
  float sy = uSurface.y / uScale;
  float sr = uSurface.z / uScale;
  float sb = uSurface.w / uScale;
  float radius = uRadius / uScale;
  float dx = p.x - bx;
  float adx = abs(dx);
  // How squarely the beam hits the surface: 1 on the flat face, falling off as
  // it slides round a corner and past the side. The splash follows the point
  // of contact down the corner, and the surface shadows the beam pixel by
  // pixel, so the light streams past the corner as the beam leaves it.
  float miss = max(sl - bx, bx - sr);
  float hit = 1.0 - smoothstep(-radius, 24.0 * uShape.x, miss);
  float contact = min(faceAt(bx, sl, sr, sy, radius), sy + radius);
  float h = contact - p.y;
  float hp = max(h, 0.0);
  float shade = faceAt(p.x, sl, sr, sy, radius) - p.y;
  // The shadow is sharp at the surface and softens with distance behind it,
  // so the glow round the beam is not cut off along a hard line.
  float lateral = min(p.x - sl, sr - p.x);
  float penumbra = 1.0 + 0.12 * max(p.y - sy, 0.0);
  float above = 1.0 - (1.0 - smoothstep(-0.5, 0.5, shade)) * smoothstep(-penumbra, penumbra, lateral);
  float side = smoothstep(-24.0, 24.0, dx);
  vec3 sideK = mix(mix(LAVENDER, LEFT, smoothstep(40.0, 140.0, adx)), RIGHT, side);
  float beamWidth = uShape.x;
  float flare = uShape.y;
  float spread = 250.0 * uShape.z;
  float reachL = max(bx - sl, 1.0);
  float reachR = max(sr - bx, 1.0);
  float reach = dx < 0.0 ? reachL : reachR;
  float layerLen = clamp(0.29 * reach, 20.0, 100.0) * sqrt(uShape.z);
  float run = uRun.x;
  float runMask = 1.0 - smoothstep(run - 34.0, run + 6.0, adx);
  float bead = exp(-sq((adx - run + 16.0) / (18.0 + 0.04 * run))) * uRun.y;
  float flowMask = (1.0 - smoothstep(0.75 * spread, 1.1 * spread, adx)) * runMask;
  float edgeMask = (1.0 - smoothstep(0.8 * spread, 1.25 * spread, adx)) * runMask;
  float bloom = uIntro.y;
  float splash = min(bloom, 1.0) * hit * (1.0 - uContour);
  vec2 center = vec2((sl + sr) * 0.5, (sy + sb) * 0.5);
  vec2 halfSize = vec2((sr - sl) * 0.5, (sb - sy) * 0.5);
  float sd = roundBox(p - center, halfSize, radius);
  float outline = max(sd, 0.0);
  float below = max(p.y - sy - radius, 0.0);
  float hug = smoothstep(-0.5, 0.5, sd) * exp(-sq(below / 14.0));
  float hugWide = smoothstep(-0.5, 0.5, sd) * exp(-sq(below / 40.0));

  vec3 col = vec3(0.0);

  float breathe = 1.0 + uExtra.x * (0.12 * sin(t * 1.5708) + 0.08 * (noise(vec2(t * 0.5, 3.0)) - 0.5));

  float front = uIntro.x / uScale;
  float drop = smoothstep(front + 10.0, front - 110.0, p.y);
  float falling = 1.0 - smoothstep(sy - 24.0, sy, front);
  float top = mix(0.3, 1.0, smoothstep(0.0, uBase / uScale, p.y));
  float beamCore = 24.0 * exp(-adx / (2.0 * beamWidth));
  float beamHalo = 1.3 * exp(-adx / (6.0 * beamWidth)) + 0.3 * exp(-adx / (22.0 * beamWidth));
  vec3 haloK = mix(BEAM, sideK, exp(-hp / 80.0));
  col += (BEAM * beamCore + haloK * beamHalo) * top * above * drop;
  float head = exp(-sq((p.y - front) / 24.0)) * falling;
  col += mix(WHITE, BEAM, 0.35) * head * (7.0 * exp(-adx / (2.6 * beamWidth)) + 1.0 * exp(-adx / (14.0 * beamWidth)));

  float psi = adx * (outline + 1.0);
  float rise = max(hp - 17.9 * flare, 0.0);
  float skirtAmp = 16.6 * (exp(-sq(rise / (11.8 * flare))) + 0.3 * exp(-rise / (60.0 * flare)));
  float skirtSpread = mix(134.0, 155.0, side) * breathe * flare * flare * mix(0.35, 1.0, min(bloom, 1.0)) * max(bloom, 1.0);
  float skirt = skirtAmp * exp(-psi / skirtSpread) * exp(-sq(adx / (max(layerLen, 60.0 * sqrt(uShape.z)) * 1.48))) * hug;
  col += sideK * skirt * flowMask * splash;

  float layer = 12.0 * exp(-adx / layerLen) * exp(-outline / (0.19 * layerLen)) * (1.0 + 0.4 * bead);
  col += sideK * layer * hug * flowMask * splash;
  float washMask = smoothstep(sl - 60.0, sl + 6.0, p.x) * (1.0 - smoothstep(sr - 6.0, sr + 45.0, p.x));
  float wash = 1.4 * exp(-adx / 100.0) * exp(-outline / 30.0);
  col += mix(BEAM, sideK, 0.25) * wash * hugWide * washMask * flowMask * splash;
  float highWash = 0.7 * exp(-adx / 140.0) * exp(-outline / 60.0);
  col += mix(BEAM, NAVY, 0.5) * highWash * hugWide * washMask * runMask * splash;

  float sideSign = dx < 0.0 ? 0.0 : 1.0;
  float along = 0.5 * log((hp + 1.0) / (adx + 1.0));
  float lineScale = 6.0;
  float lp = log(max(psi, 1.0) / (120.0 * flare * flare)) * lineScale;
  float lineIndex = floor(lp) + sideSign * 97.0;
  float wobble = 0.22 * (noise(vec2(lineIndex * 3.7, t * 0.4 + along)) - 0.5);
  float lf = fract(lp + wobble) - 0.5;
  float gradient = lineScale * length(vec2(hp + 1.0, adx)) / max(psi, 1.0) / uScale;
  float halfWidth = max(0.35 * gradient, 0.0001);
  float drawWidth = max(halfWidth, 0.6 * gradient);
  float lineShape = exp(-lf * lf / (drawWidth * drawWidth)) * (halfWidth / drawWidth);
  float lineOn = step(0.3, hash(vec2(lineIndex, 1.3)));
  float lineFlow = smoothstep(0.25, 0.85, noise(vec2(lineIndex * 5.3 + 2.0, along * 3.0 + t * 1.1)));
  float flareArea = 120.0 * flare * flare;
  float lineEnvelope = smoothstep(0.85 * flareArea, 1.4 * flareArea, psi) * (1.0 - smoothstep(3.2 * flareArea, 7.5 * flareArea, psi));
  lineEnvelope *= exp(-adx / (layerLen * 1.5)) * hug * flowMask * (1.0 - smoothstep(35.0 * flare, 80.0 * flare, hp));
  float lineBright = mix(0.35, 1.0, hash(vec2(lineIndex, 4.0)));
  col += mix(sideK, WHITE, 0.6) * lineShape * lineOn * lineFlow * lineEnvelope * lineBright * 2.6 * uAmount.w * splash;

  float edgeGlow = 22.8 * exp(-sq(adx / (150.0 * uShape.z))) * edgeMask * (1.0 + 0.9 * bead);
  float onTop = 1.0 - smoothstep(sy + radius, sy + radius + 10.0, p.y);
  float edgeLine = (exp(-sq(max(sd, 0.0) / 0.9)) + 0.12 * exp(-max(sd, 0.0) / 3.0)) * edgeGlow * onTop;
  col += mix(sideK, WHITE, 0.6) * edgeLine * splash;

  if (uContour > 0.001) {
    // Contour light, anchored to the beam: it starts at the point of the
    // outline the beam strikes (or, once the beam has slid off, the point it
    // last touched) and runs along the outline both ways, round the corners,
    // fading with the distance travelled. How much arrives depends on how
    // squarely the beam still meets the surface. Pulses stream away from that
    // point, and rays grow outward wherever the edge is lit.
    vec2 q = p - center;
    float along = perimeter(q, halfSize, radius);
    float offset = bx - center.x;
    float missBy = abs(offset) - halfSize.x;
    // Where the beam line meets the near face or its rounded corner, as arc
    // length; continuous as the beam slides round the corner and off.
    float innerX = halfSize.x - radius;
    float intoCorner = clamp(abs(offset) - innerX, 0.0, radius);
    float origin = sign(offset) * (min(abs(offset), innerX) + radius * asin(intoCorner / max(radius, 1e-4)));
    float incoming = exp(-max(missBy, 0.0) / (18.0 * beamWidth));
    float travel = abs(along - origin);
    float stream = 0.6 + 0.8 * smoothstep(0.35, 0.85, noise(vec2((travel - t * 70.0) / 24.0, 3.0 + sign(along - origin))));
    float light = uWrap.x * incoming * exp(-travel / (uWrap.y / uScale)) * stream;

    float rayOn = smoothstep(0.45, 0.9, noise(vec2(along / 5.0, t * 0.7)));
    float rayLength = 4.0 + 30.0 * noise(vec2(along / 11.0 + 7.0, t * 0.4)) * min(light, 1.0);
    float rim = exp(-sq(outline / 0.9)) + 0.2 * exp(-outline / 6.0);
    // Bloom: wide, soft halos round the lit edge.
    float halo = uWrap.z * (0.22 * exp(-outline / 16.0) + 0.09 * exp(-outline / 42.0));
    float rays = rayOn * exp(-outline / rayLength) * smoothstep(0.0, 1.5, outline);
    float outside = smoothstep(-0.5, 0.5, sd) * min(bloom, 1.0) * uContour;
    col += mix(sideK, WHITE, 0.55) * (3.2 * rim + 1.6 * rays) * light * outside;
    col += mix(BEAM, sideK, 0.4) * 3.2 * halo * light * outside;

    // A hot spot where the beam strikes, sliding off with it.
    vec2 strike = center + vec2(clamp(offset, -halfSize.x, halfSize.x), -halfSize.y);
    float strikeDistance = length(p - strike);
    col += mix(BEAM, WHITE, 0.4) * 2.5 * uWrap.x * incoming * exp(-strikeDistance / (10.0 * beamWidth)) * outside;
    col += BEAM * 0.6 * uWrap.x * uWrap.z * incoming * exp(-strikeDistance / 55.0) * outside;
  }

  float pour = uShape.w;
  float baseline = exp(-sq(130.0 / 150.0));
  float strengthR = hit * (1.0 - uContour) * exp(-sq(reachR / (150.0 * uShape.z))) * (1.0 - smoothstep(0.8 * spread, 1.25 * spread, reachR)) / baseline * pour;
  float strengthL = hit * (1.0 - uContour) * exp(-sq(reachL / (150.0 * uShape.z))) * (1.0 - smoothstep(0.8 * spread, 1.25 * spread, reachL)) / baseline * pour;
  float fallY = p.y - sy - 0.3 * radius;
  float rightHalf = smoothstep(center.x - 4.0, center.x + 4.0, p.x);
  float haloR = exp(-length(p - vec2(sr - 0.3 * radius, sy + 0.3 * radius)) / 40.0) * sqrt(strengthR);
  float haloL = exp(-length(p - vec2(sl + 0.3 * radius, sy + 0.3 * radius)) / 40.0) * sqrt(strengthL);
  vec3 glowR;
  vec3 glowL;
  col += spill(sd, fallY, strengthR, uPour.y, t, glowR) * rightHalf;
  col += spill(sd, fallY, strengthL, uPour.x, t, glowL) * (1.0 - rightHalf);
  col += easeLight(glowR * rightHalf + NAVY * 0.9 * haloR, uPour.w);
  col += easeLight(glowL * (1.0 - rightHalf) + NAVY * 0.9 * haloL, uPour.z);

  vec2 toLens = frag - uLens.xy;
  float lens = exp(-dot(toLens, toLens) / sq(uLens.z)) * uLens.w;
  col *= 1.0 + 0.35 * lens * hug;
  float fogAmount = uAmount.y * uAtmosphere;
  float near = exp(-adx / 150.0);
  float envelope = near * (0.3 + 0.4 * hit * exp(-hp / 50.0) + 1.2 * uBaseGlow * exp(-p.y / 120.0));
  if (fogAmount > 0.001 && (h > -2.0 || hit < 0.999) && envelope * max(0.25, 6.0 * exp(-adx / 50.0)) > 0.002) {
    // Anchored to the source edge, not the surface, so the smoke keeps its
    // shape when the beam lands on a different surface.
    vec2 fq = vec2(dx / 1.7, -p.y) / 85.0 + vec2(t * 0.012, -t * 0.03) + uExtra.zw;
    vec2 fw = vec2(fbm(fq * 1.3 + vec2(1.7, 9.2) + t * 0.03), fbm(fq * 1.3 + vec2(8.3, 2.8) - t * 0.025));
    float cloud = fbm(fq + 1.4 * fw);
    float density = smoothstep(0.5, 0.78, cloud);
    float lit = exp(-adx / 50.0);
    // Smoke lies in front of the point of contact, and opens up past the
    // surface as the beam slides off it.
    float fogMask = max(smoothstep(-2.0, 20.0, h), 1.0 - hit);
    float reached = smoothstep(front + 80.0, front - 40.0, p.y);
    vec3 fog = (HAZE * 0.45 + BEAM * 6.0 * lit * reached) * density * envelope * fogMask;
    float surfaceLit = exp(-adx / (layerLen * 1.3)) * exp(-outline / 28.0) * hugWide * flowMask * washMask * splash;
    fog += sideK * 2.2 * surfaceLit * (smoothstep(0.38, 0.72, cloud) - 0.35) * fogMask;
    float smoke = smoothstep(0.3, 0.75, cloud);
    fog += BEAM * 0.35 * exp(-adx / (22.0 * beamWidth)) * (0.35 + 0.9 * smoke) * fogMask * top * drop;
    col += fog * fogAmount * (1.0 + 1.2 * lens) * mix(1.0, 0.45, uTheme);
  }

  if (uRevealInfo.y > 0.001 && uLens.w > 0.002) {
    vec2 toReveal = frag - uLens.xy;
    float reveal = exp(-dot(toReveal, toReveal) / sq(uRevealInfo.x)) * uLens.w;
    vec2 uv = frag * uRevealMap.xy + uRevealMap.zw;
    float onImage = step(0.0, uv.x) * step(uv.x, 1.0) * step(0.0, uv.y) * step(uv.y, 1.0);
    vec4 ui = texture(uReveal, uv);
    float ink = max(ui.r, max(ui.g, ui.b)) * onImage;
    float lit = clamp(col.b * 0.9, 0.0, 1.0) * (1.0 - smoothstep(0.9, 2.2, col.b));
    float clearance = smoothstep(60.0 * sqrt(beamWidth), 150.0 * sqrt(beamWidth), adx);
    col += mix(BEAM, WHITE, 0.4) * ink * reveal * lit * clearance * uRevealInfo.y * 2.2;
  }

  float haze = col.b;
  float dotGrid = 1.0 - smoothstep(0.16, 0.32, length(fract(frag / 3.0) - 0.5));
  col += BEAM * dotGrid * clamp(haze, 0.0, 1.5) * (1.0 - smoothstep(1.5, 4.0, haze)) * (0.18 + 0.3 * lens) * uExtra.y;
  if (lens > 0.002) {
    vec2 drift = frag - vec2(0.0, t * 14.0);
    vec2 sparkCell = floor(drift / 7.0);
    vec2 sparkPos = (sparkCell + 0.2 + 0.6 * vec2(hash(sparkCell + 5.1), hash(sparkCell + 2.3))) * 7.0;
    float sparkDist = length(drift - sparkPos);
    float sparkOn = step(0.8, hash(sparkCell + 8.8));
    float sparkTwinkle = 0.5 + 0.5 * sin(t * 5.0 + hash(sparkCell + 3.7) * 6.283);
    col += WHITE * exp(-sparkDist * sparkDist / 0.35) * sparkOn * sparkTwinkle * lens * clamp(haze * 1.5, 0.0, 1.0) * 1.6 * uAmount.z;
  }

  float dustAmount = uAmount.z;
  if (dustAmount > 0.001) {
    float dustLp = log(max(psi, 1.0) / (120.0 * flare * flare)) * 2.2;
    vec2 flowCell = vec2(dustLp / 1.1, (along + t * 0.22) / 0.06);
    vec2 cellId = floor(flowCell) + vec2(sideSign * 131.0, 0.0);
    vec2 cellJitter = vec2(hash(cellId + 1.7), hash(cellId + 8.3));
    vec2 particleFlow = (floor(flowCell) + 0.1 + cellJitter * 0.8) * vec2(1.1, 0.06);
    float particlePsi = 120.0 * flare * flare * exp(particleFlow.x / 2.2);
    float particleAlong = particleFlow.y - t * 0.22;
    float particleX = sqrt(particlePsi * exp(-2.0 * particleAlong)) - 1.0;
    float particleH = sqrt(particlePsi * exp(2.0 * particleAlong)) - 1.0;
    float particleDist = length(vec2(adx - particleX, hp - particleH)) * uScale;
    float particleOn = step(0.62, hash(cellId + 3.1));
    float particleTwinkle = 0.5 + 0.5 * sin(t * 5.0 + hash(cellId + 9.2) * 6.283);
    float dustZone = exp(-sq(log(max(psi, 1.0) / (200.0 * flare * flare)) / 0.55)) * hug * flowMask * smoothstep(0.0, 6.0, outline);
    col += WHITE * exp(-particleDist * particleDist / 0.3) * particleOn * particleTwinkle * dustZone * 3.0 * dustAmount * splash;

    vec2 glitterCell = vec2(dx / 3.0, (p.y - t * 26.0) / 9.0);
    vec2 glitterId = floor(glitterCell);
    vec2 glitterJitter = vec2(hash(glitterId + 4.4), hash(glitterId + 2.9));
    vec2 glitterPos = (glitterId + 0.15 + glitterJitter * 0.7) * vec2(3.0, 9.0);
    float glitterDist = length(vec2(dx, p.y - t * 26.0) - glitterPos) * uScale;
    float glitterOn = step(0.7, hash(glitterId + 6.6));
    float glitterTwinkle = 0.5 + 0.5 * sin(t * 6.0 + hash(glitterId + 1.1) * 6.283);
    float glitterZone = exp(-adx / (5.0 * beamWidth)) * smoothstep(1.5, 4.0, adx / beamWidth) * above * smoothstep(25.0, 70.0, shade) * top * drop;
    col += WHITE * exp(-glitterDist * glitterDist / 0.25) * glitterOn * glitterTwinkle * glitterZone * 2.2 * dustAmount * uAtmosphere;
  }

  col *= uAmount.x * (1.0 + uIntro.z * 0.9 * exp(-length(vec2(dx, h * 1.6)) / 70.0));
  col *= smoothstep(-0.75, 0.25, sd * uScale);

  // Some smoke terms dip below zero; negative light would show as dark specks.
  col = max(col, 0.0);
  vec3 emit = 1.0 - exp(-col * mix(1.0, 0.6, uTheme));
  float peak = max(emit.r, max(emit.g, emit.b));
  if (uTheme > 0.5) {
    float low = min(emit.r, min(emit.g, emit.b));
    float chroma = peak - low;
    vec3 hue = (emit - low) / max(chroma, 0.0001);
    float alpha = clamp(pow(chroma, 1.35) * 1.3, 0.0, 1.0) * 0.9;
    outColor = vec4((hue * 0.82 + 0.06) * alpha, alpha) * uFade;
  } else {
    outColor = vec4(emit, peak) * uFade;
  }
}`;

// Hue shift and saturation scale of each palette slot, relative to `color`.
const TINTS: ReadonlyArray<readonly [number, number]> = [
	[0, 1],
	[-11.5, 0.77],
	[9.5, 0.95],
	[-53.5, 0.79],
	[39.5, 0.77],
	[16, 0.81],
	[-16.3, 0.92],
	[13.3, 0.96],
	[3, 1.01],
	[1, 0.68],
	[1, 1.15],
	[142.5, 0.51],
	[113.6, 0.28],
	[-7.5, 0.13],
	[-2.7, 0.32],
	[7.5, 0.81],
];

const BASE_SATURATION = 0.78;
const MAX_RENDER_DIM = 2048;
const INTRO_DROP = 1.25;
const INTRO_END = 5;

type Rgb = [number, number, number];

const clamp = (value: number, min: number, max: number) =>
	Math.min(max, Math.max(min, value));
const easeOut = (x: number) => 1 - (1 - clamp(x, 0, 1)) ** 3;
const spring = (time: number) => {
	const omega = 8;
	const zeta = 0.62;
	const damped = omega * Math.sqrt(1 - zeta * zeta);
	return (
		1 -
		Math.exp(-zeta * omega * time) *
			(Math.cos(damped * time) +
				((zeta * omega) / damped) * Math.sin(damped * time))
	);
};

// Sine ease-in-out: speeds up and slows down with no jerk. Maps 0..1 to 0..1.
const easeInOut = (p: number) => 0.5 - 0.5 * Math.cos(Math.PI * p);

const toHsv = ([r, g, b]: Rgb): [number, number] => {
	const max = Math.max(r, g, b);
	const min = Math.min(r, g, b);
	const delta = max - min;
	let hue = 0;
	if (delta > 0) {
		if (max === r) hue = ((g - b) / delta) % 6;
		else if (max === g) hue = (b - r) / delta + 2;
		else hue = (r - g) / delta + 4;
	}
	return [(hue * 60 + 360) % 360, max > 0 ? delta / max : 0];
};

const fromHsv = (hue: number, saturation: number): Rgb => {
	const h = (((hue % 360) + 360) % 360) / 60;
	const c = saturation;
	const x = c * (1 - Math.abs((h % 2) - 1));
	const m = 1 - c;
	const [r, g, b] =
		h < 1
			? [c, x, 0]
			: h < 2
				? [x, c, 0]
				: h < 3
					? [0, c, x]
					: h < 4
						? [0, x, c]
						: h < 5
							? [x, 0, c]
							: [c, 0, x];
	return [r + m, g + m, b + m];
};

const buildTints = (rgb: Rgb) => {
	const [hue, saturation] = toHsv(rgb);
	const strength = saturation / BASE_SATURATION;
	const data = new Float32Array(TINTS.length * 3);
	TINTS.forEach(([shift, scale], index) => {
		data.set(
			fromHsv(hue + shift, clamp(BASE_SATURATION * scale * strength, 0, 1)),
			index * 3,
		);
	});
	return data;
};

const compile = (gl: WebGL2RenderingContext, type: number, source: string) => {
	const shader = gl.createShader(type);
	if (!shader) return null;
	gl.shaderSource(shader, source);
	gl.compileShader(shader);
	if (gl.getShaderParameter(shader, gl.COMPILE_STATUS)) return shader;
	gl.deleteShader(shader);
	return null;
};

const link = (
	gl: WebGL2RenderingContext,
	vertexSource: string,
	fragmentSource: string,
) => {
	const vertex = compile(gl, gl.VERTEX_SHADER, vertexSource);
	const fragment = compile(gl, gl.FRAGMENT_SHADER, fragmentSource);
	const program = gl.createProgram();
	if (!vertex || !fragment || !program) return null;
	gl.attachShader(program, vertex);
	gl.attachShader(program, fragment);
	gl.linkProgram(program);
	gl.deleteShader(vertex);
	gl.deleteShader(fragment);
	if (gl.getProgramParameter(program, gl.LINK_STATUS)) return program;
	gl.deleteProgram(program);
	return null;
};

const UNIFORMS = [
	"uResolution",
	"uDpr",
	"uScale",
	"uTime",
	"uBeamX",
	"uSurface",
	"uRadius",
	"uIntro",
	"uPour",
	"uRun",
	"uLens",
	"uReveal",
	"uRevealMap",
	"uRevealInfo",
	"uAtmosphere",
	"uAmount",
	"uShape",
	"uExtra",
	"uTheme",
	"uAcross",
	"uMirror",
	"uFade",
	"uBase",
	"uBaseGlow",
	"uContour",
	"uWrap",
	"uTint",
] as const;

type UniformName = (typeof UNIFORMS)[number];

const locate = (gl: WebGL2RenderingContext, program: WebGLProgram) => {
	const result = {} as Record<UniformName, WebGLUniformLocation | null>;
	for (const name of UNIFORMS)
		result[name] = gl.getUniformLocation(program, name);
	return result;
};

type LaserFlowProps = Omit<ComponentProps<"div">, "color" | "children"> & {
	/** Element the beam lands on; the light spreads along its top edge. */
	surfaceRef?: RefObject<HTMLElement | null>;
	/** Horizontal beam position, 0 (left) to 1 (right). */
	beamPosition?: number;
	/**
	 * Seconds for one scan, left to right and back. The beam then sweeps across
	 * the surface instead of holding at beamPosition. 0 turns it off.
	 */
	sweepPeriod?: number;
	/** Share of the surface width the sweep covers, 0 to 1. */
	sweepWidth?: number;
	/**
	 * "bounce" swings across the surface and back. "scan" runs once across the
	 * whole container, from one edge past the other, over sweepPeriod seconds,
	 * then waits sweepRest seconds off screen and starts again.
	 */
	sweepMode?: "bounce" | "scan";
	sweepRest?: number;
	/**
	 * Share of each scan the light takes to fade in at the start and to fade out
	 * at the end, 0 to 0.5. 0 keeps it at full strength throughout.
	 */
	sweepFade?: number;
	/** Glow of the smoke where the beam enters, at its source edge. 0 hides it. */
	baseGlow?: number;
	/**
	 * How the light meets the surface: "splash" is the original flared splash;
	 * "contour" runs the light along the outline from the point of contact,
	 * round the corners, wherever the beam's light reaches.
	 */
	wrap?: "splash" | "contour";
	/** Brightness of the contour light. */
	wrapIntensity?: number;
	/** Distance in px over which the contour light fades along the outline. */
	wrapReach?: number;
	/** Strength of the soft bloom round the lit outline. 0 turns it off. */
	wrapBloom?: number;
	/** Landing height when there is no surfaceRef, 0 (top) to 1 (bottom). */
	surfaceLevel?: number;
	color?: string;
	intensity?: number;
	beamWidth?: number;
	flare?: number;
	spread?: number;
	spill?: number;
	fog?: number;
	dust?: number;
	streaks?: number;
	dots?: number;
	pulse?: number;
	speed?: number;
	seed?: number;
	mouseInteraction?: boolean;
	/** Image revealed through the light around the cursor. */
	revealImage?: string;
	revealRadius?: number;
	revealOpacity?: number;
	intro?: boolean;
	theme?: "dark" | "light";
	/**
	 * Which way the beam travels: "down" falls from the top onto the top edge
	 * of the surface, "right" comes in from the left onto its left edge. With
	 * "right", beamPosition and the sweep run along the vertical axis. "left"
	 * mirrors "right": the beam comes in from the right onto the right edge.
	 */
	direction?: "down" | "right" | "left";
	paused?: boolean;
	/** Maximum device pixel ratio, capped at 2. */
	dpr?: number;
};

function LaserFlow({
	surfaceRef,
	beamPosition = 0.6,
	sweepPeriod = 0,
	sweepWidth = 0.8,
	sweepMode = "bounce",
	sweepRest = 0,
	sweepFade = 0,
	baseGlow = 1,
	wrap = "splash",
	wrapIntensity = 1,
	wrapReach = 90,
	wrapBloom = 1,
	surfaceLevel = 1,
	color = "#3847ff",
	intensity = 1.8,
	beamWidth = 1.5,
	flare = 1.5,
	spread = 1.5,
	spill = 1,
	fog = 0.2,
	dust = 1.6,
	streaks = 1.5,
	dots = 1,
	pulse = 1.5,
	speed = 1.5,
	seed = 3,
	mouseInteraction = true,
	revealImage,
	revealRadius = 220,
	revealOpacity = 0.6,
	intro = true,
	theme = "dark",
	direction = "down",
	paused = false,
	dpr,
	className,
	...attributes
}: LaserFlowProps) {
	const containerRef = useRef<HTMLDivElement>(null);
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const wakeRef = useRef<(() => void) | null>(null);
	const settings = {
		surfaceRef,
		beamPosition: clamp(beamPosition, 0, 1),
		sweepPeriod: Math.max(0, sweepPeriod),
		sweepWidth: clamp(sweepWidth, 0, 1),
		sweepMode,
		sweepRest: Math.max(0, sweepRest),
		sweepFade: clamp(sweepFade, 0, 0.5),
		baseGlow: Math.max(0, baseGlow),
		wrap,
		wrapIntensity: Math.max(0, wrapIntensity),
		wrapReach: Math.max(1, wrapReach),
		wrapBloom: Math.max(0, wrapBloom),
		surfaceLevel: clamp(surfaceLevel, 0, 1),
		color: String(color),
		intensity: Math.max(0, intensity),
		beamWidth: clamp(beamWidth, 0.2, 5),
		flare: clamp(flare, 0.2, 4),
		spread: clamp(spread, 0.1, 4),
		spill: Math.max(0, spill),
		fog: Math.max(0, fog),
		dust: Math.max(0, dust),
		streaks: Math.max(0, streaks),
		dots: Math.max(0, dots),
		pulse: Math.max(0, pulse),
		speed,
		seed,
		mouseInteraction,
		revealImage,
		revealRadius: Math.max(1, revealRadius),
		revealOpacity: clamp(revealOpacity, 0, 1),
		intro,
		theme,
		direction,
		paused,
		dpr,
	};
	const settingsRef = useRef(settings);
	settingsRef.current = settings;

	useEffect(() => {
		const container = containerRef.current;
		const canvas = canvasRef.current;
		const gl = canvas?.getContext("webgl2", {
			alpha: true,
			premultipliedAlpha: true,
			antialias: false,
			depth: false,
			stencil: false,
		});
		if (!container || !canvas || !gl) return undefined;

		const program = link(gl, VERTEX, FRAGMENT);
		if (!program) return undefined;

		const uniforms = locate(gl, program);

		// One oversized triangle covers the whole viewport.
		const vao = gl.createVertexArray();
		const buffer = gl.createBuffer();
		gl.bindVertexArray(vao);
		gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
		gl.bufferData(
			gl.ARRAY_BUFFER,
			new Float32Array([-1, -1, 3, -1, -1, 3]),
			gl.STATIC_DRAW,
		);
		const positionLocation = gl.getAttribLocation(program, "aPosition");
		gl.enableVertexAttribArray(positionLocation);
		gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);
		gl.bindVertexArray(null);

		const revealTexture = gl.createTexture();
		gl.bindTexture(gl.TEXTURE_2D, revealTexture);
		gl.texImage2D(
			gl.TEXTURE_2D,
			0,
			gl.RGBA,
			1,
			1,
			0,
			gl.RGBA,
			gl.UNSIGNED_BYTE,
			new Uint8Array([0, 0, 0, 0]),
		);
		gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
		gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
		gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
		gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

		// A 1x1 canvas resolves any CSS color string to RGB.
		const probe = document.createElement("canvas");
		probe.width = 1;
		probe.height = 1;
		const probeContext = probe.getContext("2d", { willReadFrequently: true });
		const reduce =
			window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
		const state = {
			time: 0,
			sweepTime: 0,
			introTime: settingsRef.current.intro && !reduce ? 0 : INTRO_END,
			width: 1,
			height: 1,
			ratio: 1,
			colorKey: "",
			tints: buildTints([0.22, 0.28, 1]),
			observed: null as HTMLElement | null,
			pointer: { x: 0, y: 0, inside: false },
			lens: { x: 0, y: 0, vx: 0, vy: 0, strength: 0, placed: false },
			reveal: {
				src: "",
				ready: false,
				width: 1,
				height: 1,
				image: null as HTMLImageElement | null,
			},
		};
		let raf = 0;
		let last = 0;
		let visible = true;
		let alive = true;

		const toRgb = (value: string): Rgb => {
			if (!probeContext) return [0.22, 0.28, 1];
			probeContext.clearRect(0, 0, 1, 1);
			probeContext.fillStyle = "#3847ff";
			probeContext.fillStyle = value;
			probeContext.fillRect(0, 0, 1, 1);
			const [r, g, b] = probeContext.getImageData(0, 0, 1, 1).data;
			return [r / 255, g / 255, b / 255];
		};

		type Settings = typeof settingsRef.current;

		const resolveColor = (s: Settings) => {
			if (s.color === state.colorKey) return;
			state.colorKey = s.color;
			state.tints = buildTints(toRgb(s.color));
		};

		const resolveReveal = (s: Settings) => {
			const src = s.revealImage ? String(s.revealImage) : "";
			const reveal = state.reveal;
			if (src === reveal.src) return;
			reveal.src = src;
			reveal.ready = false;
			if (reveal.image) reveal.image.onload = null;
			if (!src) return;
			const image = new Image();
			image.crossOrigin = "anonymous";
			image.decoding = "async";
			image.onload = () => {
				if (!alive || reveal.src !== src) return;
				const width = image.naturalWidth || image.width || 1;
				const height = image.naturalHeight || image.height || 1;
				const scale = Math.min(1, 2048 / Math.max(width, height));
				const sheet = document.createElement("canvas");
				sheet.width = Math.max(1, Math.round(width * scale));
				sheet.height = Math.max(1, Math.round(height * scale));
				sheet
					.getContext("2d")
					?.drawImage(image, 0, 0, sheet.width, sheet.height);
				gl.bindTexture(gl.TEXTURE_2D, revealTexture);
				gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
				gl.texImage2D(
					gl.TEXTURE_2D,
					0,
					gl.RGBA,
					gl.RGBA,
					gl.UNSIGNED_BYTE,
					sheet,
				);
				gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
				reveal.width = sheet.width;
				reveal.height = sheet.height;
				reveal.ready = true;
				wakeRef.current?.();
			};
			image.src = src;
			reveal.image = image;
		};

		const measure = (s: Settings, width: number, height: number) => {
			const element = s.surfaceRef?.current ?? null;
			if (element !== state.observed) {
				if (state.observed) resizeObserver.unobserve(state.observed);
				if (element) resizeObserver.observe(element);
				state.observed = element;
			}
			if (element) {
				const box = container.getBoundingClientRect();
				const rect = element.getBoundingClientRect();
				if (rect.width > 0) {
					const computed = getComputedStyle(element);
					const radius = Math.max(
						parseFloat(computed.borderTopLeftRadius) || 0,
						parseFloat(computed.borderTopRightRadius) || 0,
					);
					const mirror = s.direction === "left";
					const left = mirror ? box.right - rect.right : rect.left - box.left;
					const right = mirror ? box.right - rect.left : rect.right - box.left;
					const top = rect.top - box.top;
					const bottom = rect.bottom - box.top;
					const across = s.direction !== "down";
					return {
						left: across ? top : left,
						top: across ? left : top,
						right: across ? bottom : right,
						bottom: across ? right : bottom,
						radius: Math.min(radius, rect.width / 2, rect.height / 2),
						real: true,
					};
				}
			}
			return {
				left: -width * 2,
				top: s.surfaceLevel * height,
				right: width * 3,
				bottom: height * 3,
				radius: 0,
				real: false,
			};
		};

		const render = () => {
			const s = settingsRef.current;
			resolveColor(s);
			// Everything below runs in the beam's frame: for a sideways beam the
			// axes are swapped, and the shader swaps them back per pixel.
			const across = s.direction !== "down";
			const mirror = s.direction === "left";
			const lensX = mirror ? state.width - state.lens.x : state.lens.x;
			const width = across ? state.height : state.width;
			const height = across ? state.width : state.height;
			const scale = Math.max(0.2, Math.min(width / 585, height / 507));
			const surface = measure(s, width, height);
			let beamX = s.beamPosition * width;
			// Overall strength of the light; a scan fades it in and out.
			let strength = 1;
			if (s.sweepPeriod > 0 && s.sweepMode === "scan") {
				// One pass from just before the container to just past it, easing in
				// and out, then a rest off screen.
				const phase = state.sweepTime % (s.sweepPeriod + s.sweepRest);
				const time = phase / s.sweepPeriod;
				const progress = easeInOut(clamp(time, 0, 1));
				if (time >= 1) strength = 0;
				else if (s.sweepFade > 0)
					strength =
						easeInOut(clamp(time / s.sweepFade, 0, 1)) *
						easeInOut(clamp((1 - time) / s.sweepFade, 0, 1));
				const reach = 0.08 * width;
				beamX = -reach + (width + 2 * reach) * progress;
			} else if (s.sweepPeriod > 0) {
				// Ping-pong across the surface (or the container without one),
				// starting from the centre and heading right.
				const left = surface.real ? surface.left : 0;
				const right = surface.real ? surface.right : width;
				const swing =
					0.5 *
					s.sweepWidth *
					Math.sin((2 * Math.PI * state.sweepTime) / s.sweepPeriod);
				beamX = left + (right - left) * (0.5 + swing);
			}
			const open = {
				left: -width * 2,
				top: height,
				right: width * 3,
				bottom: height * 3,
				radius: 0,
				real: false,
			};
			const baseTop = surface.real ? surface.top : open.top;
			// Each pass is the light for one surface, weighted; the passes add up.
			const passes: Array<[typeof surface, number]> = [];
			if (!surface.real) {
				passes.push([surface, 1]);
			} else if (s.sweepPeriod > 0) {
				// A sweeping beam is not held off the corners: the shader lets it
				// slide round them and past the surface.
				passes.push([surface, 1]);
			} else {
				const margin = surface.radius + 6;
				if (beamX >= surface.left && beamX <= surface.right) {
					beamX = clamp(beamX, surface.left + margin, surface.right - margin);
					passes.push([surface, 1]);
				} else {
					passes.push([open, 1]);
				}
			}

			gl.viewport(0, 0, canvas.width, canvas.height);
			gl.clearColor(0, 0, 0, 0);
			gl.clear(gl.COLOR_BUFFER_BIT);
			// biome-ignore lint/correctness/useHookAtTopLevel: WebGL call, not a React hook
			gl.useProgram(program);
			// Premultiplied output, so weighted passes simply add.
			gl.enable(gl.BLEND);
			gl.blendFunc(gl.ONE, gl.ONE);
			for (const [surface, weight] of strength > 0.001 ? passes : []) {
				const startY = -0.15 * height;
				const span = surface.top - startY + 0.3 * height;
				const it = state.introTime;
				const settled = it >= INTRO_END;
				const front = settled
					? surface.top + 0.3 * height
					: startY + span * clamp(it / INTRO_DROP, 0, 1) ** 1.3;
				const impact =
					INTRO_DROP * (Math.max(0, surface.top - startY) / span) ** (1 / 1.3);
				const tau = it - impact;
				const bloom = settled ? 1 : tau <= 0 ? 0 : spring(tau);
				const flash =
					settled || tau <= 0
						? 0
						: Math.exp(-tau / 0.35) * (1 - Math.exp(-tau / 0.05));
				const runRange = s.spread * 250 * 1.3 + 80;
				const runFront = settled
					? 100000
					: tau <= 0
						? -40
						: runRange * (1 - Math.exp(-1.15 * tau));
				const beadStrength =
					settled || tau <= 0
						? 0
						: Math.exp(-1.15 * tau) * (1 - Math.exp(-tau / 0.08));
				const pour = (reach: number): [number, number] => {
					if (settled) return [1000, 1];
					if (tau <= 0) return [-reach, 0];
					const target = Math.min(reach, runRange * 0.97);
					const arrival = -Math.log(1 - target / runRange) / 1.15;
					const elapsed = tau - arrival;
					const ease = clamp((elapsed + 0.15) / 0.8, 0, 1);
					const fill = ease * ease * ease * (ease * (ease * 6 - 15) + 10);
					if (elapsed <= 0) return [runFront - target, fill];
					const speed = 1.15 * (runRange - target);
					return [speed * elapsed + 260 * elapsed * elapsed, fill];
				};
				const [frontL, fillL] = pour((beamX - surface.left) / scale);
				const [frontR, fillR] = pour((surface.right - beamX) / scale);
				const atmosphere = settled
					? 1
					: tau <= 0
						? 0.3 * easeOut(it / INTRO_DROP)
						: 0.3 + 0.7 * (1 - Math.exp(-1.3 * tau));
				const seedValue = Number(s.seed) || 0;

				gl.uniform2f(uniforms.uResolution, state.width, state.height);
				gl.uniform1f(uniforms.uDpr, state.ratio);
				gl.uniform1f(uniforms.uScale, scale);
				gl.uniform1f(uniforms.uTime, state.time);
				gl.uniform1f(uniforms.uBeamX, beamX);
				gl.uniform4f(
					uniforms.uSurface,
					surface.left,
					surface.top,
					surface.right,
					surface.bottom,
				);
				gl.uniform1f(uniforms.uRadius, surface.radius);
				gl.uniform3f(uniforms.uIntro, front, bloom, flash);
				gl.uniform4f(uniforms.uPour, frontL, frontR, fillL, fillR);
				gl.uniform2f(uniforms.uRun, runFront, beadStrength);
				gl.uniform4f(
					uniforms.uLens,
					across ? state.lens.y : lensX,
					across ? lensX : state.lens.y,
					95 * scale,
					state.lens.strength,
				);
				resolveReveal(s);
				const { reveal } = state;
				const cover = Math.max(width / reveal.width, height / reveal.height);
				const coverWidth = reveal.width * cover;
				const coverHeight = reveal.height * cover;
				gl.activeTexture(gl.TEXTURE0);
				gl.bindTexture(gl.TEXTURE_2D, revealTexture);
				gl.uniform1i(uniforms.uReveal, 0);
				gl.uniform4f(
					uniforms.uRevealMap,
					1 / coverWidth,
					1 / coverHeight,
					(coverWidth - width) / 2 / coverWidth,
					(coverHeight - height) / 2 / coverHeight,
				);
				gl.uniform2f(
					uniforms.uRevealInfo,
					s.revealRadius,
					reveal.ready ? s.revealOpacity : 0,
				);
				gl.uniform1f(uniforms.uAtmosphere, atmosphere);
				gl.uniform4f(uniforms.uAmount, s.intensity, s.fog, s.dust, s.streaks);
				gl.uniform4f(uniforms.uShape, s.beamWidth, s.flare, s.spread, s.spill);
				gl.uniform4f(
					uniforms.uExtra,
					s.pulse,
					s.dots,
					34.34 + seedValue * 7.31,
					11.58 + seedValue * 3.17,
				);
				gl.uniform1f(uniforms.uTheme, s.theme === "light" ? 1 : 0);
				gl.uniform1f(uniforms.uAcross, across ? 1 : 0);
				gl.uniform1f(uniforms.uMirror, mirror ? 1 : 0);
				gl.uniform1f(uniforms.uFade, weight * strength);
				// The beam brightens over its first stretch; keep that stretch the
				// same in every pass so blended passes agree at the base.
				gl.uniform1f(uniforms.uBase, 0.3 * baseTop);
				gl.uniform1f(uniforms.uBaseGlow, s.baseGlow);
				gl.uniform1f(uniforms.uContour, s.wrap === "contour" ? 1 : 0);
				gl.uniform3f(uniforms.uWrap, s.wrapIntensity, s.wrapReach, s.wrapBloom);
				gl.uniform3fv(uniforms.uTint, state.tints);
				gl.bindVertexArray(vao);
				gl.drawArrays(gl.TRIANGLES, 0, 3);
				gl.bindVertexArray(null);
			}
		};

		const resize = () => {
			const width = Math.max(1, container.clientWidth);
			const height = Math.max(1, container.clientHeight);
			const s = settingsRef.current;
			const baseDpr = Math.min(s.dpr || window.devicePixelRatio || 1, 2);
			const longest = Math.max(width, height) * baseDpr;
			const ratio =
				longest > MAX_RENDER_DIM
					? (baseDpr * MAX_RENDER_DIM) / longest
					: baseDpr;
			const pixelWidth = Math.max(1, Math.round(width * ratio));
			const pixelHeight = Math.max(1, Math.round(height * ratio));
			if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
				canvas.width = pixelWidth;
				canvas.height = pixelHeight;
			}
			state.width = width;
			state.height = height;
			state.ratio = canvas.width / width;
			render();
		};

		const frame = (now: number) => {
			raf = 0;
			if (!alive || !visible || document.hidden) return;
			const s = settingsRef.current;
			const dt = last ? Math.min(0.05, (now - last) / 1000) : 1 / 60;
			last = now;
			const moving = !s.paused && !reduce;
			if (moving) state.time += dt * s.speed;
			if (moving && s.sweepPeriod > 0) state.sweepTime += dt;
			const introducing = state.introTime < INTRO_END;
			if (introducing)
				state.introTime = Math.min(INTRO_END, state.introTime + dt);

			// The cursor lens follows the pointer on a damped spring.
			const { pointer, lens } = state;
			const active = s.mouseInteraction && pointer.inside && !reduce;
			if (active && !lens.placed) {
				lens.x = pointer.x;
				lens.y = pointer.y;
				lens.vx = 0;
				lens.vy = 0;
				lens.placed = true;
			}
			const ax = 120 * (pointer.x - lens.x) - 19 * lens.vx;
			const ay = 120 * (pointer.y - lens.y) - 19 * lens.vy;
			lens.vx += ax * dt;
			lens.vy += ay * dt;
			lens.x += lens.vx * dt;
			lens.y += lens.vy * dt;
			const goal = active ? 1 : 0;
			lens.strength +=
				(goal - lens.strength) *
				(1 - Math.exp(-dt / (goal > lens.strength ? 0.3 : 0.55)));
			if (lens.strength < 0.001 && !active) lens.placed = false;

			render();
			const settling =
				Math.abs(
					state.lens.strength -
						(s.mouseInteraction && state.pointer.inside ? 1 : 0),
				) > 0.002 || Math.hypot(state.lens.vx, state.lens.vy) > 0.5;
			if (moving || introducing || settling) raf = requestAnimationFrame(frame);
			else last = 0;
		};

		const wake = () => {
			if (!raf && alive && visible && !document.hidden)
				raf = requestAnimationFrame(frame);
		};

		const onPointerMove = (event: PointerEvent) => {
			const rect = container.getBoundingClientRect();
			const x = event.clientX - rect.left;
			const y = event.clientY - rect.top;
			state.pointer.x = x;
			state.pointer.y = y;
			state.pointer.inside =
				x >= 0 && y >= 0 && x <= rect.width && y <= rect.height;
			wake();
		};

		const onPointerLeave = () => {
			state.pointer.inside = false;
			wake();
		};

		const onVisibility = () => {
			last = 0;
			wake();
		};

		const resizeObserver = new ResizeObserver(resize);
		resizeObserver.observe(container);
		const intersection = new IntersectionObserver((entries) => {
			visible = entries.some((entry) => entry.isIntersecting);
			if (visible) {
				last = 0;
				wake();
			}
		});
		intersection.observe(container);
		window.addEventListener("pointermove", onPointerMove, { passive: true });
		document.documentElement.addEventListener("pointerleave", onPointerLeave);
		document.addEventListener("visibilitychange", onVisibility);
		resize();
		wake();

		wakeRef.current = () => {
			if (!raf) render();
			wake();
		};

		return () => {
			alive = false;
			cancelAnimationFrame(raf);
			wakeRef.current = null;
			resizeObserver.disconnect();
			intersection.disconnect();
			window.removeEventListener("pointermove", onPointerMove);
			document.documentElement.removeEventListener(
				"pointerleave",
				onPointerLeave,
			);
			document.removeEventListener("visibilitychange", onVisibility);
			gl.deleteTexture(revealTexture);
			gl.deleteBuffer(buffer);
			gl.deleteVertexArray(vao);
			gl.deleteProgram(program);
		};
	}, []);

	// Redraw after every render so prop changes show even while idle.
	useEffect(() => {
		wakeRef.current?.();
	});

	return (
		<div
			ref={containerRef}
			className={cn("laser-flow-container", className)}
			{...attributes}
		>
			<canvas ref={canvasRef} className="laser-flow-canvas" aria-hidden />
		</div>
	);
}

export { LaserFlow };
export type { LaserFlowProps };
