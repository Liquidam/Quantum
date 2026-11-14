// =============================================================================
// AGENT COLOUR - screen space, OUTSIDE the curtain loop.
// The curtain (comp1 = render x level(last frame)) only ever sees one colour,
// so it cannot split into RGB confetti. Colour is painted here from the twenty
// centres: each pixel takes a soft blend of the agents whose discs it is in.
// Brightness comes from the curtain, hue comes from here.
//   u_ag[i] = (cx, cy, r, hue)   from ajan_merkez via ajan_A
// =============================================================================
uniform vec2  u_half;    // world half-extent visible at z = 0 (from cam1)
uniform float u_mix;     // 0 = curtain untouched, 1 = fully coloured
uniform float u_sat;     // saturation of the agent hues
uniform float u_gain;    // brightness after tinting
uniform float u_soft;    // how far a colour bleeds past its disc (1 = disc edge)
uniform float u_debug;
uniform float u_hueKeep;
uniform float u_tone;     // 0 = off, 1 = tone curve on
uniform float u_white;    // luminance that still reaches white
uniform float u_toneGain; // level after the curve // 1 = hue-preserving compression (Q.24-Q.26), 0 = per-channel clip (white sparkle)   // 1 = draw the disc rims
uniform vec4  u_ag[20];  // Arrays page, from ajan_A (one sample per agent)
uniform vec4  u_agC[20]; // Arrays page, from ajan_C: (ang, pang, conv, pconv)
uniform float u_winner;  // drawn agent, -1 = none
uniform float u_fill;    // 0..1 the answer takes the board (same as the compute shader)
uniform float u_depth;   // 2026-11-11 DEPTH: agent layers z in +-u_depth (= glsl1 u_kDepth)
uniform float u_camD;    // camera distance to z = 0 (cam1 tz): perspective of the layers
uniform float u_fog;     // 2026-11-11 DEPTH: how much darker the farthest layer is (0 none, 1 black)
uniform float u_dens;    // 2026-11-11 DEPTH: undo the density glow (a far agent packs its particles into fewer pixels and shines MORE). luminance x persp^u_dens
uniform float u_front;   // 2026-11-11 DEPTH: where layers overlap, how strongly the nearer one owns the colour

out vec4 fragColor;

vec3 hsv2rgb(vec3 c){
    vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0/3.0, 1.0/3.0))*6.0 - 3.0);
    return c.z * mix(vec3(1.0), clamp(p-1.0, 0.0, 1.0), c.y);
}

void main(){
    vec2 uv  = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    vec2 p   = (uv*2.0 - 1.0) * u_half;

    vec3  acc  = vec3(0.0);
    float wsum = 1e-6;
    float rim  = 0.0;
    float zsum = 0.0;
    float psum = 0.0;
    for(int i = 0; i < 20; ++i){
        vec4  a = u_ag[i];
        float r = max(a.z, 0.5);
        vec2  c = a.xy;
        // 2026-11-05: colour follows ownership. A converted agent's material
        // belongs to the winner, so its own hue fades with its conversion; the
        // winner's colour moves with its basin to the middle of the board.
        int   win = int(floor(u_winner + 0.5));
        float own = 1.0;
        // DEPTH: the agent's layer, the same formula as glsl1_compute. A layer
        // nearer the camera projects bigger and further from the middle.
        float z = u_depth * (fract(float(i) * 0.6180339887 + 0.31) * 2.0 - 1.0);
        if(win >= 0 && win < 20 && i == win){
            float flz = clamp(u_fill, 0.0, 1.0); flz = flz*flz*(3.0 - 2.0*flz);
            z = mix(z, 0.0, flz);
        }
        float persp = u_camD / max(u_camD - z, 1.0);
        c *= persp;
        r *= persp;
        if(win >= 0 && win < 20){
            if(i == win){
                float fl = clamp(u_fill, 0.0, 1.0); fl = fl*fl*(3.0 - 2.0*fl);
                c = mix(c, vec2(0.0), fl);
                r = mix(r, length(u_half) * 1.3, fl);
            } else {
                own = 1.0 - smoothstep(0.3, 0.7, u_agC[i].z);
            }
        }
        float d = length(p - c) / (r * max(u_soft, 0.05));
        float w = exp(-3.0 * d * d) * own * pow(persp, u_front);   // nearer layer wins the overlap
        acc  += hsv2rgb(vec3(a.w, u_sat, 1.0)) * w;
        wsum += w;
        zsum += z * w;
        psum += persp * w;
        float dr = abs(length(p - c) - r);
        rim = max(rim, 1.0 - smoothstep(0.0, 0.35, dr));
    }
    vec3 tint = acc / wsum;
    // keep perceived brightness: a dark hue (blue) is lifted, a bright one (yellow) is not
    float tl  = max(dot(tint, vec3(0.299, 0.587, 0.114)), 0.25);
    float lum = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    // TONE (2026-11-05): overlapping particles reach luminance 30..1000 (measured),
    // so a gain cannot tame them. Extended Reinhard with a white point: sparse
    // particles stay as they are, dense piles roll off, only lum > u_white goes white.
    if(u_tone > 0.0){
        float W  = max(u_white, 1.0);
        float lt = lum * (1.0 + lum / (W * W)) / (1.0 + lum);
        lum = mix(lum, lt * u_toneGain, clamp(u_tone, 0.0, 1.0));
    }
    vec3 col  = lum * tint / tl * u_gain;
    // DEPTH FOG (2026-11-11): the pixel's depth = the weighted layer of the
    // agents painting it; the farther back, the darker. After the curtain, so
    // the feedback loop cannot level it away (in the particles it vanished).
    if(u_depth > 0.0){
        // measured 2026-11-11: back agents read 1.6x brighter in the render and
        // 2.5x after the curtain (inverse depth). Scale by the pixel's own
        // perspective so near = brighter, far = dimmer.
        col *= pow(max(psum / wsum, 0.05), u_dens);
    }
    if(u_depth > 0.0 && u_fog > 0.0){
        float zp   = zsum / wsum;
        float back = clamp((u_depth - zp) / (2.0 * u_depth), 0.0, 1.0);
        col *= 1.0 - clamp(u_fog, 0.0, 1.0) * back;
    }
    // keep the HUE when it is bright: if any channel passes 1, scale all three
    // together instead of letting each clip on its own (that washed to white)
    float mx  = max(col.r, max(col.g, col.b));
    if(mx > 1.0) col = mix(col, col / mx, clamp(u_hueKeep, 0.0, 1.0));   // 0 = white sparkle, 1 = hue kept   // 0 = channels clip on their own -> white sparkle (the look of 26 Oct, user's reference S_toprak.png)

    vec3 outc = mix(src.rgb, col, clamp(u_mix, 0.0, 1.0));
    outc += u_debug * rim * vec3(0.6);
    fragColor = TDOutputSwizzle(vec4(outc, src.a));
}
