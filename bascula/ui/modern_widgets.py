# -*- coding: utf-8 -*-
"""Modern UI components with gradients, shadows, and rounded corners for Bascula-Cam"""

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from typing import Optional, Callable, Dict, Any
from bascula.config.theme import get_current_colors

class ModernCard(tk.Frame):
    """Modern card component with shadow effect and rounded appearance"""
    
    def __init__(self, parent, title: str = "", **kwargs):
        self.colors = get_current_colors()
        
        # Extract custom options
        self.shadow_offset = kwargs.pop('shadow_offset', 4)
        self.corner_radius = kwargs.pop('corner_radius', 12)
        self.elevation = kwargs.pop('elevation', 2)
        
        super().__init__(parent, **kwargs)
        self.configure(bg=self.colors['COL_BG'])
        
        # Create shadow effect
        self._create_shadow()
        
        # Main card frame
        self.card_frame = tk.Frame(
            self,
            bg=self.colors['COL_CARD'],
            highlightbackground=self.colors['COL_BORDER'],
            highlightthickness=1,
            relief='flat'
        )
        self.card_frame.pack(fill='both', expand=True, padx=self.shadow_offset, pady=self.shadow_offset)
        
        if title:
            self.title_label = tk.Label(
                self.card_frame,
                text=title,
                bg=self.colors['COL_CARD'],
                fg=self.colors['COL_TEXT'],
                font=('DejaVu Sans', 18, 'bold')
            )
            self.title_label.pack(anchor='w', padx=16, pady=(16, 8))
        
        # Content frame for user widgets
        self.content_frame = tk.Frame(self.card_frame, bg=self.colors['COL_CARD'])
        self.content_frame.pack(fill='both', expand=True, padx=16, pady=(0, 16))
    
    def _create_shadow(self):
        """Create shadow effect using multiple frames"""
        for i in range(self.elevation):
            shadow_frame = tk.Frame(
                self,
                bg=self.colors['COL_SHADOW'],
                height=2,
                width=2
            )
            shadow_frame.place(
                x=self.shadow_offset + i,
                y=self.shadow_offset + i,
                relwidth=1,
                relheight=1
            )
            shadow_frame.lower()


