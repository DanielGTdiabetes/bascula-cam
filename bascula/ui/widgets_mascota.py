from __future__ import annotations

from .widgets import Mascot, COL_ACCENT
import math
import random


class MascotaCanvas(Mascot):
    """Mascota con animaciones avanzadas y estados expresivos."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._orig_pos = None
        self._animation_job = None
        self._expression_timer = None
        self._mood = "neutral"  # neutral, happy, excited, sleepy, worried, thinking
        self._energy_level = 0.5  # 0.0 to 1.0
        
        # Enhanced states
        self._enhanced_states = {
            "happy": {"color": "#4ecdc4", "animation": "gentle_bounce"},
            "excited": {"color": "#ff6b9d", "animation": "energetic_shake"},
            "sleepy": {"color": "#8892a0", "animation": "slow_sway"},
            "worried": {"color": "#ffe66d", "animation": "nervous_twitch"},
            "thinking": {"color": "#00d4aa", "animation": "pulse"},
            "celebrating": {"color": "#ff8fb3", "animation": "party_bounce"}
        }

    # ---- Enhanced Animations -------------------------------------------------
    def shake(self, dist: int = 10, times: int = 4, delay: int = 50):
        """Enhanced shake with easing"""
        info = self.place_info()
        x = int(info.get("x", 0))
        y = int(info.get("y", 0))

        def step(i=0):
            if i >= times * 2:
                self.place(x=x, y=y)
                return
            # Add easing - stronger at start, weaker at end
            intensity = 1.0 - (i / (times * 2))
            dx = (dist * intensity) if i % 2 == 0 else -(dist * intensity)
            self.place(x=x + int(dx), y=y)
            self.after(delay, step, i + 1)

        step()

    def bounce(self, height: int = 20, delay: int = 40):
        """Enhanced bounce with physics-like motion"""
        info = self.place_info()
        x = int(info.get("x", 0))
        y = int(info.get("y", 0))
        
        # Physics simulation
        velocity = 0
        gravity = 1.2
        position = 0
        damping = 0.8

        def physics_step():
            nonlocal velocity, position
            velocity += gravity
            position += velocity
            
            if position >= 0:  # Hit ground
                position = 0
                velocity = -velocity * damping
                
                if abs(velocity) < 0.5:  # Stop bouncing
                    self.place(x=x, y=y)
                    return
            
            self.place(x=x, y=y - int(position))
            self.after(delay, physics_step)
        
        # Initial upward velocity
        velocity = -math.sqrt(2 * gravity * height)
        physics_step()

    def gentle_bounce(self, duration: int = 2000):
        """Gentle continuous bouncing"""
        if self._animation_job:
            self.after_cancel(self._animation_job)
        
        info = self.place_info()
        x = int(info.get("x", 0))
        y = int(info.get("y", 0))
        start_time = self.tk.call('clock', 'milliseconds')
        
        def animate():
            current_time = self.tk.call('clock', 'milliseconds')
            elapsed = current_time - start_time
            
            if elapsed > duration:
                self.place(x=x, y=y)
                self._animation_job = None
                return
            
            # Sine wave for smooth bouncing
            offset = math.sin(elapsed * 0.005) * 8
            self.place(x=x, y=y + int(offset))
            self._animation_job = self.after(16, animate)  # ~60fps
        
        animate()

    def energetic_shake(self, duration: int = 1500):
        """Energetic shaking animation"""
        if self._animation_job:
            self.after_cancel(self._animation_job)
        
        info = self.place_info()
        x = int(info.get("x", 0))
        y = int(info.get("y", 0))
        start_time = self.tk.call('clock', 'milliseconds')
        
        def animate():
            current_time = self.tk.call('clock', 'milliseconds')
            elapsed = current_time - start_time
            
            if elapsed > duration:
                self.place(x=x, y=y)
                self._animation_job = None
                return
            
            # Random shake with decreasing intensity
            intensity = 1.0 - (elapsed / duration)
            dx = random.randint(-8, 8) * intensity
            dy = random.randint(-4, 4) * intensity
            self.place(x=x + int(dx), y=y + int(dy))
            self._animation_job = self.after(50, animate)
        
        animate()

    def slow_sway(self, duration: int = 3000):
        """Slow swaying motion for sleepy state"""
        if self._animation_job:
            self.after_cancel(self._animation_job)
        
        info = self.place_info()
        x = int(info.get("x", 0))
        y = int(info.get("y", 0))
        start_time = self.tk.call('clock', 'milliseconds')
        
        def animate():
            current_time = self.tk.call('clock', 'milliseconds')
            elapsed = current_time - start_time
            
            if elapsed > duration:
                self.place(x=x, y=y)
                self._animation_job = None
                return
            
            # Slow sine wave sway
            offset_x = math.sin(elapsed * 0.002) * 6
            offset_y = math.sin(elapsed * 0.001) * 3
            self.place(x=x + int(offset_x), y=y + int(offset_y))
            self._animation_job = self.after(33, animate)  # ~30fps for slower feel
        
        animate()

    def nervous_twitch(self, duration: int = 2000):
        """Nervous twitching animation"""
        if self._animation_job:
            self.after_cancel(self._animation_job)
        
        info = self.place_info()
        x = int(info.get("x", 0))
        y = int(info.get("y", 0))
        start_time = self.tk.call('clock', 'milliseconds')
        
        def animate():
            current_time = self.tk.call('clock', 'milliseconds')
            elapsed = current_time - start_time
            
            if elapsed > duration:
                self.place(x=x, y=y)
                self._animation_job = None
                return
            
            # Occasional random twitches
            if random.random() < 0.1:  # 10% chance each frame
                dx = random.choice([-3, -2, 2, 3])
                dy = random.choice([-2, -1, 1, 2])
                self.place(x=x + dx, y=y + dy)
                self.after(100, lambda: self.place(x=x, y=y))
            
            self._animation_job = self.after(100, animate)
        
        animate()

    def pulse(self, duration: int = 2500):
        """Pulsing animation for thinking state"""
        if self._animation_job:
            self.after_cancel(self._animation_job)
        
        start_time = self.tk.call('clock', 'milliseconds')
        original_size = self.size
        
        def animate():
            current_time = self.tk.call('clock', 'milliseconds')
            elapsed = current_time - start_time
            
            if elapsed > duration:
                self.configure(width=original_size, height=original_size)
                self._animation_job = None
                return
            
            # Sine wave scaling
            scale = 1.0 + math.sin(elapsed * 0.003) * 0.1
            new_size = int(original_size * scale)
            self.configure(width=new_size, height=new_size)
            self._animation_job = self.after(33, animate)
        
        animate()

    def party_bounce(self, duration: int = 3000):
        """Celebratory bouncing with rotation effect"""
        if self._animation_job:
            self.after_cancel(self._animation_job)
        
        info = self.place_info()
        x = int(info.get("x", 0))
        y = int(info.get("y", 0))
        start_time = self.tk.call('clock', 'milliseconds')
        
        def animate():
            current_time = self.tk.call('clock', 'milliseconds')
            elapsed = current_time - start_time
            
            if elapsed > duration:
                self.place(x=x, y=y)
                self._animation_job = None
                return
            
            # Bouncy sine wave with circular motion
            bounce = abs(math.sin(elapsed * 0.008)) * 15
            circle_x = math.cos(elapsed * 0.004) * 5
            circle_y = math.sin(elapsed * 0.006) * 3
            
            self.place(x=x + int(circle_x), y=y - int(bounce) + int(circle_y))
            self._animation_job = self.after(16, animate)
        
        animate()

    def wink(self, duration_ms: int = 400):
        """Enhanced wink with smooth animation"""
        old = self.state
        self.state = "wink"
        self._render()
        
        # Add a little bounce during wink
        self.after(100, lambda: self.gentle_bounce(300))
        self.after(duration_ms, lambda: (setattr(self, "state", old), self._render()))

    # ---- Enhanced State Management -------------------------------------------------
    def set_mood(self, mood: str, duration: int = 0):
        """Set mascot mood with corresponding animation"""
        if mood in self._enhanced_states:
            self._mood = mood
            state_config = self._enhanced_states[mood]
            
            # Change visual appearance
            self.state = mood
            self._render()
            
            # Start corresponding animation
            animation = state_config.get("animation")
            if animation and hasattr(self, animation):
                getattr(self, animation)(duration or 2000)
    
    def set_energy_level(self, level: float):
        """Set energy level (affects animation intensity)"""
        self._energy_level = max(0.0, min(1.0, level))
        
        # Adjust animation based on energy
        if level > 0.8:
            self.set_mood("excited")
        elif level > 0.6:
            self.set_mood("happy")
        elif level < 0.3:
            self.set_mood("sleepy")
        else:
            self.set_mood("neutral")

    def react_to_action(self, action: str):
        """React to user actions with appropriate animations"""
        reactions = {
            "success": lambda: (self.set_mood("celebrating", 2000), self.wink()),
            "error": lambda: (self.set_mood("worried", 1500), self.nervous_twitch(1000)),
            "thinking": lambda: self.set_mood("thinking", 3000),
            "idle": lambda: self.slow_sway(5000),
            "interaction": lambda: self.set_mood("happy", 1500)
        }
        
        if action in reactions:
            reactions[action]()

    def stop_animations(self):
        """Stop all running animations"""
        if self._animation_job:
            self.after_cancel(self._animation_job)
            self._animation_job = None
        
        if self._expression_timer:
            self.after_cancel(self._expression_timer)
            self._expression_timer = None

    # Override render to support enhanced states
    def _render(self):
        super()._render()
        
        # Add mood-specific visual effects
        if self._mood in self._enhanced_states:
            w = self.winfo_width() or self.size
            h = self.winfo_height() or self.size
            cx, cy = w // 2, h // 2
            
            state_config = self._enhanced_states[self._mood]
            mood_color = state_config.get("color", COL_ACCENT)
            
            # Add mood indicator (small colored circle)
            r = min(w, h) // 8
            self.create_oval(cx - r//2, cy + h//3 - r//2, 
                           cx + r//2, cy + h//3 + r//2,
                           fill=mood_color, outline="", width=0)
        
        # Special rendering for wink state
        if self.state == "wink":
            w = self.winfo_width() or self.size
            h = self.winfo_height() or self.size
            cx, cy = w // 2, h // 2
            r = min(w, h) // 5
            # Cover right eye and draw line
            self.create_rectangle(cx + r//2 - 8, cy - r, cx + r//2, cy - r + 8,
                                  fill=self["bg"], outline=self["bg"])
            self.create_line(cx + r//2 - 8, cy - r + 4, cx + r//2, cy - r + 4,
                              fill=COL_ACCENT, width=2)


__all__ = ["MascotaCanvas"]
