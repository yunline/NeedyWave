#version 460
uniform sampler2D wave_tex;
uniform sampler2D bg_tex;

uniform float u_min;
uniform float u_max;
uniform float v_min;
uniform float v_max;

in vec2 uv;
out vec4 fragColor;

vec4 amp_to_color(float amp) {
    float intensity = amp*amp;
    const vec4 BRIGGT = vec4(1.0, 1.0, 1.0, 1.0);
    const vec4 MID = vec4(0.6, 0.6, 0.2, 1.0);
    const vec4 DARK = vec4(0.0, 0.0, 0.0, 1.0);
    if (intensity <= 0.0) {
        return DARK;  // 黑色
    } else if (intensity >= 1.0) {
        return BRIGGT;  // 白色
    } else if (intensity == 0.5) {
        return MID;  // 自定义颜色
    } else if (intensity < 0.5) {
        // 在0到0.5之间线性插值(黑色到自定义颜色)
        return mix(DARK, MID, intensity * 2.0);
    } else {
        // 在0.5到1之间线性插值(自定义颜色到白色)
        return mix(MID, BRIGGT, (intensity - 0.5) * 2.0);
    }
}

vec4 amp_to_color2(float amp) {
    const vec4 RED = vec4(1.0, 0.0, 0.0, 1.0);
    const vec4 GREEN = vec4(0.0, 1.0, 0.0, 1.0);
    if (amp>=0.0) {
        return amp * RED;
    }
    else {
        return -amp * GREEN;
    }
}

void main() {
    // 判断当前uv是否在内容区域内
    if (uv.x < u_min || uv.x > u_max || uv.y < v_min || uv.y > v_max) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0); // 黑边
        return;
    }

    // 将内容区域的uv映射到[0,1]，保证内容不被拉伸
    vec2 content_uv;
    content_uv.x = (uv.x - u_min) / (u_max - u_min);
    content_uv.y = (uv.y - v_min) / (v_max - v_min);

    float amplitude = texture(wave_tex, content_uv).r;
    float bg = texture(bg_tex, content_uv).r;
    fragColor = max(amp_to_color2(amplitude), bg * vec4(0.0, 0.1, 0.2, 1.0));
}
