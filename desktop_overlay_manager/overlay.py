# -*- coding: utf-8 -*-
"""
基于 tkinter 的可拖动浮层组件
支持在屏幕任意区域创建带标签的矩形框，并支持拖动
"""

import tkinter as tk
from typing import Callable, Optional, Tuple, List

# 全局浮层管理器
_overlay_registry: List['DraggableOverlay'] = []
# 全局点标记管理器
_point_registry: List['DraggablePoint'] = []


class DraggableOverlay:
    """
    可拖动的浮层组件
    
    用法:
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        
        def on_rect_update(x, y, width, height):
            print(f"矩形更新: ({x}, {y}), 大小: {width}x{height}")
        
        overlay = DraggableOverlay(
            root=root,
            x=100,
            y=100,
            width=200,
            height=100,
            label="价格区域",
            on_rect_update=on_rect_update
        )
        overlay.show()
        
        root.mainloop()
    """
    
    def __init__(
        self,
        root: tk.Tk,
        x: int,
        y: int,
        width: int,
        height: int,
        label: str = "",
        on_rect_update: Optional[Callable[[int, int, int, int], None]] = None,
        border_color: str = "#FF0000",
        border_width: int = 2,
        bg_color: str = "white",  # 背景颜色（如果使用透明，可以设置 alpha < 1.0）
        label_bg: str = "#FF0000",
        label_fg: str = "#FFFFFF",
        label_font: Tuple = ("Arial", 10, "bold"),  # 字体元组 (family, size, weight)
        alpha: float = 0.3,  # 窗口透明度（0.0-1.0），0.3 表示 30% 不透明度
        draggable: bool = True,  # 是否可拖动
        resizable: bool = True,  # 是否可调整大小
        resize_handle_size: int = 10,  # 调整大小手柄的大小
    ):
        """
        初始化浮层组件
        
        Args:
            root: 主窗口 (tk.Tk 实例)
            x: 浮层左上角 x 坐标
            y: 浮层左上角 y 坐标
            width: 浮层宽度
            height: 浮层高度
            label: 显示的标签文本
            on_rect_update: 矩形更新回调函数，参数为 (x, y, width, height)，在拖动或调整大小时触发
            border_color: 边框颜色
            border_width: 边框宽度
            bg_color: 背景颜色（支持透明）
            label_bg: 标签背景颜色
            label_fg: 标签文字颜色
            label_font: 标签字体 (family, size, weight)
            alpha: 窗口透明度 (0.0-1.0)
            draggable: 是否可拖动
            resizable: 是否可调整大小
            resize_handle_size: 调整大小手柄的大小（像素）
        """
        self.root = root
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.label = label
        self.callback = on_rect_update  # 保持向后兼容，内部使用 callback
        
        # 样式设置
        self.border_color = border_color
        self.border_width = border_width
        self.bg_color = bg_color
        self.label_bg = label_bg
        self.label_fg = label_fg
        self.label_font = label_font
        self.alpha = alpha
        
        # 功能设置
        self.draggable = draggable
        self.resizable = resizable
        self.resize_handle_size = resize_handle_size
        
        # 拖动相关变量
        self.dragging = False
        self.resizing = False  # 是否正在调整大小
        self.start_x = 0
        self.start_y = 0
        self.offset_x = 0
        self.offset_y = 0
        self.start_width = 0
        self.start_height = 0
        
        # 创建浮层窗口
        self.overlay = None
        self.canvas = None
        self.label_widget = None
        self.resize_handle = None  # 调整大小手柄
        
        # 是否可见
        self.visible = False
        
        # 注册到全局管理器
        _overlay_registry.append(self)
    
    def show(self):
        """显示浮层"""
        if self.visible:
            return
        
        # 创建 Toplevel 窗口
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)  # 移除窗口边框和标题栏
        self.overlay.attributes('-topmost', True)  # 始终置顶
        self.overlay.attributes('-alpha', self.alpha)  # 设置透明度
        
        # 设置窗口位置和大小
        self._update_geometry()
        
        # 创建 Canvas 用于绘制边框
        # 使用系统默认背景色，配合 alpha 实现透明效果
        self.canvas = tk.Canvas(
            self.overlay,
            width=self.width,
            height=self.height,
            bg=self.bg_color,
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 如果设置了透明色，可以使用 -transparentcolor（Windows 支持）
        # 注意：这需要选择一个特定颜色作为透明色
        # 例如：self.overlay.attributes('-transparentcolor', '#000001')
        
        # 绘制边框
        self._draw_border()
        
        # 创建标签（如果有）
        if self.label:
            self._create_label()
        
        # 创建调整大小手柄（如果启用）
        if self.resizable:
            self._create_resize_handle()
        
        # 绑定事件
        self._bind_events()
        
        # 更新窗口显示
        self.overlay.update_idletasks()
        self.overlay.lift()
        self.overlay.focus_force()
        
        self.visible = True
    
    def hide(self):
        """隐藏浮层"""
        if not self.visible or not self.overlay:
            return
        
        self.overlay.destroy()
        self.overlay = None
        self.canvas = None
        self.label_widget = None
        self.resize_handle = None
        self.visible = False
    
    def update_position(self, x: int, y: int, notify: bool = True):
        """
        更新浮层位置
        
        Args:
            x: 新的 x 坐标
            y: 新的 y 坐标
            notify: 是否通知回调函数
        """
        self.x = x
        self.y = y
        if self.visible:
            self._update_geometry()
            if notify:
                self._notify_callback()
    
    def update_size(self, width: int, height: int, notify: bool = True):
        """
        更新浮层大小
        
        Args:
            width: 新的宽度
            height: 新的高度
            notify: 是否通知回调函数
        """
        # 限制最小大小
        min_width = 50
        min_height = 50
        width = max(min_width, width)
        height = max(min_height, height)
        
        self.width = width
        self.height = height
        if self.visible:
            self._update_geometry()
            self._draw_border()
            if self.label_widget:
                self._create_label()
            if self.resizable:
                self._create_resize_handle()
            if notify:
                self._notify_callback()
    
    def update_label(self, label: str):
        """
        更新标签文本
        
        Args:
            label: 新的标签文本
        """
        self.label = label
        if self.visible:
            if self.label:
                self._create_label()
            elif self.label_widget:
                self.label_widget.destroy()
                self.label_widget = None
    
    def _update_geometry(self):
        """更新窗口位置和大小"""
        if self.overlay:
            self.overlay.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
            if self.canvas:
                self.canvas.config(width=self.width, height=self.height)
    
    def _draw_border(self):
        """绘制边框"""
        if not self.canvas:
            return
        
        self.canvas.delete("border")
        
        # 绘制矩形边框
        self.canvas.create_rectangle(
            0,
            0,
            self.width,
            self.height,
            outline=self.border_color,
            width=self.border_width,
            tags="border",
        )
    
    def _create_resize_handle(self):
        """创建调整大小手柄（右下角）"""
        if not self.canvas or not self.resizable:
            return
        
        # 删除旧的手柄
        if self.resize_handle is not None:
            try:
                self.canvas.delete(self.resize_handle)
            except:
                pass
        
        # 手柄位置（右下角）
        handle_size = self.resize_handle_size
        x1 = self.width - handle_size
        y1 = self.height - handle_size
        x2 = self.width
        y2 = self.height
        
        # 绘制调整大小手柄（小正方形）
        self.resize_handle = self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill=self.border_color,
            outline=self.border_color,
            width=1,
            tags="resize_handle",
        )
        
        # 绑定调整大小事件（使用 tag_bind，这样即使重新创建也能正常工作）
        self.canvas.tag_bind("resize_handle", "<Button-1>", self._on_resize_press)
        self.canvas.tag_bind("resize_handle", "<B1-Motion>", self._on_resize_drag)
        self.canvas.tag_bind("resize_handle", "<ButtonRelease-1>", self._on_resize_release)
        
        # 改变鼠标样式为调整大小样式
        def set_resize_cursor(e):
            self.canvas.config(cursor="sizing")
        
        def reset_cursor(e):
            self.canvas.config(cursor="")
        
        self.canvas.tag_bind("resize_handle", "<Enter>", set_resize_cursor)
        self.canvas.tag_bind("resize_handle", "<Leave>", reset_cursor)
    
    def _create_label(self):
        """创建标签"""
        if not self.canvas:
            return
        
        # 删除旧标签
        if self.label_widget:
            self.label_widget.destroy()
        
        # 创建标签 Frame
        label_frame = tk.Frame(
            self.overlay,
            bg=self.label_bg,
            padx=4,
            pady=2,
        )
        
        # 创建标签文本
        label_text = tk.Label(
            label_frame,
            text=self.label,
            bg=self.label_bg,
            fg=self.label_fg,
            font=self.label_font,
        )
        label_text.pack()
        
        # 将标签放置在窗口左上角
        label_frame.place(x=0, y=0)
        
        self.label_widget = label_frame
    
    def _bind_events(self):
        """绑定事件"""
        if not self.canvas:
            return
        
        # 绑定拖动事件（始终绑定，在事件处理函数中检查是否可拖动）
        # 鼠标按下事件
        self.canvas.bind("<Button-1>", self._on_mouse_press)
        # 鼠标移动事件（全局绑定，让调整大小也能捕获）
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag_global)
        # 鼠标释放事件（全局绑定）
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release_global)
        
        # 让标签也可以拖动
        if self.label_widget:
            self.label_widget.bind("<Button-1>", self._on_mouse_press)
            self.label_widget.bind("<B1-Motion>", self._on_mouse_drag_global)
            self.label_widget.bind("<ButtonRelease-1>", self._on_mouse_release_global)
    
    def _is_in_resize_handle(self, x: int, y: int) -> bool:
        """检查坐标是否在调整大小手柄区域内"""
        if not self.resizable:
            return False
        handle_size = self.resize_handle_size
        return (x >= self.width - handle_size and 
                y >= self.height - handle_size)
    
    def _on_mouse_press(self, event):
        """鼠标按下事件处理"""
        # 检查是否点击在调整大小手柄上
        if self._is_in_resize_handle(event.x, event.y):
            # 由调整大小手柄的 tag_bind 处理
            return
        
        # 如果不是调整大小，且可拖动，则开始拖动
        if self.draggable and not self.resizing:
            self.dragging = True
            # 记录鼠标按下时的全局坐标和窗口位置
            self.start_x = event.x_root
            self.start_y = event.y_root
            self.offset_x = self.overlay.winfo_x()
            self.offset_y = self.overlay.winfo_y()
            # 阻止事件继续传播
            return "break"
    
    def _on_mouse_drag_global(self, event):
        """鼠标拖动事件处理（全局，处理拖动和调整大小）"""
        # 优先处理调整大小
        if self.resizing:
            self._on_resize_drag(event)
            return "break"
        
        # 处理拖动
        if self.dragging and self.draggable:
            # 计算鼠标移动的偏移量
            delta_x = event.x_root - self.start_x
            delta_y = event.y_root - self.start_y
            
            # 计算新位置
            new_x = self.offset_x + delta_x
            new_y = self.offset_y + delta_y
            
            # 限制窗口不超出屏幕
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            new_x = max(0, min(new_x, screen_width - self.width))
            new_y = max(0, min(new_y, screen_height - self.height))
            
            # 更新位置（拖动过程中不通知回调，只在释放时通知）
            self.x = int(new_x)
            self.y = int(new_y)
            self._update_geometry()
            
            # 阻止事件继续传播
            return "break"
    
    def _on_mouse_release_global(self, event):
        """鼠标释放事件处理（全局，处理拖动和调整大小结束）"""
        # 处理调整大小结束
        if self.resizing:
            self.resizing = False
            self.dragging = False
            # 调整大小结束后通知回调
            self._notify_callback()
            # 重新创建调整大小手柄（更新位置）
            if self.resizable:
                self._create_resize_handle()
            return "break"
        
        # 处理拖动结束
        if self.dragging:
            self.dragging = False
            self.resizing = False
            # 拖动结束后通知回调
            self._notify_callback()
            return "break"
    
    def _on_resize_press(self, event):
        """调整大小按下事件处理"""
        if not self.resizable:
            return
        
        # 确保不在拖动状态
        self.dragging = False
        self.resizing = True
        
        # 记录鼠标按下时的全局坐标和窗口大小
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_width = self.width
        self.start_height = self.height
        self.offset_x = self.overlay.winfo_x()
        self.offset_y = self.overlay.winfo_y()
        
        # 阻止事件继续传播到拖动处理
        return "break"
    
    def _on_resize_drag(self, event):
        """调整大小拖动事件处理"""
        if not self.resizing or not self.resizable:
            return "break"
        
        # 确保不在拖动状态
        self.dragging = False
        
        # 计算鼠标移动的偏移量
        delta_x = event.x_root - self.start_x
        delta_y = event.y_root - self.start_y
        
        # 计算新大小（右下角调整，所以宽度和高度都增加）
        new_width = self.start_width + delta_x
        new_height = self.start_height + delta_y
        
        # 限制最小大小
        min_width = 50
        min_height = 50
        new_width = max(min_width, new_width)
        new_height = max(min_height, new_height)
        
        # 限制不超出屏幕
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        max_width = screen_width - self.offset_x
        max_height = screen_height - self.offset_y
        new_width = min(new_width, max_width)
        new_height = min(new_height, max_height)
        
        # 更新大小（调整过程中不通知回调，只在释放时通知）
        self.width = int(new_width)
        self.height = int(new_height)
        self._update_geometry()
        self._draw_border()
        # 更新调整大小手柄位置（不重新创建，避免事件丢失）
        if self.resize_handle is not None:
            handle_size = self.resize_handle_size
            x1 = self.width - handle_size
            y1 = self.height - handle_size
            x2 = self.width
            y2 = self.height
            self.canvas.coords(self.resize_handle, x1, y1, x2, y2)
        
        if self.label_widget:
            self._create_label()
        
        # 阻止事件继续传播
        return "break"
    
    def _on_resize_release(self, event):
        """调整大小释放事件处理（由 tag_bind 触发）"""
        # 调用全局释放处理
        self._on_mouse_release_global(event)
        return "break"
    
    def _notify_callback(self):
        """通知回调函数"""
        if self.callback:
            try:
                self.callback(self.x, self.y, self.width, self.height)
            except Exception as e:
                print(f"回调函数执行错误: {e}")
    
    def get_position(self) -> Tuple[int, int, int, int]:
        """
        获取当前位置和大小
        
        Returns:
            (x, y, width, height) 元组
        """
        return (self.x, self.y, self.width, self.height)
    
    def destroy(self):
        """销毁浮层"""
        self.hide()
        # 从全局注册表中移除
        if self in _overlay_registry:
            _overlay_registry.remove(self)


