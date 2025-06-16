import moderngl
import numpy as np
import glfw # type:ignore
import cv2
import threading
import queue

class VideoWriter:
    def __init__(self, width, height, path, fps) -> None:
        self.width, self.height = width, height
        fourcc = cv2.VideoWriter_fourcc(*'XVID') # type:ignore
        self.out = cv2.VideoWriter(path, fourcc, fps, (width, height))
        self.frame_queue: queue.Queue[bytes|None] = queue.Queue(64)

        self.thread = threading.Thread(target = self.run, daemon=True)

    def run(self):
        try:
            while 1:
                pixels = self.frame_queue.get()
                if pixels is None:
                    return
                frame = np.frombuffer(pixels, dtype=np.uint8) \
                    .reshape((self.height, self.width, 3))
                frame_bgr_flipped = cv2.flip(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR), 0)
                self.out.write(frame_bgr_flipped)
        finally:
            self.out.release()

class WaveSimulation:
    def __init__(
        self, 
        terrain_path,
        width=1280, 
        height=720,
        render_intensity_view=True,
        save_video=False,
        video_path=None,
        video_fps=60,
        wave_source_freq=10.0,
        wave_source_amp=2.0,
    ):
        self.render_intensity_view = render_intensity_view
        self.save_video = save_video
        self.window_size = (width, height)
        self.wave_source_freq = wave_source_freq
        self.wave_source_amp =wave_source_amp

        # 初始化窗口
        if not glfw.init():
            raise RuntimeError("Could not initialize GLFW")
        
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 6)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.RESIZABLE, False)

        self.window = glfw.create_window(width, height, "2D Wave Simulation", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Could not create window")
        
        glfw.make_context_current(self.window)
        
        # 创建 ModernGL 上下文
        self.ctx = moderngl.create_context()
        
        # 乒乓缓冲指针
        self.current_texture = 0
        
        # 模拟参数
        self.DT = 0.01 # s
        self.DX = 1.0 # m/px
        self.C = 10.0 # m/s

        self.COEFF = (self.DT/self.DX)**2

        if self.COEFF*self.C**2>0.25:
            import warnings
            warnings.warn(f"CFL={self.COEFF*self.C**2}>0.25, simulation may be unstable")
        
        self.SIDE_DAMP_WIDTH = 50.0 # m
        self.SIDE_DAMP_MAX = 5.0

        self.t=0.0 # 时间积分

        # 如果需要保存视频，初始化视频保存器
        if self.save_video:
            if video_path is None:
                raise ValueError("--video_path not specified")
            self.video_writer = VideoWriter(width, height, video_path, video_fps)
        
        # 初始化纹理和着色器
        self.init_textures(terrain_path)
        self.init_shaders()
        self.init_quad()

        # 初始化窗口尺寸
        screen_aspect = width / height
        if screen_aspect > self.tex_aspect:
            content_width = self.tex_aspect / screen_aspect
            u_min = 0.5 - content_width / 2.0
            u_max = 0.5 + content_width / 2.0
            v_min = 0.0
            v_max = 1.0
        else:
            content_height = screen_aspect / self.tex_aspect
            v_min = 0.5 - content_height / 2.0
            v_max = 0.5 + content_height / 2.0
            u_min = 0.0
            u_max = 1.0
        self.content_uv = (u_min, u_max, v_min, v_max)

        # 设置回调
        glfw.set_key_callback(self.window, self.key_callback)

    def init_textures(self, terrain_path):
        terrain = cv2.imread(terrain_path)
        terrain = terrain[::-1, ::1] # flip y
        blue_channel, green_channel, red_channel = cv2.split(terrain)

        # 获取纹理尺寸
        self.tex_width = terrain.shape[1]
        self.tex_height = terrain.shape[0]

        # 计算纹理宽高比
        self.tex_aspect = self.tex_width / self.tex_height

        # 蓝色: 折射率，0x00为0倍光速，0xff为1倍光速
        # 绿色: 波源，0x00为0倍振幅，0xff为
        # 红色: 未使用此通道

        # 初始化振幅
        initial_data = np.zeros((self.tex_height, self.tex_width), dtype='f4')

        # 初始化折射率
        wave_speed_data = np.array(blue_channel, dtype='f4')/255.0

        # 初始化波源
        wave_source1 = np.array(green_channel, dtype='f4')/255.0

        # 初始化边角吸收
        side_damp = np.zeros((self.tex_height, self.tex_width), "f4")
        for x in range(self.tex_width):
            for y in range(self.tex_height):
                dist = min(x, self.tex_width-1 - x, y, self.tex_height-1 - y)
                if dist < (self.SIDE_DAMP_WIDTH/self.DX):
                    side_damp[y, x] = self.SIDE_DAMP_MAX * (1 - dist / (self.SIDE_DAMP_WIDTH/self.DX))**2
        del x,y
        side_damp *= self.DT
        
        # 创建两个纹理用于乒乓缓冲
        self.textures = [
            self.ctx.texture((self.tex_width, self.tex_height), 1, dtype='f4'),
            self.ctx.texture((self.tex_width, self.tex_height), 1, dtype='f4')
        ]

        self.wave_speed_tex = self.ctx.texture((self.tex_width, self.tex_height), 1, dtype='f4')
        self.side_damp_tex = self.ctx.texture((self.tex_width, self.tex_height), 1, dtype='f4')
        self.wave_source1_mask_tex = self.ctx.texture((self.tex_width, self.tex_height), 1, dtype='f4')
        
        # 设置纹理参数
        for tex in (
            *self.textures, 
            self.wave_speed_tex, 
            self.side_damp_tex, 
            self.wave_source1_mask_tex
        ):
            tex.repeat_x = False
            tex.repeat_y = False
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tex.swizzle = 'RRRR'  # 只使用红色通道
            
        # 写入初始数据
        self.textures[0].write(initial_data.tobytes())
        self.textures[1].write(initial_data.tobytes())
        self.wave_speed_tex.write(wave_speed_data.tobytes())
        self.side_damp_tex.write(side_damp.tobytes())
        self.wave_source1_mask_tex.write(wave_source1.tobytes())
        
        # 创建帧缓冲对象
        self.fbos = [
            self.ctx.framebuffer(self.textures[0]),
            self.ctx.framebuffer(self.textures[1])
        ]

        if self.save_video:
            self.fbo_video = self.ctx.framebuffer(
                self.ctx.renderbuffer(self.window_size)
            )
    
    def init_shaders(self) -> None:
        from jinja2 import Template

        # 加载着色器代码
        with open("vertex.vert", encoding="utf8") as shader_file:
            vertex_shader_code = shader_file.read()

        with open("wave.frag", encoding="utf8") as shader_file:
            wave_shader_code = shader_file.read()
        
        with open("visualize.frag", encoding="utf8") as shader_file:
            visualize_shader_code = shader_file.read()
        
        # 渲染jinja2模板
        visualize_code_template:Template = Template(visualize_shader_code)
        ext_macros:list[tuple[str, str]] = []
        if self.render_intensity_view:
            ext_macros.append(("RENDER_INTENSITY_VIEW", ""))
        visualize_shader_code = visualize_code_template.render(
            EXT_MACROS=ext_macros
        )

        # 编译着色器程序
        self.wave_update_prog = self.ctx.program(
            vertex_shader=vertex_shader_code,
            fragment_shader=wave_shader_code
        )

        self.visualize_prog = self.ctx.program(
            vertex_shader=vertex_shader_code,
            fragment_shader=visualize_shader_code
        )
    
    def init_quad(self):
        # 全屏四边形顶点数据
        vertices = np.array([
            -1.0, -1.0, 0.0, 0.0,
             1.0, -1.0, 1.0, 0.0,
             1.0,  1.0, 1.0, 1.0,
            -1.0,  1.0, 0.0, 1.0
        ], dtype='f4')
        
        indices = np.array([0, 1, 2, 0, 2, 3], dtype='i4')
        
        # 创建VBO和VAO
        self.vbo = self.ctx.buffer(vertices.tobytes())
        self.ibo = self.ctx.buffer(indices.tobytes())
        
        # 创建渲染对象
        self.quad = self.ctx.vertex_array(
            self.wave_update_prog,
            [
                (self.vbo, '2f 2f', 'in_position', 'in_texcoord')
            ],
            index_buffer=self.ibo
        )
        
        self.visualize_quad = self.ctx.vertex_array(
            self.visualize_prog,
            [
                (self.vbo, '2f 2f', 'in_position', 'in_texcoord')
            ],
            index_buffer=self.ibo
        )

    def update(self):
        TEX_PIXEL_SIZE = (1.0 / self.tex_width, 1.0 / self.tex_height)
        # 更新波场
        for _ in range(10):
            self.t+=self.DT
            wave_source_amp = self.wave_source_amp*np.sin(self.t*self.wave_source_freq/(np.pi*2))
        
            self.fbos[1 - self.current_texture].use()
            self.ctx.viewport = (0, 0, self.tex_width, self.tex_height)
            
            self.textures[self.current_texture].use(0)
            self.textures[1 - self.current_texture].use(1)
            self.wave_speed_tex.use(2)
            self.side_damp_tex.use(3)
            self.wave_source1_mask_tex.use(4)
            
            self.wave_update_prog['currentWave'].value = 0
            self.wave_update_prog['previousWave'].value = 1
            self.wave_update_prog['waveSpeed'].value = 2
            self.wave_update_prog['sideDamp'].value = 3
            self.wave_update_prog['waveSource1Mask'].value = 4
            self.wave_update_prog['waveSource1Amplitude'].value = wave_source_amp
            self.wave_update_prog['tex_pixel_size'].value = TEX_PIXEL_SIZE
            self.wave_update_prog['C'].value = self.C
            self.wave_update_prog['coeff'].value = self.COEFF
            
            self.quad.render()
            # 交换纹理
            self.current_texture = 1 - self.current_texture
        
        # 可视化
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, self.window_size[0], self.window_size[1])
        #self.ctx.clear()
        
        self.textures[1 - self.current_texture].use(0)
        self.wave_speed_tex.use(1)
        self.visualize_prog['wave_tex'].value = 0
        self.visualize_prog['bg_tex'].value = 1
        self.visualize_prog['u_min'].value = self.content_uv[0]
        self.visualize_prog['u_max'].value = self.content_uv[1]
        self.visualize_prog['v_min'].value = self.content_uv[2]
        self.visualize_prog['v_max'].value = self.content_uv[3]
        self.visualize_prog['tex_pixel_size'].value = TEX_PIXEL_SIZE
        self.visualize_quad.render()

        if self.save_video:
            self.ctx.copy_framebuffer(self.fbo_video, self.ctx.screen)
    
    def key_callback(self, window, key, scancode, action, mods):
        pass
    
    def run(self):
        if self.save_video:
            self.video_writer.thread.start()
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            self.update()
            glfw.swap_buffers(self.window)
            if self.save_video:
                frame = self.fbo_video.read()
                self.video_writer.frame_queue.put(frame)
        if self.save_video:
            self.video_writer.frame_queue.put(None)
            self.video_writer.thread.join()
        glfw.terminate()

if __name__ == "__main__":
    import click

    @click.command()
    @click.argument("terrain_path")
    @click.option("--width", default=1280)
    @click.option("--height", default=720)
    @click.option("--save-video", is_flag=True)
    @click.option("--video-path")
    @click.option("--video-fps", default=60)
    @click.option("--wave-source-freq", default=10.0)
    @click.option("--wave-source-amp", default=2.0)
    @click.option("--render-intensity-view/--render-wave-view", default=True)
    def run(*args, **kwargs):
        sim = WaveSimulation(*args, **kwargs)
        sim.run()
    run()
