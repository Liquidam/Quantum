// =============================================================================
// SADA FIELD - agents in a quantum interference field (particle compute shader)
// Goktug Kahyaoglu, 2025-2026. Written for Sada AlQuantum - AGENTS.
//
// WHAT THIS SHADER DOES (one frame, one thread per particle)
//   1. Reads the particle state (P, V, Rot, PointScale, Color, Agent) from the
//      feedback loop (feedback2).
//   2. Lets each particle feel the other 1023 particles of its workgroup with a
//      soft SPH kernel (no pressure term). sort1 re-orders the array by `key`
//      every frame, so a workgroup is a band of the field: THE KEY IS THE SHAPE.
//   3. AGENTS: each particle belongs to a home agent (attribute Agent). The
//      agent's basin pulls it home from outside (capped, never a cage); each
//      agent runs its own variant of the field (angle, frequency, time rate,
//      routing, speed). In the answer the winner takes over and fills the board.
//   4. QUANTUM FIELD: |Psi(p)|^2 of an n-qubit state (Qiskit amplitudes) is the
//      sort key. Every qubit is a direction; a basis state is a plane wave.
//   5. Integrates (speed ceiling), scrubs NaN/Inf, writes the attributes.
//
// LAWS (break them and the field breaks)
//   - Shape lives in the key; particles are never placed, only nudged.
//   - The key must be >= 0 and continuous (no floor/step on the key).
//   - Never bypass the speed ceiling.
//   - Rot is a direction: never write a zero vector (= invisible particle).
//   - Grey only in Color: the curtain (comp1 loop) takes ONE colour.
//     Colour per agent is added after it, in ajan_renk.
// =============================================================================

layout(local_size_x = 1024) in;

shared vec4 community[1024];

const float TAU = 6.28318530718;
const float PI  = 3.14159265359;

const int MAXQ = 8;      // most qubits the field can hold
const int MAXK = 256;    // 2^MAXQ basis states

// ---- particle engine ----------------------------------------------------------
uniform float u_sphRadius;   // SPH reach (world units)
uniform float u_repel;       // pair repulsion
uniform float u_attract;     // pair attraction
uniform float u_time;        // seconds
uniform float u_velMemory;   // share of last frame's velocity kept (0 = none)
uniform float u_flowAmp;     // ambient flow strength (0 = still air)
uniform float u_flowScale;   // ambient flow spatial frequency
uniform float u_speedMax;    // speed ceiling, world units per frame
uniform float u_centerPull;  // pull toward the middle (0 = off)
uniform vec3  u_world;       // half-size of the world box
uniform int   u_scene;       // 0 = quantum field, anything else = free dust
uniform float u_morph;       // 1 = field, 0 = flat key, < -0.5 = rebirth pulse

// ---- quantum field --------------------------------------------------------------
uniform float u_nq;          // number of qubits
uniform float u_fieldScale;  // world units -> field units
uniform float u_dirSpread;   // radians between successive qubit directions
uniform float u_kScale;      // spatial frequency (fringe density)
uniform float u_evolve;      // time evolution rate (x number of excited qubits)
uniform float u_keyGain;     // |Psi|^2 -> sort key
uniform float u_forceGain;   // drift up the brightness gradient (0 = off)
uniform float u_signal;      // external drive 0..1, opens the speed ceiling