class DraggablePoint:
    """
    可拖动的点标记组件
    
    用法:
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        
        def on_point_update(x, y):
            print(f"点更新: ({x}, {y})")
        
        point = DraggablePoint(
            root=root,
            x=100,
            y=100,
            label="价格点",
            draggable=True,
            callback=on_point_update
        )
        point.show()
        
        root.mainloop()
    """
    
    def __init__(
        self,
        root: tk.Tk,
        x: int,
        y: int,
        label: str = "",
        draggable: bool = True,
        callback: Optional[Callable[[int, int], None]] = None,
        point_color: str = "#FF0000",
        point_size: int = 8,  # 点的半径
        label_bg: str = "#FF0000",
        label_fg: str = "#FFFFFF",
        label_font: Tuple = ("Arial", 10, "bold"),
        alpha: float = 0.9,  # 窗口透明度
        label_offset_x: int = 10,  # 标签相对于点的 x 偏移
        label_offset_y: int = -25,  # 标签相对于点的 y 偏移（负值表示在点上方）
    ):
        """
        初始化点标记组件
        
        Args:
            root: 主窗口 (tk.Tk 实例)
            x: 点的 x 坐标
            y: 点的 y 坐标
            label: 显示的标签文本
            draggable: 是否可拖动
            callback: 拖动回调函数，参数为 (x, y)，在拖动结束时触发
            point_color: 点的颜色
            point_size: 点的半径（像素）
            label_bg: 标签背景颜色
            label_fg: 标签文字颜色
            label_font: 标签字体 (family, size, weight)
            alpha: 窗口透明度 (0.0-1.0)
            label_offset_x: 标签相对于点的 x 偏移
            label_offset_y: 标签相对于点的 y 偏移
        """
        self.root = root
        self.x = x
        self.y = y
        self.label = label
        self.draggable = draggable
        self.callback = callback
        
        # 样式设置
        self.point_color = point_color
        self.point_size = point_size
        self.label_bg = label_bg
        self.label_fg = label_fg
        self.label_font = label_font
        self.alpha = alpha
        self.label_offset_x = label_offset_x
        self.label_offset_y = label_offset_y
        
        # 拖动相关变量
        self.dragging = False
        self.start_x = 0
        self.start_y = 0
        self.offset_x = 0
        self.offset_y = 0
        
        # 透明色（用于实现透明背景）
        self.transparent_color = "#000001"  # 使用一个几乎不可见的颜色作为透明色
        
        # 窗口大小（需要足够大以容纳点和标签）
        # 计算时考虑标签的偏移和大小
        min_size = max(100, point_size * 4)
        # 考虑标签偏移，确保标签不会被裁剪
        label_margin = max(abs(label_offset_x), abs(label_offset_y)) + 50  # 额外留出50像素边距
        self.window_size = max(min_size, label_margin * 2)
        
        # 创建窗口
        self.overlay = None
        self.canvas = None
        self.label_widget = None
        
        # 是否可见
        self.visible = False
        
        # 注册到全局管理器
        _point_registry.append(self)
    
    def show(self):
        """显示点标记"""
        if self.visible:
            return
        
        # 创建 Toplevel 窗口
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)  # 移除窗口边框和标题栏
        self.overlay.attributes('-topmost', True)  # 始终置顶
        self.overlay.attributes('-alpha', self.alpha)  # 设置透明度
        # 设置透明色（Windows 支持，使指定颜色透明）
        try:
            self.overlay.attributes('-transparentcolor', self.transparent_color)
        except:
            pass  # 如果不支持透明色属性，则忽略
        
        # 设置窗口位置和大小
        self._update_geometry()
        
        # 创建 Canvas 用于绘制点
        # 使用透明色作为背景，配合 -transparentcolor 实现透明效果
        self.canvas = tk.Canvas(
            self.overlay,
            width=self.window_size,
            height=self.window_size,
            bg=self.transparent_color,  # 使用透明色
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 绘制点
        self._draw_point()
        
        # 创建标签（如果有）
        if self.label:
            self._create_label()
        
        # 绑定事件
        self._bind_events()
        
        # 更新窗口显示
        self.overlay.update_idletasks()
        self.overlay.lift()
        self.overlay.focus_force()
        
        self.visible = True
    
    def hide(self):
        """隐藏点标记"""
        if not self.visible or not self.overlay:
            return
        
        self.overlay.destroy()
        self.overlay = None
        self.canvas = None
        self.label_widget = None
        self.visible = False
    
    def update_position(self, x: int, y: int, notify: bool = True):
        """
        更新点标记位置
        
        Args:
            x: 新的 x 坐标
            y: 新的 y 坐标
            notify: 是否通知回调函数
        """
        self.x = x
        self.y = y
        if self.visible:
            self._update_geometry()
            if notify:
                self._notify_callback()
    
    def update_label(self, label: str):
        """
        更新标签文本
        
        Args:
            label: 新的标签文本
        """
        self.label = label
        if self.visible:
            if self.label:
                self._create_label()
            elif self.label_widget:
                self.label_widget.destroy()
                self.label_widget = None
    
    def _update_geometry(self, update_label: bool = True):
        """
        更新窗口位置和大小
        
        Args:
            update_label: 是否更新标签位置（拖动过程中设为 False 以避免重复调整窗口大小）
        """
        if self.overlay:
            # 窗口中心点应该对应点的坐标
            # 所以窗口左上角 = (x - window_size/2, y - window_size/2)
            window_x = self.x - self.window_size // 2
            window_y = self.y - self.window_size // 2
            self.overlay.geometry(f"{self.window_size}x{self.window_size}+{window_x}+{window_y}")
            if self.canvas:
                self.canvas.config(width=self.window_size, height=self.window_size)
                # 重新绘制点（位置可能改变）
                self._draw_point()
                # 更新标签位置（如果标签存在且需要更新）
                if update_label and self.label and self.label_widget:
                    # 只更新标签位置，不重新创建（避免调整窗口大小）
                    center_x = self.window_size // 2
                    center_y = self.window_size // 2
                    label_x = center_x + self.label_offset_x
                    label_y = center_y + self.label_offset_y
                    self.label_widget.place(x=label_x, y=label_y)
                elif update_label and self.label and not self.label_widget:
                    # 如果标签应该存在但不存在，则创建它（但不调整窗口大小，因为可能在拖动过程中）
                    # 注意：这通常不应该在拖动过程中发生
                    self._create_label(allow_resize=False)
    
    def _draw_point(self):
        """绘制点"""
        if not self.canvas:
            return
        
        self.canvas.delete("point")
        
        # 计算点在窗口中的位置（窗口中心）
        center_x = self.window_size // 2
        center_y = self.window_size // 2
        
        # 绘制圆形点
        self.canvas.create_oval(
            center_x - self.point_size,
            center_y - self.point_size,
            center_x + self.point_size,
            center_y + self.point_size,
            fill=self.point_color,
            outline=self.point_color,
            width=2,
            tags="point",
        )
    
    def _create_label(self, allow_resize: bool = True):
        """
        创建标签
        
        Args:
            allow_resize: 是否允许调整窗口大小以适应标签（拖动过程中应设为 False）
        """
        if not self.overlay:
            return
        
        # 删除旧标签
        if self.label_widget:
            self.label_widget.destroy()
        
        # 创建标签 Frame
        label_frame = tk.Frame(
            self.overlay,
            bg=self.label_bg,
            padx=4,
            pady=2,
        )
        
        # 创建标签文本
        label_text = tk.Label(
            label_frame,
            text=self.label,
            bg=self.label_bg,
            fg=self.label_fg,
            font=self.label_font,
        )
        label_text.pack()
        
        # 先更新窗口以获取标签实际大小
        self.overlay.update_idletasks()
        
        # 计算标签位置（相对于窗口中心，加上偏移）
        center_x = self.window_size // 2
        center_y = self.window_size // 2
        label_x = center_x + self.label_offset_x
        label_y = center_y + self.label_offset_y
        
        # 将标签放置在指定位置
        label_frame.place(x=label_x, y=label_y)
        
        # 更新窗口以获取标签实际大小
        self.overlay.update_idletasks()
        
        # 只有在允许调整大小时才检查并调整窗口大小
        if allow_resize:
            # 获取标签的实际大小
            label_width = label_frame.winfo_reqwidth()
            label_height = label_frame.winfo_reqheight()
            
            # 检查标签是否超出窗口边界，如果是则调整窗口大小
            label_right = label_x + label_width
            label_bottom = label_y + label_height
            label_left = label_x
            label_top = label_y
            
            # 计算需要的最小窗口大小
            min_x = min(0, label_left)
            min_y = min(0, label_top)
            max_x = max(self.window_size, label_right)
            max_y = max(self.window_size, label_bottom)
            
            new_size = max(max_x - min_x, max_y - min_y) + 20  # 额外留出20像素边距
            
            # 如果窗口需要调整大小
            if new_size > self.window_size:
                self.window_size = new_size
                # 重新计算窗口位置（保持点位置不变）
                window_x = self.x - self.window_size // 2
                window_y = self.y - self.window_size // 2
                self.overlay.geometry(f"{self.window_size}x{self.window_size}+{window_x}+{window_y}")
                if self.canvas:
                    self.canvas.config(width=self.window_size, height=self.window_size)
                    # 重新绘制点（位置可能改变）
                    self._draw_point()
                # 重新计算标签位置
                center_x = self.window_size // 2
                center_y = self.window_size // 2
                label_x = center_x + self.label_offset_x
                label_y = center_y + self.label_offset_y
                label_frame.place(x=label_x, y=label_y)
        
        self.label_widget = label_frame
    
    def _bind_events(self):
        """绑定事件"""
        if not self.canvas:
            return
        
        # 绑定拖动事件
        if self.draggable:
            self.canvas.bind("<Button-1>", self._on_mouse_press)
            self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
            self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)
            
            # 让标签也可以拖动
            if self.label_widget:
                self.label_widget.bind("<Button-1>", self._on_mouse_press)
                self.label_widget.bind("<B1-Motion>", self._on_mouse_drag)
                self.label_widget.bind("<ButtonRelease-1>", self._on_mouse_release)
    
    def _on_mouse_press(self, event):
        """鼠标按下事件处理"""
        if self.draggable:
            self.dragging = True
            # 记录鼠标按下时的全局坐标和窗口位置
            self.start_x = event.x_root
            self.start_y = event.y_root
            self.offset_x = self.overlay.winfo_x()
            self.offset_y = self.overlay.winfo_y()
            return "break"
    
    def _on_mouse_drag(self, event):
        """鼠标拖动事件处理"""
        if self.dragging and self.draggable:
            # 计算鼠标移动的偏移量
            delta_x = event.x_root - self.start_x
            delta_y = event.y_root - self.start_y
            
            # 计算新位置（窗口左上角）
            new_window_x = self.offset_x + delta_x
            new_window_y = self.offset_y + delta_y
            
            # 限制窗口不超出屏幕
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            new_window_x = max(0, min(new_window_x, screen_width - self.window_size))
            new_window_y = max(0, min(new_window_y, screen_height - self.window_size))
            
            # 计算点的实际坐标（窗口中心）
            new_x = new_window_x + self.window_size // 2
            new_y = new_window_y + self.window_size // 2
            
            # 限制点不超出屏幕
            new_x = max(self.point_size, min(new_x, screen_width - self.point_size))
            new_y = max(self.point_size, min(new_y, screen_height - self.point_size))
            
            # 更新位置（拖动过程中不通知回调，只在释放时通知）
            self.x = int(new_x)
            self.y = int(new_y)
            # 拖动过程中只更新位置，不重新创建标签（避免调整窗口大小）
            self._update_geometry(update_label=True)  # 仍然更新标签位置，但不重新创建
            
            return "break"
    
    def _on_mouse_release(self, event):
        """鼠标释放事件处理"""
        if self.dragging:
            self.dragging = False
            # 拖动结束后通知回调
            self._notify_callback()
            return "break"
    
    def _notify_callback(self):
        """通知回调函数"""
        if self.callback:
            try:
                self.callback(self.x, self.y)
            except Exception as e:
                print(f"回调函数执行错误: {e}")
    
    def get_position(self) -> Tuple[int, int]:
        """
        获取当前位置
        
        Returns:
            (x, y) 元组
        """
        return (self.x, self.y)
    
    def destroy(self):
        """销毁点标记"""
        self.hide()
        # 从全局注册表中移除
        if self in _point_registry:
            _point_registry.remove(self)


