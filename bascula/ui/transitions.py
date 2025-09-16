# -*- coding: utf-8 -*-
"""
Screen Transition Animation System for Bascula-Cam UI
Provides smooth animations between screen changes
"""

import tkinter as tk
from typing import Callable, Optional, Dict, Any
from enum import Enum
import math

class TransitionType(Enum):
    """Available transition types"""
    FADE = "fade"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    SLIDE_UP = "slide_up"
    SLIDE_DOWN = "slide_down"
    SCALE = "scale"
    NONE = "none"


class TransitionManager:
    """Manages smooth transitions between screens"""
    
    def __init__(self, container: tk.Widget):
        self.container = container
        self.current_screen = None
        self.is_animating = False
        self.animation_duration = 300  # milliseconds
        self.animation_steps = 20
        
    def transition_to_screen(self, new_screen: tk.Widget, 
                           transition_type: TransitionType = TransitionType.FADE,
                           duration: int = None,
                           callback: Callable = None):
        """
        Transition from current screen to new screen with animation
        """
        if self.is_animating:
            return False
        
        if duration:
            self.animation_duration = duration
        
        # If no current screen, just show new screen
        if not self.current_screen:
            self._show_screen_immediately(new_screen)
            if callback:
                callback()
            return True
        
        # Start transition animation
        self.is_animating = True
        
        if transition_type == TransitionType.NONE:
            self._show_screen_immediately(new_screen)
            self.is_animating = False
            if callback:
                callback()
        elif transition_type == TransitionType.FADE:
            self._fade_transition(new_screen, callback)
        elif transition_type in [TransitionType.SLIDE_LEFT, TransitionType.SLIDE_RIGHT,
                               TransitionType.SLIDE_UP, TransitionType.SLIDE_DOWN]:
            self._slide_transition(new_screen, transition_type, callback)
        elif transition_type == TransitionType.SCALE:
            self._scale_transition(new_screen, callback)
        
        return True
    
    def _show_screen_immediately(self, screen: tk.Widget):
        """Show screen without animation"""
        if self.current_screen:
            self.current_screen.pack_forget()
        
        screen.pack(fill='both', expand=True)
        self.current_screen = screen
    
    def _fade_transition(self, new_screen: tk.Widget, callback: Callable = None):
        """Fade transition between screens"""
        # Create overlay for fade effect
        overlay = tk.Frame(self.container, bg='black')
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        
        # Fade out current screen
        self._animate_fade_out(overlay, lambda: self._complete_fade_transition(
            new_screen, overlay, callback))
    
    def _complete_fade_transition(self, new_screen: tk.Widget, overlay: tk.Frame, 
                                callback: Callable = None):
        """Complete fade transition by showing new screen and fading in"""
        # Switch screens
        if self.current_screen:
            self.current_screen.pack_forget()
        
        new_screen.pack(fill='both', expand=True)
        self.current_screen = new_screen
        
        # Fade in new screen
        self._animate_fade_in(overlay, lambda: self._cleanup_transition(overlay, callback))
    
    def _animate_fade_out(self, overlay: tk.Frame, callback: Callable):
        """Animate fade out effect"""
        step_duration = self.animation_duration // (self.animation_steps * 2)
        
        def fade_step(step: int):
            if step >= self.animation_steps:
                callback()
                return
            
            alpha = step / self.animation_steps
            # Simulate alpha by adjusting overlay visibility
            overlay.lift()
            self.container.after(step_duration, lambda: fade_step(step + 1))
        
        fade_step(0)
    
    def _animate_fade_in(self, overlay: tk.Frame, callback: Callable):
        """Animate fade in effect"""
        step_duration = self.animation_duration // (self.animation_steps * 2)
        
        def fade_step(step: int):
            if step >= self.animation_steps:
                callback()
                return
            
            alpha = 1.0 - (step / self.animation_steps)
            # Simulate alpha by lowering overlay gradually
            if step == self.animation_steps - 1:
                overlay.lower()
            
            self.container.after(step_duration, lambda: fade_step(step + 1))
        
        fade_step(0)
    
    def _slide_transition(self, new_screen: tk.Widget, direction: TransitionType, 
                         callback: Callable = None):
        """Slide transition between screens"""
        container_width = self.container.winfo_width()
        container_height = self.container.winfo_height()
        
        if container_width <= 1 or container_height <= 1:
            # Fallback if container not properly sized
            self._show_screen_immediately(new_screen)
            self.is_animating = False
            if callback:
                callback()
            return
        
        # Create temporary container for animation
        temp_container = tk.Frame(self.container)
        temp_container.place(x=0, y=0, width=container_width, height=container_height)
        
        # Position screens for slide animation
        if direction == TransitionType.SLIDE_LEFT:
            # New screen starts from right
            if self.current_screen:
                self.current_screen.place(in_=temp_container, x=0, y=0, 
                                        width=container_width, height=container_height)
            new_screen.place(in_=temp_container, x=container_width, y=0,
                           width=container_width, height=container_height)
            
            self._animate_slide_horizontal(temp_container, -container_width, 
                                         new_screen, callback)
        
        elif direction == TransitionType.SLIDE_RIGHT:
            # New screen starts from left
            if self.current_screen:
                self.current_screen.place(in_=temp_container, x=0, y=0,
                                        width=container_width, height=container_height)
            new_screen.place(in_=temp_container, x=-container_width, y=0,
                           width=container_width, height=container_height)
            
            self._animate_slide_horizontal(temp_container, container_width, 
                                         new_screen, callback)
        
        elif direction == TransitionType.SLIDE_UP:
            # New screen starts from bottom
            if self.current_screen:
                self.current_screen.place(in_=temp_container, x=0, y=0,
                                        width=container_width, height=container_height)
            new_screen.place(in_=temp_container, x=0, y=container_height,
                           width=container_width, height=container_height)
            
            self._animate_slide_vertical(temp_container, -container_height, 
                                       new_screen, callback)
        
        elif direction == TransitionType.SLIDE_DOWN:
            # New screen starts from top
            if self.current_screen:
                self.current_screen.place(in_=temp_container, x=0, y=0,
                                        width=container_width, height=container_height)
            new_screen.place(in_=temp_container, x=0, y=-container_height,
                           width=container_width, height=container_height)
            
            self._animate_slide_vertical(temp_container, container_height, 
                                       new_screen, callback)
    
    def _animate_slide_horizontal(self, temp_container: tk.Frame, total_distance: int,
                                new_screen: tk.Widget, callback: Callable = None):
        """Animate horizontal slide"""
        step_duration = self.animation_duration // self.animation_steps
        
        def slide_step(step: int):
            if step >= self.animation_steps:
                self._complete_slide_transition(temp_container, new_screen, callback)
                return
            
            # Easing function for smooth animation
            progress = step / self.animation_steps
            eased_progress = self._ease_in_out_cubic(progress)
            
            offset = int(total_distance * eased_progress)
            
            # Move both screens
            if self.current_screen:
                current_x = offset
                self.current_screen.place(x=current_x)
            
            new_x = (total_distance - offset) if total_distance > 0 else (total_distance - offset)
            new_screen.place(x=new_x)
            
            self.container.after(step_duration, lambda: slide_step(step + 1))
        
        slide_step(0)
    
    def _animate_slide_vertical(self, temp_container: tk.Frame, total_distance: int,
                              new_screen: tk.Widget, callback: Callable = None):
        """Animate vertical slide"""
        step_duration = self.animation_duration // self.animation_steps
        
        def slide_step(step: int):
            if step >= self.animation_steps:
                self._complete_slide_transition(temp_container, new_screen, callback)
                return
            
            # Easing function for smooth animation
            progress = step / self.animation_steps
            eased_progress = self._ease_in_out_cubic(progress)
            
            offset = int(total_distance * eased_progress)
            
            # Move both screens
            if self.current_screen:
                current_y = offset
                self.current_screen.place(y=current_y)
            
            new_y = (total_distance - offset) if total_distance > 0 else (total_distance - offset)
            new_screen.place(y=new_y)
            
            self.container.after(step_duration, lambda: slide_step(step + 1))
        
        slide_step(0)
    
    def _complete_slide_transition(self, temp_container: tk.Frame, new_screen: tk.Widget,
                                 callback: Callable = None):
        """Complete slide transition"""
        # Clean up temporary container
        if self.current_screen:
            self.current_screen.place_forget()
        
        temp_container.destroy()
        
        # Show new screen normally
        new_screen.pack(fill='both', expand=True)
        self.current_screen = new_screen
        
        self._cleanup_transition(None, callback)
    
    def _scale_transition(self, new_screen: tk.Widget, callback: Callable = None):
        """Scale transition (zoom out old, zoom in new)"""
        # Create overlay container
        overlay = tk.Frame(self.container)
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        
        # Position current screen in overlay
        if self.current_screen:
            self.current_screen.place(in_=overlay, relx=0.5, rely=0.5, 
                                    relwidth=1, relheight=1, anchor='center')
        
        # Animate scale out
        self._animate_scale_out(overlay, lambda: self._complete_scale_transition(
            new_screen, overlay, callback))
    
    def _animate_scale_out(self, overlay: tk.Frame, callback: Callable):
        """Animate scale out effect"""
        step_duration = self.animation_duration // (self.animation_steps * 2)
        
        def scale_step(step: int):
            if step >= self.animation_steps:
                callback()
                return
            
            # Scale down from 1.0 to 0.1
            scale = 1.0 - (step / self.animation_steps) * 0.9
            
            if self.current_screen:
                self.current_screen.place(relx=0.5, rely=0.5, 
                                        relwidth=scale, relheight=scale, anchor='center')
            
            self.container.after(step_duration, lambda: scale_step(step + 1))
        
        scale_step(0)
    
    def _complete_scale_transition(self, new_screen: tk.Widget, overlay: tk.Frame,
                                 callback: Callable = None):
        """Complete scale transition"""
        # Switch to new screen
        if self.current_screen:
            self.current_screen.place_forget()
        
        # Position new screen in overlay (scaled down initially)
        new_screen.place(in_=overlay, relx=0.5, rely=0.5, 
                        relwidth=0.1, relheight=0.1, anchor='center')
        self.current_screen = new_screen
        
        # Animate scale in
        self._animate_scale_in(overlay, new_screen, 
                             lambda: self._cleanup_transition(overlay, callback))
    
    def _animate_scale_in(self, overlay: tk.Frame, new_screen: tk.Widget, 
                         callback: Callable):
        """Animate scale in effect"""
        step_duration = self.animation_duration // (self.animation_steps * 2)
        
        def scale_step(step: int):
            if step >= self.animation_steps:
                callback()
                return
            
            # Scale up from 0.1 to 1.0
            scale = 0.1 + (step / self.animation_steps) * 0.9
            
            new_screen.place(relx=0.5, rely=0.5, 
                           relwidth=scale, relheight=scale, anchor='center')
            
            self.container.after(step_duration, lambda: scale_step(step + 1))
        
        scale_step(0)
    
    def _cleanup_transition(self, overlay: tk.Frame = None, callback: Callable = None):
        """Clean up after transition"""
        if overlay:
            overlay.destroy()
        
        # Ensure new screen is properly packed
        if self.current_screen:
            self.current_screen.place_forget()
            self.current_screen.pack(fill='both', expand=True)
        
        self.is_animating = False
        
        if callback:
            callback()
    
    def _ease_in_out_cubic(self, t: float) -> float:
        """Cubic easing function for smooth animations"""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2
    
    def set_animation_duration(self, duration: int):
        """Set animation duration in milliseconds"""
        self.animation_duration = max(100, min(1000, duration))
    
    def is_transition_active(self) -> bool:
        """Check if a transition is currently active"""
        return self.is_animating