// ---- agents -----------------------------------------------------------------------
uniform float u_kume;        // 1 = agents on, 0 = one shared field
uniform float u_winner;      // drawn agent, -1 = none
uniform float u_kFill;       // 0..1 the answer fills the board (follows collapse)
uniform float u_kFillPush;   // strength of that inflating push
uniform float u_kBind;       // pull home per world unit outside the basin
uniform float u_kBindCap;    // ceiling of that pull (stays below the SPH scale)
uniform float u_kSoft;       // the pull starts at this fraction of the radius
uniform float u_kLobe;       // living basin: lobes on the rim (0 = round)
uniform float u_kVary;       // 0..1 how far each agent's own system departs
uniform float u_kSwirlGain;  // gain on each agent's own weather
uniform float u_kFollow;     // particles feel their body's velocity (swimming)
uniform float u_kRadMul;     // basin radius / contact radius
uniform float u_kRef;        // basin radius of a territory (A) - reference scale
uniform float u_kMini;       // 0..1 a smaller basin carries a smaller texture
uniform float u_kDepth;      // each agent on its own layer, z in +-u_kDepth
uniform float u_kFog;        // farthest layer this much darker (0 = none)
uniform float u_board;       // A-BOARD VIEW (9 Sept): N > 1 colours the pool by the
                             // territory each particle stands in (kume off only). 0 = off

// ---- routing (the 11 Sept board) ------------------------------------------------
// The traces are not drawn: they are level sets of the same field, sampled
// through a piecewise-constant warp of the plane. floor() touches the WARP only,
// never the key, so the key stays continuous.
uniform float u_chipMode;    // 0 off, 1 jog, 2 weave, 3 jog+weave, 4 route
uniform float u_chipN;       // routing cells per field unit
uniform float u_chipAmp;     // jog offset, field units
uniform float u_chipSeed;    // routing seed when agents are off
uniform float u_chipBlend;   // 0 = smooth field, 1 = fully routed

// Arrays page (auto-declared by TD - never declare them here):
//   u_qre[k], u_qim[k]   amplitudes of |k>, k = 0 .. 2^nq - 1     (qsim)
//   u_kA[20]  (cx, cy, r, hue)            this frame               (ajan_A)
//   u_kB[20]  (cx, cy, r, pitch)          previous frame           (ajan_B)
//   u_kC[20]  (ang, pang, conv, alias)                             (ajan_C)


// =============================================================================
// HELPERS
// =============================================================================

// Integer hash -> [0,1]. Deterministic per number: a particle's permanent traits.
float rand1(uint n){
    n = (n << 13U) ^ n;
    n = n * (n * n * 15731U + 789221U) + 1376312589U;
    return float(n & uint(0x7fffffffU)) / float(0x7fffffff);
}
vec3 rand3(uint n){ return vec3(rand1(n), rand1(n*1664525u+1013904223u), rand1(n*22695477u+1u)); }

// Three-octave simplex sum.
float octaves(vec3 p){
    float v = 0.0, a = 0.5;
    for(int i = 0; i < 3; i++){ v += a*TDSimplexNoise(p); p *= 2.0; a *= 0.5; }
    return v;
}

// One SPH neighbour: smooth cubic kernel, attraction minus repulsion.
void sphPair(vec3 other, vec3 pos, float invH2, float h2,
             float attr, float rep, float pwr, inout vec3 force){
    vec3  d  = other - pos;
    float d2 = dot(d, d);
    if(d2 < h2 && d2 > 1e-9){
        float w = 1.0 - d2*invH2; w = w*w*w;
        force += normalize(d) * ((attr - rep) * w * pwr);
    }
}

// What makes one agent's board LOOK different: routing pitch and degree of
// crystallisation read across a room; a routing seed alone does not.
void agentBoard(int a, out float seed, out float pitch, out float cryst){
    float h1 = rand1(uint(a) * 2654435761u + 11u);
    float h2 = rand1(uint(a) * 2246822519u + 27u);
    seed  = 1.0 + float(a) * 7.0;
    pitch = mix(0.42, 2.20, h1);   // coarse .. fine
    cryst = mix(0.22, 1.00, h2);   // flowing .. hard
}


// ---- A-board view (9 Sept 2026) -------------------------------------------------
// The pool split into a grid of territories over the world box (5 x 4 for 20),
// columns chosen from the box's aspect so no territory is a thin strip.
int boardCols(int NA, vec2 hbox){
    float asp = max(hbox.x, 1e-3) / max(hbox.y, 1e-3);
    int c = int(floor(sqrt(float(NA) * asp) + 0.5));
    return max(1, min(c, NA));
}