def create_overlay(
    root: tk.Tk,
    x: int,
    y: int,
    width: int,
    height: int,
        label: str = "",
        on_rect_update: Optional[Callable[[int, int, int, int], None]] = None,
        callback: Optional[Callable[[int, int, int, int], None]] = None,  # 向后兼容
        **kwargs
) -> DraggableOverlay:
    """
    创建浮层的便捷函数
    
    Args:
        root: 主窗口
        x: x 坐标
        y: y 坐标
        width: 宽度
        height: 高度
        label: 标签文本
        on_rect_update: 矩形更新回调（拖动或调整大小时触发）
        callback: 位置更新回调（已弃用，使用 on_rect_update）
        **kwargs: 其他样式参数（包括 draggable, resizable 等）
    
    Returns:
        DraggableOverlay 实例
    """
    # 向后兼容：如果提供了 callback 但没有 on_rect_update，使用 callback
    if on_rect_update is None and callback is not None:
        on_rect_update = callback
    
    overlay = DraggableOverlay(
        root=root,
        x=x,
        y=y,
        width=width,
        height=height,
        label=label,
        on_rect_update=on_rect_update,
        **kwargs
    )
    overlay.show()
    return overlay


def clear_all_overlays():
    """
    清空所有浮层
    
    销毁所有已创建的浮层并清空注册表
    """
    # 创建列表的副本，避免在迭代时修改列表
    overlays = _overlay_registry.copy()
    
    # 销毁所有浮层
    for overlay in overlays:
        try:
            overlay.destroy()
        except Exception as e:
            print(f"销毁浮层时出错: {e}")
    
    # 清空注册表
    _overlay_registry.clear()
    print(f"已清空所有浮层（共 {len(overlays)} 个）")


