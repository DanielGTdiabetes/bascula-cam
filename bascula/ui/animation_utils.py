# -*- coding: utf-8 -*-
"""
Animation Utilities for Bascula-Cam UI
Provides common animation functions and easing curves
"""

import tkinter as tk
import math
from typing import Callable, Optional, Union, Tuple


class EasingFunctions:
    """Collection of easing functions for smooth animations"""
    
    @staticmethod
    def linear(t: float) -> float:
        """Linear interpolation"""
        return t
    
    @staticmethod
    def ease_in_quad(t: float) -> float:
        """Quadratic ease-in"""
        return t * t
    
    @staticmethod
    def ease_out_quad(t: float) -> float:
        """Quadratic ease-out"""
        return 1 - (1 - t) * (1 - t)
    
    @staticmethod
    def ease_in_out_quad(t: float) -> float:
        """Quadratic ease-in-out"""
        if t < 0.5:
            return 2 * t * t
        else:
            return 1 - pow(-2 * t + 2, 2) / 2
    
    @staticmethod
    def ease_in_cubic(t: float) -> float:
        """Cubic ease-in"""
        return t * t * t
    
    @staticmethod
    def ease_out_cubic(t: float) -> float:
        """Cubic ease-out"""
        return 1 - pow(1 - t, 3)
    
    @staticmethod
    def ease_in_out_cubic(t: float) -> float:
        """Cubic ease-in-out"""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2
    
    @staticmethod
    def ease_in_bounce(t: float) -> float:
        """Bounce ease-in"""
        return 1 - EasingFunctions.ease_out_bounce(1 - t)
    
    @staticmethod
    def ease_out_bounce(t: float) -> float:
        """Bounce ease-out"""
        n1 = 7.5625
        d1 = 2.75
        
        if t < 1 / d1:
            return n1 * t * t
        elif t < 2 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        elif t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        else:
            t -= 2.625 / d1
            return n1 * t * t + 0.984375
    
    @staticmethod
    def ease_elastic(t: float) -> float:
        """Elastic easing"""
        if t == 0:
            return 0
        elif t == 1:
            return 1
        else:
            c4 = (2 * math.pi) / 3
            return -pow(2, 10 * t - 10) * math.sin((t * 10 - 10.75) * c4)