int territoryAt(vec2 xy, int NA, vec2 hbox){
    int cols = boardCols(NA, hbox);
    int rows = (NA + cols - 1) / cols;
    vec2 t = clamp(xy / (2.0*hbox) + 0.5, vec2(0.0), vec2(0.99999));
    int a = int(t.y * float(rows)) * cols + int(t.x * float(cols));
    return min(a, NA - 1);
}

vec3 hsv2rgb(vec3 c){
    vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0/3.0, 1.0/3.0))*6.0 - 3.0);
    return c.z * mix(vec3(1.0), clamp(p-1.0, 0.0, 1.0), c.y);
}

// one family, cyan -> violet; neighbours never share a brightness
vec3 territoryColor(int a, int NA){
    float t   = float(a) / max(float(NA-1), 1.0);
    float hue = mix(0.46, 0.84, t);
    float sat = mix(0.90, 0.60, t);
    float val = mix(0.62, 1.0, fract(float(a) * 0.6180339887));
    return hsv2rgb(vec3(hue, sat, val));
}

// blended across borders: the four nearest territory centres, interpolated
vec3 territoryColorSmooth(vec2 xy, int NA, vec2 hbox){
    int cols = boardCols(NA, hbox);
    int rows = (NA + cols - 1) / cols;
    vec2 tg = clamp(xy / (2.0*hbox) + 0.5, vec2(0.0), vec2(0.99999))
              * vec2(float(cols), float(rows));
    vec2 f  = tg - 0.5;
    vec2 i0 = floor(f);
    vec2 fr = smoothstep(vec2(0.0), vec2(1.0), f - i0);
    vec3 c  = vec3(0.0);
    for(int dy=0; dy<2; ++dy){
        for(int dx=0; dx<2; ++dx){
            vec2 cc = clamp(i0 + vec2(float(dx), float(dy)),
                            vec2(0.0), vec2(float(cols-1), float(rows-1)));
            int a = min(int(cc.y)*cols + int(cc.x), NA-1);
            float w = (dx==0 ? 1.0-fr.x : fr.x) * (dy==0 ? 1.0-fr.y : fr.y);
            c += territoryColor(a, NA) * w;
        }
    }
    return c;
}