def get_all_overlays() -> List[DraggableOverlay]:
    """
    获取所有浮层
    
    Returns:
        所有浮层的列表
    """
    return _overlay_registry.copy()


def create_point(
    root: tk.Tk,
    x: int,
    y: int,
    label: str = "",
    draggable: bool = True,
    callback: Optional[Callable[[int, int], None]] = None,
    **kwargs
) -> DraggablePoint:
    """
    创建点标记的便捷函数
    
    Args:
        root: 主窗口
        x: x 坐标
        y: y 坐标
        label: 标签文本
        draggable: 是否可拖动
        callback: 拖动回调函数，参数为 (x, y)，在拖动结束时触发
        **kwargs: 其他样式参数（包括 point_color, point_size, label_bg 等）
    
    Returns:
        DraggablePoint 实例
    """
    point = DraggablePoint(
        root=root,
        x=x,
        y=y,
        label=label,
        draggable=draggable,
        callback=callback,
        **kwargs
    )
    point.show()
    return point


def clear_all_points():
    """
    清空所有点标记
    
    销毁所有已创建的点标记并清空注册表
    """
    # 创建列表的副本，避免在迭代时修改列表
    points = _point_registry.copy()
    
    # 销毁所有点标记
    for point in points:
        try:
            point.destroy()
        except Exception as e:
            print(f"销毁点标记时出错: {e}")
    
    # 清空注册表
    _point_registry.clear()
    print(f"已清空所有点标记（共 {len(points)} 个）")


