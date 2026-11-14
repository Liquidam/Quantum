// CONTROL knob face. One shader, shared by every knob.
// uVal 0..1 = the knob's position along its 270 degree sweep.
uniform float uVal;
uniform vec3  uAcc;     // accent colour of the lit arc
out vec4 fragColor;

void main(){
    vec2  p = vUV.st * 2.0 - 1.0;
    float r = length(p);
    float a = atan(p.x, p.y);                 // 0 at the top, + to the right
    float s = radians(135.0);                 // sweep -135 .. +135 degrees
    float t = (a + s) / (2.0 * s);            // 0..1 along the sweep
    float aa = 2.5 / 220.0;                   // anti-alias width

    // inner disc
    float disc = 1.0 - smoothstep(0.60 - aa, 0.60 + aa, r);
    vec3  col  = vec3(0.145, 0.155, 0.175) * disc;
    float al   = disc;

    // ring: grey track, accent up to the value
    float ring = smoothstep(0.68 - aa, 0.68 + aa, r) * (1.0 - smoothstep(0.82 - aa, 0.82 + aa, r));
    float inSw = step(-s, a) * step(a, s);
    vec3  rc   = (t <= uVal) ? uAcc : vec3(0.23, 0.24, 0.27);
    col = mix(col, rc, ring * inSw);
    al  = max(al, ring * inSw);

    // pointer
    float pa = -s + uVal * 2.0 * s;
    vec2  dp = vec2(sin(pa), cos(pa));
    float ln = abs(dot(p, vec2(dp.y, -dp.x)));               // distance to the pointer line
    float al2 = dot(p, dp);
    float ptr = (1.0 - smoothstep(0.022, 0.022 + aa, ln)) * step(0.44, al2) * step(al2, 0.585);
    col = mix(col, vec3(0.95), ptr);
    al  = max(al, ptr);

    fragColor = TDOutputSwizzle(vec4(col, al));
}