// =============================================================================
// MAIN
// =============================================================================
void main(){
    const uint WG  = gl_WorkGroupSize.x;
    uint lid       = gl_LocalInvocationIndex;
    uint groupBase = gl_WorkGroupID.x * WG;
    uint total     = TDInputNumPoints(0);
    uint id        = groupBase + lid;
    bool isLive    = (id < total);

    // ---- read state -------------------------------------------------------------
    vec3  pos   = vec3(0.0);
    vec3  vel   = vec3(0.0);
    vec3  rot   = vec3(0.0);
    vec4  color = vec4(1.0);
    float size  = 0.0;

    if(isLive){
        pos   = TDIn_P(0,id);
        vel   = TDIn_V(0,id);
        color = TDIn_Color(0,id);
        rot   = TDIn_Rot(0,id);
        size  = TDIn_PointScale(0,id);
    }

    // share positions with the community (the workgroup)
    community[lid] = isLive ? vec4(pos,1.0) : vec4(1e9,1e9,1e9,0.0);
    barrier();
    if(!isLive) return;

    // =========================================================================
    // AGENT OF THIS PARTICLE
    // Agent.x = home agent (never rewritten), Agent.y = own seed (sprite size).
    // =========================================================================
    vec2 agIn = Agent[id];
    if(agIn.x < -0.5)      // first frame: split the pool into 20 by index
        agIn = vec2(floor(float(id) * 20.0 / float(max(total, 1u))), rand1(id * 7919u + 17u));
    int home = clamp(int(agIn.x + 0.5), 0, 19);
    // an agent off stage hands its particles to its alias (u_kC.w); Agent is
    // untouched, so when it returns its own material comes back
    if(u_kume > 0.5){ int al = int(u_kC[home].w + 0.5); if(al >= 0 && al < 20) home = al; }

    bool  agentsOn = (u_kume > 0.5);
    int   win      = int(floor(u_winner + 0.5));
    bool  hasWin   = (win >= 0 && win < 20);
    int   owner    = home;
    vec2  bC = vec2(0.0), bVel = vec2(0.0);     // basin centre, basin velocity
    float bR = 1.0, bAng = 0.0, bZ = 0.0;       // basin radius, field angle, layer
    // the agent's own particle system (1.0 = the shared engine)
    float attrMul = 1.0, speedMul = 1.0, evolveMul = 1.0, swirl = 0.0, freqMul = 1.0;
    float scaleR  = 1.0;                        // texture scale follows the basin

    if(agentsOn){
        // TAKEOVER: past half-way through the wave a particle answers to the winner
        if(hasWin && u_kC[home].z > 0.5) owner = win;
        vec4 A = u_kA[owner], B = u_kB[owner];
        bC   = A.xy;
        bR   = max(A.z * u_kRadMul, 0.5);
        bVel = A.xy - B.xy;
        uint  ou = uint(owner);
        float v  = clamp(u_kVary, 0.0, 1.0);
        bAng      = u_kC[owner].x + v * rand1(ou * 3266489917u + 5u) * PI;
        attrMul   = mix(1.0, mix(0.93, 1.05, rand1(ou * 668265263u + 1u)), v);
        speedMul  = mix(1.0, mix(0.55, 1.45, rand1(ou * 374761393u + 2u)), v);
        evolveMul = mix(1.0, mix(0.35, 2.40, rand1(ou * 2246822519u + 3u)), v);
        swirl     = v * mix(0.0, 0.04, rand1(ou * 3266489917u + 4u)) * max(u_kSwirlGain, 0.0);
        freqMul   = mix(1.0, mix(0.75, 1.45, rand1(ou * 2654435761u + 6u)), v);
        // shrink only: the winner's world propagates at the same fineness
        scaleR    = mix(1.0, min(bR / max(u_kRef, 1e-3), 1.0), clamp(u_kMini, 0.0, 1.0));
        // THE ANSWER FILLS THE BOARD: the winner's basin slides to the middle
        // and grows past the corners. Only the basin moves.
        if(hasWin && owner == win && u_kFill > 0.0){
            float fl = clamp(u_kFill, 0.0, 1.0); fl = fl*fl*(3.0 - 2.0*fl);
            bC = mix(bC, vec2(0.0), fl);
            bR = mix(bR, length(u_world.xy) / max(u_kSoft, 0.1), fl);
        }
        // DEPTH: own layer (same formula in ajan_renk_pixel); the answering
        // winner comes to the middle layer
        bZ = u_kDepth * (fract(float(owner) * 0.6180339887 + 0.31) * 2.0 - 1.0);
        if(hasWin && owner == win && u_kFill > 0.0){
            float flz = clamp(u_kFill, 0.0, 1.0);
            bZ = mix(bZ, 0.0, flz * flz * (3.0 - 2.0 * flz));
        }
    }

    float time  = u_time;
    vec3  world = u_world;

    // ---- A-BOARD VIEW: colour by the territory the particle stands in -------
    int   NB      = int(u_board + 0.5);
    bool  boardOn = (NB > 1);
    vec2  boxHalf = max(u_world.xy, vec2(0.001));
    int   aid     = boardOn ? territoryAt(pos.xy, NB, boxHalf) : 0;
    float conv    = 0.0;                    // 1 = this territory is the winner's
    if(boardOn && win >= 0 && win < NB && aid == win) conv = 1.0;
    vec3  boardCol = vec3(1.0);
    if(boardOn){
        // colour arrives with the shape: one colour at u_chipBlend 0
        boardCol = mix(vec3(1.0), territoryColorSmooth(pos.xy, NB, boxHalf),
                       clamp(u_chipBlend, 0.0, 1.0));
        if(win >= 0 && win < NB) boardCol = mix(boardCol, territoryColor(win, NB), conv);
    }

    // the routing this particle is sampled through
    float rtSeed  = u_chipSeed;
    float rtPitch = u_chipN;
    float rtCryst = u_chipBlend;
    if(agentsOn){
        float agS, agP, agC;
        agentBoard(owner, agS, agP, agC);
        rtSeed  = agS;
        // routing cells keep the TERRITORY's size even when the texture shrinks
        rtPitch = u_chipN * agP * scaleR;
        rtCryst = u_chipBlend * agC;
    }

    vec3  force = vec3(0.0);
    float shapeKey = 0.0;

    // =========================================================================
    // COMMUNITY FORCES (SPH)
    // =========================================================================
    float jH    = 1.0 + 0.002*(rand1(id*911u)-0.5);              // radius jitter
    // SPH reach follows the basin: same fluid, at the body's own scale
    float h     = u_sphRadius*jH*scaleR; float h2=h*h; float invH2=1.0/h2;
    float power = TDSimplexNoise(vec3(float(id)*0.0007)) + 1.0;  // temperament 0..2
    uint  valid = (total>groupBase) ? min(WG,total-groupBase) : 0u;

    float sig  = clamp(u_signal, 0.0, 1.0);
    float attr = u_attract * (1.0 + sig * 3.5) * attrMul;
    float rep  = u_repel;

    for(uint i=0u; i<valid; ++i){
        if(i==lid) continue;
        sphPair(community[i].xyz, pos, invH2, h2, attr, rep, power, force);
    }

    if(u_centerPull > 0.0){
        vec3 d=-pos; float L=length(d);
        if(L>1e-6) force += (d/L)*(u_centerPull*L);
    }

    // =========================================================================
    // BASIN: free inside, a capped pull home outside, ADDED to the SPH force
    // =========================================================================
    if(agentsOn){
        vec2  d  = pos.xy - bC;
        float L  = length(d);
        float st = bR * clamp(u_kSoft, 0.0, 1.0);
        // living rim: slow turning lobes, each agent its own rhythm
        if(u_kLobe > 0.0 && L > 1e-6){
            uint  ouL = uint(owner);
            float th  = atan(d.y, d.x);
            float wL  = mix(0.15, 0.45, rand1(ouL * 2654435761u + 11u));
            float pL  = rand1(ouL * 97u + 13u) * TAU;
            float lob = 0.6 * sin(3.0 * th + time * wL + pL)
                      + 0.4 * sin(5.0 * th - time * wL * 1.3 + 2.0 * pL);
            st *= 1.0 + u_kLobe * lob;
        }
        if(L > st && L > 1e-6)
            force.xy -= (d / L) * min((L - st) * u_kBind, u_kBindCap);
        // swim with the body - except the answering winner, whose centre is
        // travelling to the middle
        float fw = (hasWin && owner == win) ? clamp(u_kFill, 0.0, 1.0) : 0.0;
        force.xy += bVel * u_kFollow * (1.0 - fw);
        // inflate: zero in the middle (no hole) and at the screen edge
        if(hasWin && owner == win && u_kFill > 0.0){
            vec2  q  = pos.xy / max(u_world.xy, vec2(0.001));
            float sq = max(abs(q.x), abs(q.y));
            float fl = clamp(u_kFill, 0.0, 1.0);
            if(length(pos.xy) > 1e-4)
                force.xy += normalize(pos.xy) * u_kFillPush * fl * smoothstep(0.0, 0.45, sq) * max(0.0, 1.0 - sq);
        }
        if(swirl > 0.0){                            // the agent's own weather
            float n = octaves(vec3(pos.xy * 0.07, time * 0.12 + float(owner) * 3.1));
            force.xy += swirl * vec2(sin(n * TAU), cos(n * TAU));
        }
    }

    // =========================================================================
    // QUANTUM INTERFERENCE FIELD -> key
    // =========================================================================
    if(u_scene == 0){
        int NQ = int(u_nq + 0.5);
        int K  = 1 << NQ;

        vec2 p = pos.xy * u_fieldScale;
        float ca = cos(bAng), sa = sin(bAng);
        if(agentsOn){
            // the field is anchored to the body: own centre, angle, frequency
            vec2 l = pos.xy - bC;
            p = vec2(ca*l.x + sa*l.y, -sa*l.x + ca*l.y) * u_fieldScale * freqMul / scaleR;
        }

        // ---- routing warp ------------------------------------------------------
        int cmode = int(u_chipMode + 0.5);
        if(cmode > 0 && rtCryst > 1e-4){
            vec2  p0   = p;
            float N    = max(rtPitch, 1e-3);
            vec2  cell = floor(p * N);

            if(cmode == 2 || cmode == 3){
                // WEAVE: quarter-turn every other cell
                if(mod(cell.x + cell.y, 2.0) > 0.5){
                    vec2 c = (cell + 0.5) / N;
                    vec2 l = p - c;
                    p = c + vec2(-l.y, l.x);
                }
            }
            if(cmode == 4){
                // ROUTE: each cell's quarter-turn drawn from the cell and the seed
                float hc = fract(sin(dot(cell + vec2(rtSeed, rtSeed * 1.7),
                                         vec2(127.1, 311.7))) * 43758.5453);
                int   turn = int(hc * 4.0);
                vec2  c = (cell + 0.5) / N;
                vec2  l = p - c;
                if     (turn == 1) l = vec2(-l.y,  l.x);
                else if(turn == 2) l = -l;
                else if(turn == 3) l = vec2( l.y, -l.x);
                p = c + l;
            }
            if(cmode == 1 || cmode == 3){
                // JOG: staircase offset by row / column
                p += u_chipAmp * vec2(cell.y, cell.x) / N;
            }
            // CRYSTALLISATION by degree: 0 = smooth field, 1 = routed board
            p = mix(p0, p, clamp(rtCryst, 0.0, 1.0));
        }

        // per-qubit spatial phase and its gradient
        float thj[MAXQ];
        vec2  gdj[MAXQ];
        for(int j=0;j<MAXQ;++j){
            float a = float(j) * u_dirSpread;
            vec2  d = vec2(cos(a), sin(a)) * u_kScale;
            thj[j]  = dot(p, d);
            gdj[j]  = d * u_fieldScale;
        }

        // time phase, wrapped so float32 sin/cos stay precise for hours
        float tphase = mod(u_evolve * evolveMul * time, TAU);

        vec2 psi = vec2(0.0);   // (re, im)
        vec2 dPx = vec2(0.0);   // d(psi)/dx
        vec2 dPy = vec2(0.0);   // d(psi)/dy

        for(int k=0;k<MAXK;++k){
            if(k >= K) break;

            float ph = 0.0;
            vec2  gd = vec2(0.0);
            int   hw = 0;               // excited qubits in |k>
            for(int j=0;j<MAXQ;++j){
                if(j >= NQ) break;
                if(((k >> j) & 1) == 1){ ph += thj[j]; gd += gdj[j]; hw += 1; }
            }
            // number operator: phase turns with the number of excited qubits
            ph += float(hw) * tphase;

            float re = u_qre[k];
            float im = u_qim[k];
            float c  = cos(ph), s = sin(ph);

            vec2 w = vec2(re*c - im*s, re*s + im*c);   // amplitude * exp(i ph)
            psi += w;

            vec2 iw = vec2(-w.y, w.x);                 // i * w
            dPx += iw * gd.x;
            dPy += iw * gd.y;
        }

        float I = dot(psi, psi);    // |Psi|^2
        shapeKey = I * u_keyGain;   // order is all the sort uses

        // optional drift up the brightness gradient: grad|Psi|^2 = 2 Re(conj(Psi) dPsi)
        if(u_forceGain > 0.0){
            vec2 g = 2.0 * vec2(psi.x*dPx.x + psi.y*dPx.y,
                                psi.x*dPy.x + psi.y*dPy.y);
            if(agentsOn) g = vec2(ca*g.x - sa*g.y, sa*g.x + ca*g.y) * freqMul / scaleR;
            float gl = length(g);
            if(gl > 1e-6) force.xy += (g/gl) * min(gl, 4.0) * u_forceGain;
        }

        if(!agentsOn) force.z -= pos.z * 0.002;   // stay in the slab
    }
    // u_scene != 0: key stays 0 -> one bucket -> free dust

    shapeKey *= u_morph;

    // =========================================================================
    // INTEGRATION
    // =========================================================================
    float fS = max(u_flowScale, 0.12);    // flow varies over space, never a uniform gale
    float n0 = octaves(pos*(fS*0.5) + vec3(0,0,time*0.2));
    float n1 = octaves(pos*(fS*0.8) + vec3(time*0.1,0,0));
    force += vec3(sin(n0*TAU+0.5*time), sin(n0*TAU-0.3*time), cos(n0*TAU+0.2*time)) * u_flowAmp;
    force += vec3(sin(n1*TAU), n1, cos(n1*TAU+time*0.4)) * (u_flowAmp*0.5);

    vel = u_velMemory*vel + force;
    if(agentsOn) vel.z = 0.0;             // an agent is a sheet on its own layer

    // speed ceiling: the signal grants permission to move (silence = 7 %);
    // a miniature body gets a miniature ceiling
    float vLen   = length(vel);
    float vMax   = u_speedMax * mix(0.07, 1.0, clamp(sig + 0.06, 0.0, 1.0)) * speedMul * scaleR;
    if(vLen > vMax) vel *= vMax/vLen;

    pos += vel;
    pos += (rand3(id)-0.5)*2.0e-4;
    // glide to the owner's layer (material changing owner travels through depth)
    if(agentsOn) pos.z += clamp(bZ - pos.z, -0.12, 0.12);

    if(agentsOn) pos.xy = clamp(pos.xy, -world.xy, world.xy);   // a basin must not wrap
    else         pos.xy = mod(pos.xy+world.xy, 2.0*world.xy) - world.xy;
    pos.z  = mod(pos.z +world.z,  2.0*world.z ) - world.z;

    // ---- rotation ---------------------------------------------------------------
    float vLen2 = length(vel);
    float nrot  = TDSimplexNoise(pos*0.1);
    rot.x += nrot * 15.0;
    rot.y += nrot * 120.0 * vLen2;

    // ---- NaN guard: one NaN would spread through its community ---------------
    if(u_morph < -0.5 ||                    // REBIRTH PULSE: u_morph = -1 for a frame
       any(isnan(pos)) || any(isinf(pos)) ||
       any(isnan(vel)) || any(isinf(vel))){
        pos = (rand3(id) - 0.5) * 2.0 * u_world;
        vel = vec3(0.0);
    }
    if(isnan(shapeKey) || isinf(shapeKey)) shapeKey = 0.0;
    if(any(isnan(rot)) || any(isinf(rot)) || dot(rot,rot) < 1e-8)
        rot = normalize(rand3(id*13u) - 0.5 + vec3(1e-4));

    if(size < 1e-5) size = mix(0.004, 0.08, rand3(id*11u).y);

    // ---- write ----------------------------------------------------------------------
    P[id]          = pos;
    V[id]          = vel;
    Rot[id]        = rot;
    PointScale[id] = agentsOn ? mix(0.004, 0.08, agIn.y) * scaleR : size;
    Agent[id]      = agIn;
    key[id]        = shapeKey;
    vec3 outCol = boardOn ? boardCol : color.rgb;
    // DEPTH FOG: the farther back, the darker (grey only)
    if(agentsOn){
        float back = clamp((u_kDepth - pos.z) / max(2.0 * u_kDepth, 1e-3), 0.0, 1.0);
        outCol = vec3(1.0 - clamp(u_kFog, 0.0, 1.0) * back);
    }
    Color[id]      = vec4(outCol, 1.0);
}