class ModernButton(tk.Button):
    """Modern button with hover effects and improved styling"""
    
    def __init__(self, parent, **kwargs):
        self.colors = get_current_colors()
        
        # Extract custom options
        self.style = kwargs.pop('style', 'primary')  # primary, secondary, outline, ghost
        self.size = kwargs.pop('size', 'medium')     # small, medium, large
        self.icon = kwargs.pop('icon', None)
        
        # Set default styling based on style type
        self._apply_style_defaults(kwargs)
        
        super().__init__(parent, **kwargs)
        
        # Bind hover effects
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_click)
        self.bind('<ButtonRelease-1>', self._on_release)
        
        # Store original colors for hover effects
        self.original_bg = self['bg']
        self.original_fg = self['fg']
    
    def _apply_style_defaults(self, kwargs):
        """Apply default styling based on button style"""
        size_configs = {
            'small': {'font': ('DejaVu Sans', 14), 'padx': 12, 'pady': 6},
            'medium': {'font': ('DejaVu Sans', 16), 'padx': 16, 'pady': 10},
            'large': {'font': ('DejaVu Sans', 18, 'bold'), 'padx': 20, 'pady': 14}
        }
        
        style_configs = {
            'primary': {
                'bg': self.colors['COL_ACCENT'],
                'fg': 'white',
                'activebackground': self.colors['COL_ACCENT_LIGHT'],
                'activeforeground': 'white'
            },
            'secondary': {
                'bg': self.colors['COL_CARD'],
                'fg': self.colors['COL_TEXT'],
                'activebackground': self.colors['COL_CARD_HOVER'],
                'activeforeground': self.colors['COL_TEXT']
            },
            'outline': {
                'bg': self.colors['COL_BG'],
                'fg': self.colors['COL_ACCENT'],
                'highlightbackground': self.colors['COL_ACCENT'],
                'highlightthickness': 2,
                'activebackground': self.colors['COL_ACCENT'],
                'activeforeground': 'white'
            },
            'ghost': {
                'bg': self.colors['COL_BG'],
                'fg': self.colors['COL_TEXT'],
                'relief': 'flat',
                'bd': 0,
                'activebackground': self.colors['COL_CARD_HOVER'],
                'activeforeground': self.colors['COL_TEXT']
            }
        }
        
        # Apply size configuration
        if self.size in size_configs:
            kwargs.update(size_configs[self.size])
        
        # Apply style configuration
        if self.style in style_configs:
            kwargs.update(style_configs[self.style])
        
        # Common defaults
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('bd', 0)
        kwargs.setdefault('cursor', 'hand2')
    
    def _on_enter(self, event):
        """Handle mouse enter (hover)"""
        if self.style == 'primary':
            self.configure(bg=self.colors['COL_ACCENT_LIGHT'])
        elif self.style == 'secondary':
            self.configure(bg=self.colors['COL_CARD_HOVER'])
        elif self.style == 'outline':
            self.configure(bg=self.colors['COL_ACCENT'], fg='white')
        elif self.style == 'ghost':
            self.configure(bg=self.colors['COL_CARD_HOVER'])
    
    def _on_leave(self, event):
        """Handle mouse leave"""
        self.configure(bg=self.original_bg, fg=self.original_fg)
    
    def _on_click(self, event):
        """Handle button press"""
        # Add pressed effect
        if self.style == 'primary':
            self.configure(bg=self.colors['COL_ACCENT'])
        elif self.style in ['secondary', 'ghost']:
            self.configure(bg=self.colors['COL_CARD'])
    
    def _on_release(self, event):
        """Handle button release"""
        # Return to hover state if still hovering
        if self.winfo_containing(event.x_root, event.y_root) == self:
            self._on_enter(event)


class ModernProgressBar(tk.Frame):
    """Modern progress bar with smooth animations"""
    
    def __init__(self, parent, **kwargs):
        self.colors = get_current_colors()
        
        # Extract custom options
        self.height = kwargs.pop('height', 8)
        self.corner_radius = kwargs.pop('corner_radius', 4)
        self.animated = kwargs.pop('animated', True)
        
        super().__init__(parent, **kwargs)
        self.configure(bg=self.colors['COL_BG'], height=self.height)
        
        # Background track
        self.track = tk.Frame(
            self,
            bg=self.colors['COL_BORDER'],
            height=self.height
        )
        self.track.pack(fill='x', expand=True)
        
        # Progress fill
        self.fill = tk.Frame(
            self.track,
            bg=self.colors['COL_ACCENT'],
            height=self.height
        )
        
        self._progress = 0.0
        self._target_progress = 0.0
        self._animation_job = None
    
    def set_progress(self, value: float):
        """Set progress value (0.0 to 1.0)"""
        value = max(0.0, min(1.0, value))
        self._target_progress = value
        
        if self.animated:
            self._animate_to_target()
        else:
            self._progress = value
            self._update_visual()
    
    def _animate_to_target(self):
        """Animate progress to target value"""
        if self._animation_job:
            self.after_cancel(self._animation_job)
        
        diff = self._target_progress - self._progress
        if abs(diff) < 0.01:
            self._progress = self._target_progress
            self._update_visual()
            return
        
        self._progress += diff * 0.1  # Smooth easing
        self._update_visual()
        self._animation_job = self.after(16, self._animate_to_target)  # ~60fps
    
    def _update_visual(self):
        """Update visual representation"""
        if self._progress <= 0:
            self.fill.place_forget()
        else:
            self.fill.place(x=0, y=0, relwidth=self._progress, relheight=1)