def get_all_points() -> List[DraggablePoint]:
    """
    获取所有点标记
    
    Returns:
        所有点标记的列表
    """
    return _point_registry.copy()


# 测试代码
if __name__ == "__main__":
    def on_rect_update(x, y, width, height):
        print(f"矩形更新: x={x}, y={y}, width={width}, height={height}")
    
    root = tk.Tk()
    root.title("测试浮层")
    root.geometry("400x300")
    
    # 创建浮层
    overlay1 = create_overlay(
        root=root,
        x=100,
        y=100,
        width=200,
        height=100,
        label="可拖动",
        on_rect_update=on_rect_update,
        border_color="#FF0000",
        label_bg="#FF0000",
        draggable=True,
        resizable=True,
    )
    
 
    # 添加关闭按钮
    close_btn = tk.Button(
        root,
        text="关闭所有浮层",
        command=clear_all_overlays,
    )
    close_btn.pack(pady=20)
    
    
    # 测试点标记
    def on_point_update(x, y):
        print(f"点更新: x={x}, y={y}")
    

    
    # 创建不可拖动的点标记
    point2 = create_point(
        root=root,
        x=300,
        y=250,
        label="价格点2",
        draggable=True,
        point_color="#00FF00",
        point_size=8,
        label_bg="#00FF00",
    )
    
    # 添加关闭所有点标记的按钮
    close_points_btn = tk.Button(
        root,
        text="关闭所有点标记",
        command=clear_all_points,
    )
    close_points_btn.pack(pady=10)
    
    root.mainloop()

