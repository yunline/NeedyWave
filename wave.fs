#version 460
uniform sampler2D currentWave;
uniform sampler2D previousWave;
uniform sampler2D waveSpeed;
uniform sampler2D sideDamp;
uniform sampler2D waveSource1Mask;
uniform float waveSource1Amplitude;
uniform float C;

uniform float coeff; // coeff = (DT/DX)**2
uniform vec2 texelSize;

in vec2 uv;
out vec4 fragColor;

void main() {
    // 2D wave equation: u(t+1) = (c*dt/dx)^2 * ∇²u(t) + 2u(t) - u(t-1) - side_damp * (u(t) - u(t-1))
    float center = texture(currentWave, uv).r;
    float left = texture(currentWave, uv - vec2(texelSize.x, 0.0)).r;
    float right = texture(currentWave, uv + vec2(texelSize.x, 0.0)).r;
    float top = texture(currentWave, uv + vec2(0.0, texelSize.y)).r;
    float bottom = texture(currentWave, uv - vec2(0.0, texelSize.y)).r;

    float c = C*texture(waveSpeed, uv).r;
    float side_damp = texture(sideDamp, uv).r;
    
    float laplacian = (left + right + top + bottom - 4.0 * center);
    float previous = texture(previousWave, uv).r;
    float next = c*c*coeff * laplacian + 2.0 * center - previous - side_damp * (center - previous);

    float is_on_source1 = texture(waveSource1Mask, uv).r;

    next = next*(1-is_on_source1) + waveSource1Amplitude*is_on_source1;
    
    fragColor = vec4(next, 0.0, 0.0, 1.0);
}
