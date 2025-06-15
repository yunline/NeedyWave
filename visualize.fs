#version 460
uniform sampler2D waveTexture;
uniform sampler2D bgTexture;
uniform float texAspect;  // 纹理宽高比 (width/height)
uniform float screenAspect; // 屏幕宽高比 (width/height)


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
    // 计算正确的UV坐标，保持比例
    vec2 scaledUV = uv;
    
    if (screenAspect > texAspect) {
        // 屏幕比纹理更宽 - 在水平方向缩放
        scaledUV.x = (uv.x - 0.5) * (texAspect / screenAspect) + 0.5;
    } else {
        // 屏幕比纹理更高 - 在垂直方向缩放
        scaledUV.y = (uv.y - 0.5) * (screenAspect / texAspect) + 0.5;
    }

    float amplitude = texture(waveTexture, scaledUV).r;

    float bg = texture(bgTexture, scaledUV).r;

    fragColor = max(amp_to_color2(amplitude), bg * vec4(0.0, 0.1, 0.2, 1.0));
}