class AnimatedWidget:
    """Utility class for animating individual widgets"""
    
    @staticmethod
    def fade_in(widget: tk.Widget, duration: int = 300, callback: Callable = None):
        """Fade in a widget"""
        steps = 20
        step_duration = duration // steps
        
        def fade_step(step: int):
            if step >= steps:
                if callback:
                    callback()
                return
            
            # Simulate fade by adjusting widget state
            alpha = step / steps
            if hasattr(widget, 'config'):
                try:
                    # For labels and buttons, we can't directly set alpha,
                    # but we can simulate it by adjusting colors
                    pass
                except:
                    pass
            
            widget.after(step_duration, lambda: fade_step(step + 1))
        
        fade_step(0)
    
    @staticmethod
    def slide_in(widget: tk.Widget, direction: str = 'left', 
                distance: int = 100, duration: int = 300, callback: Callable = None):
        """Slide in a widget from specified direction"""
        steps = 20
        step_duration = duration // steps
        
        # Store original position
        original_x = widget.winfo_x()
        original_y = widget.winfo_y()
        
        # Set starting position
        if direction == 'left':
            start_x = original_x - distance
            start_y = original_y
        elif direction == 'right':
            start_x = original_x + distance
            start_y = original_y
        elif direction == 'up':
            start_x = original_x
            start_y = original_y - distance
        elif direction == 'down':
            start_x = original_x
            start_y = original_y + distance
        else:
            start_x = original_x
            start_y = original_y
        
        widget.place(x=start_x, y=start_y)
        
        def slide_step(step: int):
            if step >= steps:
                widget.place(x=original_x, y=original_y)
                if callback:
                    callback()
                return
            
            progress = step / steps
            eased_progress = AnimatedWidget._ease_out_cubic(progress)
            
            current_x = start_x + (original_x - start_x) * eased_progress
            current_y = start_y + (original_y - start_y) * eased_progress
            
            widget.place(x=int(current_x), y=int(current_y))
            widget.after(step_duration, lambda: slide_step(step + 1))
        
        slide_step(0)
    
    @staticmethod
    def _ease_out_cubic(t: float) -> float:
        """Cubic ease-out function"""
        return 1 - pow(1 - t, 3)