class ModernToggle(tk.Frame):
    """Modern toggle switch component"""
    
    def __init__(self, parent, text: str = "", command: Optional[Callable] = None, **kwargs):
        self.colors = get_current_colors()
        
        super().__init__(parent, **kwargs)
        self.configure(bg=self.colors['COL_BG'])
        
        self.command = command
        self._state = False
        
        # Create toggle components
        if text:
            self.label = tk.Label(
                self,
                text=text,
                bg=self.colors['COL_BG'],
                fg=self.colors['COL_TEXT'],
                font=('DejaVu Sans', 14)
            )
            self.label.pack(side='left', padx=(0, 12))
        
        # Toggle track
        self.track = tk.Frame(
            self,
            bg=self.colors['COL_BORDER'],
            width=50,
            height=24,
            cursor='hand2'
        )
        self.track.pack(side='right')
        self.track.pack_propagate(False)
        
        # Toggle thumb
        self.thumb = tk.Frame(
            self.track,
            bg=self.colors['COL_MUTED'],
            width=20,
            height=20
        )
        self.thumb.place(x=2, y=2)
        
        # Bind click events
        self.track.bind('<Button-1>', self._toggle)
        self.thumb.bind('<Button-1>', self._toggle)
        if hasattr(self, 'label'):
            self.label.bind('<Button-1>', self._toggle)
    
    def _toggle(self, event=None):
        """Toggle the switch state"""
        self.set_state(not self._state)
        if self.command:
            self.command()
    
    def set_state(self, state: bool):
        """Set toggle state"""
        self._state = state
        
        if state:
            # ON state
            self.track.configure(bg=self.colors['COL_ACCENT'])
            self.thumb.configure(bg='white')
            self.thumb.place(x=28, y=2)  # Move to right
        else:
            # OFF state
            self.track.configure(bg=self.colors['COL_BORDER'])
            self.thumb.configure(bg=self.colors['COL_MUTED'])
            self.thumb.place(x=2, y=2)  # Move to left
    
    def get_state(self) -> bool:
        """Get current toggle state"""
        return self._state


class ModernToast(tk.Toplevel):
    """Modern toast notification"""
    
    def __init__(self, parent, message: str, type: str = 'info', duration: int = 3000):
        super().__init__(parent)
        
        self.colors = get_current_colors()
        
        # Configure window
        self.withdraw()  # Hide initially
        self.overrideredirect(True)  # Remove window decorations
        self.attributes('-topmost', True)
        
        # Style based on type
        type_colors = {
            'info': self.colors['COL_ACCENT'],
            'success': self.colors['COL_SUCCESS'],
            'warning': self.colors['COL_WARN'],
            'error': self.colors['COL_DANGER']
        }
        
        bg_color = type_colors.get(type, self.colors['COL_ACCENT'])
        
        # Create toast frame
        self.toast_frame = tk.Frame(
            self,
            bg=bg_color,
            padx=20,
            pady=12
        )
        self.toast_frame.pack(fill='both', expand=True)
        
        # Message label
        self.message_label = tk.Label(
            self.toast_frame,
            text=message,
            bg=bg_color,
            fg='white',
            font=('DejaVu Sans', 14, 'bold')
        )
        self.message_label.pack()
        
        # Position and show
        self._position_toast()
        self.deiconify()
        
        # Auto-hide after duration
        self.after(duration, self._hide_toast)
    
    def _position_toast(self):
        """Position toast at top-right of screen"""
        self.update_idletasks()
        
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Get toast dimensions
        toast_width = self.winfo_reqwidth()
        toast_height = self.winfo_reqheight()
        
        # Position at top-right with margin
        x = screen_width - toast_width - 20
        y = 20
        
        self.geometry(f"+{x}+{y}")
    
    def _hide_toast(self):
        """Hide and destroy toast"""
        self.destroy()