class AnimationController:
    """Controls and manages animations"""
    
    def __init__(self, widget: tk.Widget):
        self.widget = widget
        self.active_animations = {}
        self.animation_id_counter = 0
    
    def animate_property(self, property_name: str, start_value: Union[int, float], 
                        end_value: Union[int, float], duration: int = 300,
                        easing_func: Callable[[float], float] = EasingFunctions.ease_out_cubic,
                        callback: Optional[Callable] = None,
                        update_func: Optional[Callable] = None) -> int:
        """
        Animate a property from start_value to end_value
        Returns animation ID that can be used to cancel the animation
        """
        animation_id = self.animation_id_counter
        self.animation_id_counter += 1
        
        steps = max(20, duration // 15)  # At least 20 steps, or one per 15ms
        step_duration = duration // steps
        
        def animate_step(step: int):
            if animation_id not in self.active_animations:
                return  # Animation was cancelled
            
            if step >= steps:
                # Final step
                final_value = end_value
                if update_func:
                    update_func(property_name, final_value)
                else:
                    self._default_update(property_name, final_value)
                
                # Clean up and call callback
                del self.active_animations[animation_id]
                if callback:
                    callback()
                return
            
            # Calculate current value
            progress = step / steps
            eased_progress = easing_func(progress)
            current_value = start_value + (end_value - start_value) * eased_progress
            
            # Update property
            if update_func:
                update_func(property_name, current_value)
            else:
                self._default_update(property_name, current_value)
            
            # Schedule next step
            self.widget.after(step_duration, lambda: animate_step(step + 1))
        
        # Start animation
        self.active_animations[animation_id] = True
        animate_step(0)
        return animation_id
    
    def _default_update(self, property_name: str, value: Union[int, float]):
        """Default property update function"""
        try:
            if property_name in ['x', 'y', 'width', 'height']:
                # Geometry properties
                current_info = self.widget.place_info()
                if property_name == 'x':
                    self.widget.place(x=int(value))
                elif property_name == 'y':
                    self.widget.place(y=int(value))
                elif property_name == 'width':
                    self.widget.place(width=int(value))
                elif property_name == 'height':
                    self.widget.place(height=int(value))
            else:
                # Try to configure as widget property
                self.widget.config(**{property_name: value})
        except Exception:
            pass  # Ignore errors in property updates
    
    def cancel_animation(self, animation_id: int):
        """Cancel an active animation"""
        if animation_id in self.active_animations:
            del self.active_animations[animation_id]
    
    def cancel_all_animations(self):
        """Cancel all active animations"""
        self.active_animations.clear()


class UIEffects:
    """Common UI effect animations"""
    
    @staticmethod
    def fade_in(widget: tk.Widget, duration: int = 300, 
               callback: Optional[Callable] = None):
        """Fade in effect (simulated with opacity-like behavior)"""
        controller = AnimationController(widget)
        
        # Store original state
        original_state = widget.cget('state') if hasattr(widget, 'cget') else 'normal'
        
        def update_fade(prop: str, value: float):
            # Simulate fade by adjusting widget visibility/state
            if value < 0.1:
                try:
                    widget.config(state='disabled')
                except:
                    pass
            elif value > 0.9:
                try:
                    widget.config(state=original_state)
                except:
                    pass
        
        controller.animate_property('alpha', 0.0, 1.0, duration,
                                  EasingFunctions.ease_out_cubic,
                                  callback, update_fade)
    
    @staticmethod
    def slide_in(widget: tk.Widget, direction: str = 'left', 
                distance: int = 100, duration: int = 300,
                callback: Optional[Callable] = None):
        """Slide in animation"""
        controller = AnimationController(widget)
        
        # Get current position
        try:
            current_x = widget.winfo_x()
            current_y = widget.winfo_y()
        except:
            current_x = 0
            current_y = 0
        
        # Calculate start position
        if direction == 'left':
            start_x, start_y = current_x - distance, current_y
            end_x, end_y = current_x, current_y
        elif direction == 'right':
            start_x, start_y = current_x + distance, current_y
            end_x, end_y = current_x, current_y
        elif direction == 'up':
            start_x, start_y = current_x, current_y - distance
            end_x, end_y = current_x, current_y
        elif direction == 'down':
            start_x, start_y = current_x, current_y + distance
            end_x, end_y = current_x, current_y
        else:
            start_x, start_y = current_x, current_y
            end_x, end_y = current_x, current_y
        
        # Set initial position
        widget.place(x=start_x, y=start_y)
        
        # Animate to final position
        def update_position(prop: str, value: float):
            if prop == 'x':
                widget.place(x=int(value))
            elif prop == 'y':
                widget.place(y=int(value))
        
        # Animate X and Y separately if needed
        if start_x != end_x:
            controller.animate_property('x', start_x, end_x, duration,
                                      EasingFunctions.ease_out_cubic,
                                      None, update_position)
        if start_y != end_y:
            controller.animate_property('y', start_y, end_y, duration,
                                      EasingFunctions.ease_out_cubic,
                                      callback, update_position)
        elif start_x == end_x and callback:
            callback()
    
    @staticmethod
    def scale_in(widget: tk.Widget, duration: int = 300,
                callback: Optional[Callable] = None):
        """Scale in animation"""
        controller = AnimationController(widget)
        
        # Get current size
        try:
            current_width = widget.winfo_width()
            current_height = widget.winfo_height()
        except:
            current_width = 100
            current_height = 100
        
        # Start small
        widget.place(width=1, height=1)
        
        def update_scale(prop: str, value: float):
            if prop == 'scale':
                new_width = int(current_width * value)
                new_height = int(current_height * value)
                widget.place(width=new_width, height=new_height)
        
        controller.animate_property('scale', 0.1, 1.0, duration,
                                  EasingFunctions.ease_out_bounce,
                                  callback, update_scale)
    
    @staticmethod
    def pulse(widget: tk.Widget, scale_factor: float = 1.1, 
             duration: int = 200, cycles: int = 1,
             callback: Optional[Callable] = None):
        """Pulse animation"""
        controller = AnimationController(widget)
        
        def pulse_cycle(cycle: int):
            if cycle >= cycles:
                if callback:
                    callback()
                return
            
            # Scale up
            def on_scale_up():
                # Scale down
                controller.animate_property('scale', scale_factor, 1.0, duration // 2,
                                          EasingFunctions.ease_out_cubic,
                                          lambda: pulse_cycle(cycle + 1))
            
            controller.animate_property('scale', 1.0, scale_factor, duration // 2,
                                      EasingFunctions.ease_in_cubic,
                                      on_scale_up)
        
        pulse_cycle(0)
    
    @staticmethod
    def shake(widget: tk.Widget, intensity: int = 10, 
             duration: int = 300, callback: Optional[Callable] = None):
        """Shake animation"""
        controller = AnimationController(widget)
        
        # Get current position
        try:
            original_x = widget.winfo_x()
        except:
            original_x = 0
        
        steps = 20
        step_duration = duration // steps
        
        def shake_step(step: int):
            if step >= steps:
                widget.place(x=original_x)
                if callback:
                    callback()
                return
            
            # Calculate shake offset
            progress = step / steps
            shake_amount = intensity * (1 - progress) * math.sin(step * 2)
            new_x = original_x + int(shake_amount)
            
            widget.place(x=new_x)
            widget.after(step_duration, lambda: shake_step(step + 1))
        
        shake_step(0)


class LoadingAnimations:
    """Loading and progress animations"""
    
    @staticmethod
    def spinning_loader(canvas: tk.Canvas, x: int, y: int, radius: int = 20,
                       color: str = '#3b82f6', duration: int = 1000) -> int:
        """Create a spinning loader animation"""
        # Create spinning arc
        arc_id = canvas.create_arc(x - radius, y - radius, x + radius, y + radius,
                                  start=0, extent=90, outline=color, width=3,
                                  style='arc')
        
        def rotate_arc(angle: int):
            canvas.itemconfig(arc_id, start=angle)
            canvas.after(50, lambda: rotate_arc((angle + 15) % 360))
        
        rotate_arc(0)
        return arc_id
    
    @staticmethod
    def progress_bar_animation(progress_widget, target_value: float,
                             duration: int = 500, callback: Optional[Callable] = None):
        """Animate progress bar to target value"""
        if not hasattr(progress_widget, 'set'):
            return
        
        current_value = getattr(progress_widget, 'get', lambda: 0)()
        controller = AnimationController(progress_widget)
        
        def update_progress(prop: str, value: float):
            try:
                progress_widget.set(value)
            except:
                pass
        
        controller.animate_property('progress', current_value, target_value,
                                  duration, EasingFunctions.ease_out_cubic,
                                  callback, update_progress)
