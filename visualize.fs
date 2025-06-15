#version 460
uniform sampler2D wave_tex;
uniform sampler2D bg_tex;

uniform float u_min;
uniform float u_max;
uniform float v_min;
uniform float v_max;

in vec2 uv;
out vec4 fragColor;

vec4 wave_view(vec2 content_uv) {
    // 采样幅值
    float amp = texture(wave_tex, content_uv).r;

    // 将幅值转为颜色
    const vec4 POS_COLOR = vec4(1.0, 0.0, 0.0, 1.0);
    const vec4 NEG_COLOR = vec4(0.0, 1.0, 0.0, 1.0);
    if (amp>=0.0) {
        return amp * POS_COLOR;
    }
    else {
        return -amp * NEG_COLOR;
    }
}

vec4 intensity_view(vec2 content_uv) {
    vec2 texel = vec2(1.0/textureSize(wave_tex, 0).x, 1.0/textureSize(wave_tex, 0).y);
    float sum_intensity = 0.0;
    int count = 0;
    // 采样5x5范围内平均光强
    for(int j=-2;j<=2;++j){
        for(int i=-2;i<=2;++i){
            vec2 offset = vec2(float(i), float(j)) * texel;
            float amp = texture(wave_tex, content_uv + offset).r;
            sum_intensity += amp * amp;
            count++;
        }
    }
    float intensity = sum_intensity / float(count);

    // 定义颜色
    const vec4 BRIGGT = vec4(1.0, 1.0, 1.0, 1.0);
    const vec4 MID = vec4(0.6, 0.55, 0.2, 1.0);
    const vec4 DARK = vec4(0.0, 0.0, 0.0, 1.0);

    // 将光强转为颜色
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

    // 采样波形
    vec4 wave_color = intensity_view(content_uv);
    // 采样背景
    vec4 bg_color = texture(bg_tex, content_uv).r * vec4(0.0, 0.1, 0.2, 1.0);
    // 混合输出
    fragColor = max(wave_color, bg_color);
}