class ModernInput(tk.Frame):
    """Modern input field with floating label"""
    
    def __init__(self, parent, label: str = "", placeholder: str = "", **kwargs):
        self.colors = get_current_colors()
        
        super().__init__(parent, **kwargs)
        self.configure(bg=self.colors['COL_BG'])
        
        self.label_text = label
        self.placeholder_text = placeholder
        
        # Floating label
        if label:
            self.label = tk.Label(
                self,
                text=label,
                bg=self.colors['COL_BG'],
                fg=self.colors['COL_MUTED'],
                font=('DejaVu Sans', 12)
            )
            self.label.pack(anchor='w', pady=(0, 4))
        
        # Input frame with border
        self.input_frame = tk.Frame(
            self,
            bg=self.colors['COL_CARD'],
            highlightbackground=self.colors['COL_BORDER'],
            highlightthickness=1
        )
        self.input_frame.pack(fill='x', pady=(0, 8))
        
        # Entry widget
        self.entry = tk.Entry(
            self.input_frame,
            bg=self.colors['COL_CARD'],
            fg=self.colors['COL_TEXT'],
            font=('DejaVu Sans', 14),
            relief='flat',
            bd=0,
            insertbackground=self.colors['COL_ACCENT']
        )
        self.entry.pack(fill='x', padx=12, pady=8)
        
        # Bind focus events
        self.entry.bind('<FocusIn>', self._on_focus_in)
        self.entry.bind('<FocusOut>', self._on_focus_out)
        
        # Set placeholder if provided
        if placeholder:
            self._set_placeholder()
    
    def _on_focus_in(self, event):
        """Handle focus in"""
        self.input_frame.configure(highlightbackground=self.colors['COL_ACCENT'])
        if hasattr(self, 'label'):
            self.label.configure(fg=self.colors['COL_ACCENT'])
        
        # Clear placeholder
        if self.entry.get() == self.placeholder_text:
            self.entry.delete(0, tk.END)
            self.entry.configure(fg=self.colors['COL_TEXT'])
    
    def _on_focus_out(self, event):
        """Handle focus out"""
        self.input_frame.configure(highlightbackground=self.colors['COL_BORDER'])
        if hasattr(self, 'label'):
            self.label.configure(fg=self.colors['COL_MUTED'])
        
        # Restore placeholder if empty
        if not self.entry.get() and self.placeholder_text:
            self._set_placeholder()
    
    def _set_placeholder(self):
        """Set placeholder text"""
        self.entry.insert(0, self.placeholder_text)
        self.entry.configure(fg=self.colors['COL_MUTED'])
    
    def get(self) -> str:
        """Get entry value (excluding placeholder)"""
        value = self.entry.get()
        return "" if value == self.placeholder_text else value
    
    def set(self, value: str):
        """Set entry value"""
        self.entry.delete(0, tk.END)
        if value:
            self.entry.insert(0, value)
            self.entry.configure(fg=self.colors['COL_TEXT'])
        elif self.placeholder_text:
            self._set_placeholder()


# Utility functions for modern styling
def apply_modern_styling(widget, style_type: str = 'card'):
    """Apply modern styling to existing widgets"""
    colors = get_current_colors()
    
    if style_type == 'card':
        widget.configure(
            bg=colors['COL_CARD'],
            highlightbackground=colors['COL_BORDER'],
            highlightthickness=1,
            relief='flat'
        )
    elif style_type == 'button':
        widget.configure(
            bg=colors['COL_ACCENT'],
            fg='white',
            relief='flat',
            bd=0,
            cursor='hand2',
            activebackground=colors['COL_ACCENT_LIGHT']
        )


def create_gradient_frame(parent, colors: tuple, direction: str = 'vertical'):
    """Create a frame with gradient background effect"""
    # Note: Tkinter doesn't support true gradients, so we simulate with multiple frames
    frame = tk.Frame(parent)
    
    start_color, end_color = colors
    steps = 20
    
    # Convert hex to RGB
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def rgb_to_hex(rgb):
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    
    start_rgb = hex_to_rgb(start_color)
    end_rgb = hex_to_rgb(end_color)
    
    for i in range(steps):
        ratio = i / (steps - 1)
        r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
        g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
        b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
        
        color = rgb_to_hex((r, g, b))
        
        gradient_strip = tk.Frame(frame, bg=color, height=1)
        if direction == 'vertical':
            gradient_strip.pack(fill='x', expand=True)
        else:
            gradient_strip.pack(side='left', fill='y', expand=True)
    
    return frame
